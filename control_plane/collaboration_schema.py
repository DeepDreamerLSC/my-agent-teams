from __future__ import annotations

import sqlite3


COLLABORATION_SCHEMA_VERSION = 4
COLLABORATION_SCHEMA_METADATA_KEY = "collaboration_schema_version"


def initialize_collaboration_schema(conn: sqlite3.Connection) -> None:
    """Install the bounded collaboration extension in the shared SQLite DB.

    The core control-plane schema has independent migrations.  Keeping this
    extension under its own metadata key avoids colliding with unpublished
    control-plane migrations while preserving one database and one fact store.
    """

    conn.execute(
        "CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
    )
    row = conn.execute(
        "SELECT value FROM metadata WHERE key = ?",
        (COLLABORATION_SCHEMA_METADATA_KEY,),
    ).fetchone()
    current = int(row[0]) if row is not None else 0
    if current > COLLABORATION_SCHEMA_VERSION:
        raise RuntimeError(
            f"collaboration database version {current} is newer than code version "
            f"{COLLABORATION_SCHEMA_VERSION}"
        )
    if current == COLLABORATION_SCHEMA_VERSION:
        return
    if current < 1:
        _migrate_to_v1(conn)
        current = 1
    if current < 2:
        _migrate_to_v2(conn)
        current = 2
    if current < 3:
        _migrate_to_v3(conn)
        current = 3
    if current < 4:
        _migrate_to_v4(conn)
        current = 4
    conn.execute(
        "INSERT INTO metadata(key, value) VALUES(?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (COLLABORATION_SCHEMA_METADATA_KEY, str(current)),
    )


def _migrate_to_v1(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS control_plane_authorizations (
            request_id TEXT PRIMARY KEY,
            request_event_id TEXT NOT NULL UNIQUE,
            project_id TEXT NOT NULL,
            requirement_id TEXT,
            task_id TEXT NOT NULL,
            session_id TEXT NOT NULL,
            requester_json TEXT NOT NULL DEFAULT '{}',
            action TEXT,
            action_type TEXT,
            environment TEXT,
            target_scope TEXT,
            exact_targets_json TEXT NOT NULL DEFAULT '[]',
            head_sha TEXT,
            secret_refs_json TEXT NOT NULL DEFAULT '[]',
            reason TEXT NOT NULL DEFAULT '',
            reversible INTEGER,
            expires_at TEXT,
            authorization_level TEXT NOT NULL,
            risk_level TEXT NOT NULL,
            matched_rule_id TEXT,
            routing_reason TEXT NOT NULL,
            incomplete_fields_json TEXT NOT NULL DEFAULT '[]',
            policy_version TEXT NOT NULL,
            status TEXT NOT NULL,
            approver_json TEXT NOT NULL DEFAULT '{}',
            decision_reason TEXT NOT NULL DEFAULT '',
            decision_event_id TEXT,
            requested_at TEXT NOT NULL,
            decided_at TEXT,
            consumed_at TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY(session_id) REFERENCES control_plane_sessions(session_id) ON DELETE CASCADE,
            FOREIGN KEY(project_id) REFERENCES control_plane_projects(project_id) ON DELETE CASCADE,
            FOREIGN KEY(requirement_id) REFERENCES control_plane_requirements(requirement_id) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS control_plane_authorization_policy_overrides (
            rule_id TEXT PRIMARY KEY,
            enabled INTEGER NOT NULL,
            updated_by TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS ix_cp_authorizations_status_level
            ON control_plane_authorizations(status, authorization_level, requested_at DESC);
        CREATE INDEX IF NOT EXISTS ix_cp_authorizations_project_task
            ON control_plane_authorizations(project_id, task_id, requested_at DESC);
        CREATE INDEX IF NOT EXISTS ix_cp_authorizations_expiry
            ON control_plane_authorizations(status, expires_at);
        """
    )
    conn.execute(
        "INSERT INTO metadata(key, value) VALUES(?, '1') "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (COLLABORATION_SCHEMA_METADATA_KEY,),
    )


def _migrate_to_v2(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS control_plane_event_inbox (
            event_id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            session_id TEXT NOT NULL,
            event_type TEXT NOT NULL,
            entity_type TEXT NOT NULL,
            entity_id TEXT NOT NULL,
            task_id TEXT NOT NULL,
            source_task_id TEXT,
            destination_task_id TEXT,
            head_sha TEXT,
            sequence INTEGER,
            priority TEXT NOT NULL,
            requires_human INTEGER NOT NULL DEFAULT 0,
            supersedes_event_id TEXT,
            payload_digest TEXT NOT NULL,
            classification TEXT,
            route_reason TEXT NOT NULL DEFAULT '',
            route_status TEXT NOT NULL DEFAULT 'RECEIVED',
            target_task_id TEXT,
            target_role TEXT,
            focus_scope_id TEXT NOT NULL DEFAULT 'main',
            deferred_until_checkpoint TEXT,
            received_at TEXT NOT NULL,
            validated_at TEXT,
            routed_at TEXT,
            acked_at TEXT,
            escalated_at TEXT,
            ack_actor TEXT,
            ack_summary TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL,
            FOREIGN KEY(event_id) REFERENCES control_plane_session_events(event_id) ON DELETE CASCADE,
            FOREIGN KEY(session_id) REFERENCES control_plane_sessions(session_id) ON DELETE CASCADE,
            FOREIGN KEY(project_id) REFERENCES control_plane_projects(project_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS control_plane_event_routing_transitions (
            transition_id TEXT PRIMARY KEY,
            event_id TEXT NOT NULL,
            state TEXT NOT NULL,
            actor TEXT NOT NULL,
            reason TEXT NOT NULL DEFAULT '',
            detail_json TEXT NOT NULL DEFAULT '{}',
            occurred_at TEXT NOT NULL,
            FOREIGN KEY(event_id) REFERENCES control_plane_event_inbox(event_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS control_plane_focus_leases (
            scope_id TEXT PRIMARY KEY,
            project_id TEXT,
            focus_task_id TEXT,
            operation TEXT NOT NULL DEFAULT '',
            head_sha TEXT,
            critical_section INTEGER NOT NULL DEFAULT 0,
            next_safe_checkpoint TEXT,
            lease_owner TEXT NOT NULL,
            acquired_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY(project_id) REFERENCES control_plane_projects(project_id) ON DELETE SET NULL
        );

        CREATE INDEX IF NOT EXISTS ix_cp_event_inbox_status_priority
            ON control_plane_event_inbox(route_status, priority, received_at);
        CREATE INDEX IF NOT EXISTS ix_cp_event_inbox_destination
            ON control_plane_event_inbox(target_task_id, target_role, route_status, received_at);
        CREATE INDEX IF NOT EXISTS ix_cp_event_inbox_entity_head
            ON control_plane_event_inbox(entity_type, entity_id, head_sha, sequence);
        CREATE INDEX IF NOT EXISTS ix_cp_event_transitions_event_time
            ON control_plane_event_routing_transitions(event_id, occurred_at, transition_id);
        CREATE INDEX IF NOT EXISTS ix_cp_focus_expiry
            ON control_plane_focus_leases(expires_at);
        """
    )
    conn.execute(
        "INSERT INTO metadata(key, value) VALUES(?, '2') "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (COLLABORATION_SCHEMA_METADATA_KEY,),
    )


def _migrate_to_v3(conn: sqlite3.Connection) -> None:
    """Add the bounded authorization envelope without rebuilding user data."""

    existing = {
        str(row[1])
        for row in conn.execute("PRAGMA table_info(control_plane_authorizations)")
    }
    additions = {
        "authorization_kind": "TEXT NOT NULL DEFAULT 'text'",
        "source_task_id": "TEXT",
        "requester_role": "TEXT NOT NULL DEFAULT 'unknown'",
        "action_class": "TEXT",
        "command_or_action_digest": "TEXT NOT NULL DEFAULT ''",
        "capability_status": "TEXT NOT NULL DEFAULT 'text_route_available'",
        "human_required": "INTEGER NOT NULL DEFAULT 1",
        "platform_request_ref": "TEXT",
    }
    for column, declaration in additions.items():
        if column not in existing:
            conn.execute(
                f"ALTER TABLE control_plane_authorizations ADD COLUMN {column} {declaration}"
            )
    conn.execute(
        "UPDATE control_plane_authorizations SET human_required = "
        "CASE WHEN authorization_level = 'L0_AUTO' THEN 0 ELSE 1 END "
        "WHERE authorization_kind = 'text'"
    )
    conn.executescript(
        """
        CREATE INDEX IF NOT EXISTS ix_cp_authorizations_kind_capability
            ON control_plane_authorizations(authorization_kind, capability_status, status);
        CREATE INDEX IF NOT EXISTS ix_cp_authorizations_source_task
            ON control_plane_authorizations(project_id, source_task_id, requested_at DESC);
        """
    )
    conn.execute(
        "INSERT INTO metadata(key, value) VALUES(?, '3') "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (COLLABORATION_SCHEMA_METADATA_KEY,),
    )


def _migrate_to_v4(conn: sqlite3.Connection) -> None:
    """Bind deferred Inbox events to the focus task that delayed them."""

    existing = {
        str(row[1])
        for row in conn.execute("PRAGMA table_info(control_plane_event_inbox)")
    }
    if "deferred_focus_task_id" not in existing:
        conn.execute(
            "ALTER TABLE control_plane_event_inbox "
            "ADD COLUMN deferred_focus_task_id TEXT"
        )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS ix_cp_event_inbox_focus_deferred "
        "ON control_plane_event_inbox("
        "focus_scope_id, project_id, deferred_focus_task_id, "
        "deferred_until_checkpoint, route_status)"
    )
    conn.execute(
        "INSERT INTO metadata(key, value) VALUES(?, '4') "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (COLLABORATION_SCHEMA_METADATA_KEY,),
    )
