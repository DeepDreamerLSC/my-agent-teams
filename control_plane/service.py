from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping
from urllib.parse import urlparse

from .errors import (
    ControlPlaneError,
    GateConflict,
    ProjectConflict,
    ProjectNotFound,
    RequirementNotFound,
    SessionNotFound,
    UnsafePath,
)
from .backends.base import ExecutionBackend
from .models import (
    EVENT_TYPES,
    SESSION_STATUSES,
    is_relative_to,
    json_dumps,
    new_id,
    now_iso,
    resolve_path,
    row_to_dict,
)
from .workflow import OWNER_DECISION_CATEGORIES, STAGE_BY_NAME, stage_definition


class ControlPlaneService:
    """Application service for control-plane metadata and audit state.

    A caller owns the SQLite transaction. Mutations intentionally do not read
    task transcripts or write business-project files.
    """

    def __init__(self, conn: sqlite3.Connection, *, liveness_ttl_seconds: int = 180) -> None:
        self.conn = conn
        self.liveness_ttl_seconds = liveness_ttl_seconds

    # ---- projects -----------------------------------------------------
    def register_project(
        self,
        *,
        project_id: str,
        name: str,
        repo_root: str,
        prod_root: str | None = None,
        default_branch: str = "main",
        control_plane_url: str | None = None,
        capabilities: Mapping[str, Any] | None = None,
        metadata: Mapping[str, Any] | None = None,
        status: str = "active",
        actor: str = "owner",
        source: str = "api",
    ) -> dict[str, Any]:
        self._validate_identifier(project_id, "project_id")
        if not str(name).strip():
            raise ControlPlaneError("project name is required")
        root = self._validate_repo_root(repo_root)
        prod = self._validate_optional_root(prod_root, field="prod_root")
        existing = self._fetchone(
            "SELECT * FROM control_plane_projects WHERE project_id = ?", (project_id,)
        )
        owner = self._fetchone(
            "SELECT project_id FROM control_plane_projects WHERE repo_root = ? AND project_id != ?",
            (str(root), project_id),
        )
        if owner:
            raise ProjectConflict(f"repo root already registered as project {owner['project_id']}")
        now = now_iso()
        payload = {
            "project_id": project_id,
            "name": str(name).strip(),
            "repo_root": str(root),
            "prod_root": str(prod) if prod else None,
            "default_branch": str(default_branch or "main"),
            "status": str(status or "active"),
            "control_plane_url": control_plane_url,
            "capabilities_json": json_dumps(dict(capabilities or {})),
            "metadata_json": json_dumps(dict(metadata or {})),
            "registered_at": existing["registered_at"] if existing else now,
            "updated_at": now,
            "last_check_at": existing["last_check_at"] if existing else None,
            "last_error": None,
        }
        if existing and str(existing["repo_root"]) != str(root):
            raise ProjectConflict(f"project id already points to {existing['repo_root']}")
        self.conn.execute(
            """
            INSERT INTO control_plane_projects(
                project_id, name, repo_root, prod_root, default_branch, status,
                control_plane_url, capabilities_json, metadata_json, registered_at,
                updated_at, last_check_at, last_error
            ) VALUES(
                :project_id, :name, :repo_root, :prod_root, :default_branch, :status,
                :control_plane_url, :capabilities_json, :metadata_json, :registered_at,
                :updated_at, :last_check_at, :last_error
            ) ON CONFLICT(project_id) DO UPDATE SET
                name = excluded.name,
                prod_root = excluded.prod_root,
                default_branch = excluded.default_branch,
                status = excluded.status,
                control_plane_url = excluded.control_plane_url,
                capabilities_json = excluded.capabilities_json,
                metadata_json = excluded.metadata_json,
                updated_at = excluded.updated_at,
                last_error = NULL
            """,
            payload,
        )
        current = self._fetchone(
            "SELECT * FROM control_plane_projects WHERE project_id = ?", (project_id,)
        )
        self._record_change(
            entity_type="project",
            entity_id=project_id,
            event_type="registered" if not existing else "updated",
            idempotency_key=f"project:{project_id}:{payload['updated_at']}",
            previous=dict(existing or {}),
            next_value=dict(current or {}),
            actor=actor,
            source=source,
        )
        return self._project(current)

    def import_legacy_projects(self, config: Mapping[str, Any], *, actor: str = "migration") -> dict[str, Any]:
        imported: list[dict[str, Any]] = []
        skipped: list[dict[str, str]] = []
        projects = config.get("projects") or {}
        if not isinstance(projects, Mapping):
            raise ControlPlaneError("config.projects must be an object")
        for project_id, payload in projects.items():
            if not isinstance(payload, Mapping) or not payload.get("dev_root"):
                skipped.append({"project_id": str(project_id), "reason": "missing dev_root"})
                continue
            try:
                imported.append(
                    self.register_project(
                        project_id=str(project_id),
                        name=str(payload.get("name") or project_id),
                        repo_root=str(payload["dev_root"]),
                        prod_root=str(payload["prod_root"]) if payload.get("prod_root") else None,
                        default_branch=str(payload.get("target_branch") or "main"),
                        metadata={"legacy_config": True, "deploy_script": payload.get("deploy_script")},
                        actor=actor,
                        source="legacy_config",
                    )
                )
            except ControlPlaneError as exc:
                skipped.append({"project_id": str(project_id), "reason": f"{exc.code}: {exc}"})
        return {"imported": imported, "skipped": skipped}

    def get_project(self, project_id: str) -> dict[str, Any]:
        row = self._fetchone(
            "SELECT * FROM control_plane_projects WHERE project_id = ?", (project_id,)
        )
        if row is None:
            raise ProjectNotFound(project_id)
        return self._project(row)

    def list_projects(self, *, status: str | None = None) -> list[dict[str, Any]]:
        if status:
            rows = self._fetchall(
                "SELECT * FROM control_plane_projects WHERE status = ? ORDER BY name", (status,)
            )
        else:
            rows = self._fetchall("SELECT * FROM control_plane_projects ORDER BY name")
        return [self._project(row) for row in rows]

    def check_project(self, project_id: str) -> dict[str, Any]:
        project = self.get_project(project_id)
        root = Path(project["repo_root"])
        errors: list[str] = []
        if not root.is_dir():
            errors.append("repo_root_missing")
        if not (root / ".git").exists():
            errors.append("git_metadata_missing")
        now = now_iso()
        self.conn.execute(
            "UPDATE control_plane_projects SET last_check_at = ?, last_error = ?, status = ?, updated_at = ? WHERE project_id = ?",
            (now, "; ".join(errors) or None, "error" if errors else "active", now, project_id),
        )
        return {
            **self.get_project(project_id),
            "ok": not errors,
            "errors": errors,
            "checked_at": now,
        }

    # ---- requirements ------------------------------------------------
    def create_requirement(
        self,
        *,
        project_id: str,
        title: str,
        description: str = "",
        acceptance: Iterable[Any] = (),
        priority: str = "medium",
        owner_id: str | None = None,
        requirement_id: str | None = None,
        actor: str = "owner",
    ) -> dict[str, Any]:
        self.get_project(project_id)
        if not str(title).strip():
            raise ControlPlaneError("requirement title is required")
        requirement_id = requirement_id or new_id("req")
        self._validate_identifier(requirement_id, "requirement_id")
        existing = self._fetchone(
            "SELECT * FROM control_plane_requirements WHERE requirement_id = ?", (requirement_id,)
        )
        if existing:
            if existing["project_id"] != project_id or existing["title"] != title:
                raise ProjectConflict(f"requirement id already exists: {requirement_id}")
            return self._requirement(existing)
        now = now_iso()
        self.conn.execute(
            """
            INSERT INTO control_plane_requirements(
                requirement_id, project_id, title, description, acceptance_json, priority,
                status, current_stage, owner_id, created_at, updated_at, last_error
            ) VALUES(?, ?, ?, ?, ?, ?, 'submitted', 'pm_clarification', ?, ?, ?, NULL)
            """,
            (
                requirement_id,
                project_id,
                str(title).strip(),
                str(description or ""),
                json_dumps(list(acceptance)),
                str(priority or "medium"),
                owner_id,
                now,
                now,
            ),
        )
        row = self._fetchone(
            "SELECT * FROM control_plane_requirements WHERE requirement_id = ?", (requirement_id,)
        )
        self._record_change(
            entity_type="requirement",
            entity_id=requirement_id,
            event_type="submitted",
            idempotency_key=f"requirement:{requirement_id}:submitted",
            previous={},
            next_value=dict(row or {}),
            actor=actor,
            source="service",
        )
        return self._requirement(row)

    def get_requirement(self, requirement_id: str) -> dict[str, Any]:
        row = self._fetchone(
            "SELECT * FROM control_plane_requirements WHERE requirement_id = ?", (requirement_id,)
        )
        if row is None:
            raise RequirementNotFound(requirement_id)
        return self._requirement(row)

    def list_requirements(
        self, *, project_id: str | None = None, status: str | None = None
    ) -> list[dict[str, Any]]:
        clauses: list[str] = []
        args: list[Any] = []
        if project_id:
            clauses.append("project_id = ?")
            args.append(project_id)
        if status:
            clauses.append("status = ?")
            args.append(status)
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = self._fetchall(
            f"SELECT * FROM control_plane_requirements{where} ORDER BY updated_at DESC", args
        )
        return [self._requirement(row) for row in rows]

    def list_tasks(self, *, project_id: str | None = None) -> list[dict[str, Any]]:
        """Expose the existing task read model without replacing its facts."""
        clauses: list[str] = []
        args: list[Any] = []
        if project_id:
            clauses.append("project = ?")
            args.append(project_id)
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        try:
            rows = self._fetchall(
                "SELECT task_id, title, project, current_status, board_status, merge_gate_state, "
                "assigned_agent, reviewer, owner_pm, updated_at, task_dir, task_json_path "
                f"FROM tasks{where} ORDER BY updated_at DESC, task_id",
                args,
            )
        except sqlite3.OperationalError:
            return []
        return [dict(row) for row in rows]

    # ---- sessions and events ----------------------------------------
    def register_session(
        self,
        *,
        project_id: str,
        role: str,
        execution_backend: str,
        session_id: str | None = None,
        requirement_id: str | None = None,
        task_id: str | None = None,
        thread_id: str | None = None,
        parent_thread_id: str | None = None,
        cwd: str | None = None,
        environment: str | None = None,
        worktree: str | None = None,
        branch: str | None = None,
        session_status: str = "unknown",
        current_gate: str | None = None,
        capabilities: Mapping[str, Any] | None = None,
        external_ref: str | None = None,
        actor: str = "system",
    ) -> dict[str, Any]:
        project = self.get_project(project_id)
        if requirement_id:
            requirement = self.get_requirement(requirement_id)
            if requirement["project_id"] != project_id:
                raise ControlPlaneError("requirement belongs to another project", code="project_mismatch")
        self._validate_session_paths(project, cwd=cwd, worktree=worktree)
        if session_status not in SESSION_STATUSES:
            raise ControlPlaneError(f"unsupported session status: {session_status}")
        if not str(role).strip() or not str(execution_backend).strip():
            raise ControlPlaneError("role and execution_backend are required")
        session_id = session_id or new_id("session")
        existing = self._fetchone(
            "SELECT * FROM control_plane_sessions WHERE session_id = ?", (session_id,)
        )
        if existing and existing["project_id"] != project_id:
            raise ProjectConflict("session id is already registered to another project")
        if thread_id and execution_backend:
            thread_owner = self._fetchone(
                "SELECT * FROM control_plane_sessions WHERE execution_backend = ? AND thread_id = ?",
                (execution_backend, thread_id),
            )
            if thread_owner and thread_owner["session_id"] != session_id:
                if thread_owner["project_id"] != project_id:
                    raise ProjectConflict("thread is already registered to another project")
                return self._session(thread_owner)
        now = now_iso()
        payload = (
            session_id,
            project_id,
            requirement_id,
            task_id,
            thread_id,
            parent_thread_id,
            str(role),
            cwd,
            str(execution_backend),
            environment,
            worktree,
            branch,
            session_status,
            current_gate,
            None,
            None,
            json_dumps(dict(capabilities or {})),
            external_ref,
            existing["registered_at"] if existing else now,
            now,
        )
        self.conn.execute(
            """
            INSERT INTO control_plane_sessions(
                session_id, project_id, requirement_id, task_id, thread_id, parent_thread_id,
                role, cwd, execution_backend, environment, worktree, branch, session_status,
                current_gate, last_seen_at, last_error, capabilities_json, external_ref,
                registered_at, updated_at
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(session_id) DO UPDATE SET
                requirement_id = excluded.requirement_id,
                task_id = excluded.task_id,
                thread_id = excluded.thread_id,
                parent_thread_id = excluded.parent_thread_id,
                role = excluded.role,
                cwd = excluded.cwd,
                execution_backend = excluded.execution_backend,
                environment = excluded.environment,
                worktree = excluded.worktree,
                branch = excluded.branch,
                session_status = excluded.session_status,
                current_gate = excluded.current_gate,
                capabilities_json = excluded.capabilities_json,
                external_ref = excluded.external_ref,
                updated_at = excluded.updated_at
            """,
            payload,
        )
        row = self._fetchone("SELECT * FROM control_plane_sessions WHERE session_id = ?", (session_id,))
        self._record_change(
            entity_type="session",
            entity_id=session_id,
            event_type="registered" if not existing else "updated",
            idempotency_key=f"session:{session_id}:{now}",
            previous=dict(existing or {}),
            next_value=dict(row or {}),
            actor=actor,
            source="service",
        )
        return self._session(row)

    def bind_session(
        self,
        session_id: str,
        *,
        requirement_id: str | None = None,
        task_id: str | None = None,
        actor: str = "pm",
    ) -> dict[str, Any]:
        session = self._session_row(session_id)
        if requirement_id:
            requirement = self.get_requirement(requirement_id)
            if requirement["project_id"] != session["project_id"]:
                raise ControlPlaneError("requirement belongs to another project", code="project_mismatch")
        previous = dict(session)
        self.conn.execute(
            "UPDATE control_plane_sessions SET requirement_id = ?, task_id = ?, updated_at = ? WHERE session_id = ?",
            (requirement_id, task_id, now_iso(), session_id),
        )
        next_row = self._session_row(session_id)
        self._record_change(
            entity_type="session",
            entity_id=session_id,
            event_type="bound" if requirement_id or task_id else "unbound",
            idempotency_key=f"session:{session_id}:binding:{now_iso()}",
            previous=previous,
            next_value=dict(next_row),
            actor=actor,
            source="service",
        )
        return self._session(next_row)

    def list_sessions(
        self,
        *,
        project_id: str | None = None,
        requirement_id: str | None = None,
        task_id: str | None = None,
    ) -> list[dict[str, Any]]:
        clauses: list[str] = []
        args: list[Any] = []
        for field, value in (("project_id", project_id), ("requirement_id", requirement_id), ("task_id", task_id)):
            if value:
                clauses.append(f"{field} = ?")
                args.append(value)
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = self._fetchall(
            f"SELECT * FROM control_plane_sessions{where} ORDER BY updated_at DESC", args
        )
        return [self._session(row) for row in rows]

    def record_session_event(
        self,
        *,
        session_id: str,
        event_type: str,
        idempotency_key: str,
        event_id: str | None = None,
        event_at: str | None = None,
        sequence: int | None = None,
        status: str | None = None,
        current_gate: str | None = None,
        last_error: str | None = None,
        payload: Mapping[str, Any] | None = None,
        source: str = "backend",
        actor: str = "system",
    ) -> dict[str, Any]:
        if event_type not in EVENT_TYPES:
            raise ControlPlaneError(f"unsupported session event type: {event_type}")
        if not idempotency_key:
            raise ControlPlaneError("idempotency_key is required")
        if status is not None and status not in SESSION_STATUSES:
            raise ControlPlaneError(f"unsupported session status: {status}")
        session = self._session_row(session_id)
        existing_event = self._fetchone(
            "SELECT * FROM control_plane_session_events WHERE idempotency_key = ?",
            (idempotency_key,),
        )
        if existing_event:
            return {"duplicate": True, "applied": bool(existing_event["applied"]), "event": row_to_dict(existing_event), "session": self._session(session)}
        event_id = event_id or new_id("event")
        event_at = event_at or now_iso()
        previous_event = self._fetchone(
            "SELECT sequence, event_at FROM control_plane_session_events "
            "WHERE session_id = ? AND applied = 1 ORDER BY sequence DESC, event_at DESC LIMIT 1",
            (session_id,),
        )
        rejection_reason = self._out_of_order_reason(previous_event, sequence, event_at)
        applied = rejection_reason is None
        self.conn.execute(
            """
            INSERT INTO control_plane_session_events(
                event_id, idempotency_key, session_id, project_id, event_type, event_at,
                observed_at, sequence, status, current_gate, last_error, payload_json,
                source, applied, rejection_reason
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event_id,
                idempotency_key,
                session_id,
                session["project_id"],
                event_type,
                event_at,
                now_iso(),
                sequence,
                status,
                current_gate,
                last_error,
                json_dumps(dict(payload or {})),
                source,
                1 if applied else 0,
                rejection_reason,
            ),
        )
        if applied:
            previous = dict(session)
            next_status = status or session["session_status"]
            next_gate = current_gate if current_gate is not None else session["current_gate"]
            next_error = last_error if last_error is not None else session["last_error"]
            last_seen = event_at if event_type in {"heartbeat", "status", "gate_changed", "registered"} else session["last_seen_at"]
            self.conn.execute(
                "UPDATE control_plane_sessions SET session_status = ?, current_gate = ?, last_seen_at = ?, last_error = ?, updated_at = ? WHERE session_id = ?",
                (next_status, next_gate, last_seen, next_error, now_iso(), session_id),
            )
            self._record_change(
                entity_type="session",
                entity_id=session_id,
                event_type=event_type,
                idempotency_key=f"session-event:{idempotency_key}",
                previous=previous,
                next_value=dict(self._session_row(session_id)),
                actor=actor,
                source=source,
            )
        row = self._fetchone(
            "SELECT * FROM control_plane_session_events WHERE event_id = ?", (event_id,)
        )
        return {
            "duplicate": False,
            "applied": applied,
            "event": row_to_dict(row),
            "session": self.session_health(session_id),
        }

    def heartbeat(
        self,
        session_id: str,
        *,
        idempotency_key: str,
        sequence: int | None = None,
        status: str | None = None,
        capabilities: Mapping[str, Any] | None = None,
        source: str = "backend",
    ) -> dict[str, Any]:
        if capabilities is not None:
            self.conn.execute(
                "UPDATE control_plane_sessions SET capabilities_json = ?, updated_at = ? WHERE session_id = ?",
                (json_dumps(dict(capabilities)), now_iso(), session_id),
            )
        return self.record_session_event(
            session_id=session_id,
            event_type="heartbeat",
            idempotency_key=idempotency_key,
            sequence=sequence,
            status=status or "online",
            payload={"capabilities": dict(capabilities or {})},
            source=source,
        )

    def probe_session(
        self, session_id: str, backend: ExecutionBackend, *, actor: str = "system"
    ) -> dict[str, Any]:
        """Persist a backend probe without claiming more than it knows."""
        row = self._session_row(session_id)
        session = self._session(row)
        health = backend.health(session)
        status = health.status if health.status in SESSION_STATUSES else "unknown"
        return self.record_session_event(
            session_id=session_id,
            event_type="status",
            idempotency_key=f"probe:{session_id}:{now_iso()}",
            status=status,
            last_error=health.reason,
            payload={"probe": True, "backend": backend.name, "capabilities": dict(health.capabilities)},
            source=backend.name,
            actor=actor,
        )

    def session_health(self, session_id: str, *, now: str | None = None) -> dict[str, Any]:
        row = self._session_row(session_id)
        health = self._health_for_row(row, now=now)
        return {**self._session(row), **health}

    def list_session_events(self, session_id: str) -> list[dict[str, Any]]:
        self._session_row(session_id)
        rows = self._fetchall(
            "SELECT * FROM control_plane_session_events WHERE session_id = ? ORDER BY observed_at, event_id",
            (session_id,),
        )
        return [row_to_dict(row) or {} for row in rows]

    # ---- artifacts and gates ----------------------------------------
    def attach_artifact(
        self,
        *,
        project_id: str,
        kind: str,
        uri: str,
        summary: str = "",
        requirement_id: str | None = None,
        task_id: str | None = None,
        session_id: str | None = None,
        checksum: str | None = None,
        metadata: Mapping[str, Any] | None = None,
        actor: str = "system",
    ) -> dict[str, Any]:
        project = self.get_project(project_id)
        if requirement_id:
            requirement = self.get_requirement(requirement_id)
            if requirement["project_id"] != project_id:
                raise ControlPlaneError("requirement belongs to another project", code="project_mismatch")
        if session_id:
            session = self._session_row(session_id)
            if session["project_id"] != project_id:
                raise ControlPlaneError("session belongs to another project", code="project_mismatch")
        self._validate_artifact_uri(project, uri)
        artifact_id = new_id("artifact")
        now = now_iso()
        self.conn.execute(
            """
            INSERT INTO control_plane_artifacts(
                artifact_id, project_id, requirement_id, task_id, session_id, kind, uri,
                checksum, summary, metadata_json, created_at
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                artifact_id,
                project_id,
                requirement_id,
                task_id,
                session_id,
                str(kind),
                str(uri),
                checksum,
                str(summary or ""),
                json_dumps(dict(metadata or {})),
                now,
            ),
        )
        row = self._fetchone("SELECT * FROM control_plane_artifacts WHERE artifact_id = ?", (artifact_id,))
        self._record_change(
            entity_type="artifact",
            entity_id=artifact_id,
            event_type="attached",
            idempotency_key=f"artifact:{artifact_id}",
            previous={},
            next_value=dict(row or {}),
            actor=actor,
            source="service",
        )
        return row_to_dict(row) or {}

    def list_artifacts(
        self, *, project_id: str | None = None, requirement_id: str | None = None, task_id: str | None = None
    ) -> list[dict[str, Any]]:
        clauses: list[str] = []
        args: list[Any] = []
        for field, value in (("project_id", project_id), ("requirement_id", requirement_id), ("task_id", task_id)):
            if value:
                clauses.append(f"{field} = ?")
                args.append(value)
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        return [row_to_dict(row) or {} for row in self._fetchall(
            f"SELECT * FROM control_plane_artifacts{where} ORDER BY created_at DESC", args
        )]

    def decide_gate(
        self,
        *,
        requirement_id: str,
        stage: str,
        status: str,
        actor: str,
        output: Mapping[str, Any] | None = None,
        rejection_reason: str | None = None,
        task_id: str | None = None,
        round_number: int | None = None,
    ) -> dict[str, Any]:
        requirement = self.get_requirement(requirement_id)
        definition = stage_definition(stage)
        if status not in {"pending", "passed", "rejected", "blocked"}:
            raise GateConflict(f"unsupported gate status: {status}")
        if stage != requirement["current_stage"] and status != "pending":
            raise GateConflict(
                f"stage {stage} is not current stage {requirement['current_stage']}"
            )
        if status == "passed" and not isinstance(output, Mapping):
            raise GateConflict("a passed gate requires structured output")
        round_number = round_number or self._next_gate_round(requirement_id, stage)
        gate_id = new_id("gate")
        now = now_iso()
        self.conn.execute(
            """
            INSERT INTO control_plane_gates(
                gate_id, requirement_id, task_id, stage, round, status, required_role,
                entered_at, decided_at, actor, output_json, rejection_reason, updated_at
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(requirement_id, stage, round) DO UPDATE SET
                status = excluded.status,
                decided_at = excluded.decided_at,
                actor = excluded.actor,
                output_json = excluded.output_json,
                rejection_reason = excluded.rejection_reason,
                updated_at = excluded.updated_at
            """,
            (
                gate_id,
                requirement_id,
                task_id,
                stage,
                round_number,
                status,
                definition["role"],
                requirement["updated_at"] or now,
                now if status != "pending" else None,
                actor,
                json_dumps(dict(output or {})),
                rejection_reason,
                now,
            ),
        )
        if status == "passed":
            next_stage = definition["next"] or stage
            next_status = "release_ready" if stage == "release_ready" else "in_progress"
            self.conn.execute(
                "UPDATE control_plane_requirements SET current_stage = ?, status = ?, updated_at = ?, last_error = NULL WHERE requirement_id = ?",
                (next_stage, next_status, now, requirement_id),
            )
        elif status == "rejected":
            self.conn.execute(
                "UPDATE control_plane_requirements SET status = 'rework_required', updated_at = ?, last_error = ? WHERE requirement_id = ?",
                (now, rejection_reason, requirement_id),
            )
        elif status == "blocked":
            self.conn.execute(
                "UPDATE control_plane_requirements SET status = 'blocked', updated_at = ?, last_error = ? WHERE requirement_id = ?",
                (now, rejection_reason, requirement_id),
            )
        row = self._fetchone(
            "SELECT * FROM control_plane_gates WHERE requirement_id = ? AND stage = ? AND round = ?",
            (requirement_id, stage, round_number),
        )
        self._record_change(
            entity_type="gate",
            entity_id=str(row["gate_id"]),
            event_type=f"{stage}:{status}",
            idempotency_key=f"gate:{requirement_id}:{stage}:{round_number}:{status}:{now}",
            previous={"requirement": requirement},
            next_value={"gate": dict(row or {}), "requirement": self.get_requirement(requirement_id)},
            actor=actor,
            source="service",
        )
        return {"gate": row_to_dict(row), "requirement": self.get_requirement(requirement_id)}

    def list_gates(self, requirement_id: str) -> list[dict[str, Any]]:
        self.get_requirement(requirement_id)
        return [row_to_dict(row) or {} for row in self._fetchall(
            "SELECT * FROM control_plane_gates WHERE requirement_id = ? ORDER BY entered_at, stage, round",
            (requirement_id,),
        )]

    # ---- Owner decisions and overview -------------------------------
    def create_owner_decision(
        self,
        *,
        project_id: str,
        category: str,
        summary: str,
        options: Iterable[Any] = (),
        impact: str = "",
        recommendation: str = "",
        due_at: str | None = None,
        requirement_id: str | None = None,
        task_id: str | None = None,
        actor: str = "pm",
    ) -> dict[str, Any]:
        self.get_project(project_id)
        if category not in OWNER_DECISION_CATEGORIES:
            raise ControlPlaneError(f"unsupported Owner decision category: {category}")
        if not str(summary).strip():
            raise ControlPlaneError("Owner decision summary is required")
        if requirement_id:
            requirement = self.get_requirement(requirement_id)
            if requirement["project_id"] != project_id:
                raise ControlPlaneError("requirement belongs to another project", code="project_mismatch")
        decision_id = new_id("decision")
        now = now_iso()
        self.conn.execute(
            """
            INSERT INTO control_plane_owner_decisions(
                decision_id, project_id, requirement_id, task_id, category, summary,
                options_json, impact, recommendation, due_at, status, decision_json,
                created_at, updated_at
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'open', '{}', ?, ?)
            """,
            (
                decision_id,
                project_id,
                requirement_id,
                task_id,
                category,
                str(summary).strip(),
                json_dumps(list(options)),
                str(impact or ""),
                str(recommendation or ""),
                due_at,
                now,
                now,
            ),
        )
        row = self._fetchone(
            "SELECT * FROM control_plane_owner_decisions WHERE decision_id = ?", (decision_id,)
        )
        self._record_change(
            entity_type="owner_decision",
            entity_id=decision_id,
            event_type="opened",
            idempotency_key=f"owner-decision:{decision_id}",
            previous={},
            next_value=dict(row or {}),
            actor=actor,
            source="service",
        )
        return row_to_dict(row) or {}

    def list_owner_decisions(self, *, status: str = "open", project_id: str | None = None) -> list[dict[str, Any]]:
        clauses = ["status = ?"]
        args: list[Any] = [status]
        if project_id:
            clauses.append("project_id = ?")
            args.append(project_id)
        return [row_to_dict(row) or {} for row in self._fetchall(
            f"SELECT * FROM control_plane_owner_decisions WHERE {' AND '.join(clauses)} ORDER BY due_at IS NULL, due_at, updated_at DESC",
            args,
        )]

    def resolve_owner_decision(
        self, decision_id: str, *, decision: Mapping[str, Any], actor: str = "owner"
    ) -> dict[str, Any]:
        row = self._fetchone(
            "SELECT * FROM control_plane_owner_decisions WHERE decision_id = ?", (decision_id,)
        )
        if row is None:
            raise ControlPlaneError(f"unknown Owner decision: {decision_id}", code="decision_not_found")
        now = now_iso()
        self.conn.execute(
            "UPDATE control_plane_owner_decisions SET status = 'decided', decision_json = ?, updated_at = ? WHERE decision_id = ?",
            (json_dumps(dict(decision)), now, decision_id),
        )
        next_row = self._fetchone(
            "SELECT * FROM control_plane_owner_decisions WHERE decision_id = ?", (decision_id,)
        )
        self._record_change(
            entity_type="owner_decision",
            entity_id=decision_id,
            event_type="decided",
            idempotency_key=f"owner-decision:{decision_id}:decided:{now}",
            previous=dict(row),
            next_value=dict(next_row or {}),
            actor=actor,
            source="service",
        )
        return row_to_dict(next_row) or {}

    def overview(self, *, project_id: str | None = None) -> dict[str, Any]:
        projects = self.list_projects()
        if project_id:
            projects = [project for project in projects if project["project_id"] == project_id]
        requirements = self.list_requirements(project_id=project_id)
        tasks = self.list_tasks(project_id=project_id)
        sessions = self.list_sessions(project_id=project_id)
        healthy_sessions = [self._health_for_row(self._session_row(item["session_id"])) for item in sessions]
        health_by_status: dict[str, int] = {}
        for health in healthy_sessions:
            key = str(health["health"])
            health_by_status[key] = health_by_status.get(key, 0) + 1
        return {
            "generated_at": now_iso(),
            "projects": projects,
            "requirements": requirements,
            "tasks": tasks,
            "sessions": [dict(item, **health) for item, health in zip(sessions, healthy_sessions)],
            "session_health": health_by_status,
            "owner_decisions": self.list_owner_decisions(project_id=project_id),
            "artifacts": self.list_artifacts(project_id=project_id),
        }

    # ---- internals ---------------------------------------------------
    def _fetchone(self, sql: str, args: tuple[Any, ...] | list[Any] = ()) -> sqlite3.Row | None:
        return self.conn.execute(sql, args).fetchone()

    def _fetchall(self, sql: str, args: tuple[Any, ...] | list[Any] = ()) -> list[sqlite3.Row]:
        return self.conn.execute(sql, args).fetchall()

    @staticmethod
    def _validate_identifier(value: str, field: str) -> None:
        if not str(value).strip() or any(char in str(value) for char in "/\\\x00"):
            raise ControlPlaneError(f"invalid {field}")

    @staticmethod
    def _validate_repo_root(raw: str) -> Path:
        root = resolve_path(raw)
        if not root.is_dir():
            raise UnsafePath(f"repo_root is not a directory: {root}")
        if not (root / ".git").exists():
            raise UnsafePath(f"repo_root is not a Git project: {root}")
        return root

    @staticmethod
    def _validate_optional_root(raw: str | None, *, field: str) -> Path | None:
        if not raw:
            return None
        root = resolve_path(raw)
        if not root.is_dir():
            raise UnsafePath(f"{field} is not a directory: {root}")
        return root

    def _validate_session_paths(self, project: Mapping[str, Any], *, cwd: str | None, worktree: str | None) -> None:
        allowed = [Path(project["repo_root"])]
        metadata = self._json_field(project.get("metadata"), {})
        for raw in metadata.get("allowed_roots", []) if isinstance(metadata, Mapping) else []:
            allowed.append(resolve_path(str(raw)))
        for field, raw in (("cwd", cwd), ("worktree", worktree)):
            if not raw:
                continue
            candidate = resolve_path(raw)
            if not any(is_relative_to(candidate, root) for root in allowed):
                raise UnsafePath(f"{field} is outside registered project roots: {candidate}")

    def _validate_artifact_uri(self, project: Mapping[str, Any], uri: str) -> None:
        parsed = urlparse(str(uri))
        if parsed.scheme and parsed.scheme not in {"file"}:
            return
        raw_path = parsed.path if parsed.scheme == "file" else str(uri)
        candidate = resolve_path(raw_path)
        allowed = [Path(project["repo_root"])]
        metadata = self._json_field(project.get("metadata"), {})
        for raw in metadata.get("allowed_roots", []) if isinstance(metadata, Mapping) else []:
            allowed.append(resolve_path(str(raw)))
        if not any(is_relative_to(candidate, root) for root in allowed):
            raise UnsafePath(f"artifact uri is outside registered project roots: {candidate}")

    def _session_row(self, session_id: str) -> sqlite3.Row:
        row = self._fetchone(
            "SELECT * FROM control_plane_sessions WHERE session_id = ?", (session_id,)
        )
        if row is None:
            raise SessionNotFound(session_id)
        return row

    @staticmethod
    def _json_field(value: Any, default: Any) -> Any:
        if isinstance(value, Mapping):
            return value
        try:
            parsed = json.loads(value or "")
            return parsed if parsed is not None else default
        except (TypeError, ValueError):
            return default

    def _project(self, row: sqlite3.Row | None) -> dict[str, Any]:
        value = row_to_dict(row) or {}
        value["capabilities"] = self._json_field(value.get("capabilities"), {})
        value["metadata"] = self._json_field(value.get("metadata"), {})
        return value

    def _requirement(self, row: sqlite3.Row | None) -> dict[str, Any]:
        value = row_to_dict(row) or {}
        value["acceptance"] = value.get("acceptance") if isinstance(value.get("acceptance"), list) else []
        return value

    def _session(self, row: sqlite3.Row | None) -> dict[str, Any]:
        value = row_to_dict(row) or {}
        value["capabilities"] = value.get("capabilities") if isinstance(value.get("capabilities"), Mapping) else {}
        return value

    @staticmethod
    def _out_of_order_reason(previous: sqlite3.Row | None, sequence: int | None, event_at: str) -> str | None:
        if previous is None:
            return None
        if sequence is not None and previous["sequence"] is not None and sequence <= previous["sequence"]:
            return "out_of_order_sequence"
        if sequence is None and str(event_at) < str(previous["event_at"]):
            return "out_of_order_timestamp"
        return None

    def _health_for_row(self, row: sqlite3.Row, *, now: str | None = None) -> dict[str, Any]:
        current = str(row["session_status"] or "unknown")
        if current == "unsupported":
            return {"health": "unsupported", "health_reason": "backend capability unavailable", "age_seconds": None}
        if current == "unknown":
            return {"health": "unknown", "health_reason": row["last_error"] or "backend state is unknown", "age_seconds": None}
        last_seen = row["last_seen_at"]
        if not last_seen:
            return {"health": "unknown", "health_reason": "no accepted heartbeat", "age_seconds": None}
        try:
            observed = datetime.fromisoformat(str(last_seen).replace("Z", "+00:00"))
            reference = datetime.fromisoformat(str(now or now_iso()).replace("Z", "+00:00"))
            age = max(0.0, (reference - observed).total_seconds())
        except ValueError:
            return {"health": "unknown", "health_reason": "invalid last_seen_at", "age_seconds": None}
        if current in {"ended", "offline", "error", "blocked", "waiting_approval"}:
            return {"health": current, "health_reason": row["last_error"] or current, "age_seconds": age}
        if age > self.liveness_ttl_seconds:
            return {"health": "offline", "health_reason": "heartbeat_expired", "age_seconds": age}
        return {"health": "online", "health_reason": None, "age_seconds": age}

    def _next_gate_round(self, requirement_id: str, stage: str) -> int:
        row = self._fetchone(
            "SELECT COALESCE(MAX(round), 0) + 1 AS next_round FROM control_plane_gates WHERE requirement_id = ? AND stage = ?",
            (requirement_id, stage),
        )
        return int(row["next_round"] if row else 1)

    def _record_change(
        self,
        *,
        entity_type: str,
        entity_id: str,
        event_type: str,
        idempotency_key: str,
        previous: Mapping[str, Any],
        next_value: Mapping[str, Any],
        actor: str,
        source: str,
    ) -> None:
        self.conn.execute(
            """
            INSERT INTO control_plane_state_changes(
                change_id, entity_type, entity_id, event_type, idempotency_key,
                previous_json, next_json, actor, source, occurred_at
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(idempotency_key) DO NOTHING
            """,
            (
                new_id("change"),
                entity_type,
                entity_id,
                event_type,
                idempotency_key,
                json_dumps(dict(previous)),
                json_dumps(dict(next_value)),
                actor,
                source,
                now_iso(),
            ),
        )
