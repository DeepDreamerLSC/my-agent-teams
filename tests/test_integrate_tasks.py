from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
INTEGRATE_TASK = REPO_ROOT / "scripts" / "integrate-task.py"
INTEGRATE_READY = REPO_ROOT / "scripts" / "integrate-ready-tasks.py"


class IntegrateTaskTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tmpdir.name)
        self.project = self.root / "project"
        self.project.mkdir()
        self.tasks_root = self.root / "tasks"
        self.tasks_root.mkdir()
        self.config_path = self.root / "config.json"

        self.git("init", "-b", "main")
        self.git("config", "user.email", "test@example.com")
        self.git("config", "user.name", "Test User")
        (self.project / "app.txt").write_text("base\n", encoding="utf-8")
        self.git("add", ".")
        self.git("commit", "-m", "init")
        self.git("branch", "integration")

        self.config_path.write_text(json.dumps({
            "workspace_root": str(self.root),
            "defaults": {
                "target_branch": "integration",
            },
            "projects": {
                "demo": {
                    "dev_root": str(self.project),
                    "prod_root": str(self.root / "prod"),
                },
            },
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def tearDown(self):
        self.tmpdir.cleanup()

    def git(self, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", *args],
            cwd=str(self.project),
            capture_output=True,
            text=True,
            check=check,
        )

    def create_branch(self, branch: str, files: dict[str, str], base: str = "main") -> None:
        self.git("checkout", "-B", branch, base)
        for rel_path, content in files.items():
            path = self.project / rel_path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        self.git("add", ".")
        self.git("commit", "-m", f"change {branch}")
        self.git("checkout", "main")

    def create_task(self, task_id: str, branch: str, completed_at: str = "2026-05-27T10:00:00+08:00") -> Path:
        task_dir = self.tasks_root / task_id
        task_dir.mkdir()
        task = {
            "id": task_id,
            "title": task_id,
            "status": "ready_for_merge",
            "project": "demo",
            "workspace_root": str(self.project),
            "workspace_branch": branch,
            "integration_target_branch": "integration",
            "merge_gate_state": "pm_acceptance_pending",
            "review_required": "false",
            "test_required": "false",
            "completed_at": completed_at,
        }
        (task_dir / "task.json").write_text(json.dumps(task, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (task_dir / "result.json").write_text(json.dumps({
            "task_id": task_id,
            "status": "success",
            "summary": "ready",
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return task_dir

    def run_integrate_task(self, task_dir: Path, *extra: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        completed = subprocess.run(
            [
                sys.executable,
                str(INTEGRATE_TASK),
                "--task-dir",
                str(task_dir),
                "--config",
                str(self.config_path),
                *extra,
            ],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
        if check and completed.returncode != 0:
            self.fail(f"integrate-task failed\nstdout={completed.stdout}\nstderr={completed.stderr}")
        return completed

    def branch_file(self, branch: str, rel_path: str) -> str:
        completed = self.git("show", f"{branch}:{rel_path}")
        return completed.stdout

    def test_branch_merge_updates_target_and_closes_task(self):
        self.create_branch("task/feature", {"app.txt": "base\nfeature\n"})
        task_dir = self.create_task("集成成功", "task/feature")

        completed = self.run_integrate_task(task_dir)
        payload = json.loads(completed.stdout)
        task = json.loads((task_dir / "task.json").read_text(encoding="utf-8"))

        self.assertEqual(payload["status"], "pass")
        self.assertEqual(task["status"], "done")
        self.assertEqual(task["merge_gate_state"], "closed")
        self.assertIn("feature", self.branch_file("integration", "app.txt"))
        self.assertEqual(json.loads((task_dir / "integration.json").read_text(encoding="utf-8"))["status"], "pass")

    def test_merge_conflict_blocks_task_with_conflict_files(self):
        self.create_branch("integration", {"app.txt": "integration\n"})
        self.create_branch("task/conflict", {"app.txt": "task\n"})
        task_dir = self.create_task("集成冲突", "task/conflict")

        completed = self.run_integrate_task(task_dir, check=False)
        task = json.loads((task_dir / "task.json").read_text(encoding="utf-8"))
        integration = json.loads((task_dir / "integration.json").read_text(encoding="utf-8"))

        self.assertNotEqual(completed.returncode, 0)
        self.assertEqual(task["status"], "blocked")
        self.assertEqual(integration["status"], "fail")
        self.assertEqual(integration["reason"], "merge_conflict")
        self.assertIn("app.txt", integration["conflict_files"])

    def test_missing_source_blocks_task_with_integration_failure(self):
        task_dir = self.create_task("缺少合入源", "task/missing")

        completed = self.run_integrate_task(task_dir, check=False)
        task = json.loads((task_dir / "task.json").read_text(encoding="utf-8"))
        integration = json.loads((task_dir / "integration.json").read_text(encoding="utf-8"))

        self.assertNotEqual(completed.returncode, 0)
        self.assertEqual(task["status"], "blocked")
        self.assertEqual(integration["status"], "fail")
        self.assertEqual(integration["reason"], "integration_source_missing")

    def test_dry_run_does_not_write_task_or_target_branch(self):
        self.create_branch("task/dry", {"app.txt": "base\ndry\n"})
        task_dir = self.create_task("集成DryRun", "task/dry")
        before = self.git("rev-parse", "integration").stdout.strip()

        completed = self.run_integrate_task(task_dir, "--dry-run")
        payload = json.loads(completed.stdout)
        task = json.loads((task_dir / "task.json").read_text(encoding="utf-8"))
        after = self.git("rev-parse", "integration").stdout.strip()

        self.assertTrue(payload["dry_run"])
        self.assertEqual(task["status"], "ready_for_merge")
        self.assertFalse((task_dir / "integration.json").exists())
        self.assertEqual(before, after)

    def test_ready_queue_integrates_tasks_serially(self):
        self.create_branch("task/a", {"a.txt": "a\n"})
        self.create_branch("task/b", {"b.txt": "b\n"})
        first = self.create_task("队列任务A", "task/a", "2026-05-27T10:00:00+08:00")
        second = self.create_task("队列任务B", "task/b", "2026-05-27T10:01:00+08:00")

        completed = subprocess.run(
            [
                sys.executable,
                str(INTEGRATE_READY),
                "--tasks-root",
                str(self.tasks_root),
                "--config",
                str(self.config_path),
            ],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
        if completed.returncode != 0:
            self.fail(f"integrate-ready-tasks failed\nstdout={completed.stdout}\nstderr={completed.stderr}")
        payload = json.loads(completed.stdout)

        self.assertEqual(payload["processed_count"], 2)
        self.assertEqual(payload["failed_count"], 0)
        self.assertEqual(json.loads((first / "task.json").read_text(encoding="utf-8"))["status"], "done")
        self.assertEqual(json.loads((second / "task.json").read_text(encoding="utf-8"))["status"], "done")
        self.assertEqual(self.branch_file("integration", "a.txt"), "a\n")
        self.assertEqual(self.branch_file("integration", "b.txt"), "b\n")


if __name__ == "__main__":
    unittest.main()
