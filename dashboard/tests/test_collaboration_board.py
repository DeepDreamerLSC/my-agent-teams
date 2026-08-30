from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dashboard.app import create_app
from dashboard.db import connect_db


class CollaborationBoardApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tmpdir.name)
        self.tasks_root = self.root / "tasks"
        self.tasks_root.mkdir()
        self.config_path = self.root / "config.json"
        self.config_path.write_text('{"projects": {}}', encoding="utf-8")
        self.db_path = self.root / "board.sqlite3"
        self.app = create_app(
            db_path=str(self.db_path),
            tasks_root=str(self.tasks_root),
            control_config_path=str(self.config_path),
        )
        self.client = self.app.test_client()
        self._register_project("alpha")
        self._register_project("beta")
        self.requirement_id = self._register_requirement("alpha", "统一看板")
        self._register_session(
            "alpha", "session-dev", "task-alpha", "developer", self.requirement_id
        )
        self._register_session(
            "alpha", "session-review", "task-alpha", "reviewer", self.requirement_id
        )
        beta_requirement = self._register_requirement("beta", "隔离验证")
        self._register_session(
            "beta", "session-beta", "task-beta", "developer", beta_requirement
        )

    def tearDown(self) -> None:
        self.tmpdir.cleanup()

    def _time(self, offset: int) -> str:
        return (
            datetime.now(timezone.utc) + timedelta(seconds=offset)
        ).isoformat(timespec="microseconds")

    def _register_project(self, project_id: str) -> None:
        root = self.root / project_id
        root.mkdir()
        (root / ".git").mkdir()
        response = self.client.post(
            "/api/control-plane/projects",
            json={"project_id": project_id, "name": project_id.title(), "repo_root": str(root)},
        )
        self.assertEqual(response.status_code, 201, response.get_data(as_text=True))

    def _register_requirement(self, project_id: str, title: str) -> str:
        response = self.client.post(
            "/api/control-plane/requirements",
            json={"project_id": project_id, "title": title, "acceptance": ["通过"]},
        )
        self.assertEqual(response.status_code, 201, response.get_data(as_text=True))
        return response.get_json()["requirement_id"]

    def _register_session(
        self, project_id: str, session_id: str, task_id: str, role: str, requirement_id: str
    ) -> None:
        response = self.client.post(
            "/api/control-plane/sessions",
            json={
                "project_id": project_id,
                "requirement_id": requirement_id,
                "task_id": task_id,
                "session_id": session_id,
                "role": role,
                "execution_backend": "fake",
                "session_status": "idle",
            },
        )
        self.assertEqual(response.status_code, 201, response.get_data(as_text=True))

    def _event(
        self,
        event_id: str,
        event_type: str,
        sequence: int,
        *,
        session_id: str = "session-dev",
        project_id: str = "alpha",
        task_id: str = "task-alpha",
        head: str | None = None,
        revision: dict | None = None,
        **extra,
    ):
        revision = dict(revision or {})
        if head:
            revision["head_sha"] = head
        payload = {
            "contract": "agent_event/v1",
            "event_id": event_id,
            "event_type": event_type,
            "project_id": project_id,
            "requirement_id": self.requirement_id if project_id == "alpha" else None,
            "task_id": task_id,
            "session_id": session_id,
            "sequence": sequence,
            "created_at": self._time(sequence),
            "actor": {
                "id": "review-1" if session_id == "session-review" else "dev-1",
                "role": "reviewer" if session_id == "session-review" else "developer",
            },
            "source": {"agent_id": session_id, "task_id": task_id},
            "summary": f"{event_type} 摘要",
            "revision": revision,
            **extra,
        }
        response = self.client.post("/api/control-plane/agent-events", json=payload)
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        return response.get_json()

    def _seed_complete_flow(self) -> tuple[str, str]:
        old_head = "a" * 40
        new_head = "b" * 40
        self._event(
            "evt-start", "TASK_STARTED", 1, head=old_head,
            revision={
                "pr_number": 42,
                "pr_url": "https://example.test/pr/42",
                "pr_state": "open",
                "mergeable": True,
                "source_branch": "codex/task-alpha",
                "base_branch": "main",
                "base_sha": "c" * 40,
                "merge_base_sha": "d" * 40,
            },
            metadata={"prompt": "DO-NOT-LEAK", "safe_counter": 1},
        )
        self._event("evt-ready", "READY_FOR_REVIEW", 2, head=old_head)
        self._event(
            "evt-changes", "CHANGES_REQUESTED", 1,
            session_id="session-review", head=old_head,
            review={
                "status": "changes_requested",
                "findings": [
                    {"id": "f-1", "severity": "P1", "summary": "补测试", "owner": "dev-1"}
                ],
            },
        )
        self._event(
            "evt-fix", "FIX_READY", 3, head=new_head,
            revision={"supersedes_head_sha": old_head},
        )
        self._event(
            "evt-approved", "APPROVED", 2,
            session_id="session-review", head=new_head,
            review={"status": "approved", "approver": "review-1", "findings": []},
        )
        self._event(
            "evt-ci", "LOCAL_CI_COMPLETED", 4, head=new_head,
            local_ci={
                "run_id": "local-ci-42",
                "status": "passed",
                "completed_at": self._time(4),
                "head_sha": new_head,
                "evidence_uri": "artifacts/ci/local-ci-42.json",
            },
        )
        revision = {
            "pr_number": 42,
            "pr_url": "https://example.test/pr/42",
            "pr_state": "open",
            "mergeable": True,
            "source_branch": "codex/task-alpha",
            "base_branch": "main",
            "base_sha": "c" * 40,
            "merge_base_sha": "d" * 40,
        }
        self._event("evt-gate", "MERGE_GATE_RUNNING", 5, head=new_head, revision=revision)
        self._event(
            "evt-merge-ready", "MERGE_READY", 6, head=new_head, revision=revision,
            merge_gate={"state": "ready", "blocking_checks": []},
        )
        self._event(
            "evt-artifact", "ARTIFACT_CREATED", 7,
            artifact={
                "artifact_id": "artifact-1",
                "kind": "screenshot",
                "uri": "artifacts/preview.png",
                "summary": "看板截图",
            },
        )
        self._event(
            "evt-msg-sent", "MESSAGE_SENT", 8,
            delivery={
                "delivery_id": "delivery-1",
                "status": "sent",
                "source_task_id": "task-alpha",
                "destination_task_id": "task-review",
            },
            destination={"agent_id": "review-1", "task_id": "task-review"},
        )
        self._event(
            "evt-msg-delivered", "MESSAGE_DELIVERED", 9,
            delivery={"delivery_id": "delivery-1", "status": "delivered", "ack_id": "ack-1"},
        )
        self._event(
            "evt-callback", "CALLBACK_RECEIVED", 10,
            delivery={"delivery_id": "delivery-1", "callback_id": "callback-1"},
        )
        return old_head, new_head

    def test_full_developer_review_fix_rereview_merge_gate_projection(self) -> None:
        _, new_head = self._seed_complete_flow()
        response = self.client.get("/api/collaboration/overview?project=alpha")
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        payload = response.get_json()
        self.assertEqual(payload["summary"]["task_count"], 1)
        self.assertEqual(payload["summary"]["merge_ready_count"], 1)
        task = payload["tasks"][0]
        self.assertEqual(task["stage"], "merge_ready")
        self.assertEqual(task["revision"]["head_sha"], new_head)
        self.assertTrue(task["local_ci"]["fresh"])
        self.assertTrue(task["merge_gate"]["allowed"])
        self.assertEqual(task["messages"][0]["status"], "completed")
        self.assertEqual(task["messages"][0]["ack_id"], "ack-1")
        self.assertEqual(task["artifacts"][0]["kind"], "screenshot")
        self.assertGreaterEqual(len(task["segments"]), 5)
        self.assertTrue(payload["topology"]["nodes"])
        self.assertTrue(payload["timeline"])

    def test_detail_is_summary_only_and_old_head_does_not_override(self) -> None:
        old_head, new_head = self._seed_complete_flow()
        stale = self._event(
            "evt-stale-ci", "LOCAL_CI_COMPLETED", 11, head=old_head,
            local_ci={"run_id": "stale", "status": "failed", "head_sha": old_head},
        )
        self.assertFalse(stale["applied"])
        response = self.client.get(
            "/api/collaboration/tasks/task-alpha?project=alpha"
        )
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["task"]["revision"]["head_sha"], new_head)
        self.assertEqual(payload["local_ci"]["run_id"], "local-ci-42")
        self.assertEqual(payload["task"]["stale_event_count"], 1)
        raw = response.get_data(as_text=True)
        self.assertNotIn("DO-NOT-LEAK", raw)
        self.assertEqual(payload["privacy"]["projection"], "summary_and_references")

    def test_project_role_and_event_cursors_do_not_cross_scope(self) -> None:
        self._event("alpha-start", "TASK_STARTED", 1, head="a" * 40)
        beta = {
            "contract": "agent_event/v1",
            "event_id": "beta-start",
            "event_type": "TASK_STARTED",
            "project_id": "beta",
            "task_id": "task-beta",
            "session_id": "session-beta",
            "sequence": 1,
            "created_at": self._time(1),
            "actor": {"id": "beta-dev", "role": "developer"},
            "source": {"agent_id": "beta-dev"},
            "revision": {"head_sha": "e" * 40},
        }
        self.assertEqual(
            self.client.post("/api/control-plane/agent-events", json=beta).status_code, 200
        )
        alpha = self.client.get(
            "/api/collaboration/overview?project=alpha&role=developer"
        ).get_json()
        self.assertEqual([item["task_id"] for item in alpha["tasks"]], ["task-alpha"])
        first = self.client.get("/api/collaboration/event-log?project=alpha&limit=1").get_json()
        cursor = first["last_event_id"]
        self._event("alpha-progress", "TASK_PROGRESS", 2, head="a" * 40)
        next_page = self.client.get(
            f"/api/collaboration/event-log?project=alpha&after_event_id={cursor}"
        ).get_json()
        self.assertEqual([item["event_id"] for item in next_page["events"]], ["alpha-progress"])
        reset = self.client.get(
            "/api/collaboration/event-log?project=alpha&after_event_id=missing"
        ).get_json()
        self.assertTrue(reset["cursor_reset"])

    def test_sse_uses_event_id_for_reconnect_and_polling_fallback(self) -> None:
        self._event("stream-start", "TASK_STARTED", 1, head="f" * 40)
        response = self.client.get(
            "/api/collaboration/events?project=alpha&once=1",
            headers={"Last-Event-ID": "stream-start"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "text/event-stream")
        self.assertIn("no new events", response.get_data(as_text=True))
        self._event("stream-progress", "TASK_PROGRESS", 2, head="f" * 40)
        resumed = self.client.get(
            "/api/collaboration/events?project=alpha&once=1",
            headers={"Last-Event-ID": "stream-start"},
        ).get_data(as_text=True)
        self.assertIn("id: stream-progress", resumed)
        self.assertIn("event: agent_event", resumed)

    def test_delegated_authorization_routes_and_authority(self) -> None:
        l0 = self._event(
            "auth-l0", "AUTHORIZATION_REQUESTED", 1,
            authorization={
                "request_id": "request-l0",
                "action": "RUN_TESTS",
                "action_type": "verification",
                "environment": "test",
                "target_scope": "task_workspace",
                "exact_targets": [str(self.root / "alpha")],
                "reason": "运行回归",
                "reversible": True,
                "expires_at": self._time(3600),
            },
        )["authorization"]
        self.assertEqual(l0["authorization_level"], "L0_AUTO")
        self.assertEqual(l0["status"], "GRANTED")
        l1 = self._event(
            "auth-l1", "AUTHORIZATION_REQUESTED", 2,
            authorization={
                "request_id": "request-l1",
                "action": "RESTART_TEST_SERVICE",
                "action_type": "service_control",
                "environment": "test",
                "target_scope": "registered_test_environment",
                "exact_targets": ["service:test-api"],
                "reason": "恢复测试服务",
                "reversible": True,
                "expires_at": self._time(3600),
            },
        )["authorization"]
        self.assertEqual(l1["authorization_level"], "L1_REVIEWER_COORDINATOR")
        denied = self.client.post(
            "/api/collaboration/authorizations/request-l1/decision",
            json={
                "decision": "GRANT",
                "approver": {"id": "dev-1", "role": "developer"},
                "reason": "越权",
            },
        )
        self.assertEqual(denied.status_code, 403)
        missing_reason = self.client.post(
            "/api/collaboration/authorizations/request-l1/decision",
            json={
                "decision": "GRANT",
                "approver": {"id": "review-1", "role": "reviewer"},
                "reason": "",
            },
        )
        self.assertEqual(missing_reason.status_code, 400)
        self.assertEqual(
            missing_reason.get_json()["error"]["code"],
            "authorization_decision_reason_required",
        )
        granted = self.client.post(
            "/api/collaboration/authorizations/request-l1/decision",
            json={
                "decision": "GRANT",
                "approver": {"id": "review-1", "role": "reviewer"},
                "reason": "目标和环境已确认",
            },
        )
        self.assertEqual(granted.status_code, 200, granted.get_data(as_text=True))
        self.assertEqual(granted.get_json()["status"], "GRANTED")
        l2 = self._event(
            "auth-l2", "AUTHORIZATION_REQUESTED", 3,
            authorization={
                "request_id": "request-l2",
                "action": "UNKNOWN_ACTION",
                "action_type": "unknown",
                "environment": "test",
                "target_scope": "task_workspace",
                "exact_targets": [str(self.root / "alpha")],
                "reason": "未知操作",
                "reversible": True,
                "expires_at": self._time(3600),
            },
        )["authorization"]
        self.assertEqual(l2["authorization_level"], "L2_OWNER")
        listing = self.client.get(
            "/api/collaboration/authorizations?project=alpha&status=PENDING"
        ).get_json()["authorizations"]
        self.assertEqual([item["request_id"] for item in listing], ["request-l2"])
        self.assertIn("未命中", listing[0]["routing_reason"])

    def test_collaboration_schema_upgrades_an_existing_database(self) -> None:
        conn = connect_db(self.db_path, initialize=False)
        try:
            version = conn.execute(
                "SELECT value FROM metadata WHERE key = 'collaboration_schema_version'"
            ).fetchone()[0]
            self.assertEqual(version, "4")
            tables = {
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                ).fetchall()
            }
            self.assertIn("control_plane_authorizations", tables)
            self.assertIn("control_plane_authorization_policy_overrides", tables)
            self.assertIn("control_plane_event_inbox", tables)
            self.assertIn("control_plane_focus_leases", tables)
        finally:
            conn.close()

    def test_pr175_inbox_e2e_routes_progress_to_dashboard_and_p0_to_human(self) -> None:
        fix = self._event(
            "pr175-fix-ready",
            "FIX_READY",
            1,
            head="7" * 40,
            revision={"pr_number": 175},
            destination_task_id="task-alpha",
            destination={"agent_id": "review-1", "task_id": "task-alpha"},
        )
        self.assertEqual(fix["inbox"]["classification"], "route_deferred")
        self.assertEqual(fix["inbox"]["target_role"], "reviewer")
        self.assertEqual(fix["inbox"]["route_status"], "ROUTED")

        progress = self._event("ordinary-progress", "TASK_PROGRESS", 2)
        self.assertEqual(progress["inbox"]["classification"], "dashboard_only")
        self.assertEqual(progress["inbox"]["route_status"], "ACKED")

        p0 = self._event(
            "p0-security",
            "SECURITY_ALERT",
            3,
            priority="P0",
            requires_human=True,
        )
        self.assertEqual(p0["inbox"]["route_status"], "ESCALATED")

        overview = self.client.get(
            "/api/collaboration/overview?project=alpha"
        ).get_json()
        self.assertEqual(overview["inbox"]["summary"]["human_required_count"], 1)
        self.assertEqual(
            [item["event_id"] for item in overview["inbox"]["auto_forwarded"]],
            ["pr175-fix-ready"],
        )
        self.assertEqual(
            [item["event_id"] for item in overview["inbox"]["human_decisions"]],
            ["p0-security"],
        )
        trace = self.client.get(
            "/api/collaboration/inbox/pr175-fix-ready"
        ).get_json()["trace"]
        self.assertEqual(
            [item["state"] for item in trace],
            ["RECEIVED", "VALIDATED", "DEDUPED", "ROUTED"],
        )

    def test_focus_checkpoint_ack_and_native_platform_manual_api(self) -> None:
        self._register_session(
            "alpha",
            "session-focus",
            "other-active-task",
            "coordinator",
            self.requirement_id,
        )
        focus = self.client.post(
            "/api/collaboration/focus",
            json={
                "scope_id": "main",
                "lease_owner": "coordinator-1",
                "project_id": "alpha",
                "focus_task_id": "other-active-task",
                "operation": "running tests",
                "critical_section": True,
                "next_safe_checkpoint": "test",
                "expires_at": self._time(600),
            },
        )
        self.assertEqual(focus.status_code, 200, focus.get_data(as_text=True))
        deferred = self._event(
            "focus-fix",
            "FIX_READY",
            1,
            head="8" * 40,
            destination_task_id="task-alpha",
            destination={"agent_id": "review-1", "task_id": "task-alpha"},
        )
        self.assertEqual(deferred["inbox"]["route_status"], "VALIDATED")
        drained = self.client.post(
            "/api/collaboration/inbox/checkpoints",
            json={"scope_id": "main", "checkpoint": "test", "actor": "coordinator-1"},
        )
        self.assertEqual(drained.status_code, 200, drained.get_data(as_text=True))
        self.assertEqual(drained.get_json()["routed"][0]["route_status"], "ROUTED")
        ack = self.client.post(
            "/api/collaboration/inbox/focus-fix/ack",
            json={"actor": "review-1", "summary": "已收到"},
        )
        self.assertEqual(ack.status_code, 200, ack.get_data(as_text=True))
        self.assertEqual(ack.get_json()["route_status"], "ACKED")

        platform = self._event(
            "platform-auth-api",
            "AUTHORIZATION_REQUESTED",
            2,
            requires_human=True,
            authorization={
                "request_id": "request-platform-api",
                "authorization_kind": "codex_platform",
                "platform_request_ref": "codex://approval/api",
                "action": "RUN_TESTS",
                "action_type": "verification",
                "environment": "test",
                "target_scope": "task_workspace",
                "exact_targets": [str(self.root / "alpha")],
                "reason": "sandbox tool approval",
                "reversible": True,
                "expires_at": self._time(600),
            },
        )
        authorization = platform["authorization"]
        self.assertEqual(authorization["capability_status"], "platform_manual_required")
        fake_text_approval = self.client.post(
            "/api/collaboration/authorizations/request-platform-api/decision",
            json={
                "decision": "GRANT",
                "approver": {"id": "owner", "role": "owner"},
                "reason": "text is not a platform click",
            },
        )
        self.assertEqual(
            fake_text_approval.get_json()["error"]["code"],
            "authorization_platform_manual_required",
        )
        recorded = self.client.post(
            "/api/collaboration/authorizations/request-platform-api/platform-decision",
            json={
                "decision": "DENY",
                "actor": {"id": "owner", "role": "owner"},
                "reason": "用户在 Codex 平台点击拒绝",
                "observed_digest": authorization["command_or_action_digest"],
            },
        )
        self.assertEqual(recorded.status_code, 200, recorded.get_data(as_text=True))
        self.assertEqual(recorded.get_json()["status"], "DENIED")


if __name__ == "__main__":
    unittest.main()
