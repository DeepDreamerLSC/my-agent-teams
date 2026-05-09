from __future__ import annotations

import tempfile
import unittest
from datetime import date
from pathlib import Path

from dashboard.app import create_app
from dashboard.db import connect_db, upsert_task
from dashboard.metrics import rebuild_daily_metrics


def _task_record(*, task_id: str, project: str, assigned_agent: str, created_at: str, ack_at: str, completed_at: str, current_status: str = "done") -> dict:
    return {
        "task_id": task_id,
        "title": task_id,
        "project": project,
        "domain": "development",
        "assigned_agent": assigned_agent,
        "reviewer": None,
        "owner_pm": "pm-chief",
        "parent_task_id": None,
        "root_request_id": task_id,
        "review_required": 0,
        "test_required": 0,
        "current_status": current_status,
        "board_status": current_status,
        "created_at": created_at,
        "dispatched_at": ack_at,
        "ack_at": ack_at,
        "completed_at": completed_at,
        "review_completed_at": None,
        "verify_completed_at": None,
        "current_status_at": completed_at,
        "ack_agent": assigned_agent,
        "result_agent": assigned_agent,
        "lease_acquired_at": None,
        "updated_at": completed_at,
        "summary": None,
        "review_state": None,
        "verify_ok": None,
        "task_dir": f"/tmp/{task_id}",
        "task_json_path": f"/tmp/{task_id}/task.json",
        "write_scope_json": "[]",
        "artifacts_json": "[]",
        "last_ingest_source": "test",
        "last_synced_at": completed_at,
    }


class DashboardMetricsTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.tmpdir.name) / "task-board.sqlite3")
        self.conn = connect_db(self.db_path, initialize=True)
        with self.conn:
            upsert_task(self.conn, _task_record(
                task_id="task-a",
                project="proj-a",
                assigned_agent="dev-1",
                created_at="2026-05-01T09:00:00+08:00",
                ack_at="2026-05-01T09:10:00+08:00",
                completed_at="2026-05-01T10:00:00+08:00",
            ))
            upsert_task(self.conn, _task_record(
                task_id="task-b",
                project="proj-b",
                assigned_agent="dev-2",
                created_at="2026-05-01T11:00:00+08:00",
                ack_at="2026-05-01T11:10:00+08:00",
                completed_at="2026-05-01T12:00:00+08:00",
            ))

    def tearDown(self):
        self.conn.close()
        self.tmpdir.cleanup()

    def test_project_rebuild_does_not_overwrite_all_aggregate_rows(self):
        rebuild_daily_metrics(self.db_path, start_date=date.fromisoformat("2026-05-01"), end_date=date.fromisoformat("2026-05-01"))
        before_all = dict(self.conn.execute(
            "SELECT * FROM task_metrics_daily WHERE project = '__all__' AND metric_date = '2026-05-01'"
        ).fetchone())

        rebuild_daily_metrics(
            self.db_path,
            start_date=date.fromisoformat("2026-05-01"),
            end_date=date.fromisoformat("2026-05-01"),
            project="proj-a",
        )
        after_all = dict(self.conn.execute(
            "SELECT * FROM task_metrics_daily WHERE project = '__all__' AND metric_date = '2026-05-01'"
        ).fetchone())
        scoped_row = dict(self.conn.execute(
            "SELECT * FROM task_metrics_daily WHERE project = 'proj-a' AND metric_date = '2026-05-01'"
        ).fetchone())

        self.assertEqual(before_all["completed_task_count"], 2)
        self.assertEqual(after_all["completed_task_count"], 2)
        self.assertEqual(after_all["touched_task_count"], 2)
        self.assertEqual(scoped_row["completed_task_count"], 1)
        self.assertEqual(scoped_row["touched_task_count"], 1)

    def test_api_metrics_default_query_keeps_all_scope_after_project_rebuild(self):
        rebuild_daily_metrics(self.db_path, start_date=date.fromisoformat("2026-05-01"), end_date=date.fromisoformat("2026-05-01"))
        rebuild_daily_metrics(
            self.db_path,
            start_date=date.fromisoformat("2026-05-01"),
            end_date=date.fromisoformat("2026-05-01"),
            project="proj-a",
        )
        app = create_app(self.db_path)
        client = app.test_client()
        resp = client.get('/api/metrics/daily?start_date=2026-05-01&end_date=2026-05-01')
        self.assertEqual(resp.status_code, 200)
        payload = resp.get_json()
        self.assertEqual(payload['filters']['project'], '__all__')
        self.assertEqual(payload['task_metrics'][0]['project'], '__all__')
        self.assertEqual(payload['task_metrics'][0]['completed_task_count'], 2)
        self.assertEqual(payload['task_metrics'][0]['touched_task_count'], 2)

    def test_aggregate_summary_includes_collaboration_metrics(self):
        from dashboard.query import build_task_aggregate_payload

        with self.conn:
            upsert_task(self.conn, {
                **_task_record(
                    task_id="task-c",
                    project="proj-a",
                    assigned_agent="review-1",
                    created_at="2026-05-01T13:00:00+08:00",
                    ack_at="2026-05-01T13:10:00+08:00",
                    completed_at="2026-05-01T14:00:00+08:00",
                ),
                "current_status": "ready_for_merge",
                "board_status": "ready_for_merge",
                "review_completed_at": "2026-05-01T15:00:00+08:00",
                "verify_completed_at": "2026-05-01T16:00:00+08:00",
                "current_status_at": "2026-05-01T16:30:00+08:00",
                "last_synced_at": "2026-05-01T16:30:00+08:00",
            })
        payload = build_task_aggregate_payload(self.conn)
        metrics = payload['summary']['collaboration_metrics']
        self.assertIsNotNone(metrics['avg_review_wait_hours'])
        self.assertIsNotNone(metrics['avg_qa_wait_hours'])


if __name__ == '__main__':
    unittest.main()
