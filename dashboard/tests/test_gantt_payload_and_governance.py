from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from dashboard.db import connect_db, upsert_task
from dashboard.query import build_gantt_payload


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


class GanttPayloadTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.tmpdir.name) / 'task-board.sqlite3')
        self.conn = connect_db(self.db_path, initialize=True)

    def tearDown(self):
        self.conn.close()
        self.tmpdir.cleanup()

    def test_skip_review_task_omits_waiting_review_segment(self):
        with self.conn:
            upsert_task(self.conn, _task_record(
                task_id='skip-review',
                review_required=0,
                review_level='skip',
                current_status='done',
                board_status='done',
                current_status_at='2026-05-04T01:05:00+08:00',
                updated_at='2026-05-04T01:05:00+08:00',
                last_synced_at='2026-05-04T01:05:00+08:00',
            ))
        payload = build_gantt_payload(self.conn)
        item = payload['items'][0]
        keys = [segment['key'] for segment in item['phase_segments']]
        self.assertNotIn('completed', keys)
        self.assertEqual(item['display_end_at'], '2026-05-04T01:05:00+08:00')

    def test_terminal_blocked_task_uses_current_status_at_as_end(self):
        with self.conn:
            upsert_task(self.conn, _task_record(
                task_id='failed-task',
                current_status='failed',
                board_status='blocked',
                completed_at='2026-05-04T01:00:00+08:00',
                review_completed_at=None,
                current_status_at='2026-05-04T02:30:00+08:00',
                updated_at='2026-05-09T00:00:00+08:00',
                last_synced_at='2026-05-09T00:00:00+08:00',
            ))
        payload = build_gantt_payload(self.conn)
        item = next(entry for entry in payload['items'] if entry['task_id'] == 'failed-task')
        self.assertTrue(item['phase_segments'])
        self.assertEqual(item['phase_segments'][-1]['end_at'], '2026-05-04T02:30:00+08:00')
        self.assertEqual(item['display_end_at'], '2026-05-04T02:30:00+08:00')


if __name__ == '__main__':
    unittest.main()
