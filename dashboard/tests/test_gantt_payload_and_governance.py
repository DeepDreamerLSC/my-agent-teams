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
        'quality_gate_mode': 'serial',
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
        'review_gate_state': 'pending',
        'qa_gate_state': 'pending',
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
                test_required=0,
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
        self.assertNotIn('review', keys)
        self.assertIn('pm_acceptance', keys)
        self.assertEqual(item['display_end_at'], '2026-05-04T01:05:00+08:00')
        self.assertIn('source', item['phase_segments'][0])
        self.assertEqual(item['phase_segments'][0]['source']['start']['field'], 'dispatched_at')
        self.assertIn(item['phase_segments'][0]['precision'], {'exact', 'inferred'})

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
        self.assertEqual(item['phase_segments'][-1]['source']['end']['field'], 'current_status_at')
        self.assertEqual(item['display_end_at'], '2026-05-04T02:30:00+08:00')

    def test_mixed_naive_and_aware_times_do_not_break_duration_calculation(self):
        with self.conn:
            upsert_task(self.conn, _task_record(
                task_id='mixed-time-task',
                created_at='2026-05-04T00:00:00',
                dispatched_at='2026-05-04T00:10:00+08:00',
                ack_at='2026-05-04T00:20:00',
                completed_at='2026-05-04T01:00:00+08:00',
                current_status_at='2026-05-04T01:10:00+08:00',
                updated_at='2026-05-04T01:10:00+08:00',
                last_synced_at='2026-05-04T01:10:00+08:00',
            ))
        payload = build_gantt_payload(self.conn)
        item = next(entry for entry in payload['items'] if entry['task_id'] == 'mixed-time-task')
        self.assertTrue(item['phase_segments'])
        self.assertTrue(all(segment['duration_seconds'] >= 0 for segment in item['phase_segments']))

    def test_pooled_task_gets_pooled_segment_with_inferred_end(self):
        task_dir = Path(self.tmpdir.name) / 'pooled-task'
        task_dir.mkdir()
        (task_dir / 'task.json').write_text(
            '{"pool_entered_at":"2026-05-04T00:05:00+08:00","claim_scope":["dev-1"]}',
            encoding='utf-8',
        )
        with self.conn:
            upsert_task(self.conn, _task_record(
                task_id='pooled-task',
                current_status='pooled',
                board_status='pending',
                dispatched_at=None,
                ack_at=None,
                completed_at=None,
                current_status_at='2026-05-04T00:05:00+08:00',
                updated_at='2026-05-04T00:05:00+08:00',
                task_dir=str(task_dir),
                task_json_path=str(task_dir / 'task.json'),
            ))
        payload = build_gantt_payload(self.conn)
        item = next(entry for entry in payload['items'] if entry['task_id'] == 'pooled-task')
        pooled = next(segment for segment in item['phase_segments'] if segment['key'] == 'pooled')
        self.assertEqual(pooled['start_at'], '2026-05-04T00:05:00+08:00')
        self.assertEqual(pooled['source']['end']['field'], 'generated_at')
        self.assertEqual(pooled['precision'], 'inferred')

    def test_parallel_quality_gate_starts_review_and_qa_from_result_completion(self):
        with self.conn:
            upsert_task(self.conn, _task_record(
                task_id='parallel-quality',
                merge_gate_state='quality_pending',
                quality_gate_mode='parallel',
                review_gate_state='pending',
                qa_gate_state='pending',
                completed_at='2026-05-04T01:00:00+08:00',
                review_completed_at='2026-05-04T02:00:00+08:00',
                verify_completed_at='2026-05-04T03:00:00+08:00',
                current_status_at='2026-05-04T03:30:00+08:00',
                updated_at='2026-05-04T03:30:00+08:00',
                last_synced_at='2026-05-04T03:30:00+08:00',
            ))
        payload = build_gantt_payload(self.conn)
        item = next(entry for entry in payload['items'] if entry['task_id'] == 'parallel-quality')
        review = next(segment for segment in item['phase_segments'] if segment['key'] == 'review')
        qa = next(segment for segment in item['phase_segments'] if segment['key'] == 'qa')
        self.assertEqual(review['start_at'], '2026-05-04T01:00:00+08:00')
        self.assertEqual(review['end_at'], '2026-05-04T02:00:00+08:00')
        self.assertEqual(qa['start_at'], '2026-05-04T01:00:00+08:00')
        self.assertEqual(qa['end_at'], '2026-05-04T03:00:00+08:00')


if __name__ == '__main__':
    unittest.main()
