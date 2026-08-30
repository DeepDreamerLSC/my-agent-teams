from __future__ import annotations

import tempfile
import unittest
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from control_plane.agent_events import AgentEventRecorder
from control_plane.authorization import AuthorizationService
from control_plane.collaboration_schema import (
    _migrate_to_v1 as migrate_collaboration_v1,
    _migrate_to_v2 as migrate_collaboration_v2,
    initialize_collaboration_schema,
)
from control_plane.errors import ControlPlaneError
from control_plane.event_router import EventRouter
from control_plane.service import ControlPlaneService
from control_plane.schema import initialize_control_plane_schema
from dashboard.db import connect_db


class EventRouterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tmpdir.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        (self.repo / ".git").mkdir()
        self.db_path = self.root / "board.sqlite3"
        self.db = connect_db(self.db_path)
        service = ControlPlaneService(self.db)
        with self.db:
            service.register_project(
                project_id="demo", name="Demo", repo_root=str(self.repo)
            )
            for session_id, task_id, role in (
                ("session-dev", "开发任务", "developer"),
                ("session-review", "审查任务", "reviewer"),
                ("session-coordinator", "协调任务", "coordinator"),
            ):
                service.register_session(
                    project_id="demo",
                    session_id=session_id,
                    task_id=task_id,
                    role=role,
                    execution_backend="fake",
                    session_status="idle",
                )

    def tearDown(self) -> None:
        self.db.close()
        self.tmpdir.cleanup()

    @staticmethod
    def at(offset: int = 0) -> str:
        return (
            datetime.now(timezone.utc) + timedelta(seconds=offset)
        ).isoformat(timespec="microseconds")

    def event(
        self,
        event_id: str,
        event_type: str,
        sequence: int,
        *,
        head: str | None = None,
        destination_task_id: str | None = None,
        destination_agent: str | None = None,
        priority: str = "P3",
        requires_human: bool = False,
        **extra,
    ) -> dict:
        revision = dict(extra.pop("revision", {}))
        if head:
            revision["head_sha"] = head
        destination = dict(extra.pop("destination", {}))
        if destination_task_id:
            destination["task_id"] = destination_task_id
        if destination_agent:
            destination["agent_id"] = destination_agent
        return {
            "contract": "agent_event/v1",
            "event_id": event_id,
            "event_type": event_type,
            "project_id": "demo",
            "task_id": "开发任务",
            "session_id": "session-dev",
            "entity_type": "pr" if head else "task",
            "entity_id": "PR175" if head else "开发任务",
            "source_task_id": "开发任务",
            "destination_task_id": destination_task_id,
            "sequence": sequence,
            "occurred_at": self.at(sequence),
            "actor": {"id": "dev-1", "role": "developer"},
            "source": {"agent_id": "dev-1", "task_id": "开发任务"},
            "destination": destination,
            "priority": priority,
            "requires_human": requires_human,
            "revision": revision,
            **extra,
        }

    def record_route(self, payload: dict) -> dict:
        with self.db:
            result = AgentEventRecorder(self.db).record(payload)
            result["inbox"] = EventRouter(self.db).accept(
                result["event"], duplicate=bool(result.get("duplicate"))
            )
            return result

    def test_idempotent_duplicate_has_one_route_action(self) -> None:
        payload = self.event(
            "fix-175",
            "FIX_READY",
            1,
            head="b" * 40,
            destination_task_id="审查任务",
            destination_agent="reviewer-1",
        )
        first = self.record_route(payload)
        duplicate = self.record_route(payload)
        self.assertEqual(first["inbox"]["route_status"], "ROUTED")
        self.assertTrue(duplicate["duplicate"])
        self.assertEqual(
            self.db.execute(
                "SELECT COUNT(*) FROM control_plane_event_inbox WHERE event_id = ?",
                ("fix-175",),
            ).fetchone()[0],
            1,
        )
        self.assertEqual(
            self.db.execute(
                "SELECT COUNT(*) FROM control_plane_event_routing_transitions "
                "WHERE event_id = ? AND state = 'ROUTED'",
                ("fix-175",),
            ).fetchone()[0],
            1,
        )

    def test_pr175_fix_ready_routes_progress_stays_dashboard_and_p0_escalates(self) -> None:
        routed = self.record_route(
            self.event(
                "pr175-fix-ready",
                "FIX_READY",
                1,
                head="1" * 40,
                destination_task_id="审查任务",
                destination_agent="reviewer-1",
                revision={"pr_number": 175},
            )
        )["inbox"]
        progress = self.record_route(
            self.event("ordinary-progress", "TASK_PROGRESS", 2)
        )["inbox"]
        p0 = self.record_route(
            self.event("security-p0", "SECURITY_ALERT", 3, priority="P0")
        )["inbox"]
        self.assertEqual((routed["route_status"], routed["target_role"]), ("ROUTED", "reviewer"))
        self.assertEqual(progress["classification"], "dashboard_only")
        self.assertEqual(progress["route_status"], "ACKED")
        self.assertEqual(p0["route_status"], "ESCALATED")
        router_rows = self.db.execute(
            "SELECT applied, rejection_reason FROM control_plane_session_events "
            "WHERE event_id LIKE 'router_pr175-fix-ready_%'"
        ).fetchall()
        self.assertTrue(router_rows)
        self.assertTrue(all(bool(row["applied"]) for row in router_rows))
        self.assertTrue(all(row["rejection_reason"] is None for row in router_rows))

    def test_unknown_recipient_fails_closed(self) -> None:
        item = self.record_route(
            self.event("unknown-target", "FIX_READY", 1, head="2" * 40)
        )["inbox"]
        self.assertEqual(item["route_status"], "ESCALATED")
        self.assertTrue(item["requires_human"])

        unregistered = self.record_route(
            self.event(
                "fake-explicit-target",
                "FIX_READY",
                2,
                head="2" * 40,
                destination_task_id="不存在的审查任务",
                destination_agent="invented-reviewer",
            )
        )["inbox"]
        self.assertEqual(unregistered["route_status"], "ESCALATED")
        self.assertTrue(unregistered["requires_human"])

    def test_old_head_and_out_of_order_are_audit_only(self) -> None:
        old_head = "a" * 40
        new_head = "b" * 40
        approved = self.record_route(
            self.event(
                "approved-old",
                "APPROVED",
                10,
                head=old_head,
                destination_task_id="协调任务",
                destination_agent="coordinator-1",
            )
        )
        self.record_route(
            self.event(
                "fix-new",
                "FIX_READY",
                11,
                head=new_head,
                destination_task_id="审查任务",
                destination_agent="reviewer-1",
                revision={"supersedes_head_sha": old_head},
            )
        )
        invalidated = EventRouter(self.db).get(approved["event"]["event_id"])
        self.assertEqual(invalidated["route_status"], "ACKED")
        self.assertIn("superseded_by:fix-new", invalidated["ack_summary"])

        late = self.record_route(
            self.event("late-old", "TASK_PROGRESS", 9, head=old_head)
        )
        self.assertFalse(late["applied"])
        self.assertEqual(late["inbox"]["route_status"], "ACKED")
        self.assertIn("audit_only", late["inbox"]["route_reason"])

    def test_focus_defers_and_checkpoint_drains(self) -> None:
        with self.db:
            EventRouter(self.db).set_focus(
                scope_id="main",
                lease_owner="coordinator-1",
                project_id="demo",
                focus_task_id="协调任务",
                operation="running tests",
                head_sha=None,
                critical_section=True,
                next_safe_checkpoint="test",
                expires_at=self.at(600),
            )
        deferred = self.record_route(
            self.event(
                "deferred-fix",
                "FIX_READY",
                1,
                head="c" * 40,
                destination_task_id="审查任务",
                destination_agent="reviewer-1",
            )
        )["inbox"]
        self.assertEqual(deferred["route_status"], "VALIDATED")
        self.assertEqual(deferred["deferred_until_checkpoint"], "test")
        self.assertEqual(deferred["deferred_focus_task_id"], "协调任务")
        with self.db:
            wrong_checkpoint = EventRouter(self.db).drain(
                scope_id="main", checkpoint="push", actor="coordinator-1"
            )
        self.assertEqual(wrong_checkpoint["routed"], [])
        self.assertEqual(
            EventRouter(self.db).get("deferred-fix")["route_status"], "VALIDATED"
        )
        with self.db:
            drained = EventRouter(self.db).drain(
                scope_id="main", checkpoint="test", actor="coordinator-1"
            )
        self.assertEqual(len(drained["routed"]), 1)
        self.assertEqual(drained["routed"][0]["route_status"], "ROUTED")

    def test_focus_is_project_scoped_and_cannot_release_another_project(self) -> None:
        other_repo = self.root / "other-repo"
        other_repo.mkdir()
        (other_repo / ".git").mkdir()
        service = ControlPlaneService(self.db)
        with self.db:
            service.register_project(
                project_id="other", name="Other", repo_root=str(other_repo)
            )
            service.register_session(
                project_id="other",
                session_id="other-dev",
                task_id="其他开发任务",
                role="developer",
                execution_backend="fake",
                session_status="idle",
            )
            service.register_session(
                project_id="other",
                session_id="other-review",
                task_id="其他审查任务",
                role="reviewer",
                execution_backend="fake",
                session_status="idle",
            )
            EventRouter(self.db).set_focus(
                scope_id="main",
                lease_owner="coordinator-1",
                project_id="demo",
                focus_task_id="协调任务",
                operation="running tests",
                head_sha=None,
                critical_section=True,
                next_safe_checkpoint="test",
                expires_at=self.at(600),
            )

        payload = self.event(
            "other-project-fix",
            "FIX_READY",
            1,
            head="4" * 40,
            destination_task_id="其他审查任务",
            destination_agent="other-reviewer",
        )
        payload.update(
            {
                "project_id": "other",
                "task_id": "其他开发任务",
                "session_id": "other-dev",
                "source_task_id": "其他开发任务",
                "source": {"agent_id": "other-dev", "task_id": "其他开发任务"},
            }
        )
        routed = self.record_route(payload)["inbox"]
        self.assertEqual(routed["route_status"], "ROUTED")
        self.assertIsNone(routed["deferred_until_checkpoint"])

    def test_restart_recovers_route_and_ack(self) -> None:
        item = self.record_route(
            self.event(
                "recoverable-fix",
                "FIX_READY",
                1,
                head="d" * 40,
                destination_task_id="审查任务",
                destination_agent="reviewer-1",
            )
        )["inbox"]
        self.assertEqual(item["route_status"], "ROUTED")
        self.db.commit()
        self.db.close()
        self.db = connect_db(self.db_path, initialize=False)
        recovered = EventRouter(self.db).get("recoverable-fix")
        self.assertEqual(recovered["route_status"], "ROUTED")
        with self.db:
            acked = EventRouter(self.db).acknowledge(
                "recoverable-fix", actor="reviewer-1", summary="已收到"
            )
        self.assertEqual(acked["route_status"], "ACKED")
        self.assertEqual(acked["trace"][-1]["state"], "ACKED")

    def test_delivery_ack_chain_can_cross_registered_sessions(self) -> None:
        sent = self.event(
            "cross-session-sent",
            "MESSAGE_SENT",
            1,
            destination_task_id="审查任务",
            delivery={
                "delivery_id": "delivery-cross-session",
                "status": "sent",
                "source_task_id": "开发任务",
                "destination_task_id": "审查任务",
            },
        )
        with self.db:
            self.assertTrue(AgentEventRecorder(self.db).record(sent)["applied"])

        delivered = self.event(
            "cross-session-delivered",
            "MESSAGE_DELIVERED",
            1,
            delivery={
                "delivery_id": "delivery-cross-session",
                "status": "delivered",
                "source_task_id": "开发任务",
                "destination_task_id": "审查任务",
            },
        )
        delivered.update(
            {
                "task_id": "审查任务",
                "session_id": "session-review",
                "source_task_id": "开发任务",
                "source": {"agent_id": "reviewer-1", "task_id": "开发任务"},
            }
        )
        with self.db:
            self.assertTrue(AgentEventRecorder(self.db).record(delivered)["applied"])

        callback = self.event(
            "cross-session-callback",
            "CALLBACK_RECEIVED",
            2,
            destination_task_id="审查任务",
            delivery={
                "delivery_id": "delivery-cross-session",
                "callback_id": "callback-cross-session",
                "source_task_id": "开发任务",
                "destination_task_id": "审查任务",
            },
        )
        with self.db:
            self.assertTrue(AgentEventRecorder(self.db).record(callback)["applied"])

        changed_route = self.event(
            "cross-session-wrong-route",
            "CALLBACK_RECEIVED",
            3,
            delivery={
                "delivery_id": "delivery-cross-session",
                "callback_id": "callback-wrong-route",
                "source_task_id": "别的开发任务",
                "destination_task_id": "审查任务",
            },
        )
        with self.assertRaisesRegex(ControlPlaneError, "source/destination changed"):
            with self.db:
                AgentEventRecorder(self.db).record(changed_route)

    def test_text_authorization_routes_decision_to_source_and_acks(self) -> None:
        result = self.record_route(
            self.event(
                "text-auth",
                "AUTHORIZATION_REQUESTED",
                1,
                destination_task_id="审查任务",
                destination_agent="reviewer-1",
                requires_human=True,
                authorization={
                    "request_id": "request-text",
                    "authorization_kind": "text",
                    "action": "RESTART_TEST_SERVICE",
                    "action_type": "service_control",
                    "environment": "test",
                    "target_scope": "registered_test_environment",
                    "exact_targets": ["service:test-api"],
                    "reason": "恢复测试服务",
                    "reversible": True,
                    "expires_at": self.at(600),
                },
            )
        )
        self.assertEqual(result["inbox"]["target_role"], "reviewer")
        auth_events = self.db.execute(
            "SELECT applied, rejection_reason FROM control_plane_session_events "
            "WHERE event_id LIKE 'auth_request-text_authorization_routed_%'"
        ).fetchall()
        self.assertTrue(auth_events)
        self.assertTrue(all(bool(row["applied"]) for row in auth_events))
        self.assertTrue(all(row["rejection_reason"] is None for row in auth_events))
        with self.db:
            decision = AuthorizationService(self.db).decide(
                "request-text",
                decision="GRANT",
                approver={"id": "reviewer-1", "role": "reviewer"},
                reason="目标、环境与范围已核对",
            )
        self.assertEqual(decision["status"], "GRANTED")
        callback = EventRouter(self.db).get("text-auth")
        self.assertEqual(callback["target_task_id"], "开发任务")
        self.assertEqual(callback["route_status"], "ROUTED")
        with self.db:
            ack = EventRouter(self.db).acknowledge(
                "text-auth", actor="dev-1", summary="授权结果已接收"
            )
        self.assertEqual(ack["route_status"], "ACKED")

    def test_native_platform_approval_fails_closed_and_records_owner_click(self) -> None:
        result = self.record_route(
            self.event(
                "platform-auth",
                "AUTHORIZATION_REQUESTED",
                1,
                requires_human=True,
                authorization={
                    "request_id": "request-platform",
                    "authorization_kind": "codex_platform",
                    "platform_request_ref": "codex://approval/175",
                    "action": "RUN_TESTS",
                    "action_type": "verification",
                    "environment": "test",
                    "target_scope": "task_workspace",
                    "exact_targets": [str(self.repo)],
                    "reason": "Codex sandbox requires a platform click",
                    "reversible": True,
                    "expires_at": self.at(600),
                },
            )
        )
        authorization = result["authorization"]
        self.assertEqual(authorization["capability_status"], "platform_manual_required")
        self.assertEqual(result["inbox"]["route_status"], "ESCALATED")
        with self.assertRaisesRegex(ControlPlaneError, "platform click"):
            with self.db:
                AuthorizationService(self.db).decide(
                    "request-platform",
                    decision="GRANT",
                    approver={"id": "owner", "role": "owner"},
                    reason="不能用文本假装平台点击",
                )
        with self.assertRaisesRegex(ControlPlaneError, "digest drifted"):
            with self.db:
                AuthorizationService(self.db).record_platform_decision(
                    "request-platform",
                    decision="GRANT",
                    actor={"id": "owner", "role": "owner"},
                    reason="用户已在 Codex 点允许",
                    observed_digest="wrong",
                )
        with self.db:
            recorded = AuthorizationService(self.db).record_platform_decision(
                "request-platform",
                decision="GRANT",
                actor={"id": "owner", "role": "owner"},
                reason="用户已在 Codex 点允许",
                observed_digest=authorization["command_or_action_digest"],
            )
        self.assertEqual(recorded["status"], "GRANTED")
        with self.assertRaisesRegex(ControlPlaneError, "cannot consume"):
            with self.db:
                AuthorizationService(self.db).consume(
                    "request-platform",
                    requester_id="dev-1",
                    environment="test",
                    exact_targets=[str(self.repo)],
                )

    def test_authorization_digest_expiry_stale_head_and_sensitive_body(self) -> None:
        with self.assertRaisesRegex(ControlPlaneError, "digest"):
            self.record_route(
                self.event(
                    "digest-drift",
                    "AUTHORIZATION_REQUESTED",
                    1,
                    authorization={
                        "request_id": "request-drift",
                        "action": "RUN_TESTS",
                        "action_type": "verification",
                        "environment": "test",
                        "target_scope": "task_workspace",
                        "exact_targets": [str(self.repo)],
                        "reason": "run",
                        "reversible": True,
                        "expires_at": self.at(600),
                        "command_or_action_digest": "wrong",
                    },
                )
            )
        with self.assertRaisesRegex(ControlPlaneError, "secret_refs only"):
            self.record_route(
                self.event(
                    "sensitive-auth",
                    "AUTHORIZATION_REQUESTED",
                    1,
                    authorization={
                        "request_id": "request-sensitive",
                        "action": "RUN_TESTS",
                        "action_type": "verification",
                        "environment": "test",
                        "target_scope": "task_workspace",
                        "exact_targets": [str(self.repo)],
                        "reason": "run",
                        "reversible": True,
                        "expires_at": self.at(600),
                        "command_output": "secret output",
                    },
                )
            )

        old_head = "e" * 40
        self.record_route(self.event("start-old", "TASK_STARTED", 1, head=old_head))
        auth = self.record_route(
            self.event(
                "head-auth",
                "AUTHORIZATION_REQUESTED",
                2,
                authorization={
                    "request_id": "request-head",
                    "action": "RUN_TESTS",
                    "action_type": "verification",
                    "environment": "test",
                    "target_scope": "task_workspace",
                    "exact_targets": [str(self.repo)],
                    "head_sha": old_head,
                    "requester_role": "owner",
                    "source_task_id": "审查任务",
                    "reason": "run",
                    "reversible": True,
                    "expires_at": self.at(600),
                },
            )
        )["authorization"]
        self.assertEqual(auth["status"], "GRANTED")
        self.assertEqual(auth["requester_role"], "developer")
        self.assertEqual(auth["source_task_id"], "开发任务")
        self.record_route(
            self.event(
                "new-fix",
                "FIX_READY",
                3,
                head="f" * 40,
                destination_task_id="审查任务",
                destination_agent="reviewer-1",
                revision={"supersedes_head_sha": old_head},
            )
        )
        self.assertEqual(
            AuthorizationService(self.db).get("request-head", expire=False)["status"],
            "EXPIRED",
        )
        invalid_expiry = self.record_route(
            self.event(
                "invalid-expiry-auth",
                "AUTHORIZATION_REQUESTED",
                4,
                authorization={
                    "request_id": "request-invalid-expiry",
                    "action": "RUN_TESTS",
                    "action_type": "verification",
                    "environment": "test",
                    "target_scope": "task_workspace",
                    "exact_targets": [str(self.repo)],
                    "reason": "invalid expiry must fail closed",
                    "reversible": True,
                    "expires_at": "not-a-time",
                },
            )
        )
        self.assertEqual(
            invalid_expiry["authorization"]["authorization_level"], "L2_OWNER"
        )
        self.assertEqual(invalid_expiry["inbox"]["route_status"], "ESCALATED")

        mismatched_source = self.event(
            "mismatched-auth-source",
            "AUTHORIZATION_REQUESTED",
            5,
            authorization={
                "request_id": "request-mismatched-source",
                "action": "RUN_TESTS",
                "action_type": "verification",
                "environment": "test",
                "target_scope": "task_workspace",
                "exact_targets": [str(self.repo)],
                "reason": "不能代替其他任务申请",
                "reversible": True,
                "expires_at": self.at(600),
            },
        )
        mismatched_source["source_task_id"] = "审查任务"
        mismatched_source["source"] = {
            "agent_id": "dev-1",
            "task_id": "审查任务",
        }
        with self.assertRaisesRegex(ControlPlaneError, "requesting session task"):
            self.record_route(mismatched_source)

    def test_scope_violating_authorization_is_l2_and_escalated(self) -> None:
        outside = self.root / "outside-project"
        outside.mkdir()
        result = self.record_route(
            self.event(
                "scope-violation-auth",
                "AUTHORIZATION_REQUESTED",
                1,
                authorization={
                    "request_id": "request-scope-violation",
                    "action": "RUN_TESTS",
                    "action_type": "verification",
                    "environment": "test",
                    "target_scope": "task_workspace",
                    "exact_targets": [str(outside)],
                    "reason": "伪装为当前任务目录",
                    "reversible": True,
                    "expires_at": self.at(600),
                },
            )
        )
        self.assertEqual(result["authorization"]["authorization_level"], "L2_OWNER")
        self.assertIn(
            "registered project development roots",
            result["authorization"]["routing_reason"],
        )
        self.assertEqual(
            result["event"]["payload"]["authorization"]["routing"]["level"],
            "L2_OWNER",
        )
        self.assertEqual(result["inbox"]["route_status"], "ESCALATED")

    def test_v2_database_migrates_in_place_to_v4(self) -> None:
        legacy_path = self.root / "legacy-v2.sqlite3"
        conn = sqlite3.connect(legacy_path)
        conn.row_factory = sqlite3.Row
        try:
            initialize_control_plane_schema(conn)
            migrate_collaboration_v1(conn)
            migrate_collaboration_v2(conn)
            conn.commit()
            initialize_collaboration_schema(conn)
            version = conn.execute(
                "SELECT value FROM metadata WHERE key = 'collaboration_schema_version'"
            ).fetchone()[0]
            columns = {
                row[1]
                for row in conn.execute(
                    "PRAGMA table_info(control_plane_authorizations)"
                ).fetchall()
            }
            inbox_columns = {
                row[1]
                for row in conn.execute(
                    "PRAGMA table_info(control_plane_event_inbox)"
                ).fetchall()
            }
            self.assertEqual(version, "4")
            self.assertTrue(
                {
                    "authorization_kind",
                    "source_task_id",
                    "command_or_action_digest",
                    "capability_status",
                }.issubset(columns)
            )
            self.assertIn("deferred_focus_task_id", inbox_columns)
        finally:
            conn.close()


if __name__ == "__main__":
    unittest.main()
