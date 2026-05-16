from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
CLAIM_SCRIPT = REPO_ROOT / "scripts" / "claim-task.sh"


class ClaimTaskReservedTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tmpdir.name)
        self.tasks_root = self.root / "tasks"
        self.dev_root = self.root / "dev"
        self.tasks_root.mkdir()
        self.dev_root.mkdir()
        self.config_path = self.root / "config.json"
        self.config_path.write_text(json.dumps({
            "agents": {"dev-1": {"role": "fullstack_dev"}},
            "projects": {"demo": {"dev_root": str(self.dev_root)}},
            "task_pool": {
                "default_working_limit": 1,
                "default_reserved_limit": 1,
                "default_claim_max_concurrency": 1,
            },
            "wip_limits": {"dev": 1},
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def tearDown(self):
        self.tmpdir.cleanup()

    def _env(self) -> dict[str, str]:
        return {
            **os.environ,
            "TASKS_ROOT": str(self.tasks_root),
            "CONFIG_PATH": str(self.config_path),
            "CLAIM_AGENT_ID": "dev-1",
        }

    def _write_task(self, name: str, payload: dict) -> Path:
        task_dir = self.tasks_root / name
        task_dir.mkdir(parents=True, exist_ok=True)
        (task_dir / "task.json").write_text(json.dumps({
            "id": name,
            "title": name,
            "project": "demo",
            "target_environment": "dev",
            "task_type": "development",
            "domain": "development",
            "priority": "medium",
            "claim_scope": ["dev-1"],
            "pool_entered_at": "2026-05-09T10:00:00+08:00",
            **payload,
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (task_dir / "transitions.jsonl").write_text("", encoding="utf-8")
        return task_dir

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
        task = json.loads((target_dir / "task.json").read_text(encoding="utf-8"))
        self.assertTrue(claim["reserved"])
        self.assertEqual(task["status"], "dispatched")
        self.assertEqual(task["reserved_by"], "dev-1")
        self.assertEqual(task["pre_claim_assigned_agent"], "auto")

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

        task = json.loads((target_dir / "task.json").read_text(encoding="utf-8"))
        self.assertIn("dependencies_ready_at", task)


if __name__ == "__main__":
    unittest.main()
