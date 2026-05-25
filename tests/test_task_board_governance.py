from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

from dashboard.db import connect_db, upsert_task


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / 'scripts' / 'task-board-governance.py'


def load_module():
    spec = importlib.util.spec_from_file_location('task_board_governance', SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _task_record(**overrides):
    base = {
        'task_id': 'task-1',
        'title': '任务一',
        'project': 'my-agent-teams',
        'domain': 'development',
        'assigned_agent': 'dev-1',
        'reviewer': 'review-1',
        'owner_pm': 'pm-chief',
        'integration_owner': 'arch-1',
        'parent_task_id': None,
        'root_request_id': 'root-1',
        'review_required': 1,
        'test_required': 1,
        'target_environment': 'dev',
        'priority': 'medium',
        'review_level': 'standard',
        'current_status': 'ready_for_merge',
        'board_status': 'ready_for_merge',
        'merge_gate_state': 'review_pending',
        'rework_reason': None,
        'last_gate_actor': None,
        'last_gate_decision_at': None,
        'auto_close_policy': 'manual_after_review',
        'created_at': '2026-05-04T00:00:00+08:00',
        'dispatched_at': '2026-05-04T00:10:00+08:00',
        'ack_at': '2026-05-04T00:20:00+08:00',
        'completed_at': '2026-05-04T01:00:00+08:00',
        'review_completed_at': None,
        'verify_completed_at': None,
        'current_status_at': '2026-05-04T05:00:00+08:00',
        'ack_agent': 'dev-1',
        'result_agent': 'dev-1',
        'lease_acquired_at': None,
        'updated_at': '2026-05-04T05:00:00+08:00',
        'summary': None,
        'review_state': None,
        'verify_ok': None,
        'task_dir': '/tmp/task-1',
        'task_json_path': '/tmp/task-1/task.json',
        'write_scope_json': '[]',
        'artifacts_json': '[]',
        'last_ingest_source': 'test',
        'last_synced_at': '2026-05-04T05:00:00+08:00',
    }
    base.update(overrides)
    return base


class GovernanceScriptTests(unittest.TestCase):
    def test_detects_skip_review_wait_anomaly(self):
        mod = load_module()
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / 'task-board.sqlite3'
            conn = connect_db(db_path, initialize=True)
            task_dir = Path(tmp) / 'task-1'
            task_dir.mkdir()
            (task_dir / 'task.json').write_text(json.dumps({
                'id': 'task-1',
                'title': '任务一',
                'status': 'ready_for_merge',
                'priority': 'high',
                'owner_pm': 'pm-chief',
                'pool_timeout_minutes': 30,
            }, ensure_ascii=False), encoding='utf-8')
            with conn:
                upsert_task(conn, _task_record(
                    task_id='task-1',
                    review_required=0,
                    review_level='skip',
                    task_dir=str(task_dir),
                    task_json_path=str(task_dir / 'task.json'),
                    review_completed_at='2026-05-04T03:00:00+08:00',
                ))
                conn.execute(
                    '''
                    INSERT OR REPLACE INTO task_stage_durations (
                        task_id, result_to_review_seconds, updated_at
                    ) VALUES (?, ?, ?)
                    ''',
                    ('task-1', 7200, '2026-05-04T05:00:00+08:00'),
                )
            items = mod.find_invalid_timeline_items(conn, mod.datetime.now().astimezone())
            conn.close()

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]['reason_type'], 'invalid_timeline')
        self.assertIn('skip review', items[0]['summary'])

    def test_ownerless_governance_item_uses_configured_root_pm(self):
        mod = load_module()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db_path = root / 'task-board.sqlite3'
            config_path = root / 'config.json'
            config_path.write_text(json.dumps({
                'orchestration': {'root_pm': 'lead-pm'},
                'agents': {'lead-pm': {'role': 'pm'}},
            }, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
            conn = connect_db(db_path, initialize=True)
            with conn:
                upsert_task(conn, _task_record(
                    task_id='task-ownerless',
                    owner_pm='',
                    review_required=0,
                    review_level='skip',
                    review_completed_at='2026-05-04T03:00:00+08:00',
                ))
                conn.execute(
                    '''
                    INSERT OR REPLACE INTO task_stage_durations (
                        task_id, result_to_review_seconds, updated_at
                    ) VALUES (?, ?, ?)
                    ''',
                    ('task-ownerless', 7200, '2026-05-04T05:00:00+08:00'),
                )
            root_pm_id = mod.configured_root_pm(config_path)
            items = mod.find_invalid_timeline_items(conn, mod.datetime.now().astimezone(), root_pm_id=root_pm_id)
            conn.close()

        self.assertEqual(items[0]['owner'], 'lead-pm')


if __name__ == '__main__':
    unittest.main()
