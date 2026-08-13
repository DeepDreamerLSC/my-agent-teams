#!/usr/bin/env python3
"""Run the complete delivery workflow against a temporary external Git project."""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from control_plane.backends.fake import FakeBackend
from control_plane.service import ControlPlaneService
from dashboard.db import connect_db


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="my-agent-teams-demo-") as raw:
        root = Path(raw)
        project_root = root / "external-demo"
        project_root.mkdir()
        (project_root / "src").mkdir()
        subprocess.run(["git", "init", "-q", str(project_root)], check=True)
        (project_root / "src" / "hello.txt").write_text("hello\n", encoding="utf-8")
        db = connect_db(root / "control-plane.sqlite3")
        service = ControlPlaneService(db)
        with db:
            service.register_project(
                project_id="external-demo",
                name="External demo",
                repo_root=str(project_root),
                default_branch="main",
            )
            requirement = service.create_requirement(
                project_id="external-demo",
                requirement_id="req-demo",
                title="Ship hello feature",
                acceptance=["hello.txt exists", "review and QA pass"],
            )
            pm = service.create_session(
                project_id="external-demo",
                requirement_id=requirement["requirement_id"],
                role="pm",
                execution_backend=FakeBackend(),
                cwd=str(project_root),
            )
            service.probe_session(pm["session"]["session_id"], FakeBackend())
            service.advance_workflow(requirement["requirement_id"], actor="pm-chief")
            stages = [
                ("architecture", "architect", "architecture", "architecture decision"),
                ("critic_review", "critic", "critic_review", "independent critic pass"),
                ("task_decomposition", "pm", "task_plan", "task plan"),
                ("development", "developer", "implementation", "implementation evidence"),
                ("development", "developer", "test_evidence", "developer tests"),
                ("review", "reviewer", "review", "review pass"),
                ("qa", "qa", "qa", "QA pass"),
                ("delivery_summary", "pm", "delivery_summary", "delivery summary"),
            ]
            for index, (stage, role, kind, summary) in enumerate(stages, start=1):
                service.register_session(
                    project_id="external-demo",
                    requirement_id=requirement["requirement_id"],
                    role=role,
                    execution_backend="fake",
                    thread_id=f"demo-{role}-{index}",
                    cwd=str(project_root),
                )
                artifact = project_root / "src" / f"{index}-{kind}.json"
                artifact.write_text(json.dumps({"stage": stage, "summary": summary}) + "\n", encoding="utf-8")
                service.attach_artifact(
                    project_id="external-demo",
                    requirement_id=requirement["requirement_id"],
                    kind=kind,
                    uri=str(artifact),
                    summary=summary,
                )
                if kind == "implementation":
                    continue
                if stage in {"architecture", "critic_review", "review", "qa"}:
                    service.decide_gate(
                        requirement_id=requirement["requirement_id"],
                        stage=stage,
                        status="passed",
                        actor=role,
                        output={"verdict": "pass", "summary": summary},
                    )
                else:
                    service.advance_workflow(requirement["requirement_id"], actor=role)
            owner = service.create_owner_decision(
                project_id="external-demo",
                requirement_id=requirement["requirement_id"],
                category="production_release",
                summary="Explicitly authorize release of the demo",
                options=["hold", "release"],
                recommendation="release only after Owner authorization",
            )
            blocked = service.advance_workflow(requirement["requirement_id"])
            service.resolve_owner_decision(owner["decision_id"], decision={"choice": "release"})
            ready = service.advance_workflow(requirement["requirement_id"])
            result = {
                "project": service.get_project("external-demo"),
                "requirement": ready["requirement"],
                "blocked_before_owner_decision": blocked,
                "sessions": service.list_sessions(project_id="external-demo"),
                "artifacts": service.list_artifacts(project_id="external-demo"),
                "gates": service.list_gates("req-demo"),
                "project_root": str(project_root),
                "temporary_root_removed_after_exit": True,
            }
            print(json.dumps(result, ensure_ascii=False, indent=2))
        db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
