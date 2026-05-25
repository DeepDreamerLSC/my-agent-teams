from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
CREATE_SCRIPT = REPO_ROOT / "scripts" / "create-task.sh"


class CreateTaskQualityTemplateTests(unittest.TestCase):
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
            "domain_policies": {
                "development": {"default_reviewer": "review-1"},
                "quality": {"default_reviewer": "review-1"},
            },
            "defaults": {
                "task_level": "execution",
                "timeout_minutes": 30,
            },
            "orchestration": {
                "root_pm": "pm-chief",
                "integration_owner": "arch-1",
            },
            "task_pool": {
                "default_pool_timeout_minutes": 120,
            },
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def tearDown(self):
        self.tmpdir.cleanup()

    def _env(self) -> dict[str, str]:
        return {
            **os.environ,
            "WORKSPACE_ROOT": str(REPO_ROOT),
            "TASKS_DIR": str(self.tasks_root),
            "CONFIG_PATH": str(self.config_path),
            "STRICT_WRITE_SCOPE_CONFLICT": "0",
        }

    def _run_create(self, task_id: str, title: str, assigned_agent: str, domain: str, project: str, *extra: str):
        return subprocess.run(
            [str(CREATE_SCRIPT), task_id, title, assigned_agent, domain, project, *extra],
            cwd=str(REPO_ROOT),
            env=self._env(),
            capture_output=True,
            text=True,
        )

    def _load_task(self, task_id: str) -> dict:
        return json.loads((self.tasks_root / task_id / "task.json").read_text(encoding="utf-8"))

    def test_auto_development_task_claim_scope_uses_configured_dev_agents(self):
        config = json.loads(self.config_path.read_text(encoding="utf-8"))
        config["agents"]["dev-2"] = {"role": "fullstack_dev"}
        config["agents"]["dev-3"] = {"role": "fullstack_dev"}
        self.config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        completed = self._run_create(
            "自动开发认领范围",
            "自动开发认领范围",
            "auto",
            "development",
            "demo",
            "src/auto.py",
            "",
            "",
            "reviewer",
            "dev",
            "dev",
            "",
            "execution",
            "",
            "",
            "development",
            "false",
            "review",
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        task = self._load_task("自动开发认领范围")
        self.assertEqual(task["claim_policy"], "pull")
        self.assertEqual(task["claim_scope"], ["dev-1", "dev-2", "dev-3"])

    def test_development_defaults_to_review_and_qa(self):
        completed = self._run_create(
            "开发默认模板",
            "开发默认模板",
            "dev-1",
            "development",
            "demo",
            "src/app.py",
            "",
            "",
            "reviewer",
            "dev",
            "dev",
            "",
            "execution",
            "",
            "",
            "development",
            "false",
            "review",
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        task = self._load_task("开发默认模板")
        self.assertTrue(task["review_required"])
        self.assertTrue(task["test_required"])
        self.assertEqual(task["review_level"], "standard")
        self.assertEqual(task["quality_gate_mode"], "parallel")

    def test_design_defaults_to_review_only(self):
        completed = self._run_create(
            "设计默认模板",
            "设计默认模板",
            "arch-1",
            "development",
            "demo",
            "",
            "",
            "",
            "reviewer",
            "dev",
            "dev",
            "",
            "execution",
            "",
            "",
            "design",
            "true",
            "PM 决策",
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        task = self._load_task("设计默认模板")
        self.assertTrue(task["review_required"])
        self.assertFalse(task["test_required"])
        self.assertEqual(task["review_level"], "standard")
        self.assertEqual(task["quality_gate_mode"], "single")

    def test_verification_requires_explicit_main_gate(self):
        completed = self._run_create(
            "验证模板缺省",
            "验证模板缺省",
            "qa-1",
            "quality",
            "demo",
            "",
            "",
            "",
            "reviewer",
            "dev",
            "dev",
            "",
            "execution",
            "",
            "",
            "verification",
            "true",
            "PM 收口",
        )
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("verification tasks require an explicit main quality gate", completed.stderr)

    def test_verification_qa_only_template_passes(self):
        completed = self._run_create(
            "验证QA单闸门",
            "验证QA单闸门",
            "qa-1",
            "quality",
            "demo",
            "",
            "false",
            "true",
            "reviewer",
            "dev",
            "dev",
            "",
            "execution",
            "",
            "",
            "verification",
            "true",
            "PM 收口",
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        task = self._load_task("验证QA单闸门")
        self.assertFalse(task["review_required"])
        self.assertTrue(task["test_required"])
        self.assertEqual(task["review_level"], "skip")
        self.assertEqual(task["quality_gate_mode"], "single")

    def test_integration_defaults_to_serial_review_and_qa(self):
        completed = self._run_create(
            "集成默认模板",
            "集成默认模板",
            "arch-1",
            "development",
            "demo",
            "src/integration.md",
            "",
            "",
            "reviewer",
            "dev",
            "dev",
            "",
            "integration",
            "",
            "",
            "integration",
            "false",
            "PM 收口",
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        task = self._load_task("集成默认模板")
        self.assertTrue(task["review_required"])
        self.assertTrue(task["test_required"])
        self.assertEqual(task["review_level"], "standard")
        self.assertEqual(task["quality_gate_mode"], "serial")


if __name__ == "__main__":
    unittest.main()
