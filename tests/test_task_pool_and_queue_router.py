from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
POOL_ROUTER = REPO_ROOT / 'scripts' / 'task-pool-router.py'
QUEUE_ROUTER = REPO_ROOT / 'scripts' / 'task-queue-router.py'
POOL_VIEW = REPO_ROOT / 'scripts' / 'task-pool-view.py'


class TaskPoolAndQueueRouterTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        root = Path(self.tmpdir.name)
        self.tasks_root = root / 'tasks'
        self.tasks_root.mkdir()
        self.config = root / 'config.json'
        self.config.write_text(json.dumps({
            'agents': {
                'dev-1': {'role': 'fullstack_dev'},
                'dev-2': {'role': 'fullstack_dev'},
                'review-1': {'role': 'reviewer'},
                'qa-1': {'role': 'qa'},
            },
            'task_pool': {'default_claim_max_concurrency': 1},
            'wip_limits': {'dev': 1, 'reviewer': 2, 'qa': 2},
        }, ensure_ascii=False, indent=2), encoding='utf-8')
        self._write_task('pooled-a', {
            'id': 'pooled-a', 'title': '池任务A', 'status': 'pooled', 'priority': 'high',
            'claim_scope': ['dev-1'], 'pool_entered_at': '2026-05-09T10:00:00+08:00',
            'task_type': 'development', 'domain': 'development', 'write_scope': ['/tmp/a'],
        })
        self._write_task('review-task', {
            'id': 'review-task', 'title': '待审查', 'status': 'ready_for_merge', 'priority': 'medium',
            'reviewer': 'review-1', 'review_required': True, 'test_required': True,
            'merge_gate_state': 'review_pending', 'updated_at': '2026-05-09T10:00:00+08:00',
        })
        self._write_task('qa-task', {
            'id': 'qa-task', 'title': '待QA', 'status': 'ready_for_merge', 'priority': 'medium',
            'test_required': True, 'merge_gate_state': 'qa_pending', 'last_gate_decision_at': '2026-05-09T10:05:00+08:00',
        })
        self._write_task('quality-task', {
            'id': 'quality-task', 'title': '并行质控', 'status': 'ready_for_merge', 'priority': 'low',
            'reviewer': 'review-1', 'review_required': True, 'test_required': True,
            'quality_gate_mode': 'parallel', 'merge_gate_state': 'quality_pending',
            'updated_at': '2026-05-09T10:06:00+08:00',
        })

    def tearDown(self):
        self.tmpdir.cleanup()

    def _write_task(self, name: str, payload: dict) -> None:
        task_dir = self.tasks_root / name
        task_dir.mkdir(parents=True, exist_ok=True)
        (task_dir / 'task.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        task_type = payload.get('task_type') or 'development'
        (task_dir / 'instruction.md').write_text('\n'.join([
            f'# 任务：{payload.get("title") or name}',
            '## 任务类型', str(task_type),
            '## 目标', '完成任务',
            '## 任务边界', '按指令执行',
            '## 输入事实', '已有上下文',
            '## 约束', '仅在允许范围内修改',
            '## 交付物', 'result.json',
            '## 验收标准', '满足任务要求',
            '## 下游动作', 'review',
        ]) + '\n', encoding='utf-8')

    def _write_working_busy_task(self) -> None:
        self._write_task('working-a', {
            'id': 'working-a', 'title': '当前执行', 'status': 'working',
            'assigned_agent': 'dev-1', 'task_type': 'development', 'domain': 'development',
            'write_scope': ['/tmp/y'],
        })

    def test_pool_view_and_router_expose_working_busy_fields(self):
        self._write_working_busy_task()
        view_completed = subprocess.run(
            ['python3', str(POOL_VIEW), '--tasks-root', str(self.tasks_root), '--config', str(self.config), '--json'],
            cwd=str(REPO_ROOT), capture_output=True, text=True, check=True,
        )
        view_payload = json.loads(view_completed.stdout)
        pooled_row = next(item for item in view_payload if item['task_id'] == 'pooled-a')
        agent_view = next(item for item in pooled_row['by_agent'] if item['agent_id'] == 'dev-1')
        self.assertEqual(agent_view['busy_level'], 'hard_busy')
        self.assertEqual(agent_view['busy_primary_reason'], 'working:working-a')
        self.assertEqual(agent_view['busy_reason_codes'], ['working:working-a'])
        self.assertEqual(agent_view['busy_execute_route'], 'queue_only')
        self.assertEqual(agent_view['busy_remind_route'], 'queue_only')
        self.assertEqual(agent_view['busy_preheat_route'], 'queue_only')
        self.assertTrue(agent_view['busy_queue_only'])

        router_completed = subprocess.run(
            ['python3', str(POOL_ROUTER), '--tasks-root', str(self.tasks_root), '--config', str(self.config), '--agent', 'dev-1', '--json'],
            cwd=str(REPO_ROOT), capture_output=True, text=True, check=True,
        )
        router_payload = json.loads(router_completed.stdout)
        self.assertEqual(router_payload['next_task_id'], 'pooled-a')
        self.assertEqual(router_payload['next_task_busy_level'], 'hard_busy')
        self.assertEqual(router_payload['next_task_busy_reason_codes'], ['working:working-a'])
        self.assertEqual(router_payload['next_task_busy_diagnostic']['busy_level'], 'hard_busy')
        self.assertEqual(router_payload['next_task_busy_diagnostic']['busy_reason_codes'], ['working:working-a'])
        self.assertEqual(router_payload['next_task_delivery_route'], 'queue_only')
        self.assertEqual(router_payload['next_task_remind_route'], 'queue_only')
        self.assertEqual(router_payload['next_task_preheat_route'], 'queue_only')

    def test_pool_view_marks_no_progress_requeue_cooldown_for_same_agent(self):
        self._write_task('cooldown-task', {
            'id': 'cooldown-task', 'title': '回池冷却', 'status': 'pooled', 'priority': 'high',
            'claim_scope': ['dev-1'], 'pool_entered_at': '2026-05-09T10:00:00+08:00',
            'task_type': 'development', 'domain': 'development', 'write_scope': ['/tmp/cooldown'],
            'last_no_progress_repool_agent': 'dev-1',
            'no_progress_repool_until': '2099-01-01T00:00:00+08:00',
        })
        completed = subprocess.run(
            ['python3', str(POOL_VIEW), '--tasks-root', str(self.tasks_root), '--config', str(self.config), '--json'],
            cwd=str(REPO_ROOT), capture_output=True, text=True, check=True,
        )
        payload = json.loads(completed.stdout)
        row = next(item for item in payload if item['task_id'] == 'cooldown-task')
        agent_view = next(item for item in row['by_agent'] if item['agent_id'] == 'dev-1')
        self.assertFalse(agent_view['can_claim'])
        self.assertIn('no_progress_cooldown_until:', agent_view['reasons'][0])
        self.assertEqual(row['gate_stage'], 'claim_cooldown')
        self.assertEqual(row['eligible_agents'], [])

    def test_pool_router_selects_next_task_for_agent(self):
        completed = subprocess.run(
            ['python3', str(POOL_ROUTER), '--tasks-root', str(self.tasks_root), '--config', str(self.config), '--agent', 'dev-1', '--next'],
            cwd=str(REPO_ROOT), capture_output=True, text=True, check=True,
        )
        self.assertEqual(completed.stdout.strip(), 'pooled-a')

    def test_pool_router_can_reserve_next_task_for_agent_with_working_slot_full(self):
        self._write_task('working-dev-1', {
            'id': 'working-dev-1', 'title': '当前执行', 'status': 'working',
            'assigned_agent': 'dev-1', 'task_type': 'development', 'domain': 'development',
            'write_scope': ['/tmp/current'],
        })
        completed = subprocess.run(
            ['python3', str(POOL_ROUTER), '--tasks-root', str(self.tasks_root), '--config', str(self.config), '--agent', 'dev-1', '--json'],
            cwd=str(REPO_ROOT), capture_output=True, text=True, check=True,
        )
        payload = json.loads(completed.stdout)
        self.assertEqual(payload['next_task_id'], 'pooled-a')
        self.assertEqual(payload['next_task']['eligible_agents'], ['dev-1'])

    def test_queue_router_selects_review_and_qa_candidates(self):
        review = subprocess.run(
            ['python3', str(QUEUE_ROUTER), '--tasks-root', str(self.tasks_root), '--queue', 'review', '--agent', 'review-1', '--next'],
            cwd=str(REPO_ROOT), capture_output=True, text=True, check=True,
        )
        qa = subprocess.run(
            ['python3', str(QUEUE_ROUTER), '--tasks-root', str(self.tasks_root), '--queue', 'qa', '--agent', 'qa-1', '--next'],
            cwd=str(REPO_ROOT), capture_output=True, text=True, check=True,
        )
        self.assertEqual(review.stdout.strip(), 'review-task')
        self.assertEqual(qa.stdout.strip(), 'qa-task')

    def test_queue_router_quality_pending_is_visible_to_both_review_and_qa(self):
        review = subprocess.run(
            ['python3', str(QUEUE_ROUTER), '--tasks-root', str(self.tasks_root), '--queue', 'review', '--agent', 'review-1', '--json'],
            cwd=str(REPO_ROOT), capture_output=True, text=True, check=True,
        )
        qa = subprocess.run(
            ['python3', str(QUEUE_ROUTER), '--tasks-root', str(self.tasks_root), '--queue', 'qa', '--agent', 'qa-1', '--json'],
            cwd=str(REPO_ROOT), capture_output=True, text=True, check=True,
        )
        review_payload = json.loads(review.stdout)
        qa_payload = json.loads(qa.stdout)
        self.assertIn('quality-task', [row['task_id'] for row in review_payload['rows']])
        self.assertIn('quality-task', [row['task_id'] for row in qa_payload['rows']])


    def test_pool_view_does_not_mark_qa_idle_for_pending_qa_gate(self):
        self._write_task('qa-pool', {
            'id': 'qa-pool', 'title': '待QA池任务', 'status': 'pooled', 'priority': 'medium',
            'claim_scope': ['qa-1'], 'pool_entered_at': '2026-05-09T10:00:00+08:00',
            'task_type': 'verification', 'domain': 'quality', 'write_scope': ['/tmp/qa'],
        })
        self._write_task('qa-gated', {
            'id': 'qa-gated', 'title': '待QA任务', 'status': 'ready_for_merge', 'priority': 'medium',
            'assigned_agent': 'dev-2', 'claim_scope': ['dev-2'], 'task_type': 'development', 'domain': 'development',
            'review_required': True, 'test_required': True, 'review_gate_state': 'approved', 'qa_gate_state': 'pending',
            'merge_gate_state': 'qa_pending', 'write_scope': ['/tmp/qa-gated'],
        })
        completed = subprocess.run(
            ['python3', str(POOL_VIEW), '--tasks-root', str(self.tasks_root), '--config', str(self.config), '--json'],
            cwd=str(REPO_ROOT), capture_output=True, text=True, check=True,
        )
        payload = json.loads(completed.stdout)
        pooled_row = next(item for item in payload if item['task_id'] == 'qa-pool')
        agent_view = next(item for item in pooled_row['by_agent'] if item['agent_id'] == 'qa-1')
        self.assertEqual(agent_view['busy_level'], 'idle')
        self.assertEqual(agent_view['busy_reason_codes'], [])
        self.assertTrue(agent_view['busy_can_direct_execute'])
        self.assertEqual(agent_view['busy_execute_route'], 'direct')

    def test_queue_router_qa_queue_ignores_dev_only_claim_scope(self):
        self._write_task('qa-gated', {
            'id': 'qa-gated', 'title': '待QA任务', 'status': 'ready_for_merge', 'priority': 'medium',
            'assigned_agent': 'dev-2', 'claim_scope': ['dev-2'], 'task_type': 'development', 'domain': 'development',
            'review_required': True, 'test_required': True, 'review_gate_state': 'approved', 'qa_gate_state': 'pending',
            'merge_gate_state': 'qa_pending', 'write_scope': ['/tmp/qa-gated'],
        })
        completed = subprocess.run(
            ['python3', str(QUEUE_ROUTER), '--tasks-root', str(self.tasks_root), '--config', str(self.config), '--queue', 'qa', '--agent', 'qa-1', '--json'],
            cwd=str(REPO_ROOT), capture_output=True, text=True, check=True,
        )
        payload = json.loads(completed.stdout)
        self.assertEqual(payload['next_task_id'], 'qa-gated')
        self.assertIn('qa-gated', [row['task_id'] for row in payload['rows']])

    def test_queue_router_skips_review_task_with_terminal_review_artifact(self):
        review_dir = self.tasks_root / 'review-task'
        (review_dir / 'review.json').write_text(
            json.dumps({
                'task_id': 'review-task',
                'reviewer': 'review-1',
                'status': 'request_changes',
                'summary': 'needs rework',
            }, ensure_ascii=False, indent=2) + '\n',
            encoding='utf-8',
        )
        completed = subprocess.run(
            ['python3', str(QUEUE_ROUTER), '--tasks-root', str(self.tasks_root), '--queue', 'review', '--agent', 'review-1', '--json'],
            cwd=str(REPO_ROOT), capture_output=True, text=True, check=True,
        )
        payload = json.loads(completed.stdout)
        self.assertEqual(payload['next_task_id'], 'quality-task')
        self.assertNotIn('review-task', [row['task_id'] for row in payload['rows']])

    def test_queue_router_keeps_review_task_when_terminal_review_is_stale_after_new_result(self):
        review_dir = self.tasks_root / 'review-task'
        review_json = review_dir / 'review.json'
        result_json = review_dir / 'result.json'
        review_json.write_text(
            json.dumps({
                'task_id': 'review-task',
                'reviewer': 'review-1',
                'status': 'request_changes',
                'summary': 'old review',
            }, ensure_ascii=False, indent=2) + '\n',
            encoding='utf-8',
        )
        result_json.write_text(
            json.dumps({
                'task_id': 'review-task',
                'agent': 'dev-1',
                'status': 'success',
                'summary': 'new result after review',
            }, ensure_ascii=False, indent=2) + '\n',
            encoding='utf-8',
        )
        old_time = 1_700_000_000
        new_time = old_time + 60
        import os
        os.utime(review_json, (old_time, old_time))
        os.utime(result_json, (new_time, new_time))

        completed = subprocess.run(
            ['python3', str(QUEUE_ROUTER), '--tasks-root', str(self.tasks_root), '--queue', 'review', '--agent', 'review-1', '--json'],
            cwd=str(REPO_ROOT), capture_output=True, text=True, check=True,
        )
        payload = json.loads(completed.stdout)
        self.assertEqual(payload['next_task_id'], 'review-task')
        self.assertEqual(payload['rows'][0]['task_id'], 'review-task')
        self.assertIn('quality-task', [row['task_id'] for row in payload['rows']])

    def test_queue_router_keeps_review_task_when_terminal_review_round_is_stale(self):
        review_dir = self.tasks_root / 'review-task'
        task = json.loads((review_dir / 'task.json').read_text(encoding='utf-8'))
        task['execution_round'] = 2
        (review_dir / 'task.json').write_text(json.dumps(task, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        (review_dir / 'review.json').write_text(
            json.dumps({
                'task_id': 'review-task',
                'reviewer': 'review-1',
                'status': 'request_changes',
                'round': 1,
                'summary': 'old review',
            }, ensure_ascii=False, indent=2) + '\n',
            encoding='utf-8',
        )
        completed = subprocess.run(
            ['python3', str(QUEUE_ROUTER), '--tasks-root', str(self.tasks_root), '--queue', 'review', '--agent', 'review-1', '--json'],
            cwd=str(REPO_ROOT), capture_output=True, text=True, check=True,
        )
        payload = json.loads(completed.stdout)
        self.assertEqual(payload['next_task_id'], 'review-task')

    def test_queue_router_keeps_review_task_when_review_round_is_stale_against_result_round(self):
        review_dir = self.tasks_root / 'review-task'
        (review_dir / 'result.json').write_text(
            json.dumps({
                'task_id': 'review-task',
                'agent': 'dev-1',
                'status': 'success',
                'round': 3,
                'summary': 'newer result',
            }, ensure_ascii=False, indent=2) + '\n',
            encoding='utf-8',
        )
        (review_dir / 'review.json').write_text(
            json.dumps({
                'task_id': 'review-task',
                'reviewer': 'review-1',
                'status': 'request_changes',
                'round': 2,
                'summary': 'old review',
            }, ensure_ascii=False, indent=2) + '\n',
            encoding='utf-8',
        )
        completed = subprocess.run(
            ['python3', str(QUEUE_ROUTER), '--tasks-root', str(self.tasks_root), '--queue', 'review', '--agent', 'review-1', '--json'],
            cwd=str(REPO_ROOT), capture_output=True, text=True, check=True,
        )
        payload = json.loads(completed.stdout)
        self.assertEqual(payload['next_task_id'], 'review-task')

    def test_queue_router_skips_review_task_with_terminal_markdown_artifact(self):
        review_dir = self.tasks_root / 'review-task'
        (review_dir / 'review.md').write_text('# 审查结论\n\nREQUEST CHANGES\n', encoding='utf-8')
        completed = subprocess.run(
            ['python3', str(QUEUE_ROUTER), '--tasks-root', str(self.tasks_root), '--queue', 'review', '--agent', 'review-1', '--json'],
            cwd=str(REPO_ROOT), capture_output=True, text=True, check=True,
        )
        payload = json.loads(completed.stdout)
        self.assertEqual(payload['next_task_id'], 'quality-task')
        self.assertNotIn('review-task', [row['task_id'] for row in payload['rows']])

    def test_pool_view_counts_timed_out_tasks(self):
        self._write_task('pooled-timeout', {
            'id': 'pooled-timeout', 'title': '池任务超时', 'status': 'pooled', 'priority': 'medium',
            'claim_scope': ['dev-1'], 'pool_entered_at': '2026-05-09T08:00:00+08:00',
            'pool_timeout_minutes': 60,
            'task_type': 'development', 'domain': 'development', 'write_scope': ['/tmp/b'],
        })
        completed = subprocess.run(
            ['python3', str(POOL_VIEW), '--tasks-root', str(self.tasks_root), '--config', str(self.config)],
            cwd=str(REPO_ROOT), capture_output=True, text=True, check=True,
        )
        self.assertIn('超时 1', completed.stdout)

    def test_pool_view_marks_definition_blockers_for_missing_write_scope(self):
        self._write_task('pooled-invalid-scope', {
            'id': 'pooled-invalid-scope', 'title': '缺写范围', 'status': 'pooled', 'priority': 'medium',
            'claim_scope': ['dev-1'], 'pool_entered_at': '2026-05-09T10:00:00+08:00',
            'task_type': 'development', 'domain': 'development', 'write_scope': [],
        })
        completed = subprocess.run(
            ['python3', str(POOL_VIEW), '--tasks-root', str(self.tasks_root), '--config', str(self.config), '--json'],
            cwd=str(REPO_ROOT), capture_output=True, text=True, check=True,
        )
        payload = json.loads(completed.stdout)
        row = next(item for item in payload if item['task_id'] == 'pooled-invalid-scope')
        self.assertEqual(row['definition_blockers'], ['write_scope_missing'])
        self.assertEqual(row['eligible_agents'], [])
        self.assertEqual(row['gate_stage'], 'definition')

    def test_pool_router_skips_owner_approval_pending_task(self):
        self._write_task('owner-approval-pending', {
            'id': 'owner-approval-pending', 'title': '待 Owner 批准', 'status': 'pooled', 'priority': 'critical',
            'claim_scope': ['dev-1'], 'pool_entered_at': '2026-05-09T11:00:00+08:00',
            'task_type': 'development', 'domain': 'development', 'write_scope': ['/tmp/owner-pending'],
            'owner_approval_required': True,
        })
        completed = subprocess.run(
            ['python3', str(POOL_ROUTER), '--tasks-root', str(self.tasks_root), '--config', str(self.config), '--agent', 'dev-1', '--json'],
            cwd=str(REPO_ROOT), capture_output=True, text=True, check=True,
        )
        payload = json.loads(completed.stdout)
        blocked_row = next(item for item in payload['rows'] if item['task_id'] == 'owner-approval-pending')
        self.assertIn('owner_approval_pending', blocked_row['blocked_reasons'])
        self.assertNotEqual(payload['next_task_id'], 'owner-approval-pending')


if __name__ == '__main__':
    unittest.main()
