from __future__ import annotations

import json
import os
import subprocess
import tempfile
import threading
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
CLAIM_SCRIPT = REPO_ROOT / "scripts" / "claim-task.sh"
TASK_WATCHER = REPO_ROOT / "scripts" / "task-watcher.sh"
ENSURE_TASK_WORKSPACE = REPO_ROOT / "scripts" / "ensure-task-workspace.py"


class ClaimTaskReservedTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tmpdir.name)
        self.tasks_root = self.root / "tasks"
        self.dev_root = self.root / "dev"
        self.scripts_root = self.root / "scripts"
        self.tasks_root.mkdir()
        self.dev_root.mkdir()
        self.scripts_root.mkdir()
        subprocess.run(["git", "init", "-b", "main"], cwd=str(self.dev_root), check=True, capture_output=True, text=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=str(self.dev_root), check=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=str(self.dev_root), check=True)
        (self.dev_root / "src").mkdir()
        (self.dev_root / "src" / "base.txt").write_text("base\n", encoding="utf-8")
        subprocess.run(["git", "add", "."], cwd=str(self.dev_root), check=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=str(self.dev_root), check=True, capture_output=True, text=True)
        self.config_path = self.root / "config.json"
        self.config_path.write_text(json.dumps({
            "agents": {"dev-1": {"role": "fullstack_dev"}},
            "projects": {"demo": {"dev_root": str(self.dev_root)}},
            "defaults": {
                "workspace_mode": "worktree",
                "target_branch": "integration",
            },
            "workspace_management": {
                "worktree_root": str(self.root / "worktrees"),
            },
            "task_pool": {
                "default_working_limit": 1,
                "default_reserved_limit": 1,
                "default_claim_max_concurrency": 1,
            },
            "wip_limits": {"dev": 1},
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        for name in ("claim-task.sh", "ensure-task-workspace.py", "task-pool-router.py"):
            (self.scripts_root / name).symlink_to(REPO_ROOT / "scripts" / name)
        (self.scripts_root / "lib").symlink_to(REPO_ROOT / "scripts" / "lib")

    def tearDown(self):
        self.tmpdir.cleanup()

    def _env(self) -> dict[str, str]:
        return {
            **os.environ,
            "TASKS_ROOT": str(self.tasks_root),
            "CONFIG_PATH": str(self.config_path),
            "CLAIM_AGENT_ID": "dev-1",
            "WORKSPACE_ROOT": str(self.root),
        }

    def _watcher_env(self) -> dict[str, str]:
        return {
            **self._env(),
            "TASK_WATCHER_TEST_MODE": "1",
            "STATE_DIR": str(self.root / ".runtime" / "state" / "task-watcher"),
            "LOG_DIR": str(self.root / ".runtime" / "logs"),
            "LOG_FILE": str(self.root / ".runtime" / "logs" / "task-watcher.log"),
            "WATCHER_STDOUT_LOG": str(self.root / ".runtime" / "logs" / "task-watcher.log"),
            "ENSURE_TASK_WORKSPACE_PY": str(ENSURE_TASK_WORKSPACE),
        }

    def _write_task(self, name: str, payload: dict) -> Path:
        task_dir = self.tasks_root / name
        task_dir.mkdir(parents=True, exist_ok=True)
        task = {
            "id": name,
            "title": name,
            "project": "demo",
            "target_environment": "dev",
            "task_type": "development",
            "domain": "development",
            "priority": "medium",
            "claim_scope": ["dev-1"],
            "pool_entered_at": "2026-05-09T10:00:00+08:00",
            "execution_mode": "dev",
            "workspace_mode": "worktree",
            "target_branch": "integration",
            **payload,
        }
        (task_dir / "task.json").write_text(json.dumps(task, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (task_dir / "instruction.md").write_text("\n".join([
            f"# 任务：{task['title']}",
            "## 任务类型", str(task.get("task_type") or "development"),
            "## 目标", "完成任务",
            "## 任务边界", "按 scope 执行",
            "## 输入事实", "已有上下文",
            "## 约束", "遵守 write_scope",
            "## 交付物", "result.json",
            "## 验收标准", "任务完成",
            "## 下游动作", "review",
        ]) + "\n", encoding="utf-8")
        (task_dir / "transitions.jsonl").write_text("", encoding="utf-8")
        return task_dir

    def _confirm_claim_request(self, task_id: str) -> dict:
        task_dir = self.tasks_root / task_id
        completed = subprocess.run(
            [
                "bash",
                "-lc",
                f"source '{TASK_WATCHER}' && confirm_claim_request '{task_dir}' '{task_id}'",
            ],
            cwd=str(REPO_ROOT),
            env=self._watcher_env(),
            capture_output=True,
            text=True,
            check=True,
        )
        return json.loads(completed.stdout)

    def test_claim_writes_request_without_dispatching_task(self):
        target_dir = self._write_task("request-only-task", {
            "status": "pooled",
            "assigned_agent": "auto",
            "write_scope": ["src/base.txt"],
        })

        completed = subprocess.run(
            [str(CLAIM_SCRIPT), "request-only-task"],
            cwd=str(REPO_ROOT),
            env=self._env(),
            capture_output=True,
            text=True,
            check=True,
        )

        claim = json.loads(completed.stdout)
        task = json.loads((target_dir / "task.json").read_text(encoding="utf-8"))
        queued_claim = json.loads((target_dir / "claim.json").read_text(encoding="utf-8"))
        self.assertEqual(claim["claim_status"], "requested")
        self.assertEqual(task["status"], "pooled")
        self.assertEqual(task["assigned_agent"], "auto")
        self.assertEqual(queued_claim["agent"], "dev-1")

    def test_claim_allows_one_reserved_while_agent_has_one_working_task(self):
        self._write_task("working-task", {
            "status": "working",
            "assigned_agent": "dev-1",
            "write_scope": ["src/current"],
        })
        target_dir = self._write_task("next-task", {
            "status": "pooled",
            "assigned_agent": "auto",
            "write_scope": ["src/next"],
        })

        completed = subprocess.run(
            [str(CLAIM_SCRIPT), "next-task", "watcher auto-reserved while dev-1 is working"],
            cwd=str(REPO_ROOT),
            env=self._env(),
            capture_output=True,
            text=True,
            check=True,
        )

        claim = json.loads(completed.stdout)
        confirm = self._confirm_claim_request("next-task")
        task = json.loads((target_dir / "task.json").read_text(encoding="utf-8"))
        self.assertEqual(claim["claim_status"], "requested")
        self.assertEqual(task["status"], "dispatched")
        self.assertEqual(task["reserved_by"], "dev-1")
        self.assertEqual(task["pre_claim_assigned_agent"], "auto")
        self.assertEqual(confirm["agent"], "dev-1")

    def test_claim_blocks_second_reserved_task_for_same_agent(self):
        self._write_task("reserved-task", {
            "status": "dispatched",
            "assigned_agent": "dev-1",
            "write_scope": ["src/reserved"],
        })
        self._write_task("next-task", {
            "status": "pooled",
            "assigned_agent": "auto",
            "write_scope": ["src/next"],
        })

        completed = subprocess.run(
            [str(CLAIM_SCRIPT), "next-task"],
            cwd=str(REPO_ROOT),
            env=self._env(),
            capture_output=True,
            text=True,
        )

        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("reserved_limit", completed.stderr)

    def test_claim_records_dependencies_ready_at_when_dependencies_are_done(self):
        self._write_task("dep-task", {
            "status": "done",
            "assigned_agent": "dev-1",
            "write_scope": ["src/dep"],
        })
        target_dir = self._write_task("next-task", {
            "status": "pooled",
            "assigned_agent": "auto",
            "depends_on": ["dep-task"],
            "dependency_policy": "done_only",
            "write_scope": ["src/next"],
        })

        subprocess.run(
            [str(CLAIM_SCRIPT), "next-task"],
            cwd=str(REPO_ROOT),
            env=self._env(),
            capture_output=True,
            text=True,
            check=True,
        )

        self._confirm_claim_request("next-task")
        task = json.loads((target_dir / "task.json").read_text(encoding="utf-8"))
        self.assertIn("dependencies_ready_at", task)

    def test_claim_rejects_owner_approval_pending_task(self):
        self._write_task("owner-pending-task", {
            "status": "pooled",
            "assigned_agent": "auto",
            "write_scope": ["src/pending"],
            "owner_approval_required": True,
        })

        completed = subprocess.run(
            [str(CLAIM_SCRIPT), "owner-pending-task"],
            cwd=str(REPO_ROOT),
            env=self._env(),
            capture_output=True,
            text=True,
        )

        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("owner_approval_pending", completed.stderr)

    def test_claim_prepares_worktree_metadata_when_workspace_mode_enabled(self):
        target_dir = self._write_task("worktree-task", {
            "status": "pooled",
            "assigned_agent": "auto",
            "write_scope": ["src/base.txt"],
        })

        subprocess.run(
            [str(CLAIM_SCRIPT), "worktree-task"],
            cwd=str(REPO_ROOT),
            env=self._env(),
            capture_output=True,
            text=True,
            check=True,
        )

        confirm = self._confirm_claim_request("worktree-task")
        task = json.loads((target_dir / "task.json").read_text(encoding="utf-8"))
        self.assertEqual(task["workspace_status"], "prepared")
        self.assertTrue(Path(task["worktree_path"]).exists())
        self.assertIn("请在", confirm["dispatch_hint"])

    def test_concurrent_claims_only_allow_one_reserved_task(self):
        self._write_task("task-a", {
            "status": "pooled",
            "assigned_agent": "auto",
            "write_scope": ["src/a.txt"],
        })
        self._write_task("task-b", {
            "status": "pooled",
            "assigned_agent": "auto",
            "write_scope": ["src/b.txt"],
        })

        results: list[subprocess.CompletedProcess[str]] = []

        def run_claim(task_id: str) -> None:
            completed = subprocess.run(
                [str(CLAIM_SCRIPT), task_id],
                cwd=str(REPO_ROOT),
                env=self._env(),
                capture_output=True,
                text=True,
            )
            results.append(completed)

        threads = [threading.Thread(target=run_claim, args=(task_id,)) for task_id in ("task-a", "task-b")]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        successes = [item for item in results if item.returncode == 0]
        failures = [item for item in results if item.returncode != 0]
        self.assertEqual(len(successes), 1, results)
        self.assertEqual(len(failures), 1, results)
        self.assertIn("reserved_limit", failures[0].stderr)

    def test_auto_reserve_confirms_request_and_delivers_workspace_hint(self):
        self._write_task("working-task", {
            "status": "working",
            "assigned_agent": "dev-1",
            "write_scope": ["src/current"],
        })
        target_dir = self._write_task("next-task", {
            "status": "pooled",
            "assigned_agent": "auto",
            "write_scope": ["src/next"],
        })

        send_log = self.root / "send.log"
        send_script = self.scripts_root / "send-to-agent.sh"
        send_script.write_text(
            "#!/bin/bash\n"
            f"printf '%s' \"$2\" > '{send_log}'\n"
            "echo \"delivered to $1 (runtime=codex, attempt=1)\"\n",
            encoding="utf-8",
        )
        send_script.chmod(0o755)

        config = json.loads(self.config_path.read_text(encoding="utf-8"))
        config.setdefault("task_pool", {})["auto_reserve_while_working"] = True
        self.config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        subprocess.run(
            [
                "bash",
                "-lc",
                f"source '{TASK_WATCHER}' && auto_reserve_next_task_for_agent dev-1 'working sweep'",
            ],
            cwd=str(REPO_ROOT),
            env={
                **self._watcher_env(),
                "SEND_SCRIPT": str(send_script),
            },
            capture_output=True,
            text=True,
            check=True,
        )

        task = json.loads((target_dir / "task.json").read_text(encoding="utf-8"))
        message = send_log.read_text(encoding="utf-8")
        self.assertEqual(task["status"], "dispatched")
        self.assertEqual(task["reserved_by"], "dev-1")
        self.assertEqual(task["workspace_status"], "prepared")
        self.assertTrue(Path(task["worktree_path"]).exists())
        self.assertIn("当前任务完成前不要写该任务 ack", message)
        self.assertIn("请在", message)


if __name__ == "__main__":
    unittest.main()
