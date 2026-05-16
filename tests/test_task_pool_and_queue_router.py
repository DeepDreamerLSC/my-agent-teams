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

    def tearDown(self):
        self.tmpdir.cleanup()

    def _write_task(self, name: str, payload: dict) -> None:
        task_dir = self.tasks_root / name
        task_dir.mkdir(parents=True, exist_ok=True)
        (task_dir / 'task.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

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
        self.assertIsNone(payload['next_task_id'])
        self.assertEqual(payload['rows'], [])

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
        self.assertEqual([row['task_id'] for row in payload['rows']], ['review-task'])

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
        self.assertIsNone(payload['next_task_id'])
        self.assertEqual(payload['rows'], [])

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


if __name__ == '__main__':
    unittest.main()
