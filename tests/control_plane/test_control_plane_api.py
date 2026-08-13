from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from dashboard.app import create_app


class ControlPlaneApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tmpdir.name)
        self.project_root = self.root / "external"
        self.project_root.mkdir()
        (self.project_root / ".git").mkdir()
        self.app = create_app(db_path=str(self.root / "board.sqlite3"), tasks_root=str(self.root / "tasks"))
        self.client = self.app.test_client()

    def tearDown(self) -> None:
        self.tmpdir.cleanup()

    def test_http_registration_binding_event_gate_owner_and_overview(self) -> None:
        response = self.client.post(
            "/api/control-plane/projects",
            json={
                "project_id": "external",
                "name": "External",
                "repo_root": str(self.project_root),
            },
        )
        self.assertEqual(response.status_code, 201)
        requirement = self.client.post(
            "/api/control-plane/requirements",
            json={"project_id": "external", "title": "Ship externally", "acceptance": ["pass"]},
        )
        self.assertEqual(requirement.status_code, 201)
        requirement_id = requirement.get_json()["requirement_id"]
        session = self.client.post(
            "/api/control-plane/sessions",
            json={
                "project_id": "external",
                "requirement_id": requirement_id,
                "role": "developer",
                "execution_backend": "codex",
                "thread_id": "thread-external",
            },
        )
        self.assertEqual(session.status_code, 201)
        session_id = session.get_json()["session_id"]
        bound = self.client.post(
            f"/api/control-plane/sessions/{session_id}/bind", json={"task_id": "task-external"}
        )
        self.assertEqual(bound.status_code, 200)
        event = self.client.post(
            "/api/control-plane/events",
            json={
                "session_id": session_id,
                "event_type": "status",
                "idempotency_key": "external-event-1",
                "sequence": 1,
                "status": "busy",
            },
        )
        self.assertEqual(event.status_code, 200)
        gate = self.client.post(
            "/api/control-plane/gates",
            json={
                "requirement_id": requirement_id,
                "stage": "pm_clarification",
                "status": "passed",
                "actor": "pm-chief",
                "output": {"acceptance": ["pass"]},
            },
        )
        self.assertEqual(gate.status_code, 200)
        owner = self.client.post(
            "/api/control-plane/owner-decisions",
            json={
                "project_id": "external",
                "category": "production_release",
                "summary": "Authorize release",
                "options": ["hold", "release"],
            },
        )
        self.assertEqual(owner.status_code, 201)
        overview = self.client.get("/api/control-plane/overview?project=external")
        self.assertEqual(overview.status_code, 200)
        payload = overview.get_json()
        self.assertEqual(len(payload["projects"]), 1)
        self.assertEqual(len(payload["requirements"]), 1)
        self.assertEqual(len(payload["sessions"]), 1)
        self.assertEqual(len(payload["owner_decisions"]), 1)

    def test_http_can_create_fake_backend_session_and_expose_evidence(self) -> None:
        project = self.client.post(
            "/api/control-plane/projects",
            json={"project_id": "external", "name": "External", "repo_root": str(self.project_root)},
        )
        self.assertEqual(project.status_code, 201)
        requirement = self.client.post(
            "/api/control-plane/requirements",
            json={"project_id": "external", "title": "Evidence", "acceptance": ["pass"]},
        ).get_json()
        created = self.client.post(
            "/api/control-plane/sessions/create",
            json={
                "project_id": "external",
                "requirement_id": requirement["requirement_id"],
                "role": "developer",
                "execution_backend": "fake",
                "cwd": str(self.project_root),
            },
        )
        self.assertEqual(created.status_code, 201)
        self.assertTrue(created.get_json()["created"])
        artifact = self.client.post(
            "/api/control-plane/artifacts",
            json={
                "project_id": "external",
                "requirement_id": requirement["requirement_id"],
                "kind": "test_evidence",
                "uri": str(self.project_root / "tests.json"),
            },
        )
        self.assertEqual(artifact.status_code, 201)
        overview = self.client.get("/api/control-plane/overview").get_json()
        self.assertEqual(overview["artifacts"][0]["kind"], "test_evidence")
        self.assertIn(requirement["requirement_id"], overview["timelines"])
        self.assertIn("delivery", overview)
        self.assertIn("gantt", overview["delivery"])

    def test_http_returns_structured_error_for_unsafe_project(self) -> None:
        response = self.client.post(
            "/api/control-plane/projects",
            json={"project_id": "unsafe", "name": "Unsafe", "repo_root": str(self.root)},
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error"]["code"], "unsafe_path")

    def test_event_endpoint_requires_configured_bearer_token(self) -> None:
        previous = os.environ.get("MY_AGENT_TEAMS_CONTROL_PLANE_TOKEN")
        os.environ["MY_AGENT_TEAMS_CONTROL_PLANE_TOKEN"] = "test-token"
        try:
            denied = self.client.post("/api/control-plane/events", json={})
            self.assertEqual(denied.status_code, 401)
            accepted = self.client.post(
                "/api/control-plane/events",
                json={
                    "session_id": "missing-session",
                    "event_type": "status",
                    "idempotency_key": "auth-test-event",
                },
                headers={"Authorization": "Bearer test-token"},
            )
            self.assertEqual(accepted.status_code, 400)
            self.assertEqual(accepted.get_json()["error"]["code"], "session_not_found")
        finally:
            if previous is None:
                os.environ.pop("MY_AGENT_TEAMS_CONTROL_PLANE_TOKEN", None)
            else:
                os.environ["MY_AGENT_TEAMS_CONTROL_PLANE_TOKEN"] = previous


if __name__ == "__main__":
    unittest.main()
