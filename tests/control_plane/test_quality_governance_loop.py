from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from control_plane.errors import ControlPlaneError, GateConflict
from control_plane.service import ControlPlaneService
from dashboard.db import connect_db


def quality_report(
    *,
    passed: bool,
    status: str,
    findings: list[dict] | None = None,
    expired_waivers: list[dict] | None = None,
    invalid_waivers: list[dict] | None = None,
) -> dict:
    return {
        "schema_version": "quality_gate_report/v2",
        "scenario": "pr",
        "passed": passed,
        "results": [
            {
                "name": "code_quality_delta",
                "kind": "code_quality_delta",
                "status": status,
                "blocking": True,
                "owner": "engineering",
                "message": "quality evidence",
                "details": {
                    "findings": findings or [],
                    "expired_waivers": expired_waivers or [],
                    "invalid_waivers": invalid_waivers or [],
                    "active_waivers": [],
                    "debt_summary": {
                        "added": len(findings or []),
                        "reduced": 0,
                        "unchanged": 0,
                    },
                },
            }
        ],
    }


class QualityGovernanceLoopTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tmpdir.name)
        self.project_root = self.root / "project"
        self.project_root.mkdir()
        (self.project_root / ".git").mkdir()
        (self.project_root / "evidence").mkdir()
        self.db = connect_db(self.root / "control.sqlite3")
        self.service = ControlPlaneService(self.db)
        with self.db:
            self.service.register_project(
                project_id="demo",
                name="Demo",
                repo_root=str(self.project_root),
            )

    def tearDown(self) -> None:
        self.db.close()
        self.tmpdir.cleanup()

    def _attach(self, requirement_id: str, kind: str, suffix: str, *, metadata=None) -> dict:
        return self.service.attach_artifact(
            project_id="demo",
            requirement_id=requirement_id,
            kind=kind,
            uri=str(self.project_root / "evidence" / f"{suffix}-{kind}.json"),
            metadata=metadata,
        )

    def _register(self, requirement_id: str, role: str, thread: str) -> dict:
        return self.service.register_session(
            project_id="demo",
            requirement_id=requirement_id,
            role=role,
            execution_backend="fake",
            thread_id=thread,
        )

    def _requirement_at_development(self) -> dict:
        requirement = self.service.create_requirement(
            project_id="demo",
            title="Quality governed change",
            acceptance=["behavior verified"],
        )
        requirement_id = requirement["requirement_id"]
        self.service.advance_workflow(requirement_id, actor="pm")
        self._register(requirement_id, "architect", "architect-thread")
        self._attach(requirement_id, "architecture", "architecture")
        self.service.decide_gate(
            requirement_id=requirement_id,
            stage="architecture",
            status="passed",
            actor="architect",
            output={"verdict": "pass"},
        )
        self._register(requirement_id, "critic", "critic-thread")
        self._attach(requirement_id, "critic_review", "critic")
        self.service.decide_gate(
            requirement_id=requirement_id,
            stage="critic_review",
            status="passed",
            actor="critic",
            output={"verdict": "pass"},
        )
        self._register(requirement_id, "pm", "pm-thread")
        self._attach(requirement_id, "task_plan", "plan")
        result = self.service.advance_workflow(requirement_id, actor="pm")
        self.assertTrue(result["advanced"])
        self.assertEqual(result["requirement"]["current_stage"], "development")
        return result["requirement"]

    def _submit_development(self, requirement_id: str, round_number: int) -> None:
        self._attach(requirement_id, "implementation", f"r{round_number}")
        self._attach(requirement_id, "test_evidence", f"r{round_number}")
        result = self.service.advance_workflow(requirement_id, actor="developer")
        self.assertTrue(result["advanced"])
        self.assertEqual(result["requirement"]["current_stage"], "quality_gate")

    def test_developer_quality_reviewer_rework_then_pass(self) -> None:
        with self.db:
            requirement = self._requirement_at_development()
            requirement_id = requirement["requirement_id"]
            self._register(requirement_id, "developer", "developer-thread")
            self._submit_development(requirement_id, 1)
            self._attach(
                requirement_id,
                "quality_report",
                "r1",
                metadata=quality_report(
                    passed=False,
                    status="failed",
                    findings=[
                        {
                            "rule_id": "python.function.lines",
                            "path": "src/service.py",
                            "line": 20,
                            "blocking": True,
                            "recommended_action": "extract one responsibility",
                        }
                    ],
                ),
            )
            rejected = self.service.advance_workflow(requirement_id, actor="quality-automation")
            self.assertFalse(rejected["advanced"])
            self.assertEqual(rejected["reason"], "quality_gate_rejected")
            self.assertEqual(rejected["requirement"]["current_stage"], "development")
            self.assertEqual(rejected["quality"]["failure_category"], "code_quality_failure")

            stale = self.service.advance_workflow(requirement_id, actor="developer")
            self.assertFalse(stale["advanced"])
            self.assertEqual(stale["reason"], "required_artifact_missing")
            self.assertEqual(stale["missing_artifacts"], ["implementation", "test_evidence"])

            self._submit_development(requirement_id, 2)
            self._attach(
                requirement_id,
                "quality_report",
                "r2",
                metadata=quality_report(passed=True, status="passed"),
            )
            quality_pass = self.service.advance_workflow(requirement_id, actor="quality-automation")
            self.assertTrue(quality_pass["advanced"])
            self.assertEqual(quality_pass["requirement"]["current_stage"], "review")

            self._register(requirement_id, "reviewer", "reviewer-thread")
            self._attach(requirement_id, "review", "r2")
            blocking_finding = {
                "rule_id": "design.hidden_state",
                "location": "src/service.py:45",
                "severity": "blocking",
                "blocking": True,
                "status": "open",
                "risk": "state ownership is ambiguous",
                "recommended_action": "move state behind the owning boundary",
            }
            with self.assertRaisesRegex(GateConflict, "unresolved blocking findings"):
                self.service.decide_gate(
                    requirement_id=requirement_id,
                    stage="review",
                    status="passed",
                    actor="reviewer",
                    output={"verdict": "pass", "findings": [blocking_finding]},
                )
            review_reject = self.service.decide_gate(
                requirement_id=requirement_id,
                stage="review",
                status="rejected",
                actor="reviewer",
                rejection_reason="hidden state must be removed",
                output={"verdict": "request_changes", "findings": [blocking_finding]},
            )
            self.assertEqual(review_reject["requirement"]["current_stage"], "development")

            self._submit_development(requirement_id, 3)
            self._attach(
                requirement_id,
                "quality_report",
                "r3",
                metadata=quality_report(passed=True, status="passed"),
            )
            self.service.advance_workflow(requirement_id, actor="quality-automation")
            self._attach(requirement_id, "review", "r3")
            review_pass = self.service.decide_gate(
                requirement_id=requirement_id,
                stage="review",
                status="passed",
                actor="reviewer",
                output={"verdict": "pass", "findings": []},
            )
            self.assertEqual(review_pass["requirement"]["current_stage"], "qa")
            quality_state = self.service.overview(project_id="demo")["quality"][requirement_id]
            self.assertTrue(quality_state["passed"])
            self.assertEqual(quality_state["debt_summary"]["added"], 0)

    def test_infrastructure_failure_is_blocked_without_code_rework(self) -> None:
        with self.db:
            requirement = self._requirement_at_development()
            requirement_id = requirement["requirement_id"]
            self._register(requirement_id, "developer", "developer-thread")
            self._submit_development(requirement_id, 1)
            self._attach(
                requirement_id,
                "quality_report",
                "infra",
                metadata=quality_report(passed=False, status="infra_error"),
            )
            result = self.service.advance_workflow(requirement_id, actor="quality-automation")
            self.assertFalse(result["advanced"])
            self.assertEqual(result["reason"], "quality_gate_infrastructure_failure")
            self.assertEqual(result["quality"]["failure_category"], "infrastructure_failure")
            self.assertEqual(result["requirement"]["current_stage"], "quality_gate")
            self.assertEqual(result["requirement"]["status"], "blocked")
            self.assertEqual(self.service.list_owner_decisions(project_id="demo"), [])

    def test_expired_waiver_rejects_and_three_quality_rounds_open_owner_decision(self) -> None:
        with self.db:
            requirement = self._requirement_at_development()
            requirement_id = requirement["requirement_id"]
            self._register(requirement_id, "developer", "developer-thread")
            for round_number in (1, 2, 3):
                self._submit_development(requirement_id, round_number)
                self._attach(
                    requirement_id,
                    "quality_report",
                    f"expired-{round_number}",
                    metadata=quality_report(
                        passed=True,
                        status="passed",
                        expired_waivers=[
                            {
                                "rule_id": "python.function.lines",
                                "owner": "backend",
                                "expires_on": "2026-01-01",
                            }
                        ],
                    ),
                )
                result = self.service.advance_workflow(requirement_id, actor="quality-automation")
                self.assertEqual(result["reason"], "quality_gate_rejected")
                self.assertEqual(len(result["quality"]["expired_waivers"]), 1)
            decisions = self.service.list_owner_decisions(project_id="demo")
            self.assertEqual(len(decisions), 1)
            self.assertEqual(decisions[0]["category"], "repeated_gate_failure")
            self.assertIn("quality_gate", decisions[0]["summary"])

    def test_passed_report_cannot_hide_invalid_waiver_or_blocking_finding(self) -> None:
        with self.db:
            requirement = self._requirement_at_development()
            requirement_id = requirement["requirement_id"]
            self._register(requirement_id, "developer", "developer-thread")
            self._submit_development(requirement_id, 1)
            self._attach(
                requirement_id,
                "quality_report",
                "invalid-waiver",
                metadata=quality_report(
                    passed=True,
                    status="passed",
                    invalid_waivers=[{"rule_id": "code_quality.function_lines"}],
                ),
            )
            invalid = self.service.advance_workflow(requirement_id, actor="quality-automation")
            self.assertEqual(invalid["reason"], "quality_gate_rejected")
            self.assertEqual(len(invalid["quality"]["invalid_waivers"]), 1)

            self._submit_development(requirement_id, 2)
            self._attach(
                requirement_id,
                "quality_report",
                "hidden-finding",
                metadata=quality_report(
                    passed=True,
                    status="passed",
                    findings=[
                        {
                            "rule_id": "code_quality.function_lines",
                            "path": "src/service.py",
                            "delta": {"direction": "increased", "value": 1},
                            "waiver": {"status": "none"},
                        }
                    ],
                ),
            )
            hidden = self.service.advance_workflow(requirement_id, actor="quality-automation")
            self.assertEqual(hidden["reason"], "quality_gate_rejected")
            self.assertEqual(len(hidden["quality"]["blocking_findings"]), 1)

    def test_quality_report_artifact_rejects_unstructured_metadata(self) -> None:
        with self.db:
            requirement = self.service.create_requirement(
                project_id="demo", title="Invalid report", acceptance=["valid evidence"]
            )
            with self.assertRaises(ControlPlaneError) as raised:
                self._attach(
                    requirement["requirement_id"],
                    "quality_report",
                    "invalid",
                    metadata={"passed": True},
                )
            self.assertEqual(raised.exception.code, "invalid_quality_report")

            with self.assertRaises(ControlPlaneError) as empty_results:
                self._attach(
                    requirement["requirement_id"],
                    "quality_report",
                    "empty-results",
                    metadata={
                        "schema_version": "quality_gate_report/v1",
                        "scenario": "pr",
                        "passed": True,
                        "results": [],
                    },
                )
            self.assertEqual(empty_results.exception.code, "invalid_quality_report")


if __name__ == "__main__":
    unittest.main()
