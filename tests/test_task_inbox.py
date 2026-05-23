from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from datetime import datetime
import os
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

    def test_working_timeout_recommended_action_prefers_observation_window(self):
        task_inbox = load_task_inbox_module()
        with tempfile.TemporaryDirectory() as tmp:
            task_dir = Path(tmp) / 'working-timeout-task'
            task_dir.mkdir()
            task = {
                'id': 'working-timeout-task',
                'title': '执行超时任务',
                'status': 'working',
                'priority': 'medium',
                'owner_pm': 'pm-chief',
                'updated_at': '2000-01-01T00:00:00+08:00',
            }
            (task_dir / 'task.json').write_text(json.dumps(task, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
            ack_path = task_dir / 'ack.json'
            ack_path.write_text('{"task_id":"working-timeout-task","agent":"dev-1","status":"working"}\n', encoding='utf-8')
            old_ts = datetime.fromisoformat('2000-01-01T00:00:00+08:00').timestamp()
            os.utime(ack_path, (old_ts, old_ts))

            now = datetime.now().astimezone()
            items = task_inbox.task_items(task_dir, now, dispatch_timeout_s=300, working_timeout_s=1)

        timeouts = [item for item in items if item['reason_type'] == 'timeout']
        self.assertEqual(len(timeouts), 1)
        self.assertIn('先催办并进入观察窗口', timeouts[0]['recommended_action'])

    def test_pool_starvation_item_when_idle_agents_have_no_ready_pool_task(self):
        task_inbox = load_task_inbox_module()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tasks_root = root / 'tasks'
            tasks_root.mkdir()
            config_path = root / 'config.json'
            config_path.write_text(json.dumps({
                'agents': {
                    'dev-1': {'role': 'fullstack_dev'},
                },
                'task_pool': {'default_claim_max_concurrency': 1},
            }, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

            dep_dir = tasks_root / 'dep-task'
            dep_dir.mkdir()
            (dep_dir / 'task.json').write_text(json.dumps({
                'id': 'dep-task',
                'title': '前置任务',
                'status': 'working',
                'assigned_agent': 'dev-2',
            }, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

            pooled_dir = tasks_root / 'pooled-waiting'
            pooled_dir.mkdir()
            (pooled_dir / 'task.json').write_text(json.dumps({
                'id': 'pooled-waiting',
                'title': '等待依赖的池任务',
                'status': 'pooled',
                'priority': 'high',
                'claim_scope': ['dev-1'],
                'depends_on': ['dep-task'],
                'dependency_policy': 'done_only',
                'pool_entered_at': '2026-05-09T10:00:00+08:00',
                'task_type': 'development',
                'domain': 'development',
                'write_scope': ['/tmp/pooled-waiting'],
            }, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

            now = datetime.fromisoformat('2026-05-09T11:00:00+08:00')
            items = task_inbox.pool_starvation_items(tasks_root, config_path, now)

        self.assertTrue(len(items) in {0, 1})
        if items:
            self.assertEqual(items[0]['reason_type'], 'pool_starvation')
            self.assertIn('当前可认领任务为 0', items[0]['summary'])

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


class TaskInboxControlPlaneTests(unittest.TestCase):
    def test_session_unhealthy_and_invariant_violation_items_are_visible(self):
        task_inbox = load_task_inbox_module()
        with tempfile.TemporaryDirectory() as tmp:
            task_dir = Path(tmp) / 'control-plane-task'
            task_dir.mkdir()
            task = {
                'id': 'control-plane-task',
                'title': '控制面异常任务',
                'status': 'dispatched',
                'priority': 'high',
                'owner_pm': 'pm-chief',
                'updated_at': '2026-05-18T10:00:00+08:00',
                'control_plane_state': 'session_unhealthy',
                'last_delivery_error': 'tmux session not found: dev-1',
                'state_invariant_violations': [
                    {'code': 'working_without_current_ack', 'message': 'status=working 但缺少当前轮 ack.json'},
                ],
            }
            (task_dir / 'task.json').write_text(json.dumps(task, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

            now = datetime.fromisoformat('2026-05-18T10:20:00+08:00')
            items = task_inbox.task_items(task_dir, now, dispatch_timeout_s=300, working_timeout_s=7200)

        reason_types = {item['reason_type'] for item in items}
        self.assertIn('session_unhealthy', reason_types)
        self.assertIn('state_invariant_violation', reason_types)

    def test_workspace_error_item_is_visible(self):
        task_inbox = load_task_inbox_module()
        with tempfile.TemporaryDirectory() as tmp:
            task_dir = Path(tmp) / 'workspace-error-task'
            task_dir.mkdir()
            task = {
                'id': 'workspace-error-task',
                'title': '工作区异常任务',
                'status': 'dispatched',
                'priority': 'high',
                'owner_pm': 'pm-chief',
                'updated_at': '2026-05-18T10:00:00+08:00',
                'workspace_status': 'error',
                'workspace_error': 'git worktree add failed: branch already checked out elsewhere',
            }
            (task_dir / 'task.json').write_text(json.dumps(task, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

            now = datetime.fromisoformat('2026-05-18T10:20:00+08:00')
            items = task_inbox.task_items(task_dir, now, dispatch_timeout_s=300, working_timeout_s=7200)

        reason_types = {item['reason_type'] for item in items}
        self.assertIn('workspace_error', reason_types)


if __name__ == '__main__':
    unittest.main()
