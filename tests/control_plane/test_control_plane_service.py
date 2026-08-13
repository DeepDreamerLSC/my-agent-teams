from __future__ import annotations

import json
import sqlite3
import subprocess
import tempfile
import unittest
from pathlib import Path

from control_plane.backends.codex import CodexAppServerBackend, UnsupportedCodexClient
from control_plane.backends.fake import FakeBackend
from control_plane.backends.tmux import TmuxBackend
from control_plane.backends.registry import BackendRegistry
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
        with self.db:
            self.assertTrue(self.service.validate_write_scope("demo", [str(self.project_root / "src")])["ok"])
            self.assertFalse(self.service.validate_write_scope("demo", [str(self.root / "outside")])["ok"])

    def test_prod_root_is_the_only_session_and_write_scope_for_prod(self) -> None:
        prod_root = self.root / "prod"
        (prod_root / "worktree").mkdir(parents=True)
        with self.db:
            self.service.register_project(
                project_id="prod-demo",
                name="Prod demo",
                repo_root=str(self.project_root),
                prod_root=str(prod_root),
            )
            self.assertTrue(
                self.service.validate_write_scope("prod-demo", [str(prod_root / "worktree")], environment="prod")["ok"]
            )
            self.assertFalse(
                self.service.validate_write_scope("prod-demo", [str(self.project_root / "src")], environment="prod")["ok"]
            )
            session = self.service.register_session(
                project_id="prod-demo",
                role="developer",
                execution_backend="fake",
                environment="prod",
                cwd=str(prod_root / "worktree"),
                worktree=str(prod_root / "worktree"),
            )
            self.assertEqual(session["environment"], "prod")
            with self.assertRaises(UnsafePath):
                self.service.register_session(
                    project_id="prod-demo",
                    role="developer",
                    execution_backend="fake",
                    environment="prod",
                    cwd=str(self.project_root),
                )
            self.assertFalse(
                self.service.validate_write_scope("prod-demo", [str(self.project_root)], environment="prod")["ok"]
            )
            self.assertFalse(
                self.service.validate_write_scope("prod-demo", [str(prod_root)], environment="dev")["ok"]
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

    def test_out_of_order_heartbeat_does_not_regress_capabilities_or_cross_session_keys(self) -> None:
        self.project()
        with self.db:
            first = self.service.register_session(project_id="demo", role="developer", execution_backend="fake", thread_id="one")
            second = self.service.register_session(project_id="demo", role="developer", execution_backend="fake", thread_id="two")
            self.service.heartbeat(first["session_id"], idempotency_key="heartbeat-1", sequence=2, capabilities={"version": 2})
            older = self.service.heartbeat(first["session_id"], idempotency_key="heartbeat-0", sequence=1, capabilities={"version": 1})
            self.assertFalse(older["applied"])
            self.assertEqual(self.service.get_session(first["session_id"])["capabilities"]["version"], 2)
            with self.assertRaisesRegex(ControlPlaneError, "another session"):
                self.service.record_session_event(
                    session_id=second["session_id"], event_type="status", idempotency_key="heartbeat-1", status="busy"
                )

    def test_event_project_mismatch_and_repeated_gate_failure_open_owner_decision(self) -> None:
        self.project()
        with self.db:
            requirement = self.service.create_requirement(project_id="demo", title="Repeated failure", acceptance=["done"])
            session = self.service.register_session(project_id="demo", requirement_id=requirement["requirement_id"], role="architect", execution_backend="fake")
            self.service.attach_artifact(project_id="demo", requirement_id=requirement["requirement_id"], kind="architecture", uri=str(self.project_root / "arch.md"))
            with self.assertRaises(ControlPlaneError):
                self.service.record_session_event(session_id=session["session_id"], project_id="other", event_type="status", idempotency_key="mismatch", status="busy")
            self.service.decide_gate(requirement_id=requirement["requirement_id"], stage="pm_clarification", status="passed", actor="pm", output={"acceptance": ["done"]})
            self.service.decide_gate(requirement_id=requirement["requirement_id"], stage="architecture", status="rejected", actor="architect", rejection_reason="missing risk")
            for round_number in (2, 3):
                self.service.decide_gate(requirement_id=requirement["requirement_id"], stage="architecture", status="rejected", actor="architect", round_number=round_number, rejection_reason="still missing risk")
            decisions = self.service.list_owner_decisions(project_id="demo")
            self.assertEqual(len(decisions), 1)
            self.assertEqual(decisions[0]["category"], "repeated_gate_failure")

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
            self.assertIn(requirement["requirement_id"], overview["timelines"])
            self.service.resolve_owner_decision(decision["decision_id"], decision={"choice": "hold"})
            self.assertEqual(self.service.list_owner_decisions(project_id="demo"), [])

    def test_workflow_advance_requires_evidence_and_respects_owner_exception(self) -> None:
        self.project()
        with self.db:
            requirement = self.service.create_requirement(
                project_id="demo", title="Full delivery", acceptance=["demo works"]
            )
            advanced = self.service.advance_workflow(requirement["requirement_id"])
            self.assertTrue(advanced["advanced"])
            self.assertEqual(advanced["requirement"]["current_stage"], "architecture")
            missing = self.service.advance_workflow(requirement["requirement_id"])
            self.assertFalse(missing["advanced"])
            self.assertEqual(missing["reason"], "required_role_session_missing")
            self.service.register_session(
                project_id="demo", requirement_id=requirement["requirement_id"], role="architect", execution_backend="fake"
            )
            self.service.attach_artifact(
                project_id="demo", requirement_id=requirement["requirement_id"], kind="architecture", uri=str(self.project_root / "arch.md")
            )
            self.assertFalse(self.service.advance_workflow(requirement["requirement_id"])["advanced"])
            advanced = self.service.decide_gate(
                requirement_id=requirement["requirement_id"], stage="architecture", status="passed",
                actor="architect", output={"verdict": "pass", "summary": "approved"},
            )
            self.assertEqual(advanced["requirement"]["current_stage"], "critic_review")
            self.service.create_owner_decision(
                project_id="demo", requirement_id=requirement["requirement_id"], category="scope_conflict", summary="Scope conflict"
            )
            self.assertEqual(self.service.get_requirement(requirement["requirement_id"])["current_stage"], "critic_review")

    def test_pm_clarification_persists_supplied_acceptance(self) -> None:
        self.project()
        with self.db:
            requirement = self.service.create_requirement(project_id="demo", title="Clarify scope")
            result = self.service.decide_gate(
                requirement_id=requirement["requirement_id"],
                stage="pm_clarification",
                status="passed",
                actor="pm",
                output={"acceptance": ["scope is explicit"]},
            )
            self.assertEqual(result["requirement"]["acceptance"], ["scope is explicit"])

    def test_release_ready_advance_is_idempotent_after_pass(self) -> None:
        self.project()
        with self.db:
            requirement = self.service.create_requirement(
                project_id="demo", title="Release idempotency", acceptance=["done"]
            )
            self.service.advance_workflow(requirement["requirement_id"])
            self.service.register_session(
                project_id="demo", requirement_id=requirement["requirement_id"], role="architect", execution_backend="fake"
            )
            self.service.attach_artifact(
                project_id="demo", requirement_id=requirement["requirement_id"], kind="architecture", uri=str(self.project_root / "a.json")
            )
            self.service.decide_gate(
                requirement_id=requirement["requirement_id"], stage="architecture", status="passed", actor="architect",
                output={"verdict": "pass"},
            )
            # Move the requirement directly through the remaining facts for a focused release check.
            for stage, role, kind in (
                ("critic_review", "critic", "critic_review"),
                ("task_decomposition", "pm", "task_plan"),
                ("development", "developer", "implementation"),
                ("development", "developer", "test_evidence"),
                ("review", "reviewer", "review"),
                ("qa", "qa", "qa"),
                ("delivery_summary", "pm", "delivery_summary"),
            ):
                self.service.register_session(
                    project_id="demo", requirement_id=requirement["requirement_id"], role=role,
                    execution_backend="fake", thread_id=f"{role}-{kind}",
                )
                self.service.attach_artifact(
                    project_id="demo", requirement_id=requirement["requirement_id"], kind=kind,
                    uri=str(self.project_root / f"{kind}.json"),
                )
                if stage in {"critic_review", "review", "qa"}:
                    self.service.decide_gate(
                        requirement_id=requirement["requirement_id"], stage=stage, status="passed", actor=role,
                        output={"verdict": "pass"},
                    )
                elif kind != "implementation":
                    self.service.advance_workflow(requirement["requirement_id"])
            self.assertEqual(self.service.get_requirement(requirement["requirement_id"])["current_stage"], "release_ready")
            first = self.service.advance_workflow(requirement["requirement_id"])
            second = self.service.advance_workflow(requirement["requirement_id"])
            self.assertTrue(first["advanced"])
            self.assertTrue(second["idempotent"])

    def test_critic_gate_rejects_reused_author_thread(self) -> None:
        self.project()
        with self.db:
            requirement = self.service.create_requirement(
                project_id="demo", title="Independent critique", acceptance=["done"]
            )
            self.service.decide_gate(
                requirement_id=requirement["requirement_id"],
                stage="pm_clarification",
                status="passed",
                actor="pm",
                output={"acceptance": ["done"]},
            )
            self.service.register_session(
                project_id="demo", requirement_id=requirement["requirement_id"], role="architect",
                execution_backend="fake", thread_id="author-thread",
            )
            self.service.attach_artifact(
                project_id="demo", requirement_id=requirement["requirement_id"], kind="architecture",
                uri=str(self.project_root / "architecture.json"),
            )
            self.service.decide_gate(
                requirement_id=requirement["requirement_id"], stage="architecture", status="passed",
                actor="architect", output={"verdict": "pass"},
            )
            self.service.register_session(
                project_id="demo", requirement_id=requirement["requirement_id"], role="critic",
                execution_backend="codex", thread_id="author-thread",
            )
            self.service.attach_artifact(
                project_id="demo", requirement_id=requirement["requirement_id"], kind="critic_review",
                uri=str(self.project_root / "critic.json"),
            )
            with self.assertRaisesRegex(ControlPlaneError, "independent session"):
                self.service.decide_gate(
                    requirement_id=requirement["requirement_id"], stage="critic_review", status="passed",
                    actor="critic", output={"verdict": "pass"},
                )


class BackendContractTests(unittest.TestCase):
    def test_fake_backend_and_codex_unsupported_are_truthful(self) -> None:
        fake = FakeBackend()
        self.assertEqual(fake.health({}) .status, "online")
        codex = CodexAppServerBackend(client=UnsupportedCodexClient())
        health = codex.health({"thread_id": "thread-1"})
        self.assertEqual(health.status, "unsupported")
        self.assertEqual(health.capabilities["status"], "unsupported")

    def test_tmux_backend_reports_runner_facts(self) -> None:
        calls = []

        def runner(args, **kwargs):
            calls.append(args)
            return subprocess.CompletedProcess(args, 0, "", "")

        backend = TmuxBackend(runner=runner)
        health = backend.health({"external_ref": "pm-session"})
        self.assertEqual(health.status, "online")
        self.assertEqual(calls[0][-1], "pm-session")

    def test_backend_probe_persists_unsupported_without_faking_online(self) -> None:
        root = Path(tempfile.mkdtemp())
        try:
            (root / ".git").mkdir()
            db = connect_db(root / "probe.sqlite3")
            service = ControlPlaneService(db)
            with db:
                service.register_project(project_id="probe", name="Probe", repo_root=str(root))
                session = service.register_session(
                    project_id="probe", role="developer", execution_backend="codex", thread_id="t-1"
                )
                result = service.probe_session(session["session_id"], BackendRegistry().get("codex"))
                self.assertEqual(result["session"]["health"], "unsupported")
                self.assertEqual(result["session"]["session_status"], "unsupported")
            db.close()
        finally:
            import shutil
            shutil.rmtree(root)

    def test_create_session_is_backend_driven_and_unsupported_is_explicit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project_root = root / "project"
            project_root.mkdir()
            (project_root / ".git").mkdir()
            db = connect_db(root / "control.sqlite3")
            service = ControlPlaneService(db)
            with db:
                service.register_project(project_id="demo", name="Demo", repo_root=str(project_root))
                unsupported = service.create_session(
                    project_id="demo", role="developer", execution_backend=CodexAppServerBackend(client=UnsupportedCodexClient())
                )
                self.assertFalse(unsupported["created"])
                self.assertEqual(unsupported["status"], "unsupported")
                created = service.create_session(
                    project_id="demo", role="developer", execution_backend=FakeBackend(), cwd=str(project_root)
                )
                self.assertTrue(created["created"])
                self.assertEqual(created["session"]["thread_id"], "fake-thread-1")
            db.close()


if __name__ == "__main__":
    unittest.main()
