from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DISPATCH_SCRIPT = REPO_ROOT / "scripts" / "dispatch-task.sh"


def _instruction_text() -> str:
    return "\n".join([
        "# 任务：直派保护测试",
        "## 任务类型",
        "design",
        "## 目标",
        "确认方案",
        "## 任务边界",
        "只读分析",
        "## 输入事实",
        "已有上下文",
        "## 约束",
        "不写业务代码",
        "## 交付物",
        "result.json",
        "## 验收标准",
        "输出摘要",
        "## 下游动作",
        "PM 决策",
    ])


class DispatchTaskTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tmpdir.name)
        self.dev_root = self.root / "dev"
        self.prod_root = self.root / "prod"
        self.tasks_root = self.root / "tasks"
        self.dev_root.mkdir()
        self.prod_root.mkdir()
        self.tasks_root.mkdir()
        self.config_path = self.root / "config.json"
        self.config_path.write_text(json.dumps({
            "agents": {
                "dev-1": {"role": "fullstack_dev"},
                "qa-1": {"role": "qa"},
                "review-1": {"role": "reviewer"},
                "arch-1": {"role": "architect"},
            },
            "projects": {
                "demo": {
                    "dev_root": str(self.dev_root),
                    "prod_root": str(self.prod_root),
                },
            },
            "wip_limits": {"dev": 2},
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        self.task_dir = self.tasks_root / "pull-task"
        self.task_dir.mkdir()
        self.task_path = self.task_dir / "task.json"
        self._write_task()
        (self.task_dir / "instruction.md").write_text(_instruction_text(), encoding="utf-8")
        (self.task_dir / "transitions.jsonl").write_text("", encoding="utf-8")

    def tearDown(self):
        self.tmpdir.cleanup()

    def _write_task(self) -> None:
        self.task_path.write_text(json.dumps({
            "id": "pull-task",
            "title": "直派保护测试",
            "status": "pending",
            "project": "demo",
            "domain": "development",
            "assigned_agent": "dev-1",
            "execution_mode": "dev",
            "target_environment": "dev",
            "task_type": "design",
            "read_only": True,
            "write_scope": [],
            "claim_policy": "pull",
            "priority": "medium",
            "review_required": True,
            "review_level": "standard",
            "reviewer": "review-1",
            "downstream_action": "PM 决策",
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def _env(self, **overrides: str) -> dict[str, str]:
        env = {
            **os.environ,
            "CONFIG_PATH": str(self.config_path),
            "SEND_SCRIPT": str(self.root / "missing-send-to-agent.sh"),
            "SEND_CHAT_SCRIPT": str(self.root / "missing-send-chat.sh"),
        }
        env.update(overrides)
        return env

    def _init_git_repo(self, path: Path) -> None:
        subprocess.run(["git", "init", "-b", "main"], cwd=str(path), check=True, capture_output=True, text=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=str(path), check=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=str(path), check=True)
        (path / "src").mkdir(exist_ok=True)
        (path / "src" / "app.py").write_text("print('hello')\n", encoding="utf-8")
        subprocess.run(["git", "add", "."], cwd=str(path), check=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=str(path), check=True, capture_output=True, text=True)

    def test_claim_policy_pull_rejects_direct_dispatch_without_force(self):
        completed = subprocess.run(
            [str(DISPATCH_SCRIPT), str(self.task_path)],
            cwd=str(REPO_ROOT),
            env=self._env(),
            capture_output=True,
            text=True,
        )

        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("claim_policy=pull", completed.stderr)
        task = json.loads(self.task_path.read_text(encoding="utf-8"))
        self.assertEqual(task["status"], "pending")

    def test_force_direct_dispatch_records_override_reason(self):
        completed = subprocess.run(
            [str(DISPATCH_SCRIPT), str(self.task_path)],
            cwd=str(REPO_ROOT),
            env=self._env(FORCE_DIRECT_DISPATCH="1", DIRECT_DISPATCH_REASON="PM 确认紧急直派"),
            capture_output=True,
            text=True,
            check=True,
        )

        self.assertIn("dispatched pull-task", completed.stdout)
        task = json.loads(self.task_path.read_text(encoding="utf-8"))
        self.assertEqual(task["status"], "dispatched")
        transitions = [
            json.loads(line)
            for line in (self.task_dir / "transitions.jsonl").read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        self.assertEqual(transitions[-1]["to"], "dispatched")
        self.assertIn("FORCE_DIRECT_DISPATCH", transitions[-1]["reason"])
        self.assertIn("PM 确认紧急直派", transitions[-1]["reason"])

    def test_dispatch_rejects_verification_task_with_both_review_and_test(self):
        self.task_path.write_text(json.dumps({
            "id": "verification-task",
            "title": "验证任务",
            "status": "pending",
            "project": "demo",
            "domain": "quality",
            "assigned_agent": "qa-1",
            "execution_mode": "dev",
            "target_environment": "dev",
            "task_type": "verification",
            "read_only": True,
            "write_scope": [],
            "claim_policy": "push",
            "priority": "medium",
            "review_required": True,
            "test_required": True,
            "review_level": "standard",
            "reviewer": "review-1",
            "downstream_action": "PM 收口",
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (self.task_dir / "instruction.md").write_text("\n".join([
            "# 任务：验证任务",
            "## 任务类型",
            "verification",
            "## 目标",
            "完成验证",
            "## 任务边界",
            "只输出验证工件",
            "## 输入事实",
            "已有上下文",
            "## 约束",
            "不改业务代码",
            "## 交付物",
            "verify.json",
            "## 验收标准",
            "输出验证结论",
            "## 下游动作",
            "PM 收口",
        ]), encoding="utf-8")

        completed = subprocess.run(
            [str(DISPATCH_SCRIPT), str(self.task_path)],
            cwd=str(REPO_ROOT),
            env=self._env(FORCE_DIRECT_DISPATCH="1", DIRECT_DISPATCH_REASON="验证测试"),
            capture_output=True,
            text=True,
        )

        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("verification tasks require exactly one", completed.stderr)

    def test_dispatch_prepares_task_worktree_when_enabled(self):
        self._init_git_repo(self.dev_root)
        self.config_path.write_text(json.dumps({
            "agents": {
                "dev-1": {"role": "fullstack_dev"},
                "review-1": {"role": "reviewer"},
            },
            "projects": {
                "demo": {
                    "dev_root": str(self.dev_root),
                    "prod_root": str(self.prod_root),
                },
            },
            "defaults": {
                "workspace_mode": "worktree",
                "target_branch": "integration",
            },
            "workspace_management": {
                "worktree_root": str(self.root / "worktrees"),
            },
            "wip_limits": {"dev": 2},
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        self.task_path.write_text(json.dumps({
            "id": "worktree-task",
            "title": "worktree 任务",
            "status": "pending",
            "project": "demo",
            "domain": "development",
            "assigned_agent": "dev-1",
            "execution_mode": "dev",
            "target_environment": "dev",
            "task_type": "development",
            "read_only": False,
            "write_scope": ["src/app.py"],
            "claim_policy": "push",
            "priority": "medium",
            "review_required": True,
            "review_level": "standard",
            "reviewer": "review-1",
            "workspace_mode": "worktree",
            "target_branch": "integration",
            "downstream_action": "review",
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (self.task_dir / "instruction.md").write_text("\n".join([
            "# 任务：worktree 任务",
            "## 任务类型",
            "development",
            "## 目标",
            "实现变更",
            "## 任务边界",
            "只改 src/app.py",
            "## 输入事实",
            "已有代码",
            "## 约束",
            "按 scope 修改",
            "## 交付物",
            "result.json",
            "## 验收标准",
            "通过",
            "## 下游动作",
            "review",
        ]), encoding="utf-8")

        completed = subprocess.run(
            [str(DISPATCH_SCRIPT), str(self.task_path)],
            cwd=str(REPO_ROOT),
            env=self._env(),
            capture_output=True,
            text=True,
            check=True,
        )

        self.assertIn("dispatched worktree-task", completed.stdout)
        task = json.loads(self.task_path.read_text(encoding="utf-8"))
        self.assertEqual(task["workspace_status"], "prepared")
        self.assertTrue(Path(task["worktree_path"]).exists())
        self.assertTrue(str(task["workspace_branch"]).startswith("task/"))


if __name__ == "__main__":
    unittest.main()
