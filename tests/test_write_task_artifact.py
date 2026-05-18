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

    def _init_git_repo(self, path: Path) -> None:
        subprocess.run(["git", "init", "-b", "main"], cwd=str(path), check=True, capture_output=True, text=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=str(path), check=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=str(path), check=True)
        subprocess.run(["git", "add", "."], cwd=str(path), check=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=str(path), check=True, capture_output=True, text=True)

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

    def test_result_artifact_infers_branch_and_captures_patch_from_worktree(self):
        repo_root = Path(self.tmpdir.name) / "repo"
        repo_root.mkdir()
        feature_file = repo_root / "feature.txt"
        feature_file.write_text("before\n", encoding="utf-8")
        self._init_git_repo(repo_root)
        subprocess.run(["git", "checkout", "-b", "task/artifact-task"], cwd=str(repo_root), check=True, capture_output=True, text=True)
        feature_file.write_text("after\n", encoding="utf-8")

        task = json.loads((self.task_dir / "task.json").read_text(encoding="utf-8"))
        task.update({
            "workspace_mode": "worktree",
            "workspace_status": "prepared",
            "workspace_path": str(repo_root),
            "worktree_path": str(repo_root),
            "workspace_branch": "task/artifact-task",
            "workspace_base_ref": "main",
            "patch_path": str(self.task_dir / "artifacts" / "artifact-task.patch"),
            "target_branch": "main",
            "integration_target_branch": "main",
        })
        (self.task_dir / "task.json").write_text(json.dumps(task, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        subprocess.run(
            [
                str(SCRIPTS / "write-result.sh"),
                "artifact-task",
                "--tasks-root",
                str(self.tasks_root),
                "--agent",
                "dev-1",
                "--status",
                "done",
                "--summary",
                "带 branch/patch 的结果",
            ],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            check=True,
        )

        result_payload = json.loads((self.task_dir / "result.json").read_text(encoding="utf-8"))
        updated_task = json.loads((self.task_dir / "task.json").read_text(encoding="utf-8"))
        patch_path = Path(result_payload["patch_path"])
        self.assertEqual(result_payload["branch"], "task/artifact-task")
        self.assertEqual(result_payload["worktree_path"], str(repo_root))
        self.assertTrue(result_payload["patch_exists"])
        self.assertTrue(patch_path.exists())
        self.assertIn("feature.txt", patch_path.read_text(encoding="utf-8"))
        self.assertEqual(updated_task["result_branch"], "task/artifact-task")
        self.assertTrue(updated_task.get("patch_generated_at"))


if __name__ == "__main__":
    unittest.main()
