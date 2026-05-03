from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = WORKSPACE_ROOT / '.omx' / 'task-board' / 'task-board.sqlite3'
SCHEMA_VERSION = 2

TASK_COLUMNS = [
    'task_id',
    'title',
    'project',
    'domain',
    'assigned_agent',
    'reviewer',
    'owner_pm',
    'parent_task_id',
    'root_request_id',
    'review_required',
    'test_required',
    'current_status',
    'board_status',
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
            parent_task_id TEXT,
            root_request_id TEXT,
            review_required INTEGER NOT NULL DEFAULT 0,
            test_required INTEGER NOT NULL DEFAULT 0,
            current_status TEXT,
            board_status TEXT,
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
