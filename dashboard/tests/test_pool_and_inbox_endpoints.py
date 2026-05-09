from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from dashboard.app import create_app


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
        }, ensure_ascii=False, indent=2), encoding='utf-8')
        self._seed_pooled_task()
        self._seed_blocked_task()
        self.app = create_app(db_path=str(root / 'task-board.sqlite3'), tasks_root=str(self.tasks_root), control_config_path=str(self.config_path))
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

    def test_pool_endpoint_returns_pooled_items(self):
        resp = self.client.get('/api/pool')
        self.assertEqual(resp.status_code, 200)
        payload = resp.get_json()
        self.assertEqual(len(payload['items']), 1)
        self.assertEqual(payload['items'][0]['task_id'], 'pooled-task')
        self.assertEqual(payload['items'][0]['eligible_agents'], ['dev-1'])

    def test_pm_inbox_endpoint_returns_blocked_items(self):
        resp = self.client.get('/api/pm-inbox')
        self.assertEqual(resp.status_code, 200)
        payload = resp.get_json()
        self.assertEqual(len(payload['items']), 1)
        self.assertEqual(payload['items'][0]['task_id'], 'blocked-task')
        self.assertEqual(payload['items'][0]['reason_type'], 'blocked')


if __name__ == '__main__':
    unittest.main()
