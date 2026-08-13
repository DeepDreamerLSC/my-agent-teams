from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from control_plane.backends.codex import CodexAppServerBackend, UnsupportedCodexClient
from control_plane.backends.fake import FakeBackend
from control_plane.errors import ControlPlaneError, UnsafePath
from control_plane.service import ControlPlaneService
from dashboard.db import connect_db


class ControlPlaneServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tmpdir.name)
        self.project_root = self.root / "demo-project"
        self.project_root.mkdir()
        (self.project_root / ".git").mkdir()
        (self.project_root / "src").mkdir()
        self.db = connect_db(self.root / "control.sqlite3")
        self.service = ControlPlaneService(self.db, liveness_ttl_seconds=60)

    def tearDown(self) -> None:
        self.db.close()
        self.tmpdir.cleanup()

    def project(self) -> dict:
        with self.db:
            return self.service.register_project(
                project_id="demo",
                name="Demo project",
                repo_root=str(self.project_root),
                metadata={"allowed_roots": [str(self.project_root / "src")]},
            )

    def test_schema_migration_is_idempotent_and_legacy_tasks_survive(self) -> None:
        with self.db:
            self.db.execute(
                "INSERT INTO tasks(task_id, title, task_dir, task_json_path, last_synced_at) VALUES(?, ?, ?, ?, ?)",
                ("legacy-task", "legacy", str(self.root), str(self.root / "task.json"), "now"),
            )
        with self.db:
            self.project()
        tables = {
            row["name"]
            for row in self.db.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        self.assertIn("tasks", tables)
        self.assertIn("control_plane_sessions", tables)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM tasks").fetchone()[0], 1)
        self.assertEqual(
            self.db.execute(
                "SELECT value FROM metadata WHERE key = 'control_plane_schema_version'"
            ).fetchone()[0],
            "1",
        )

    def test_project_registration_and_paths_are_idempotent_and_scoped(self) -> None:
        first = self.project()
        second = self.project()
        self.assertEqual(first["project_id"], second["project_id"])
        self.assertEqual(len(self.service.list_projects()), 1)
        with self.assertRaises(UnsafePath):
            with self.db:
                self.service.register_project(
                    project_id="unsafe",
                    name="Unsafe",
                    repo_root=str(self.root),
                )

    def test_session_binding_and_event_idempotency_out_of_order_and_liveness(self) -> None:
        self.project()
        with self.db:
            requirement = self.service.create_requirement(
                project_id="demo", title="Ship feature", acceptance=["tests pass"]
            )
            session = self.service.register_session(
                project_id="demo",
                requirement_id=requirement["requirement_id"],
                role="developer",
                execution_backend="fake",
                thread_id="thread-1",
                cwd=str(self.project_root / "src"),
                worktree=str(self.project_root / "src"),
            )
            self.service.bind_session(session["session_id"], task_id="task-1")
            first = self.service.record_session_event(
                session_id=session["session_id"],
                event_type="status",
                idempotency_key="event-1",
                sequence=1,
                status="busy",
                event_at="2026-08-13T00:00:01+00:00",
            )
            duplicate = self.service.record_session_event(
                session_id=session["session_id"],
                event_type="status",
                idempotency_key="event-1",
                sequence=1,
                status="offline",
            )
            older = self.service.record_session_event(
                session_id=session["session_id"],
                event_type="status",
                idempotency_key="event-0",
                sequence=0,
                status="offline",
                event_at="2026-08-12T23:59:59+00:00",
            )
            self.assertTrue(first["applied"])
            self.assertTrue(duplicate["duplicate"])
            self.assertFalse(older["applied"])
            self.assertEqual(older["event"]["rejection_reason"], "out_of_order_sequence")
            self.assertEqual(self.service.get_requirement(requirement["requirement_id"])["requirement_id"], requirement["requirement_id"])
            health = self.service.session_health(
                session["session_id"], now="2026-08-13T00:00:30+00:00"
            )
            self.assertEqual(health["health"], "online")
            stale = self.service.session_health(
                session["session_id"], now="2026-08-13T00:02:30+00:00"
            )
            self.assertEqual(stale["health"], "offline")
            self.assertEqual(len(self.service.list_session_events(session["session_id"])), 2)

    def test_artifact_gate_owner_and_overview(self) -> None:
        self.project()
        with self.db:
            requirement = self.service.create_requirement(project_id="demo", title="Demo delivery")
            artifact = self.service.attach_artifact(
                project_id="demo",
                requirement_id=requirement["requirement_id"],
                kind="review",
                uri=str(self.project_root / "src" / "review.json"),
                summary="independent review passed",
            )
            self.assertEqual(artifact["kind"], "review")
            with self.assertRaises(UnsafePath):
                self.service.attach_artifact(
                    project_id="demo",
                    kind="trace",
                    uri=str(self.root / "outside.json"),
                )
            gate = self.service.decide_gate(
                requirement_id=requirement["requirement_id"],
                stage="pm_clarification",
                status="passed",
                actor="pm-chief",
                output={"acceptance": ["done"]},
            )
            self.assertEqual(gate["requirement"]["current_stage"], "architecture")
            decision = self.service.create_owner_decision(
                project_id="demo",
                requirement_id=requirement["requirement_id"],
                category="production_release",
                summary="Production release requires explicit authorization",
                options=["release", "hold"],
                impact="No production change is made automatically.",
                recommendation="hold until Owner authorizes",
            )
            overview = self.service.overview(project_id="demo")
            self.assertEqual(len(overview["projects"]), 1)
            self.assertEqual(len(overview["owner_decisions"]), 1)
            self.service.resolve_owner_decision(decision["decision_id"], decision={"choice": "hold"})
            self.assertEqual(self.service.list_owner_decisions(project_id="demo"), [])


class BackendContractTests(unittest.TestCase):
    def test_fake_backend_and_codex_unsupported_are_truthful(self) -> None:
        fake = FakeBackend()
        self.assertEqual(fake.health({}) .status, "online")
        codex = CodexAppServerBackend(client=UnsupportedCodexClient())
        health = codex.health({"thread_id": "thread-1"})
        self.assertEqual(health.status, "unsupported")
        self.assertEqual(health.capabilities["status"], "unsupported")


if __name__ == "__main__":
    unittest.main()
