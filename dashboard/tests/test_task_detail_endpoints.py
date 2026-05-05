from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from dashboard.app import create_app
from dashboard.db import connect_db, upsert_task, upsert_event, upsert_communication_event
from dashboard.query import (
    build_task_detail_payload,
    build_task_timeline_payload,
    build_task_communications_payload,
)


class TaskDetailQueryTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.tmpdir.name) / 'task-board.sqlite3')
        self.conn = connect_db(self.db_path, initialize=True)
        self._seed_task()

    def tearDown(self):
        self.conn.close()
        self.tmpdir.cleanup()

    def _seed_task(self):
        with self.conn:
            upsert_task(self.conn, {
                'task_id': 'task-1',
                'title': '任务一',
                'project': 'my-agent-teams',
                'domain': 'development',
                'assigned_agent': 'dev-2',
                'reviewer': 'review-1',
                'owner_pm': 'pm-chief',
                'integration_owner': 'arch-1',
                'parent_task_id': None,
                'root_request_id': 'root-1',
                'review_required': 1,
                'test_required': 1,
                'target_environment': 'dev',
                'priority': 'high',
                'review_level': 'standard',
                'current_status': 'ready_for_merge',
                'board_status': 'ready_for_merge',
                'merge_gate_state': 'qa_pending',
                'rework_reason': None,
                'last_gate_actor': 'review',
                'last_gate_decision_at': '2026-05-04T01:10:00+08:00',
                'auto_close_policy': 'manual_after_review',
                'created_at': '2026-05-04T00:00:00+08:00',
                'dispatched_at': '2026-05-04T00:10:00+08:00',
                'ack_at': '2026-05-04T00:20:00+08:00',
                'completed_at': '2026-05-04T01:00:00+08:00',
                'review_completed_at': None,
                'verify_completed_at': None,
                'current_status_at': '2026-05-04T01:00:00+08:00',
                'ack_agent': 'dev-2',
                'result_agent': 'dev-2',
                'lease_acquired_at': None,
                'updated_at': '2026-05-04T01:00:00+08:00',
                'summary': 'done',
                'review_state': None,
                'verify_ok': None,
                'task_dir': '/tmp/task-1',
                'task_json_path': '/tmp/task-1/task.json',
                'write_scope_json': '[]',
                'artifacts_json': '[]',
                'last_ingest_source': 'test',
                'last_synced_at': '2026-05-04T01:00:00+08:00',
            })
            upsert_event(self.conn, {
                'event_key': 'task-1:e1',
                'task_id': 'task-1',
                'event_type': 'created',
                'event_at': '2026-05-04T00:00:00+08:00',
                'source': 'task_json',
                'status_from': None,
                'status_to': 'pending',
                'artifact_path': '/tmp/task-1/task.json',
                'payload_json': '{}',
                'observed_at': '2026-05-04T00:00:01+08:00',
            })
            upsert_event(self.conn, {
                'event_key': 'task-1:e2',
                'task_id': 'task-1',
                'event_type': 'ack',
                'event_at': '2026-05-04T00:20:00+08:00',
                'source': 'ack_json',
                'status_from': None,
                'status_to': 'working',
                'artifact_path': '/tmp/task-1/ack.json',
                'payload_json': '{}',
                'observed_at': '2026-05-04T00:20:01+08:00',
            })
            upsert_communication_event(self.conn, {
                'event_id': 'comm-2',
                'task_id': 'task-1',
                'thread_id': 'task-1',
                'channel': 'task',
                'event_type': 'answer',
                'event_class': 'reply',
                'source_type': 'human',
                'from_actor': 'review-1',
                'to_actor': 'dev-2',
                'priority': None,
                'severity': None,
                'message_text': '已收到',
                'reply_to': 'comm-1',
                'source_file': '/tmp/chat/tasks/task-1.jsonl',
                'source_line': 2,
                'source_msg_id': 'comm-2',
                'source_name': 'review-1',
                'related_artifact_path': None,
                'happened_at': '2026-05-04T00:15:00+08:00',
                'observed_at': '2026-05-04T00:15:01+08:00',
                'payload_json': '{}',
            })
            upsert_communication_event(self.conn, {
                'event_id': 'comm-1',
                'task_id': 'task-1',
                'thread_id': 'task-1',
                'channel': 'task',
                'event_type': 'question',
                'event_class': 'request',
                'source_type': 'human',
                'from_actor': 'dev-2',
                'to_actor': 'review-1',
                'priority': None,
                'severity': None,
                'message_text': '请帮忙 review',
                'reply_to': None,
                'source_file': '/tmp/chat/tasks/task-1.jsonl',
                'source_line': 1,
                'source_msg_id': 'comm-1',
                'source_name': 'dev-2',
                'related_artifact_path': None,
                'happened_at': '2026-05-04T00:15:00+08:00',
                'observed_at': '2026-05-04T00:15:00+08:00',
                'payload_json': '{}',
            })

    def test_query_payloads_are_stable(self):
        detail = build_task_detail_payload(self.conn, 'task-1')
        timeline = build_task_timeline_payload(self.conn, 'task-1')
        communications = build_task_communications_payload(self.conn, 'task-1')
        self.assertIsNotNone(detail['task'])
        self.assertEqual(detail['timeline'], timeline['timeline'])
        self.assertEqual(detail['communication_timeline'], timeline['communication_timeline'])
        self.assertEqual(detail['communication_timeline'], communications['communications'])
        self.assertEqual([item['event_id'] for item in communications['communications']], ['comm-1', 'comm-2'])
        self.assertIsNone(detail['durations']['result_to_review_seconds'])
        self.assertIsNone(detail['durations']['review_to_verify_seconds'])
        self.assertEqual(detail['task']['integration_owner'], 'arch-1')
        self.assertEqual(detail['task']['target_environment'], 'dev')
        self.assertEqual(detail['task']['review_level'], 'standard')
        self.assertEqual(detail['task']['merge_gate_state'], 'qa_pending')

    def test_query_handles_empty_communications(self):
        empty = build_task_communications_payload(self.conn, 'missing-task')
        self.assertIsNone(empty['task'])
        self.assertEqual(empty['communications'], [])


class TaskDetailApiTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.tmpdir.name) / 'task-board.sqlite3')
        conn = connect_db(self.db_path, initialize=True)
        with conn:
            upsert_task(conn, {
                'task_id': 'task-2',
                'title': '任务二',
                'project': 'my-agent-teams',
                'domain': 'development',
                'assigned_agent': 'dev-2',
                'reviewer': None,
                'owner_pm': 'pm-chief',
                'integration_owner': 'arch-1',
                'parent_task_id': None,
                'root_request_id': 'root-2',
                'review_required': 0,
                'test_required': 0,
                'target_environment': 'dev',
                'priority': 'medium',
                'review_level': 'skip',
                'current_status': 'working',
                'board_status': 'working',
                'merge_gate_state': None,
                'rework_reason': None,
                'last_gate_actor': None,
                'last_gate_decision_at': None,
                'auto_close_policy': 'manual_after_review',
                'created_at': '2026-05-04T00:00:00+08:00',
                'dispatched_at': '2026-05-04T00:05:00+08:00',
                'ack_at': '2026-05-04T00:10:00+08:00',
                'completed_at': None,
                'review_completed_at': None,
                'verify_completed_at': None,
                'current_status_at': '2026-05-04T00:10:00+08:00',
                'ack_agent': 'dev-2',
                'result_agent': None,
                'lease_acquired_at': None,
                'updated_at': '2026-05-04T00:10:00+08:00',
                'summary': None,
                'review_state': None,
                'verify_ok': None,
                'task_dir': '/tmp/task-2',
                'task_json_path': '/tmp/task-2/task.json',
                'write_scope_json': '[]',
                'artifacts_json': '[]',
                'last_ingest_source': 'test',
                'last_synced_at': '2026-05-04T00:10:00+08:00',
            })
        conn.close()
        app = create_app(self.db_path)
        self.client = app.test_client()

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_api_exposes_timeline_and_communications(self):
        timeline_resp = self.client.get('/api/tasks/task-2/timeline')
        comm_resp = self.client.get('/api/tasks/task-2/communications')
        self.assertEqual(timeline_resp.status_code, 200)
        self.assertEqual(comm_resp.status_code, 200)
        self.assertIn('timeline', timeline_resp.get_json())
        self.assertIn('communications', comm_resp.get_json())
        self.assertEqual(comm_resp.get_json()['communications'], [])

    def test_api_returns_404_for_missing_task(self):
        resp = self.client.get('/api/tasks/not-found/timeline')
        self.assertEqual(resp.status_code, 404)
