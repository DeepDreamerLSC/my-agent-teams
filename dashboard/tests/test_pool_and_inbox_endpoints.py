from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from dashboard.app import create_app
from dashboard.db import connect_db, upsert_task


class PoolAndInboxApiTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        root = Path(self.tmpdir.name)
        self.tasks_root = root / 'tasks'
        self.tasks_root.mkdir()
        self.config_path = root / 'config.json'
        self.config_path.write_text(json.dumps({
            'agents': {
                'pm-chief': {'role': 'pm'},
                'dev-1': {'role': 'fullstack_dev'},
                'dev-2': {'role': 'fullstack_dev'},
                'review-1': {'role': 'reviewer'},
                'qa-1': {'role': 'qa'},
            },
            'task_pool': {'default_claim_max_concurrency': 1},
            'artifact_contract': {'new_tasks_require_review_json_after': '2026-05-10T00:00:00+08:00'},
        }, ensure_ascii=False, indent=2), encoding='utf-8')
        self._seed_pooled_task()
        self._seed_blocked_task()
        self._seed_review_timeout_task()
        self._seed_qa_timeout_task()
        self._seed_missing_review_json_task()
        self.db_path = str(root / 'task-board.sqlite3')
        self._seed_integration_queue_task_db()
        self.app = create_app(db_path=self.db_path, tasks_root=str(self.tasks_root), control_config_path=str(self.config_path))
        self.client = self.app.test_client()

    def tearDown(self):
        self.tmpdir.cleanup()

    def _write_task(self, task_dir: Path, task: dict, instruction: str) -> None:
        task_dir.mkdir(parents=True, exist_ok=True)
        (task_dir / 'task.json').write_text(json.dumps(task, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        (task_dir / 'instruction.md').write_text(instruction, encoding='utf-8')
        (task_dir / 'transitions.jsonl').write_text('', encoding='utf-8')

    def _seed_pooled_task(self):
        task = {
            'id': 'pooled-task',
            'title': '待认领任务',
            'status': 'pooled',
            'priority': 'high',
            'claim_scope': ['dev-1'],
            'pool_entered_at': '2026-05-09T10:00:00+08:00',
            'task_type': 'development',
            'domain': 'development',
            'write_scope': ['/tmp/work/feature-a'],
        }
        instruction = '\n'.join([
            '# 任务：待认领任务',
            '## 任务类型', 'development',
            '## 目标', '完成实现',
            '## 任务边界', '只改 feature-a',
            '## 输入事实', '无',
            '## 约束', '无',
            '## 交付物', 'result.json',
            '## 验收标准', '通过',
            '## 下游动作', 'review',
        ])
        self._write_task(self.tasks_root / 'pooled-task', task, instruction)

    def _seed_blocked_task(self):
        task = {
            'id': 'blocked-task',
            'title': '阻塞任务',
            'status': 'blocked',
            'priority': 'medium',
            'owner_pm': 'pm-chief',
            'merge_gate_state': 'review_rejected',
            'updated_at': '2026-05-09T11:00:00+08:00',
            'task_type': 'development',
            'domain': 'development',
            'write_scope': [],
        }
        instruction = '\n'.join([
            '# 任务：阻塞任务',
            '## 任务类型', 'development',
            '## 目标', '完成实现',
            '## 任务边界', '无',
            '## 输入事实', '无',
            '## 约束', '无',
            '## 交付物', 'result.json',
            '## 验收标准', '通过',
            '## 下游动作', 'review',
        ])
        self._write_task(self.tasks_root / 'blocked-task', task, instruction)

    def _seed_review_timeout_task(self):
        task = {
            'id': 'review-timeout-task',
            'title': '审查超时任务',
            'status': 'ready_for_merge',
            'priority': 'medium',
            'owner_pm': 'pm-chief',
            'merge_gate_state': 'review_pending',
            'updated_at': '2026-05-09T08:00:00+08:00',
            'last_gate_decision_at': '2026-05-09T08:00:00+08:00',
            'review_required': True,
            'reviewer': 'review-1',
            'created_at': '2026-05-09T07:00:00+08:00',
            'task_type': 'development',
            'domain': 'development',
            'write_scope': [],
        }
        instruction = '\n'.join([
            '# 任务：审查超时任务',
            '## 任务类型', 'development',
            '## 目标', '完成实现',
            '## 任务边界', '无',
            '## 输入事实', '无',
            '## 约束', '无',
            '## 交付物', 'result.json',
            '## 验收标准', '通过',
            '## 下游动作', 'review',
        ])
        self._write_task(self.tasks_root / 'review-timeout-task', task, instruction)

    def _seed_missing_review_json_task(self):
        task = {
            'id': 'review-json-required-task',
            'title': '缺 review json',
            'status': 'ready_for_merge',
            'priority': 'medium',
            'owner_pm': 'pm-chief',
            'merge_gate_state': 'review_pending',
            'updated_at': '2026-05-10T09:00:00+08:00',
            'last_gate_decision_at': '2026-05-10T09:00:00+08:00',
            'review_required': True,
            'reviewer': 'review-1',
            'review_level': 'standard',
            'created_at': '2026-05-10T09:00:00+08:00',
            'task_type': 'development',
            'domain': 'development',
            'write_scope': [],
        }
        instruction = '\n'.join([
            '# 任务：缺 review json',
            '## 任务类型', 'development',
            '## 目标', '完成实现',
            '## 任务边界', '无',
            '## 输入事实', '无',
            '## 约束', '无',
            '## 交付物', 'result.json',
            '## 验收标准', '通过',
            '## 下游动作', 'review',
        ])
        task_dir = self.tasks_root / 'review-json-required-task'
        self._write_task(task_dir, task, instruction)
        (task_dir / 'review.md').write_text('# Code Review\\n\\n## 结论\\n- 审查结论：通过（APPROVE）\\n', encoding='utf-8')

    def _seed_qa_timeout_task(self):
        task = {
            'id': 'qa-timeout-task',
            'title': 'QA 超时任务',
            'status': 'ready_for_merge',
            'priority': 'medium',
            'owner_pm': 'pm-chief',
            'merge_gate_state': 'qa_pending',
            'updated_at': '2026-05-09T08:00:00+08:00',
            'last_gate_decision_at': '2026-05-09T08:00:00+08:00',
            'review_required': True,
            'test_required': True,
            'reviewer': 'review-1',
            'created_at': '2026-05-09T07:00:00+08:00',
            'task_type': 'development',
            'domain': 'development',
            'write_scope': [],
        }
        instruction = '\n'.join([
            '# 任务：QA 超时任务',
            '## 任务类型', 'development',
            '## 目标', '完成实现',
            '## 任务边界', '无',
            '## 输入事实', '无',
            '## 约束', '无',
            '## 交付物', 'result.json',
            '## 验收标准', '通过',
            '## 下游动作', 'qa',
        ])
        self._write_task(self.tasks_root / 'qa-timeout-task', task, instruction)

    def _seed_integration_queue_task_db(self):
        task_dir = self.tasks_root / 'integration-candidate'
        task_dir.mkdir(parents=True, exist_ok=True)
        (task_dir / 'task.json').write_text(json.dumps({
            'id': 'integration-candidate',
            'title': '待集成候选',
            'status': 'ready_for_merge',
            'project': 'demo',
            'domain': 'development',
            'assigned_agent': 'dev-1',
            'integration_owner': 'arch-1',
            'workspace_mode': 'worktree',
            'workspace_status': 'prepared',
            'workspace_path': '/tmp/worktrees/integration-candidate',
            'worktree_path': '/tmp/worktrees/integration-candidate',
            'workspace_branch': 'task/integration-candidate',
            'workspace_base_ref': 'integration',
            'patch_path': str(task_dir / 'artifacts' / 'candidate.patch'),
            'integration_target_branch': 'integration',
            'target_branch': 'integration',
            'read_only': False,
        }, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        patch_dir = task_dir / 'artifacts'
        patch_dir.mkdir(exist_ok=True)
        (patch_dir / 'candidate.patch').write_text('diff --git a/a b/a\n', encoding='utf-8')
        conn = connect_db(self.db_path, initialize=True)
        with conn:
            upsert_task(conn, {
                'task_id': 'integration-candidate',
                'title': '待集成候选',
                'project': 'demo',
                'domain': 'development',
                'assigned_agent': 'dev-1',
                'reviewer': 'review-1',
                'owner_pm': 'pm-chief',
                'integration_owner': 'arch-1',
                'parent_task_id': None,
                'root_request_id': 'integration-candidate',
                'review_required': 1,
                'test_required': 1,
                'target_environment': 'dev',
                'priority': 'high',
                'review_level': 'standard',
                'current_status': 'ready_for_merge',
                'board_status': 'ready_for_merge',
                'merge_gate_state': 'pm_acceptance_pending',
                'rework_reason': None,
                'last_gate_actor': 'qa',
                'last_gate_decision_at': '2026-05-18T10:00:00+08:00',
                'auto_close_policy': 'manual_after_review',
                'quality_gate_mode': 'parallel',
                'created_at': '2026-05-18T09:00:00+08:00',
                'dispatched_at': '2026-05-18T09:10:00+08:00',
                'ack_at': '2026-05-18T09:20:00+08:00',
                'completed_at': '2026-05-18T10:00:00+08:00',
                'review_completed_at': '2026-05-18T10:10:00+08:00',
                'verify_completed_at': '2026-05-18T10:20:00+08:00',
                'current_status_at': '2026-05-18T10:20:00+08:00',
                'ack_agent': 'dev-1',
                'result_agent': 'dev-1',
                'lease_acquired_at': None,
                'updated_at': '2026-05-18T10:20:00+08:00',
                'summary': 'ready',
                'review_state': 'approve',
                'verify_ok': 1,
                'review_gate_state': 'approved',
                'qa_gate_state': 'passed',
                'task_dir': str(task_dir),
                'task_json_path': str(task_dir / 'task.json'),
                'write_scope_json': '["src/demo.py"]',
                'artifacts_json': '[]',
                'last_ingest_source': 'test',
                'last_synced_at': '2026-05-18T10:20:00+08:00',
            })
        conn.close()

    def test_pool_endpoint_returns_pooled_items(self):
        resp = self.client.get('/api/pool')
        self.assertEqual(resp.status_code, 200)
        payload = resp.get_json()
        self.assertEqual(len(payload['items']), 1)
        self.assertEqual(payload['items'][0]['task_id'], 'pooled-task')
        self.assertEqual(payload['items'][0]['eligible_agents'], ['dev-1'])
        self.assertEqual(payload['summary']['pool_ready_count'], 1)
        self.assertIn('idle_agent_count', payload['summary'])

    def test_pm_inbox_endpoint_returns_blocked_items(self):
        resp = self.client.get('/api/pm-inbox')
        self.assertEqual(resp.status_code, 200)
        payload = resp.get_json()
        task_ids = {item['task_id']: item['reason_type'] for item in payload['items']}
        self.assertEqual(task_ids['blocked-task'], 'blocked')
        self.assertEqual(task_ids['review-timeout-task'], 'timeout')
        self.assertEqual(task_ids['qa-timeout-task'], 'timeout')
        self.assertEqual(task_ids['review-json-required-task'], 'artifact_invalid')

    def test_integration_queue_endpoint_returns_merge_candidates(self):
        resp = self.client.get('/api/integration-queue')
        self.assertEqual(resp.status_code, 200)
        payload = resp.get_json()
        self.assertEqual(payload['summary']['queued_count'], 1)
        self.assertEqual(payload['items'][0]['task_id'], 'integration-candidate')
        self.assertEqual(payload['items'][0]['state'], 'queued')
        self.assertTrue(payload['items'][0]['patch_exists'])


if __name__ == '__main__':
    unittest.main()
