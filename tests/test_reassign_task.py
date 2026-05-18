from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
REASSIGN_SCRIPT = REPO_ROOT / "scripts" / "reassign-task.sh"


class ReassignTaskTests(unittest.TestCase):
    def test_reassign_script_passes_shell_syntax_check(self):
        subprocess.run(["bash", "-n", str(REASSIGN_SCRIPT)], check=True)

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tmpdir.name)
        self.state_dir = self.root / ".runtime" / "state" / "task-watcher"
        self.task_dir = self.root / "tasks" / "task-a"
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.task_dir.mkdir(parents=True, exist_ok=True)
        (self.task_dir / "transitions.jsonl").write_text("", encoding="utf-8")
        (self.task_dir / "task.json").write_text(json.dumps({
            "id": "task-a",
            "title": "重派测试",
            "status": "dispatched",
            "assigned_agent": "dev-1",
            "claim_policy": "pull",
            "claim_scope": ["dev-1", "dev-2"],
            "claimed_by": "dev-1",
            "claimed_at": "2026-05-18T10:00:00+08:00",
            "reserved_by": "dev-1",
            "reserved_at": "2026-05-18T10:00:00+08:00",
            "project": "demo",
            "task_type": "development",
            "domain": "development",
            "review_required": True,
            "test_required": True,
            "quality_gate_mode": "parallel",
            "pool_entered_at": "2026-05-18T09:50:00+08:00",
            "pre_claim_assigned_agent": "auto",
            "dispatch_delivery_attempt_count": 4,
            "dispatch_delivery_retry_count": 2,
            "dispatch_delivery_consecutive_failures": 2,
            "last_delivery_state": "session_unhealthy",
            "last_delivery_error": "tmux session missing",
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (self.task_dir / "ack.json").write_text('{"task_id":"task-a","agent":"dev-1","status":"ack"}\n', encoding="utf-8")
        (self.task_dir / "result.json").write_text('{"task_id":"task-a","agent":"dev-1","status":"success","summary":"old"}\n', encoding="utf-8")

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_reassign_script_archives_artifacts_and_resets_control_plane_fields(self):
        completed = subprocess.run(
            [str(REASSIGN_SCRIPT), "--task-dir", str(self.task_dir), "--agent", "dev-2", "--reason", "session unhealthy"],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            env={**os.environ, "STATE_DIR": str(self.state_dir)},
            check=True,
        )

        payload = json.loads(completed.stdout)
        self.assertEqual(payload["from_agent"], "dev-1")
        self.assertEqual(payload["to_agent"], "dev-2")

        task = json.loads((self.task_dir / "task.json").read_text(encoding="utf-8"))
        self.assertEqual(task["status"], "dispatched")
        self.assertEqual(task["assigned_agent"], "dev-2")
        self.assertEqual(task["claimed_by"], "dev-2")
        self.assertEqual(task["reserved_by"], "dev-2")
        self.assertEqual(task["reassign_count"], 1)
        self.assertEqual(task["control_plane_state"], "reassigned")
        self.assertEqual(task["dispatch_delivery_attempt_count"], 0)
        self.assertEqual(task["dispatch_delivery_retry_count"], 0)
        self.assertEqual(task["dispatch_delivery_consecutive_failures"], 0)
        self.assertIsNone(task["last_delivery_error"])
        self.assertTrue((self.task_dir / "history").exists())
        self.assertFalse((self.task_dir / "ack.json").exists())
        self.assertFalse((self.task_dir / "result.json").exists())
        self.assertTrue(list((self.task_dir / "history").glob("ack.*.json")))
        self.assertTrue(list((self.task_dir / "history").glob("result.*.json")))

        transitions = (self.task_dir / "transitions.jsonl").read_text(encoding="utf-8")
        self.assertIn("reassign-task: session unhealthy", transitions)


if __name__ == "__main__":
    unittest.main()
