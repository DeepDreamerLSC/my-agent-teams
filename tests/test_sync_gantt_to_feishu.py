from __future__ import annotations

import os
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SYNC_GANTT = REPO_ROOT / "scripts" / "sync-gantt-to-feishu.sh"


def test_sync_gantt_script_has_no_hardcoded_feishu_ids():
    content = SYNC_GANTT.read_text(encoding="utf-8")

    assert 'os.environ.get("GANTT_FEISHU_BASE_TOKEN", "' not in content
    assert 'os.environ.get("GANTT_FEISHU_TASK_TABLE", "' not in content
    assert 'BASE_TOKEN = os.environ["BASE_TOKEN"]' in content
    assert 'TASK_TABLE = os.environ["TASK_DETAIL_TABLE"]' in content


def test_sync_gantt_requires_task_detail_table_before_external_calls(tmp_path: Path):
    completed = subprocess.run(
        [str(SYNC_GANTT), "--dry-run"],
        cwd=str(REPO_ROOT),
        env={
            **os.environ,
            "FEISHU_CONFIG_PATH": str(tmp_path / "missing-config.local.json"),
            "GANTT_FEISHU_BASE_TOKEN": "base-token",
            "GANTT_FEISHU_TABLE_ID": "aggregate-table",
            "GANTT_FEISHU_AGENTS": "dev-1",
            "GANTT_FEISHU_RECORD_IDS": "rec-1",
        },
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 1
    assert "GANTT_FEISHU_TASK_TABLE_ID" in completed.stderr
