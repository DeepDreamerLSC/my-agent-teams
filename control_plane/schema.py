from __future__ import annotations

import sqlite3

CONTROL_PLANE_SCHEMA_VERSION = 1
SCHEMA_METADATA_KEY = "control_plane_schema_version"


def _current_version(conn: sqlite3.Connection) -> int:
    row = conn.execute(
        "SELECT value FROM metadata WHERE key = ?",
        (SCHEMA_METADATA_KEY,),
    ).fetchone()
    if row is None:
        return 0
    try:
        return int(row[0])
    except (TypeError, ValueError) as exc:
        raise RuntimeError(f"invalid {SCHEMA_METADATA_KEY}") from exc


def initialize_control_plane_schema(conn: sqlite3.Connection) -> None:
    """Create or migrate control-plane tables without touching legacy data."""

    conn.execute(
        "CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
    )
    current = _current_version(conn)
    if current > CONTROL_PLANE_SCHEMA_VERSION:
        raise RuntimeError(
            f"control-plane database version {current} is newer than code version "
            f"{CONTROL_PLANE_SCHEMA_VERSION}"
        )
    if current < 1:
        _migrate_to_v1(conn)
        current = 1
    conn.execute(
        "INSERT INTO metadata(key, value) VALUES(?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (SCHEMA_METADATA_KEY, str(current)),
    )


def _migrate_to_v1(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS control_plane_projects (
            project_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            repo_root TEXT NOT NULL,
            prod_root TEXT,
            default_branch TEXT NOT NULL DEFAULT 'main',
            status TEXT NOT NULL DEFAULT 'active',
            control_plane_url TEXT,
            capabilities_json TEXT NOT NULL DEFAULT '{}',
            metadata_json TEXT NOT NULL DEFAULT '{}',
            registered_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            last_check_at TEXT,
            last_error TEXT
        );

        CREATE TABLE IF NOT EXISTS control_plane_requirements (
            requirement_id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            acceptance_json TEXT NOT NULL DEFAULT '[]',
            priority TEXT NOT NULL DEFAULT 'medium',
            status TEXT NOT NULL DEFAULT 'submitted',
            current_stage TEXT NOT NULL DEFAULT 'pm_clarification',
            owner_id TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            last_error TEXT,
            FOREIGN KEY(project_id) REFERENCES control_plane_projects(project_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS control_plane_sessions (
            session_id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            requirement_id TEXT,
            task_id TEXT,
            thread_id TEXT,
            parent_thread_id TEXT,
            role TEXT NOT NULL,
            cwd TEXT,
            execution_backend TEXT NOT NULL,
            environment TEXT,
            worktree TEXT,
            branch TEXT,
            session_status TEXT NOT NULL DEFAULT 'unknown',
            current_gate TEXT,
            last_seen_at TEXT,
            last_error TEXT,
            capabilities_json TEXT NOT NULL DEFAULT '{}',
            external_ref TEXT,
            registered_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY(project_id) REFERENCES control_plane_projects(project_id) ON DELETE CASCADE,
            FOREIGN KEY(requirement_id) REFERENCES control_plane_requirements(requirement_id) ON DELETE SET NULL,
            UNIQUE(execution_backend, thread_id)
        );

        CREATE TABLE IF NOT EXISTS control_plane_session_events (
            event_id TEXT PRIMARY KEY,
            idempotency_key TEXT NOT NULL UNIQUE,
            session_id TEXT NOT NULL,
            project_id TEXT NOT NULL,
            event_type TEXT NOT NULL,
            event_at TEXT NOT NULL,
            observed_at TEXT NOT NULL,
            sequence INTEGER,
            status TEXT,
            current_gate TEXT,
            last_error TEXT,
            payload_json TEXT NOT NULL DEFAULT '{}',
            source TEXT NOT NULL DEFAULT 'unknown',
            applied INTEGER NOT NULL DEFAULT 0,
            rejection_reason TEXT,
            FOREIGN KEY(session_id) REFERENCES control_plane_sessions(session_id) ON DELETE CASCADE,
            FOREIGN KEY(project_id) REFERENCES control_plane_projects(project_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS control_plane_artifacts (
            artifact_id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            requirement_id TEXT,
            task_id TEXT,
            session_id TEXT,
            kind TEXT NOT NULL,
            uri TEXT NOT NULL,
            checksum TEXT,
            summary TEXT NOT NULL DEFAULT '',
            metadata_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL,
            FOREIGN KEY(project_id) REFERENCES control_plane_projects(project_id) ON DELETE CASCADE,
            FOREIGN KEY(requirement_id) REFERENCES control_plane_requirements(requirement_id) ON DELETE SET NULL,
            FOREIGN KEY(session_id) REFERENCES control_plane_sessions(session_id) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS control_plane_gates (
            gate_id TEXT PRIMARY KEY,
            requirement_id TEXT NOT NULL,
            task_id TEXT,
            stage TEXT NOT NULL,
            round INTEGER NOT NULL DEFAULT 1,
            status TEXT NOT NULL DEFAULT 'pending',
            required_role TEXT NOT NULL,
            entered_at TEXT NOT NULL,
            decided_at TEXT,
            actor TEXT,
            output_json TEXT NOT NULL DEFAULT '{}',
            rejection_reason TEXT,
            updated_at TEXT NOT NULL,
            FOREIGN KEY(requirement_id) REFERENCES control_plane_requirements(requirement_id) ON DELETE CASCADE,
            UNIQUE(requirement_id, stage, round)
        );

        CREATE TABLE IF NOT EXISTS control_plane_owner_decisions (
            decision_id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            requirement_id TEXT,
            task_id TEXT,
            category TEXT NOT NULL,
            summary TEXT NOT NULL,
            options_json TEXT NOT NULL DEFAULT '[]',
            impact TEXT NOT NULL DEFAULT '',
            recommendation TEXT NOT NULL DEFAULT '',
            due_at TEXT,
            status TEXT NOT NULL DEFAULT 'open',
            decision_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY(project_id) REFERENCES control_plane_projects(project_id) ON DELETE CASCADE,
            FOREIGN KEY(requirement_id) REFERENCES control_plane_requirements(requirement_id) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS control_plane_state_changes (
            change_id TEXT PRIMARY KEY,
            entity_type TEXT NOT NULL,
            entity_id TEXT NOT NULL,
            event_type TEXT NOT NULL,
            idempotency_key TEXT NOT NULL UNIQUE,
            previous_json TEXT NOT NULL DEFAULT '{}',
            next_json TEXT NOT NULL DEFAULT '{}',
            actor TEXT NOT NULL,
            source TEXT NOT NULL,
            occurred_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS control_plane_bootstraps (
            project_id TEXT PRIMARY KEY,
            target_root TEXT NOT NULL,
            manifest_json TEXT NOT NULL DEFAULT '{}',
            status TEXT NOT NULL DEFAULT 'unknown',
            last_check_at TEXT,
            last_error TEXT,
            updated_at TEXT NOT NULL,
            FOREIGN KEY(project_id) REFERENCES control_plane_projects(project_id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS ix_cp_requirements_project_status
            ON control_plane_requirements(project_id, status, updated_at DESC);
        CREATE INDEX IF NOT EXISTS ix_cp_sessions_project_status
            ON control_plane_sessions(project_id, session_status, updated_at DESC);
        CREATE INDEX IF NOT EXISTS ix_cp_sessions_requirement
            ON control_plane_sessions(requirement_id, task_id);
        CREATE INDEX IF NOT EXISTS ix_cp_session_events_session_time
            ON control_plane_session_events(session_id, event_at DESC);
        CREATE INDEX IF NOT EXISTS ix_cp_gates_requirement_stage
            ON control_plane_gates(requirement_id, stage, round DESC);
        CREATE INDEX IF NOT EXISTS ix_cp_owner_status_due
            ON control_plane_owner_decisions(status, due_at, updated_at DESC);
        CREATE INDEX IF NOT EXISTS ix_cp_state_entity_time
            ON control_plane_state_changes(entity_type, entity_id, occurred_at DESC);
        """
    )
    conn.execute(
        "INSERT INTO metadata(key, value) VALUES(?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (SCHEMA_METADATA_KEY, "1"),
    )
