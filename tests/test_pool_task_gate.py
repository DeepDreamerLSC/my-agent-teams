from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
POOL_SCRIPT = REPO_ROOT / "scripts" / "pool-task.sh"


class PoolTaskGateTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tmpdir.name)
        self.tasks_root = self.root / "tasks"
        self.tasks_root.mkdir()
        self.config_path = self.root / "config.json"
        self.config_path.write_text(json.dumps({
            "agents": {
                "dev-1": {"role": "fullstack_dev"},
                "dev-2": {"role": "fullstack_dev"},
                "qa-1": {"role": "qa"},
                "arch-1": {"role": "architect"},
            },
            "task_pool": {"default_claim_max_concurrency": 1},
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def tearDown(self):
        self.tmpdir.cleanup()

    def _env(self) -> dict[str, str]:
        return {
            **os.environ,
            "WORKSPACE_ROOT": str(REPO_ROOT),
            "CONFIG_PATH": str(self.config_path),
            "SEND_CHAT_SCRIPT": str(self.root / "missing-send-chat.sh"),
            "SEND_SCRIPT": str(self.root / "missing-send.sh"),
        }

    def _write_task(self, name: str, payload: dict) -> Path:
        task_dir = self.tasks_root / name
        task_dir.mkdir(parents=True, exist_ok=True)
        task = {
            "id": name,
            "title": name,
            "status": "pending",
            "assigned_agent": "auto",
            "project": "demo",
            "task_type": "development",
            "domain": "development",
            "execution_mode": "dev",
            "target_environment": "dev",
            "task_level": "execution",
            "review_level": "standard",
            "review_required": True,
            "test_required": False,
            "priority": "medium",
            "write_scope": ["src/default"],
            **payload,
        }
        (task_dir / "task.json").write_text(json.dumps(task, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (task_dir / "instruction.md").write_text("\n".join([
            f"# 任务：{task['title']}",
            "## 任务类型", str(task.get("task_type") or "development"),
            "## 目标", "完成任务",
            "## 任务边界", "按任务边界执行",
            "## 输入事实", "已有事实",
            "## 约束", "遵守约束",
            "## 交付物", "result.json",
            "## 验收标准", "满足要求",
            "## 下游动作", "review",
        ]) + "\n", encoding="utf-8")
        (task_dir / "transitions.jsonl").write_text("", encoding="utf-8")
        return task_dir

    def test_pool_task_blocks_missing_write_scope_for_write_task(self):
        task_dir = self._write_task("missing-write-scope", {
            "write_scope": [],
        })
        completed = subprocess.run(
            [str(POOL_SCRIPT), str(task_dir / "task.json")],
            cwd=str(REPO_ROOT),
            env=self._env(),
            capture_output=True,
            text=True,
        )

        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("write_scope_missing", completed.stderr)
        task = json.loads((task_dir / "task.json").read_text(encoding="utf-8"))
        self.assertEqual(task["status"], "pending")

    def test_pool_task_blocks_owner_approval_pending(self):
        task_dir = self._write_task("owner-approval-pending", {
            "owner_approval_required": True,
            "owner_approved_by": None,
            "owner_approved_at": None,
        })
        completed = subprocess.run(
            [str(POOL_SCRIPT), str(task_dir / "task.json")],
            cwd=str(REPO_ROOT),
            env=self._env(),
            capture_output=True,
            text=True,
        )

        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("owner_approval_pending", completed.stderr)

    def test_pool_task_allows_read_only_verification_without_write_scope(self):
        task_dir = self._write_task("verify-no-scope", {
            "task_type": "verification",
            "domain": "quality",
            "read_only": True,
            "review_level": "skip",
            "review_required": False,
            "test_required": True,
            "write_scope": [],
        })
        completed = subprocess.run(
            [str(POOL_SCRIPT), str(task_dir / "task.json")],
            cwd=str(REPO_ROOT),
            env=self._env(),
            capture_output=True,
            text=True,
            check=True,
        )

        self.assertIn("pooled verify-no-scope", completed.stdout)
        task = json.loads((task_dir / "task.json").read_text(encoding="utf-8"))
        self.assertEqual(task["status"], "pooled")
        self.assertEqual(task["claim_scope"], ["qa-1"])


if __name__ == "__main__":
    unittest.main()
