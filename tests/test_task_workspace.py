from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
ENSURE_WORKSPACE = REPO_ROOT / "scripts" / "ensure-task-workspace.py"


class TaskWorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tmpdir.name)
        self.project_root = self.root / "project"
        self.project_root.mkdir()
        subprocess.run(["git", "init", "-b", "main"], cwd=str(self.project_root), check=True, capture_output=True, text=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=str(self.project_root), check=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=str(self.project_root), check=True)
        (self.project_root / "src").mkdir()
        (self.project_root / "src" / "main.py").write_text("print('hello')\n", encoding="utf-8")
        subprocess.run(["git", "add", "."], cwd=str(self.project_root), check=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=str(self.project_root), check=True, capture_output=True, text=True)

        self.tasks_root = self.root / "tasks"
        self.task_dir = self.tasks_root / "task-a"
        self.task_dir.mkdir(parents=True)
        (self.task_dir / "task.json").write_text(json.dumps({
            "id": "task-a",
            "title": "任务A",
            "status": "dispatched",
            "project": "demo",
            "assigned_agent": "dev-1",
            "execution_mode": "dev",
            "target_environment": "dev",
            "task_type": "development",
            "read_only": False,
            "write_scope": ["src/main.py"],
            "workspace_mode": "worktree",
            "target_branch": "integration",
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        self.config_path = self.root / "config.json"
        self.config_path.write_text(json.dumps({
            "workspace_root": str(self.root),
            "defaults": {
                "workspace_mode": "worktree",
                "target_branch": "integration",
            },
            "workspace_management": {
                "worktree_root": str(self.root / "worktrees"),
            },
            "projects": {
                "demo": {
                    "dev_root": str(self.project_root),
                    "prod_root": str(self.root / "prod"),
                },
            },
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_ensure_task_workspace_creates_worktree_and_updates_task_metadata(self):
        completed = subprocess.run(
            [str(ENSURE_WORKSPACE), str(self.task_dir), "--config", str(self.config_path)],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            check=True,
        )

        payload = json.loads(completed.stdout)
        task = json.loads((self.task_dir / "task.json").read_text(encoding="utf-8"))
        self.assertEqual(payload["workspace_status"], "prepared")
        self.assertTrue(Path(payload["worktree_path"]).exists())
        self.assertTrue(str(payload["workspace_branch"]).startswith("task/"))
        self.assertEqual(task["workspace_status"], "prepared")
        self.assertEqual(task["integration_target_branch"], "integration")
        self.assertTrue(Path(task["patch_path"]).parent.exists())
        self.assertIn("补丁建议输出到", payload["dispatch_hint"])


if __name__ == "__main__":
    unittest.main()
