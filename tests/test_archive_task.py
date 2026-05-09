from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from dashboard.db import connect_db, upsert_task

REPO_ROOT = Path(__file__).resolve().parents[1]
ARCHIVE_SCRIPT = REPO_ROOT / 'scripts' / 'archive-task.sh'


class ArchiveTaskScriptTests(unittest.TestCase):
    def test_archive_task_moves_done_task_and_updates_index(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tasks_root = root / 'tasks'
            task_dir = tasks_root / 'task-1'
            task_dir.mkdir(parents=True)
            db_path = root / 'task-board.sqlite3'
            conn = connect_db(str(db_path), initialize=True)
            with conn:
                upsert_task(conn, {
                    'task_id': 'task-1',
                    'title': '任务一',
                    'project': 'my-agent-teams',
                    'domain': 'development',
                    'assigned_agent': 'dev-1',
                    'reviewer': None,
                    'owner_pm': 'pm-chief',
                    'integration_owner': None,
                    'parent_task_id': None,
                    'root_request_id': 'task-1',
                    'review_required': 0,
                    'test_required': 0,
                    'target_environment': 'dev',
                    'priority': 'medium',
                    'review_level': 'skip',
                    'current_status': 'done',
                    'board_status': 'done',
                    'merge_gate_state': 'closed',
                    'rework_reason': None,
                    'last_gate_actor': 'pm-chief',
                    'last_gate_decision_at': '2026-05-09T10:00:00+08:00',
                    'auto_close_policy': 'manual_after_review',
                    'created_at': '2026-05-09T09:00:00+08:00',
                    'dispatched_at': '2026-05-09T09:05:00+08:00',
                    'ack_at': '2026-05-09T09:10:00+08:00',
                    'completed_at': '2026-05-09T09:20:00+08:00',
                    'review_completed_at': None,
                    'verify_completed_at': None,
                    'current_status_at': '2026-05-09T09:20:00+08:00',
                    'ack_agent': 'dev-1',
                    'result_agent': 'dev-1',
                    'lease_acquired_at': None,
                    'updated_at': '2026-05-09T09:20:00+08:00',
                    'summary': 'finished',
                    'review_state': None,
                    'verify_ok': None,
                    'task_dir': str(task_dir),
                    'task_json_path': str(task_dir / 'task.json'),
                    'write_scope_json': '[]',
                    'artifacts_json': '[]',
                    'last_ingest_source': 'test',
                    'last_synced_at': '2026-05-09T09:20:00+08:00',
                })
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
                env={**__import__('os').environ, 'TASKS_ROOT': str(tasks_root), 'WORKSPACE_ROOT': str(root), 'TASK_BOARD_DB_PATH': str(db_path), 'BOARD_SYNC_SCRIPT': str(REPO_ROOT / 'scripts' / 'task-board-sync.py')},
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
            row = conn.execute("SELECT current_status, task_dir FROM tasks WHERE task_id = 'task-1'").fetchone()
            self.assertEqual(row['current_status'], 'archived')
            self.assertEqual(row['task_dir'], str(archived_path))
            conn.close()

    def test_archive_task_degrades_when_dashboard_sync_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tasks_root = root / 'tasks'
            task_dir = tasks_root / 'task-2'
            task_dir.mkdir(parents=True)
            (task_dir / 'task.json').write_text(json.dumps({
                'id': 'task-2',
                'title': '任务二',
                'status': 'done',
                'result_summary': 'finished',
            }, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
            (task_dir / 'instruction.md').write_text('demo', encoding='utf-8')
            (task_dir / 'transitions.jsonl').write_text('', encoding='utf-8')
            bad_sync = root / 'bad-sync.py'
            bad_sync.write_text('import sys; raise SystemExit(1)\n', encoding='utf-8')
            completed = subprocess.run(
                ['bash', str(ARCHIVE_SCRIPT), '--task-dir', str(task_dir)],
                cwd=str(REPO_ROOT),
                env={**__import__('os').environ, 'TASKS_ROOT': str(tasks_root), 'WORKSPACE_ROOT': str(root), 'BOARD_SYNC_SCRIPT': str(bad_sync)},
                capture_output=True,
                text=True,
                check=True,
            )
            payload = json.loads(completed.stdout)
            self.assertTrue(payload['warning'])
            archived_path = Path(payload['archive_path'])
            self.assertTrue(archived_path.exists())
            index_path = tasks_root / '_index' / 'archived-tasks.jsonl'
            self.assertTrue(index_path.exists())


if __name__ == '__main__':
    unittest.main()
