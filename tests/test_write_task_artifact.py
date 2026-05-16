from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = REPO_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS / "lib"))
import task_artifacts  # type: ignore


class WriteTaskArtifactTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.tasks_root = Path(self.tmpdir.name) / "tasks"
        self.task_dir = self.tasks_root / "artifact-task"
        self.task_dir.mkdir(parents=True)
        task = {
            "id": "artifact-task",
            "title": "产物写入任务",
            "status": "working",
            "assigned_agent": "dev-1",
            "reviewer": "review-1",
            "execution_round": 2,
            "created_at": "2026-05-16T10:00:00+08:00",
        }
        (self.task_dir / "task.json").write_text(
            json.dumps(task, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def tearDown(self):
        self.tmpdir.cleanup()

    def _run(self, script_name: str, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [str(SCRIPTS / script_name), "artifact-task", "--tasks-root", str(self.tasks_root), *args],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            check=True,
        )

    def test_wrappers_write_valid_artifacts_with_current_round(self):
        self._run("write-ack.sh", "--agent", "dev-1", "--summary", "已接单")
        self._run("write-result.sh", "--agent", "dev-1", "--status", "done", "--summary", "已完成")
        self._run("write-review.sh", "--reviewer", "review-1", "--status", "approve", "--summary", "通过")
        self._run("write-verify.sh", "--tester", "qa-1", "--status", "pass", "--summary", "验证通过")

        ack = task_artifacts.parse_ack(self.task_dir)
        result = task_artifacts.parse_result(self.task_dir)
        review = task_artifacts.parse_review(self.task_dir)
        verify = task_artifacts.parse_verify(self.task_dir)

        self.assertTrue(ack["valid"])
        self.assertEqual(ack["normalized_status"], "acknowledged")
        self.assertEqual(ack["artifact_round"], 2)
        self.assertTrue(result["valid"])
        self.assertEqual(result["normalized_status"], "success")
        self.assertFalse(result["legacy_mapped"])
        self.assertEqual(result["artifact_round"], 2)
        self.assertTrue(review["valid"])
        self.assertEqual(review["normalized_status"], "approve")
        self.assertTrue(verify["valid"])
        self.assertEqual(verify["normalized_status"], "pass")
        self.assertEqual(verify["artifact_round"], 2)

    def test_invalid_status_does_not_overwrite_existing_artifact(self):
        self._run("write-result.sh", "--agent", "dev-1", "--status", "done", "--summary", "第一版")
        before = (self.task_dir / "result.json").read_text(encoding="utf-8")

        failed = subprocess.run(
            [
                str(SCRIPTS / "write-result.sh"),
                "artifact-task",
                "--tasks-root",
                str(self.tasks_root),
                "--agent",
                "dev-1",
                "--status",
                "success",
                "--summary",
                "不应写入",
            ],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
        )

        self.assertNotEqual(failed.returncode, 0)
        self.assertEqual((self.task_dir / "result.json").read_text(encoding="utf-8"), before)

    def test_parser_marks_legacy_success_status(self):
        (self.task_dir / "result.json").write_text(json.dumps({
            "task_id": "artifact-task",
            "agent": "dev-1",
            "status": "success",
            "round": 2,
            "summary": "legacy",
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        parsed = task_artifacts.parse_result(self.task_dir)

        self.assertTrue(parsed["valid"])
        self.assertEqual(parsed["normalized_status"], "success")
        self.assertTrue(parsed["legacy_mapped"])


if __name__ == "__main__":
    unittest.main()
