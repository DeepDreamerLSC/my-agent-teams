from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = WORKSPACE_ROOT / '.omx' / 'task-board' / 'task-board.sqlite3'
SCHEMA_VERSION = 5

TASK_COLUMNS = [
    'task_id',
    'title',
    'project',
    'domain',
    'assigned_agent',
    'reviewer',
    'owner_pm',
    'integration_owner',
    'parent_task_id',
    'root_request_id',
    'review_required',
    'test_required',
    'target_environment',
    'priority',
    'review_level',
    'current_status',
    'board_status',
    'merge_gate_state',
    'rework_reason',
    'last_gate_actor',
    'last_gate_decision_at',
    'auto_close_policy',
    'created_at',
    'dispatched_at',
    'ack_at',
    'completed_at',
    'review_completed_at',
    'verify_completed_at',
    'current_status_at',
    'ack_agent',
    'result_agent',
    'lease_acquired_at',
    'updated_at',
    'summary',
    'review_state',
    'verify_ok',
    'task_dir',
    'task_json_path',
    'write_scope_json',
    'artifacts_json',
    'last_ingest_source',
    'last_synced_at',
]

EVENT_COLUMNS = [
    'event_key',
    'task_id',
    'event_type',
    'event_at',
    'source',
    'status_from',
    'status_to',
    'artifact_path',
    'payload_json',
    'observed_at',
]

COMMUNICATION_EVENT_COLUMNS = [
    'event_id',
    'task_id',
    'thread_id',
    'channel',
    'event_type',
    'event_class',
    'source_type',
    'from_actor',
    'to_actor',
    'priority',
    'severity',
    'message_text',
    'reply_to',
    'source_file',
    'source_line',
    'source_msg_id',
    'source_name',
    'related_artifact_path',
    'happened_at',
    'observed_at',
    'payload_json',
]

CHAT_INGEST_STATE_COLUMNS = [
    'state_key',
    'file_path',
    'last_line_number',
    'last_event_id',
    'updated_at',
]

TASK_STAGE_DURATION_COLUMNS = [
    'task_id',
    'create_to_dispatch_seconds',
    'dispatch_to_ack_seconds',
    'ack_to_result_seconds',
    'result_to_review_seconds',
    'review_to_verify_seconds',
    'verify_to_close_seconds',
    'total_cycle_seconds',
    'updated_at',
]

TASK_METRICS_DAILY_COLUMNS = [
    'metric_date',
    'project',
    'created_task_count',
    'completed_task_count',
    'blocked_task_count',
    'touched_task_count',
    'completion_rate',
    'blocked_rate',
    'avg_cycle_seconds',
    'avg_ack_to_result_seconds',
    'updated_at',
]

AGENT_METRICS_DAILY_COLUMNS = [
    'metric_date',
    'project',
    'agent_id',
    'active_task_count',
    'blocked_task_count',
    'ready_for_merge_count',
    'completed_task_count',
    'total_tracked_work_seconds',
    'avg_active_work_seconds',
    'updated_at',
]

TASK_ADDITIONAL_COLUMN_DEFINITIONS = {
    'integration_owner': 'TEXT',
    'target_environment': 'TEXT',
    'priority': 'TEXT',
    'review_level': 'TEXT',
    'merge_gate_state': 'TEXT',
    'rework_reason': 'TEXT',
    'last_gate_actor': 'TEXT',
    'last_gate_decision_at': 'TEXT',
    'auto_close_policy': 'TEXT',
}


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec='seconds')


def resolve_db_path(db_path: str | os.PathLike[str] | None = None) -> Path:
    raw_value = os.fspath(db_path) if db_path is not None else os.getenv('TASK_BOARD_DB_PATH')
    path = Path(raw_value).expanduser() if raw_value else DEFAULT_DB_PATH
    if not path.is_absolute():
        path = WORKSPACE_ROOT / path
    return path.resolve()


def connect_db(
    db_path: str | os.PathLike[str] | None = None,
    *,
    initialize: bool = True,
) -> sqlite3.Connection:
    path = resolve_db_path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')
    conn.execute('PRAGMA journal_mode = WAL')
    conn.execute('PRAGMA busy_timeout = 5000')
    if initialize:
        try:
            initialize_db(conn)
        except sqlite3.OperationalError as exc:
            if 'readonly' not in str(exc).lower() or not path.exists():
                raise
    return conn


def initialize_db(conn: sqlite3.Connection) -> None:
    conn.executescript(
        '''
        CREATE TABLE IF NOT EXISTS metadata (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS tasks (
            task_id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            project TEXT,
            domain TEXT,
            assigned_agent TEXT,
            reviewer TEXT,
            owner_pm TEXT,
            integration_owner TEXT,
            parent_task_id TEXT,
            root_request_id TEXT,
            review_required INTEGER NOT NULL DEFAULT 0,
            test_required INTEGER NOT NULL DEFAULT 0,
            target_environment TEXT,
            priority TEXT,
            review_level TEXT,
            current_status TEXT,
            board_status TEXT,
            merge_gate_state TEXT,
            rework_reason TEXT,
            last_gate_actor TEXT,
            last_gate_decision_at TEXT,
            auto_close_policy TEXT,
            created_at TEXT,
            dispatched_at TEXT,
            ack_at TEXT,
            completed_at TEXT,
            review_completed_at TEXT,
            verify_completed_at TEXT,
            current_status_at TEXT,
            ack_agent TEXT,
            result_agent TEXT,
            lease_acquired_at TEXT,
            updated_at TEXT,
            summary TEXT,
            review_state TEXT,
            verify_ok INTEGER,
            task_dir TEXT NOT NULL,
            task_json_path TEXT NOT NULL,
            write_scope_json TEXT NOT NULL DEFAULT '[]',
            artifacts_json TEXT NOT NULL DEFAULT '[]',
            last_ingest_source TEXT,
            last_synced_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS task_events (
            event_key TEXT PRIMARY KEY,
            task_id TEXT NOT NULL,
            event_type TEXT NOT NULL,
            event_at TEXT,
            source TEXT NOT NULL,
            status_from TEXT,
            status_to TEXT,
            artifact_path TEXT,
            payload_json TEXT NOT NULL DEFAULT '{}',
            observed_at TEXT NOT NULL,
            FOREIGN KEY(task_id) REFERENCES tasks(task_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS communication_events (
            event_id TEXT PRIMARY KEY,
            task_id TEXT,
            thread_id TEXT,
            channel TEXT NOT NULL,
            event_type TEXT NOT NULL,
            event_class TEXT,
            source_type TEXT NOT NULL,
            from_actor TEXT,
            to_actor TEXT,
            priority TEXT,
            severity TEXT,
            message_text TEXT NOT NULL,
            reply_to TEXT,
            source_file TEXT,
            source_line INTEGER,
            source_msg_id TEXT,
            source_name TEXT,
            related_artifact_path TEXT,
            happened_at TEXT,
            observed_at TEXT NOT NULL,
            payload_json TEXT NOT NULL DEFAULT '{}'
        );

        CREATE TABLE IF NOT EXISTS chat_ingest_state (
            state_key TEXT PRIMARY KEY,
            file_path TEXT NOT NULL,
            last_line_number INTEGER NOT NULL DEFAULT 0,
            last_event_id TEXT,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS task_stage_durations (
            task_id TEXT PRIMARY KEY,
            create_to_dispatch_seconds REAL,
            dispatch_to_ack_seconds REAL,
            ack_to_result_seconds REAL,
            result_to_review_seconds REAL,
            review_to_verify_seconds REAL,
            verify_to_close_seconds REAL,
            total_cycle_seconds REAL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY(task_id) REFERENCES tasks(task_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS task_metrics_daily (
            metric_date TEXT NOT NULL,
            project TEXT,
            created_task_count INTEGER NOT NULL DEFAULT 0,
            completed_task_count INTEGER NOT NULL DEFAULT 0,
            blocked_task_count INTEGER NOT NULL DEFAULT 0,
            touched_task_count INTEGER NOT NULL DEFAULT 0,
            completion_rate REAL,
            blocked_rate REAL,
            avg_cycle_seconds REAL,
            avg_ack_to_result_seconds REAL,
            updated_at TEXT NOT NULL,
            PRIMARY KEY(metric_date, project)
        );

        CREATE TABLE IF NOT EXISTS agent_metrics_daily (
            metric_date TEXT NOT NULL,
            project TEXT,
            agent_id TEXT NOT NULL,
            active_task_count INTEGER NOT NULL DEFAULT 0,
            blocked_task_count INTEGER NOT NULL DEFAULT 0,
            ready_for_merge_count INTEGER NOT NULL DEFAULT 0,
            completed_task_count INTEGER NOT NULL DEFAULT 0,
            total_tracked_work_seconds REAL NOT NULL DEFAULT 0,
            avg_active_work_seconds REAL,
            updated_at TEXT NOT NULL,
            PRIMARY KEY(metric_date, project, agent_id)
        );

        CREATE INDEX IF NOT EXISTS ix_tasks_board_status ON tasks(board_status, current_status_at DESC);
        CREATE INDEX IF NOT EXISTS ix_tasks_assigned_agent ON tasks(assigned_agent, current_status_at DESC);
        CREATE INDEX IF NOT EXISTS ix_tasks_project_status ON tasks(project, board_status, current_status_at DESC);
        CREATE INDEX IF NOT EXISTS ix_task_events_task_time ON task_events(task_id, event_at);
        CREATE INDEX IF NOT EXISTS ix_task_events_type_time ON task_events(event_type, event_at);
        CREATE INDEX IF NOT EXISTS ix_comm_task_time ON communication_events(task_id, happened_at);
        CREATE INDEX IF NOT EXISTS ix_comm_thread_time ON communication_events(thread_id, happened_at);
        CREATE INDEX IF NOT EXISTS ix_comm_type_time ON communication_events(event_type, happened_at);
        CREATE INDEX IF NOT EXISTS ix_comm_to_time ON communication_events(to_actor, happened_at);
        CREATE INDEX IF NOT EXISTS ix_comm_severity_time ON communication_events(severity, happened_at);
        '''
    )
    existing_task_columns = {row['name'] for row in conn.execute("PRAGMA table_info(tasks)").fetchall()}
    for column, column_sql in TASK_ADDITIONAL_COLUMN_DEFINITIONS.items():
        if column not in existing_task_columns:
            conn.execute(f'ALTER TABLE tasks ADD COLUMN {column} {column_sql}')
    conn.execute(
        "INSERT INTO metadata(key, value) VALUES('schema_version', ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (str(SCHEMA_VERSION),),
    )


def _build_upsert_sql(table: str, columns: list[str], conflict_key: str) -> str:
    placeholders = ', '.join(f':{column}' for column in columns)
    update_clause = ', '.join(
        f"{column} = excluded.{column}" for column in columns if column != conflict_key
    )
    joined_columns = ', '.join(columns)
    return (
        f'INSERT INTO {table} ({joined_columns}) VALUES ({placeholders}) '
        f'ON CONFLICT({conflict_key}) DO UPDATE SET {update_clause}'
    )


TASK_UPSERT_SQL = _build_upsert_sql('tasks', TASK_COLUMNS, 'task_id')
EVENT_UPSERT_SQL = _build_upsert_sql('task_events', EVENT_COLUMNS, 'event_key')
COMMUNICATION_EVENT_UPSERT_SQL = _build_upsert_sql('communication_events', COMMUNICATION_EVENT_COLUMNS, 'event_id')
CHAT_INGEST_STATE_UPSERT_SQL = _build_upsert_sql('chat_ingest_state', CHAT_INGEST_STATE_COLUMNS, 'state_key')
TASK_STAGE_DURATION_UPSERT_SQL = _build_upsert_sql('task_stage_durations', TASK_STAGE_DURATION_COLUMNS, 'task_id')
TASK_METRICS_DAILY_UPSERT_SQL = '''
INSERT INTO task_metrics_daily (
    metric_date, project, created_task_count, completed_task_count, blocked_task_count, touched_task_count,
    completion_rate, blocked_rate, avg_cycle_seconds, avg_ack_to_result_seconds, updated_at
) VALUES (
    :metric_date, :project, :created_task_count, :completed_task_count, :blocked_task_count, :touched_task_count,
    :completion_rate, :blocked_rate, :avg_cycle_seconds, :avg_ack_to_result_seconds, :updated_at
) ON CONFLICT(metric_date, project) DO UPDATE SET
    created_task_count = excluded.created_task_count,
    completed_task_count = excluded.completed_task_count,
    blocked_task_count = excluded.blocked_task_count,
    touched_task_count = excluded.touched_task_count,
    completion_rate = excluded.completion_rate,
    blocked_rate = excluded.blocked_rate,
    avg_cycle_seconds = excluded.avg_cycle_seconds,
    avg_ack_to_result_seconds = excluded.avg_ack_to_result_seconds,
    updated_at = excluded.updated_at
'''
AGENT_METRICS_DAILY_UPSERT_SQL = '''
INSERT INTO agent_metrics_daily (
    metric_date, project, agent_id, active_task_count, blocked_task_count, ready_for_merge_count, completed_task_count,
    total_tracked_work_seconds, avg_active_work_seconds, updated_at
) VALUES (
    :metric_date, :project, :agent_id, :active_task_count, :blocked_task_count, :ready_for_merge_count, :completed_task_count,
    :total_tracked_work_seconds, :avg_active_work_seconds, :updated_at
) ON CONFLICT(metric_date, project, agent_id) DO UPDATE SET
    active_task_count = excluded.active_task_count,
    blocked_task_count = excluded.blocked_task_count,
    ready_for_merge_count = excluded.ready_for_merge_count,
    completed_task_count = excluded.completed_task_count,
    total_tracked_work_seconds = excluded.total_tracked_work_seconds,
    avg_active_work_seconds = excluded.avg_active_work_seconds,
    updated_at = excluded.updated_at
'''


def upsert_task(conn: sqlite3.Connection, task_record: Mapping[str, Any]) -> None:
    payload = {column: task_record.get(column) for column in TASK_COLUMNS}
    conn.execute(TASK_UPSERT_SQL, payload)


def upsert_event(conn: sqlite3.Connection, event_record: Mapping[str, Any]) -> None:
    payload = {column: event_record.get(column) for column in EVENT_COLUMNS}
    conn.execute(EVENT_UPSERT_SQL, payload)


def upsert_communication_event(conn: sqlite3.Connection, event_record: Mapping[str, Any]) -> None:
    payload = {column: event_record.get(column) for column in COMMUNICATION_EVENT_COLUMNS}
    conn.execute(COMMUNICATION_EVENT_UPSERT_SQL, payload)


def upsert_chat_ingest_state(conn: sqlite3.Connection, state_record: Mapping[str, Any]) -> None:
    payload = {column: state_record.get(column) for column in CHAT_INGEST_STATE_COLUMNS}
    conn.execute(CHAT_INGEST_STATE_UPSERT_SQL, payload)


def upsert_task_stage_duration(conn: sqlite3.Connection, duration_record: Mapping[str, Any]) -> None:
    payload = {column: duration_record.get(column) for column in TASK_STAGE_DURATION_COLUMNS}
    conn.execute(TASK_STAGE_DURATION_UPSERT_SQL, payload)


def upsert_task_metric_daily(conn: sqlite3.Connection, metric_record: Mapping[str, Any]) -> None:
    payload = {column: metric_record.get(column) for column in TASK_METRICS_DAILY_COLUMNS}
    conn.execute(TASK_METRICS_DAILY_UPSERT_SQL, payload)


def upsert_agent_metric_daily(conn: sqlite3.Connection, metric_record: Mapping[str, Any]) -> None:
    payload = {column: metric_record.get(column) for column in AGENT_METRICS_DAILY_COLUMNS}
    conn.execute(AGENT_METRICS_DAILY_UPSERT_SQL, payload)
