from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
ARCHIVE_SCRIPT = REPO_ROOT / 'scripts' / 'archive-task.sh'


class ArchiveTaskScriptTests(unittest.TestCase):
    def test_archive_task_moves_done_task_and_updates_index(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tasks_root = root / 'tasks'
            task_dir = tasks_root / 'task-1'
            task_dir.mkdir(parents=True)
            (task_dir / 'task.json').write_text(json.dumps({
                'id': 'task-1',
                'title': '任务一',
                'status': 'done',
                'result_summary': 'finished',
            }, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
            (task_dir / 'instruction.md').write_text('demo', encoding='utf-8')
            (task_dir / 'transitions.jsonl').write_text('', encoding='utf-8')
            completed = subprocess.run(
                ['bash', str(ARCHIVE_SCRIPT), '--task-dir', str(task_dir)],
                cwd=str(REPO_ROOT),
                env={**__import__('os').environ, 'TASKS_ROOT': str(tasks_root), 'WORKSPACE_ROOT': str(root)},
                capture_output=True,
                text=True,
                check=True,
            )
            payload = json.loads(completed.stdout)
            archived_path = Path(payload['archive_path'])
            self.assertTrue(archived_path.exists())
            self.assertFalse(task_dir.exists())
            index_path = tasks_root / '_index' / 'archived-tasks.jsonl'
            self.assertTrue(index_path.exists())
            lines = [json.loads(line) for line in index_path.read_text(encoding='utf-8').splitlines() if line.strip()]
            self.assertEqual(lines[-1]['task_id'], 'task-1')
            archived_task = json.loads((archived_path / 'task.json').read_text(encoding='utf-8'))
            self.assertEqual(archived_task['status'], 'archived')


if __name__ == '__main__':
    unittest.main()
