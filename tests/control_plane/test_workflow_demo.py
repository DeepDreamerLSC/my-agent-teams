from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from control_plane.backends.fake import FakeBackend
from control_plane.service import ControlPlaneService
from dashboard.db import connect_db


def quality_report() -> dict:
    return {
        "schema_version": "quality_gate_report/v2",
        "scenario": "pr",
        "passed": True,
        "results": [
            {
                "name": "code_quality_delta",
                "status": "passed",
                "blocking": True,
                "owner": "engineering",
                "details": {
                    "findings": [],
                    "debt_summary": {"added": 0, "reduced": 1, "unchanged": 2},
                    "active_waivers": [],
                    "expired_waivers": [],
                },
            }
        ],
    }


class WorkflowDemoTests(unittest.TestCase):
    def test_temporary_external_git_project_runs_full_delivery_workflow(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            external = root / "external-demo"
            external.mkdir()
            subprocess.run(["git", "init", "-q", str(external)], check=True)
            (external / "src").mkdir()
            db = connect_db(root / "control.sqlite3")
            service = ControlPlaneService(db)
            stages = [
                ("architecture", "architect", "architecture", "architecture decision"),
                ("critic_review", "critic", "critic_review", "independent critique"),
                ("task_decomposition", "pm", "task_plan", "task plan"),
                ("development", "developer", "implementation", "implementation"),
                ("development", "developer", "test_evidence", "tests"),
                ("quality_gate", "developer", "quality_report", "automated quality passed"),
                ("review", "reviewer", "review", "review passed"),
                ("qa", "qa", "qa", "qa passed"),
                ("delivery_summary", "pm", "delivery_summary", "delivery summary"),
            ]
            with db:
                service.register_project(project_id="external-demo", name="External Demo", repo_root=str(external), default_branch="main")
                requirement = service.create_requirement(
                    project_id="external-demo", title="Add hello feature", acceptance=["hello output"], requirement_id="req-demo"
                )
                session = service.register_session(
                    project_id="external-demo", requirement_id=requirement["requirement_id"], role="pm", execution_backend="fake", thread_id="thread-pm"
                )
                service.probe_session(session["session_id"], FakeBackend())
                first = service.advance_workflow(requirement["requirement_id"], actor="pm-chief")
                self.assertTrue(first["advanced"])
                for index, (stage, role, kind, summary) in enumerate(stages, start=1):
                    service.register_session(
                        project_id="external-demo", requirement_id=requirement["requirement_id"], role=role, execution_backend="fake", thread_id=f"thread-{role}-{index}"
                    )
                    service.attach_artifact(
                        project_id="external-demo", requirement_id=requirement["requirement_id"], kind=kind,
                        uri=str(external / "src" / f"{index}-{kind}.json"), summary=summary,
                        metadata=(
                            quality_report()
                            if kind == "quality_report"
                            else {
                                "quality_summary": {
                                    "debt_added": 0,
                                    "debt_reduced": 1,
                                    "active_waivers": [],
                                    "residual_risks": [],
                                }
                            }
                            if kind == "delivery_summary"
                            else None
                        ),
                    )
                    if stage == "development":
                        if kind == "implementation":
                            continue
                    if stage in {"architecture", "critic_review", "review", "qa"}:
                        result = service.decide_gate(
                            requirement_id=requirement["requirement_id"], stage=stage, status="passed",
                            actor=role,
                            output={
                                "verdict": "pass",
                                "summary": summary,
                                **({"findings": []} if stage == "review" else {}),
                            },
                        )
                        result = {"advanced": True, **result}
                    else:
                        result = service.advance_workflow(requirement["requirement_id"], actor=role)
                    self.assertTrue(result["advanced"], (stage, result))
                current = service.get_requirement(requirement["requirement_id"])
                self.assertEqual(current["current_stage"], "release_ready")
                owner = service.create_owner_decision(
                    project_id="external-demo", requirement_id=requirement["requirement_id"], category="production_release", summary="Authorize release"
                )
                blocked = service.advance_workflow(requirement["requirement_id"])
                self.assertFalse(blocked["advanced"])
                self.assertEqual(blocked["reason"], "owner_decision_open")
                service.resolve_owner_decision(owner["decision_id"], decision={"choice": "release"})
                ready = service.advance_workflow(requirement["requirement_id"])
                self.assertTrue(ready["advanced"])
                self.assertEqual(ready["requirement"]["status"], "release_ready")
            db.close()


if __name__ == "__main__":
    unittest.main()
