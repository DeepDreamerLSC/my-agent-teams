from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CLI = ROOT / "scripts" / "control-plane.py"


def run_cli(db_path: Path, *args: str) -> dict | list:
    result = subprocess.run(
        [sys.executable, str(CLI), "--db", str(db_path), *args],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return json.loads(result.stdout)


def test_cli_attaches_quality_report_from_metadata_file(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / ".git").mkdir()
    report_path = project / "quality-gates-pr.json"
    report = {
        "schema_version": "quality_gate_report/v1",
        "scenario": "pr",
        "passed": True,
        "results": [
            {
                "name": "code_quality_incremental",
                "status": "passed",
                "blocking": True,
                "owner": "architecture",
                "details": {
                    "findings": [],
                    "debt_summary": {"added": 0, "reduced": 1, "unchanged": 0},
                    "active_waivers": [],
                    "expired_waivers": [],
                },
            }
        ],
    }
    report_path.write_text(json.dumps(report), encoding="utf-8")
    db_path = tmp_path / "control.sqlite3"

    run_cli(
        db_path,
        "project",
        "register",
        "--id",
        "demo",
        "--name",
        "Demo",
        "--repo-root",
        str(project),
    )
    requirement = run_cli(
        db_path,
        "requirement",
        "submit",
        "--project-id",
        "demo",
        "--title",
        "Quality report",
        "--acceptance-json",
        '["quality evidence attached"]',
    )
    artifact = run_cli(
        db_path,
        "artifact",
        "attach",
        "--project-id",
        "demo",
        "--requirement-id",
        str(requirement["requirement_id"]),
        "--kind",
        "quality_report",
        "--uri",
        str(report_path),
        "--metadata-file",
        str(report_path),
    )

    assert artifact["kind"] == "quality_report"
    assert artifact["metadata"]["passed"] is True
    listed = run_cli(
        db_path,
        "artifact",
        "list",
        "--requirement-id",
        str(requirement["requirement_id"]),
    )
    assert [item["artifact_id"] for item in listed] == [artifact["artifact_id"]]
