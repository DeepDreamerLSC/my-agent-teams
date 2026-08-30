from __future__ import annotations

import sqlite3
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

from control_plane.agent_events import AgentEventRecorder, list_agent_events
from control_plane.authorization import AuthorizationService
from control_plane.authorization_policy import (
    L0_AUTO,
    L1_REVIEWER_COORDINATOR,
    L2_OWNER,
)
from control_plane.errors import ControlPlaneError
from control_plane.service import ControlPlaneService
from dashboard.db import connect_db


class AgentEventContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tmpdir.name)
        self.project_root = self.root / "demo"
        self.project_root.mkdir()
        (self.project_root / ".git").mkdir()
        self.other_project_root = self.root / "other-demo"
        self.other_project_root.mkdir()
        (self.other_project_root / ".git").mkdir()
        self.db_path = self.root / "board.sqlite3"
        self.db = connect_db(self.db_path)
        service = ControlPlaneService(self.db)
        with self.db:
            service.register_project(
                project_id="demo",
                name="Demo",
                repo_root=str(self.project_root),
            )
            service.register_project(
                project_id="other-demo",
                name="Other Demo",
                repo_root=str(self.other_project_root),
            )
            service.register_session(
                project_id="demo",
                session_id="session-dev",
                task_id="任务一",
                role="developer",
                execution_backend="fake",
                cwd=str(self.project_root),
                session_status="idle",
            )
        # Install the collaboration extension before concurrency tests.
        AgentEventRecorder(self.db)
        self.db.commit()

    def tearDown(self) -> None:
        self.db.close()
        self.tmpdir.cleanup()

    @staticmethod
    def now(offset_seconds: int = 0) -> str:
        return (
            datetime.now(timezone.utc) + timedelta(seconds=offset_seconds)
        ).isoformat(timespec="microseconds")

    def event(
        self,
        event_id: str,
        event_type: str,
        *,
        sequence: int | None = None,
        head_sha: str | None = None,
        summary: str = "",
        **extra,
    ) -> dict:
        revision = dict(extra.pop("revision", {}))
        if head_sha:
            revision["head_sha"] = head_sha
        return {
            "contract": "agent_event/v1",
            "event_id": event_id,
            "event_type": event_type,
            "project_id": "demo",
            "task_id": "任务一",
            "session_id": "session-dev",
            "sequence": sequence,
            "created_at": self.now(sequence or 0),
            "actor": {"id": "dev-1", "role": "developer"},
            "source": {"agent_id": "dev-1", "task_id": "任务一"},
            "summary": summary,
            "revision": revision,
            **extra,
        }

    def record(self, payload: dict) -> dict:
        with self.db:
            return AgentEventRecorder(self.db).record(payload)

    def test_event_is_idempotent_and_conflicting_reuse_is_rejected(self) -> None:
        payload = self.event("evt-1", "TASK_STARTED", sequence=1, head_sha="a" * 40)
        first = self.record(payload)
        duplicate = self.record(payload)
        self.assertTrue(first["applied"])
        self.assertFalse(first["duplicate"])
        self.assertTrue(duplicate["duplicate"])
        self.assertEqual(
            self.db.execute(
                "SELECT COUNT(*) FROM control_plane_session_events WHERE event_id = 'evt-1'"
            ).fetchone()[0],
            1,
        )
        conflicting = {**payload, "summary": "different"}
        with self.assertRaisesRegex(ControlPlaneError, "different content"):
            self.record(conflicting)

    def test_out_of_order_and_old_head_events_are_retained_but_not_applied(self) -> None:
        old_head = "a" * 40
        new_head = "b" * 40
        self.record(self.event("start", "TASK_STARTED", sequence=10, head_sha=old_head))
        out_of_order = self.record(
            self.event("late-progress", "TASK_PROGRESS", sequence=9, head_sha=old_head)
        )
        self.assertFalse(out_of_order["applied"])
        self.assertEqual(out_of_order["event"]["rejection_reason"], "out_of_order_sequence")

        fix = self.event(
            "fix-ready",
            "FIX_READY",
            sequence=11,
            head_sha=new_head,
            revision={"supersedes_head_sha": old_head},
        )
        self.assertTrue(self.record(fix)["applied"])
        stale = self.record(
            self.event(
                "old-ci",
                "LOCAL_CI_COMPLETED",
                sequence=12,
                head_sha=old_head,
                local_ci={"run_id": "ci-old", "status": "passed"},
            )
        )
        self.assertFalse(stale["applied"])
        self.assertTrue(stale["stale"])
        self.assertEqual(stale["event"]["rejection_reason"], "stale_head")
        session = ControlPlaneService(self.db).get_session("session-dev")
        self.assertEqual(session["current_gate"], "rereview")

    def test_delivery_requires_sent_delivered_callback_order(self) -> None:
        delivered = self.event(
            "msg-delivered",
            "MESSAGE_DELIVERED",
            sequence=2,
            delivery={"delivery_id": "delivery-1", "status": "delivered"},
        )
        with self.assertRaisesRegex(ControlPlaneError, "prior MESSAGE_SENT"):
            self.record(delivered)
        self.record(
            self.event(
                "msg-sent",
                "MESSAGE_SENT",
                sequence=1,
                delivery={"delivery_id": "delivery-1", "status": "sent"},
            )
        )
        self.assertTrue(self.record(delivered)["applied"])
        callback = self.record(
            self.event(
                "msg-callback",
                "CALLBACK_RECEIVED",
                sequence=3,
                delivery={"delivery_id": "delivery-1", "callback_id": "cb-1"},
            )
        )
        self.assertTrue(callback["applied"])

    def test_sensitive_payload_is_not_persisted(self) -> None:
        payload = self.event(
            "safe-event",
            "TASK_PROGRESS",
            sequence=1,
            metadata={
                "prompt": "SECRET-PROMPT",
                "tool_output": "SECRET-TOOL-OUTPUT",
                "student_record": "SECRET-STUDENT",
                "safe_counter": 3,
            },
            review={
                "findings": [
                    {"id": "f1", "severity": "P1", "summary": "安全摘要", "owner": "dev-1"}
                ]
            },
        )
        self.record(payload)
        raw = self.db.execute(
            "SELECT payload_json FROM control_plane_session_events WHERE event_id = 'safe-event'"
        ).fetchone()[0]
        self.assertNotIn("SECRET-PROMPT", raw)
        self.assertNotIn("SECRET-TOOL-OUTPUT", raw)
        self.assertNotIn("SECRET-STUDENT", raw)
        self.assertIn("safe_counter", raw)
        self.assertIn("metadata.prompt", raw)

    def test_l0_auto_grant_is_exact_expiring_and_one_shot(self) -> None:
        request = self.event(
            "auth-l0",
            "AUTHORIZATION_REQUESTED",
            sequence=1,
            authorization={
                "request_id": "request-l0",
                "action": "RUN_TESTS",
                "action_type": "verification",
                "environment": "test",
                "target_scope": "task_workspace",
                "exact_targets": [str(self.project_root)],
                "reason": "运行回归",
                "reversible": True,
                "expires_at": self.now(3600),
            },
        )
        result = self.record(request)
        authorization = result["authorization"]
        self.assertEqual(authorization["authorization_level"], L0_AUTO)
        self.assertEqual(authorization["status"], "GRANTED")
        with self.assertRaisesRegex(ControlPlaneError, "exact_targets changed"):
            with self.db:
                AuthorizationService(self.db).consume(
                    "request-l0",
                    requester_id="dev-1",
                    environment="test",
                    exact_targets=[str(self.project_root / "other")],
                )
        with self.db:
            consumed = AuthorizationService(self.db).consume(
                "request-l0",
                requester_id="dev-1",
                environment="test",
                exact_targets=[str(self.project_root)],
            )
        self.assertEqual(consumed["status"], "CONSUMED")
        with self.assertRaisesRegex(ControlPlaneError, "not consumable"):
            with self.db:
                AuthorizationService(self.db).consume(
                    "request-l0",
                    requester_id="dev-1",
                    environment="test",
                    exact_targets=[str(self.project_root)],
                )

    def test_task_workspace_targets_must_stay_inside_project_and_workspace(self) -> None:
        outside = self.root / "outside"
        outside.mkdir()
        outside_request = self.record(
            self.event(
                "auth-outside-workspace",
                "AUTHORIZATION_REQUESTED",
                sequence=1,
                authorization={
                    "request_id": "request-outside-workspace",
                    "action": "RUN_TESTS",
                    "action_type": "verification",
                    "environment": "test",
                    "target_scope": "task_workspace",
                    "exact_targets": [str(outside)],
                    "reason": "伪装成任务工作区",
                    "reversible": True,
                    "expires_at": self.now(3600),
                },
            )
        )["authorization"]
        self.assertEqual(outside_request["authorization_level"], L2_OWNER)
        self.assertIn("exact_targets", outside_request["incomplete_fields"])

        other_project_request = self.record(
            self.event(
                "auth-other-project-workspace",
                "AUTHORIZATION_REQUESTED",
                sequence=2,
                authorization={
                    "request_id": "request-other-project-workspace",
                    "action": "RUN_TESTS",
                    "action_type": "verification",
                    "environment": "test",
                    "target_scope": "task_workspace",
                    "exact_targets": [str(self.other_project_root)],
                    "reason": "跨项目路径不应自动授权",
                    "reversible": True,
                    "expires_at": self.now(3600),
                },
            )
        )["authorization"]
        self.assertEqual(other_project_request["authorization_level"], L2_OWNER)
        self.assertIn("exact_targets", other_project_request["incomplete_fields"])

        valid_request = self.record(
            self.event(
                "auth-valid-workspace",
                "AUTHORIZATION_REQUESTED",
                sequence=3,
                authorization={
                    "request_id": "request-valid-workspace",
                    "action": "RUN_TESTS",
                    "action_type": "verification",
                    "environment": "test",
                    "target_scope": "task_workspace",
                    "exact_targets": [str(self.project_root)],
                    "reason": "当前任务工作区内测试",
                    "reversible": True,
                    "expires_at": self.now(3600),
                },
            )
        )["authorization"]
        self.assertEqual(valid_request["authorization_level"], L0_AUTO)

    def test_registered_test_environment_must_use_explicit_test_targets(self) -> None:
        request = self.record(
            self.event(
                "auth-fake-test-target",
                "AUTHORIZATION_REQUESTED",
                sequence=1,
                authorization={
                    "request_id": "request-fake-test-target",
                    "action": "RESTART_TEST_SERVICE",
                    "action_type": "service_control",
                    "environment": "test",
                    "target_scope": "registered_test_environment",
                    "exact_targets": ["service:prod-api"],
                    "reason": "生产目标不应伪装成测试环境",
                    "reversible": True,
                    "expires_at": self.now(3600),
                },
            )
        )["authorization"]
        self.assertEqual(request["authorization_level"], L2_OWNER)
        self.assertIn("exact_targets", request["incomplete_fields"])

    def test_l1_delegated_and_l2_owner_authority_are_enforced(self) -> None:
        l1 = self.record(
            self.event(
                "auth-l1",
                "AUTHORIZATION_REQUESTED",
                sequence=1,
                authorization={
                    "request_id": "request-l1",
                    "action": "RESTART_TEST_SERVICE",
                    "action_type": "service_control",
                    "environment": "test",
                    "target_scope": "registered_test_environment",
                    "exact_targets": ["service:test-api"],
                    "reason": "恢复测试 API",
                    "reversible": True,
                    "expires_at": self.now(3600),
                },
            )
        )["authorization"]
        self.assertEqual(l1["authorization_level"], L1_REVIEWER_COORDINATOR)
        with self.db:
            granted = AuthorizationService(self.db).decide(
                "request-l1",
                decision="GRANT",
                approver={"id": "review-1", "role": "reviewer"},
                reason="测试环境目标已确认",
            )
        self.assertEqual(granted["status"], "GRANTED")

        l2 = self.record(
            self.event(
                "auth-l2",
                "AUTHORIZATION_REQUESTED",
                sequence=2,
                authorization={
                    "request_id": "request-l2",
                    "action": "DEPLOY_PRODUCTION",
                    "action_type": "deployment",
                    "environment": "production",
                    "target_scope": "registered_production_environment",
                    "exact_targets": ["service:prod-api"],
                    "reason": "上线",
                    "reversible": False,
                    "expires_at": self.now(3600),
                },
            )
        )["authorization"]
        self.assertEqual(l2["authorization_level"], L2_OWNER)
        with self.assertRaisesRegex(ControlPlaneError, "requires one of"):
            with self.db:
                AuthorizationService(self.db).decide(
                    "request-l2",
                    decision="GRANT",
                    approver={"id": "review-1", "role": "reviewer"},
                    reason="attempt",
                )
        with self.db:
            owner_grant = AuthorizationService(self.db).decide(
                "request-l2",
                decision="GRANT",
                approver={"id": "owner", "role": "owner"},
                reason="Owner 明确批准",
            )
        self.assertEqual(owner_grant["status"], "GRANTED")

    def test_incomplete_request_fails_closed_and_rule_can_be_disabled(self) -> None:
        incomplete = self.record(
            self.event(
                "auth-incomplete",
                "AUTHORIZATION_REQUESTED",
                sequence=1,
                authorization={
                    "request_id": "request-incomplete",
                    "action": "RUN_TESTS",
                },
            )
        )["authorization"]
        self.assertEqual(incomplete["authorization_level"], L2_OWNER)
        self.assertTrue(incomplete["incomplete_fields"])
        with self.assertRaisesRegex(ControlPlaneError, "incomplete"):
            with self.db:
                AuthorizationService(self.db).decide(
                    "request-incomplete",
                    decision="GRANT",
                    approver={"id": "owner", "role": "owner"},
                    reason="cannot broaden",
                )

        with self.db:
            AuthorizationService(self.db).set_rule_enabled(
                "l0.run_tests.task_workspace",
                enabled=False,
                actor={"id": "owner", "role": "owner"},
            )
        disabled = self.record(
            self.event(
                "auth-disabled",
                "AUTHORIZATION_REQUESTED",
                sequence=2,
                authorization={
                    "request_id": "request-disabled",
                    "action": "RUN_TESTS",
                    "action_type": "verification",
                    "environment": "test",
                    "target_scope": "task_workspace",
                    "exact_targets": [str(self.project_root)],
                    "reason": "运行回归",
                    "reversible": True,
                    "expires_at": self.now(3600),
                },
            )
        )["authorization"]
        self.assertEqual(disabled["authorization_level"], L2_OWNER)
        self.assertIn("未命中", disabled["routing_reason"])

    def test_authorization_rule_matches_action_type_and_rejects_secret_body(self) -> None:
        mismatched = self.record(
            self.event(
                "auth-mismatched-type",
                "AUTHORIZATION_REQUESTED",
                sequence=1,
                authorization={
                    "request_id": "request-mismatched-type",
                    "action": "RUN_TESTS",
                    "action_type": "deployment",
                    "environment": "test",
                    "target_scope": "task_workspace",
                    "exact_targets": [str(self.project_root)],
                    "reason": "类型不匹配",
                    "reversible": True,
                    "expires_at": self.now(3600),
                },
            )
        )["authorization"]
        self.assertEqual(mismatched["authorization_level"], L2_OWNER)
        with self.assertRaisesRegex(ControlPlaneError, "secret_refs only"):
            self.record(
                self.event(
                    "auth-secret-body",
                    "AUTHORIZATION_REQUESTED",
                    sequence=2,
                    authorization={
                        "request_id": "request-secret-body",
                        "action": "CHANGE_SECRET",
                        "action_type": "security",
                        "environment": "production",
                        "target_scope": "secret_store",
                        "exact_targets": ["secret:service/api"],
                        "reason": "轮换",
                        "reversible": False,
                        "expires_at": self.now(3600),
                        "secret_value": "must-not-be-persisted",
                    },
                )
            )
        raw = "\n".join(
            row[0]
            for row in self.db.execute(
                "SELECT payload_json FROM control_plane_session_events"
            ).fetchall()
        )
        self.assertNotIn("must-not-be-persisted", raw)

    def test_duplicate_authorization_event_stays_idempotent_after_policy_change(self) -> None:
        payload = self.event(
            "auth-policy-stable",
            "AUTHORIZATION_REQUESTED",
            sequence=1,
            authorization={
                "request_id": "request-policy-stable",
                "action": "RUN_TESTS",
                "action_type": "verification",
                "environment": "test",
                "target_scope": "task_workspace",
                "exact_targets": [str(self.project_root)],
                "reason": "运行回归",
                "reversible": True,
                "expires_at": self.now(3600),
            },
        )
        first = self.record(payload)
        with self.db:
            AuthorizationService(self.db).set_rule_enabled(
                "l0.run_tests.task_workspace",
                enabled=False,
                actor={"id": "owner", "role": "owner"},
            )
        duplicate = self.record(payload)
        self.assertTrue(duplicate["duplicate"])
        self.assertEqual(
            duplicate["authorization"]["authorization_level"],
            first["authorization"]["authorization_level"],
        )

    def test_merge_delegation_requires_review_ci_gate_and_exact_head(self) -> None:
        head = "c" * 40
        revision = {
            "head_sha": head,
            "pr_number": 12,
            "pr_state": "open",
            "mergeable": True,
            "source_branch": "codex/demo",
            "base_branch": "main",
        }
        self.record(self.event("merge-start", "TASK_STARTED", sequence=1, head_sha=head))
        self.record(self.event("merge-review-ready", "READY_FOR_REVIEW", sequence=2, revision=revision))
        self.record(
            self.event(
                "merge-approved",
                "APPROVED",
                sequence=3,
                revision=revision,
                review={"status": "approved", "approver": "review-1"},
            )
        )
        self.record(
            self.event(
                "merge-ci",
                "LOCAL_CI_COMPLETED",
                sequence=4,
                revision=revision,
                local_ci={
                    "run_id": "ci-12",
                    "status": "passed",
                    "completed_at": self.now(),
                    "head_sha": head,
                    "evidence_uri": "file:///tmp/ci-12.json",
                },
            )
        )
        self.record(
            self.event(
                "merge-ready",
                "MERGE_READY",
                sequence=5,
                revision=revision,
                merge_gate={"state": "ready", "allowed": True, "blocking_checks": []},
            )
        )
        request = self.record(
            self.event(
                "auth-merge",
                "AUTHORIZATION_REQUESTED",
                sequence=6,
                revision=revision,
                authorization={
                    "request_id": "request-merge",
                    "action": "MERGE_PR",
                    "action_type": "merge",
                    "environment": "repository",
                    "target_scope": "exact_pr_head",
                    "exact_targets": [f"pr:12@{head}"],
                    "reason": "通过冻结 HEAD 门禁后合入",
                    "reversible": False,
                    "expires_at": self.now(1800),
                    "head_sha": head,
                },
            )
        )["authorization"]
        self.assertEqual(request["authorization_level"], L1_REVIEWER_COORDINATOR)
        with self.db:
            granted = AuthorizationService(self.db).decide(
                "request-merge",
                decision="GRANT",
                approver={"id": "coordinator-1", "role": "coordinator"},
                reason="独立审查、Local CI、merge-gate 均绑定当前 HEAD",
            )
        self.assertEqual(granted["status"], "GRANTED")
        with self.assertRaisesRegex(ControlPlaneError, "HEAD changed"):
            with self.db:
                AuthorizationService(self.db).consume(
                    "request-merge",
                    requester_id="dev-1",
                    environment="repository",
                    exact_targets=[f"pr:12@{head}"],
                    head_sha="d" * 40,
                )

    def test_event_cursor_replays_only_events_after_known_event_id(self) -> None:
        self.record(self.event("cursor-1", "TASK_STARTED", sequence=1))
        self.record(self.event("cursor-2", "TASK_PROGRESS", sequence=2))
        feed = list_agent_events(self.db, after_event_id="cursor-1")
        self.assertEqual([item["event_id"] for item in feed["events"]], ["cursor-2"])
        reset = list_agent_events(self.db, after_event_id="unknown")
        self.assertTrue(reset["cursor_reset"])

    def test_concurrent_duplicate_event_does_not_corrupt_state(self) -> None:
        payload = self.event("concurrent-1", "TASK_STARTED", sequence=1)

        def write_event() -> str:
            conn = connect_db(self.db_path, initialize=False)
            try:
                with conn:
                    result = AgentEventRecorder(conn).record(payload)
                return "duplicate" if result["duplicate"] else "inserted"
            finally:
                conn.close()

        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = sorted(pool.map(lambda _: write_event(), range(2)))
        self.assertEqual(outcomes, ["duplicate", "inserted"])
        self.assertEqual(
            self.db.execute(
                "SELECT COUNT(*) FROM control_plane_session_events WHERE event_id = 'concurrent-1'"
            ).fetchone()[0],
            1,
        )


if __name__ == "__main__":
    unittest.main()
