from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
INBOX_SCRIPT = REPO_ROOT / 'scripts' / 'task-inbox.py'


def load_task_inbox_module():
    spec = importlib.util.spec_from_file_location('task_inbox', INBOX_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class TaskInboxTests(unittest.TestCase):
    def test_review_deadline_timeout_does_not_wait_for_default_window(self):
        task_inbox = load_task_inbox_module()
        with tempfile.TemporaryDirectory() as tmp:
            task_dir = Path(tmp) / 'deadline-review-task'
            task_dir.mkdir()
            task = {
                'id': 'deadline-review-task',
                'title': '审查 deadline 到期任务',
                'status': 'ready_for_merge',
                'priority': 'medium',
                'owner_pm': 'pm-chief',
                'merge_gate_state': 'review_pending',
                'updated_at': '2026-05-09T10:50:00+08:00',
                'last_gate_decision_at': '2026-05-09T10:50:00+08:00',
                'review_deadline': '2026-05-09T10:55:00+08:00',
                'review_required': True,
                'reviewer': 'review-1',
                'created_at': '2026-05-09T10:00:00+08:00',
                'task_type': 'development',
                'domain': 'development',
                'write_scope': [],
            }
            (task_dir / 'task.json').write_text(json.dumps(task, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

            now = datetime.fromisoformat('2026-05-09T11:00:00+08:00')
            items = task_inbox.task_items(task_dir, now, dispatch_timeout_s=300, working_timeout_s=7200)

        timeouts = [item for item in items if item['reason_type'] == 'timeout']
        self.assertEqual(len(timeouts), 1)
        self.assertEqual(timeouts[0]['task_id'], 'deadline-review-task')
        self.assertIn('review_deadline 已过', timeouts[0]['summary'])


if __name__ == '__main__':
    unittest.main()
