from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from control_plane.bootstrap import bootstrap_project, check_bootstrap, uninstall_project


class BootstrapTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tmpdir.name) / "external"
        self.root.mkdir()
        (self.root / ".git").mkdir()
        (self.root / "AGENTS.md").write_text("# Existing project rules\n", encoding="utf-8")

    def tearDown(self) -> None:
        self.tmpdir.cleanup()

    def test_preview_apply_check_and_uninstall_are_scoped(self) -> None:
        preview = bootstrap_project(
            repo_root=str(self.root),
            project_id="external-demo",
            control_plane_url="http://127.0.0.1:5001",
            apply=False,
        )
        self.assertEqual(preview["status"], "preview")
        self.assertEqual((self.root / "AGENTS.md").read_text(encoding="utf-8"), "# Existing project rules\n")
        applied = bootstrap_project(
            repo_root=str(self.root),
            project_id="external-demo",
            control_plane_url="http://127.0.0.1:5001",
            apply=True,
        )
        self.assertTrue(applied["ok"])
        checked = check_bootstrap(repo_root=str(self.root))
        self.assertTrue(checked["ok"])
        self.assertIn("Existing project rules", (self.root / "AGENTS.md").read_text(encoding="utf-8"))
        removed = uninstall_project(repo_root=str(self.root), apply=True)
        self.assertTrue(Path(removed["backup"]).exists())
        self.assertFalse((self.root / ".my-agent-teams" / "control-plane.json").exists())
        self.assertIn("Existing project rules", (self.root / "AGENTS.md").read_text(encoding="utf-8"))

    def test_conflicting_managed_block_is_not_overwritten(self) -> None:
        bootstrap_project(
            repo_root=str(self.root),
            project_id="other-project",
            control_plane_url="http://127.0.0.1:5001",
            apply=True,
        )
        result = bootstrap_project(
            repo_root=str(self.root),
            project_id="external-demo",
            control_plane_url="http://127.0.0.1:5001",
            apply=True,
        )
        self.assertFalse(result["ok"])
        self.assertIn("other-project", (self.root / "AGENTS.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
