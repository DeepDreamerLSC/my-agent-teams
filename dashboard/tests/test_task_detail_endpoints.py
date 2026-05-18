from __future__ import annotations

import json
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
        task_dir = Path(self.tmpdir.name) / 'task-1'
        task_dir.mkdir()
        (task_dir / 'task.json').write_text(json.dumps({
            'id': 'task-1',
            'workspace_mode': 'worktree',
            'workspace_status': 'prepared',
            'workspace_path': str(task_dir / 'worktree'),
            'worktree_path': str(task_dir / 'worktree'),
            'workspace_branch': 'task/task-1',
            'workspace_base_ref': 'integration',
            'patch_path': str(task_dir / 'artifacts' / 'task-1.patch'),
            'integration_target_branch': 'integration',
            'control_plane_state': 'session_unhealthy',
            'dispatch_delivery_retry_count': 2,
            'session_health': 'missing_session',
            'read_only': False,
        }, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
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
                'quality_gate_mode': 'parallel',
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
                'review_gate_state': 'approved',
                'qa_gate_state': 'pending',
                'task_dir': str(task_dir),
                'task_json_path': str(task_dir / 'task.json'),
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
        self.assertEqual(detail['task']['quality_gate_mode'], 'parallel')
        self.assertEqual(detail['task']['review_gate_state'], 'approved')
        self.assertEqual(detail['task']['qa_gate_state'], 'pending')
        self.assertEqual(detail['task']['workspace_status'], 'prepared')
        self.assertEqual(detail['task']['integration_queue_state'], 'queued')
        self.assertEqual(detail['task']['control_plane_state'], 'session_unhealthy')

    def test_query_handles_empty_communications(self):
        empty = build_task_communications_payload(self.conn, 'missing-task')
        self.assertIsNone(empty['task'])
        self.assertEqual(empty['communications'], [])


class TaskDetailApiTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        root = Path(self.tmpdir.name)
        self.db_path = str(root / 'task-board.sqlite3')
        self.tasks_root = root / 'tasks'
        self.tasks_root.mkdir()
        self.config_path = root / 'config.json'
        self.config_path.write_text(json.dumps({
            'agents': {
                'dev-1': {'role': 'fullstack_dev'},
                'dev-2': {'role': 'fullstack_dev'},
            },
            'task_pool': {'default_claim_max_concurrency': 1},
        }, ensure_ascii=False), encoding='utf-8')
        task2_dir = root / 'task-2'
        task2_dir.mkdir()
        (task2_dir / 'task.json').write_text(json.dumps({
            'id': 'task-2',
            'workspace_mode': 'worktree',
            'workspace_status': 'prepared',
            'workspace_path': str(task2_dir / 'worktree'),
            'worktree_path': str(task2_dir / 'worktree'),
            'workspace_branch': 'task/task-2',
            'workspace_base_ref': 'integration',
            'patch_path': str(task2_dir / 'artifacts' / 'task-2.patch'),
            'integration_target_branch': 'integration',
            'control_plane_state': 'delivery_failed',
            'dispatch_delivery_retry_count': 1,
            'last_delivery_error': 'send failed',
            'session_health': 'idle_session',
            'read_only': False,
        }, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
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
                'quality_gate_mode': 'single',
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
                'review_gate_state': 'skipped',
                'qa_gate_state': 'skipped',
                'task_dir': str(task2_dir),
                'task_json_path': str(task2_dir / 'task.json'),
                'write_scope_json': '[]',
                'artifacts_json': '[]',
                'last_ingest_source': 'test',
                'last_synced_at': '2026-05-04T00:10:00+08:00',
            })
            pooled_dir = self.tasks_root / 'pooled-detail'
            pooled_dir.mkdir()
            (pooled_dir / 'task.json').write_text(json.dumps({
                'id': 'pooled-detail',
                'title': '池中详情任务',
                'status': 'pooled',
                'priority': 'high',
                'claim_scope': ['dev-1'],
                'depends_on': ['missing-dep'],
                'pool_entered_at': '2026-05-04T00:00:00+08:00',
                'task_type': 'development',
                'domain': 'development',
                'write_scope': ['/tmp/pooled-detail'],
            }, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
            (pooled_dir / 'instruction.md').write_text('\n'.join([
                '# 任务：池中详情任务',
                '## 任务类型', 'development',
                '## 目标', '完成任务',
                '## 任务边界', '按范围执行',
                '## 输入事实', '已有上下文',
                '## 约束', '遵守约束',
                '## 交付物', 'result.json',
                '## 验收标准', '满足要求',
                '## 下游动作', 'review',
            ]) + '\n', encoding='utf-8')
            upsert_task(conn, {
                'task_id': 'pooled-detail',
                'title': '池中详情任务',
                'project': 'my-agent-teams',
                'domain': 'development',
                'assigned_agent': 'auto',
                'reviewer': None,
                'owner_pm': 'pm-chief',
                'integration_owner': 'arch-1',
                'parent_task_id': None,
                'root_request_id': 'root-3',
                'review_required': 0,
                'test_required': 0,
                'target_environment': 'dev',
                'priority': 'high',
                'review_level': 'skip',
                'current_status': 'pooled',
                'board_status': 'pending',
                'merge_gate_state': None,
                'rework_reason': None,
                'last_gate_actor': None,
                'last_gate_decision_at': None,
                'auto_close_policy': 'manual_after_review',
                'quality_gate_mode': 'single',
                'created_at': '2026-05-04T00:00:00+08:00',
                'dispatched_at': None,
                'ack_at': None,
                'completed_at': None,
                'review_completed_at': None,
                'verify_completed_at': None,
                'current_status_at': '2026-05-04T00:00:00+08:00',
                'ack_agent': None,
                'result_agent': None,
                'lease_acquired_at': None,
                'updated_at': '2026-05-04T00:00:00+08:00',
                'summary': None,
                'review_state': None,
                'verify_ok': None,
                'review_gate_state': 'skipped',
                'qa_gate_state': 'skipped',
                'task_dir': str(pooled_dir),
                'task_json_path': str(pooled_dir / 'task.json'),
                'write_scope_json': '[]',
                'artifacts_json': '[]',
                'last_ingest_source': 'test',
                'last_synced_at': '2026-05-04T00:00:00+08:00',
            })
        conn.close()
        app = create_app(self.db_path, tasks_root=str(self.tasks_root), control_config_path=str(self.config_path))
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

    def test_detail_includes_pool_blockers_for_pooled_task(self):
        resp = self.client.get('/api/tasks/pooled-detail/detail')
        self.assertEqual(resp.status_code, 200)
        payload = resp.get_json()
        self.assertIsNotNone(payload.get('pool_status'))
        self.assertIn('dependency_missing:missing-dep', payload['pool_status']['blocked_reasons'])

    def test_detail_includes_workspace_and_control_plane_fields(self):
        resp = self.client.get('/api/tasks/task-2/detail')
        self.assertEqual(resp.status_code, 200)
        payload = resp.get_json()
        self.assertEqual(payload['task']['workspace_status'], 'prepared')
        self.assertEqual(payload['task']['workspace_branch'], 'task/task-2')
        self.assertEqual(payload['task']['control_plane_state'], 'delivery_failed')
        self.assertEqual(payload['task']['integration_queue_state'], 'in_progress')
