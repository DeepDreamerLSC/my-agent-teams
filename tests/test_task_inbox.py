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

    def test_loads_governance_items_from_generated_file(self):
        task_inbox = load_task_inbox_module()
        with tempfile.TemporaryDirectory() as tmp:
            governance_path = Path(tmp) / 'pm-inbox-governance.json'
            governance_path.write_text(json.dumps([
                {
                    'item_id': 'task-1:invalid_timeline',
                    'task_id': 'task-1',
                    'title': '任务一',
                    'reason_type': 'invalid_timeline',
                    'severity': 'L2',
                    'priority': 'high',
                    'status': 'ready_for_merge',
                    'merge_gate_state': 'review_pending',
                    'summary': '阶段时间倒挂',
                    'recommended_action': '修正时间线',
                    'owner': 'pm-chief',
                    'first_seen_at': '2026-05-09T11:00:00+08:00',
                    'last_seen_at': '2026-05-09T11:00:00+08:00',
                    'age_minutes': 5,
                    'links': {'task_dir': '/tmp/task-1', 'timeline': 'chat/tasks/task-1.jsonl'},
                }
            ], ensure_ascii=False), encoding='utf-8')

            items = task_inbox.load_governance_items(governance_path)

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]['reason_type'], 'invalid_timeline')
        self.assertEqual(items[0]['summary'], '阶段时间倒挂')

class TaskInboxStaleReviewTests(unittest.TestCase):
    def test_ready_for_merge_with_stale_rejected_review_is_not_pm_blocked(self):
        task_inbox = load_task_inbox_module()
        with tempfile.TemporaryDirectory() as tmp:
            task_dir = Path(tmp) / 'stale-review-task'
            task_dir.mkdir()
            task = {
                'id': 'stale-review-task',
                'title': '旧审查后新提交',
                'status': 'ready_for_merge',
                'priority': 'medium',
                'owner_pm': 'pm-chief',
                'merge_gate_state': 'review_rejected',
                'rework_reason': 'review',
                'review_required': True,
                'reviewer': 'review-1',
                'execution_round': 2,
                'created_at': '2026-05-09T10:00:00+08:00',
                'updated_at': '2026-05-09T10:30:00+08:00',
            }
            (task_dir / 'task.json').write_text(json.dumps(task, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
            (task_dir / 'result.json').write_text(json.dumps({
                'task_id': 'stale-review-task',
                'agent': 'dev-1',
                'status': 'success',
                'round': 2,
                'summary': '补修后提交',
            }, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
            (task_dir / 'review.json').write_text(json.dumps({
                'task_id': 'stale-review-task',
                'reviewer': 'review-1',
                'status': 'request_changes',
                'round': 1,
                'summary': '旧审查',
            }, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

            now = datetime.fromisoformat('2026-05-09T11:00:00+08:00')
            items = task_inbox.task_items(task_dir, now, dispatch_timeout_s=300, working_timeout_s=7200)

        self.assertFalse([item for item in items if item['reason_type'] == 'blocked'])


if __name__ == '__main__':
    unittest.main()
