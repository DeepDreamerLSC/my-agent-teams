from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping

from .authorization import (
    CODEX_PLATFORM_AUTHORIZATION,
    PLATFORM_MANUAL_REQUIRED,
    AuthorizationService,
)
from .authorization_policy import L0_AUTO, L1_REVIEWER_COORDINATOR, L2_OWNER
from .collaboration_schema import initialize_collaboration_schema
from .errors import ControlPlaneError
from .models import json_dumps, json_loads, now_iso
from .service import ControlPlaneService


IMMEDIATE_ESCALATE = "immediate_escalate"
ROUTE_DEFERRED = "route_deferred"
DASHBOARD_ONLY = "dashboard_only"

ROUTE_STATUSES = {"RECEIVED", "VALIDATED", "ROUTED", "ACKED", "ESCALATED"}
PRIORITY_ORDER = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
SAFE_CHECKPOINTS = {"commit", "test", "push", "pr_created", "idle", "manual"}
ROUTABLE_EVENT_TYPES = {"CHANGES_REQUESTED", "FIX_READY", "APPROVED", "TASK_COMPLETED"}
CURRENT_ACTION_INVALIDATORS = {"CHANGES_REQUESTED", "FIX_READY", "GATE_BLOCKED"}
OLD_HEAD_INVALIDATED_TYPES = {
    "APPROVED",
    "TASK_BLOCKED",
    "GATE_BLOCKED",
    "MERGE_GATE_RUNNING",
    "MERGE_READY",
}
IMMEDIATE_EVENT_TYPES = {"USER_INSTRUCTION", "SECURITY_ALERT"}
TARGET_ROLE = {
    "CHANGES_REQUESTED": "developer",
    "FIX_READY": "reviewer",
    "APPROVED": "coordinator",
    "TASK_COMPLETED": "coordinator",
}


def _parse_time(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _latest_iso(*values: Any) -> str:
    candidates = [datetime.now(timezone.utc)]
    candidates.extend(parsed for value in values if (parsed := _parse_time(value)))
    return max(candidates).isoformat(timespec="microseconds")


def _safe_detail(value: Mapping[str, Any] | None) -> dict[str, Any]:
    value = value if isinstance(value, Mapping) else {}
    return {
        str(key)[:100]: str(item)[:500]
        for key, item in value.items()
        if key in {"classification", "target_task_id", "target_role", "checkpoint", "status"}
    }


class EventRouter:
    """Persist and route safe event projections without granting authority."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn
        initialize_collaboration_schema(conn)

    def accept(
        self,
        event: Mapping[str, Any],
        *,
        duplicate: bool = False,
        focus_scope_id: str = "main",
    ) -> dict[str, Any]:
        self._begin_immediate()
        payload = event.get("payload") if isinstance(event.get("payload"), Mapping) else {}
        event_id = str(event.get("event_id") or payload.get("event_id") or "")
        if not event_id:
            raise ControlPlaneError("router event_id is required", code="router_event_invalid")
        existing = self._row(event_id)
        if duplicate:
            if existing is not None:
                self._transition(
                    event_id,
                    "DEDUPED",
                    actor="router",
                    reason="duplicate_delivery_no_second_action",
                )
                return self.get(event_id)
            # Recover a transaction where the durable session event committed before
            # inbox projection; the event remains idempotent because event_id is the key.
            duplicate = False
        if existing is not None:
            return self.get(event_id)

        required = {
            "project_id": payload.get("project_id"),
            "session_id": payload.get("session_id"),
            "event_type": payload.get("event_type"),
            "entity_type": payload.get("entity_type"),
            "entity_id": payload.get("entity_id"),
            "task_id": payload.get("task_id"),
            "payload_digest": payload.get("payload_digest"),
        }
        missing = [key for key, value in required.items() if not value]
        if missing:
            raise ControlPlaneError(
                "router event is missing fields: " + ", ".join(missing),
                code="router_event_invalid",
            )
        received_at = now_iso()
        revision = payload.get("revision") if isinstance(payload.get("revision"), Mapping) else {}
        self.conn.execute(
            """
            INSERT INTO control_plane_event_inbox(
                event_id, project_id, session_id, event_type, entity_type, entity_id,
                task_id, source_task_id, destination_task_id, head_sha, sequence,
                priority, requires_human, supersedes_event_id, payload_digest,
                route_status, focus_scope_id, received_at, updated_at
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'RECEIVED', ?, ?, ?)
            """,
            (
                event_id,
                required["project_id"],
                required["session_id"],
                required["event_type"],
                required["entity_type"],
                required["entity_id"],
                required["task_id"],
                payload.get("source_task_id"),
                payload.get("destination_task_id"),
                revision.get("head_sha"),
                payload.get("sequence"),
                payload.get("priority") or "P3",
                1 if payload.get("requires_human") else 0,
                payload.get("supersedes_event_id"),
                required["payload_digest"],
                focus_scope_id,
                received_at,
                received_at,
            ),
        )
        self._transition(event_id, "RECEIVED", actor="router", reason="persisted_safe_projection")
        self.conn.execute(
            "UPDATE control_plane_event_inbox SET route_status = 'VALIDATED', validated_at = ?, updated_at = ? WHERE event_id = ?",
            (received_at, received_at, event_id),
        )
        self._transition(event_id, "VALIDATED", actor="router", reason="contract_and_scope_validated")
        self._transition(event_id, "DEDUPED", actor="router", reason="unique_event_id")

        if not bool(event.get("applied")):
            reason = str(event.get("rejection_reason") or "event_not_applied")
            return self._dashboard_ack(event_id, reason=f"audit_only:{reason}")

        supersedes = str(payload.get("supersedes_event_id") or "")
        if supersedes:
            self._invalidate_event(supersedes, invalidated_by=event_id)
        if required["event_type"] in {"FIX_READY", "CHANGES_REQUESTED"} and revision.get("head_sha"):
            self._invalidate_old_head(payload)

        classification, reason, target_task_id, target_role = self._classify(
            payload, focus_scope_id=focus_scope_id
        )
        self.conn.execute(
            """
            UPDATE control_plane_event_inbox
               SET classification = ?, route_reason = ?, target_task_id = ?,
                   target_role = ?, requires_human = ?, updated_at = ?
             WHERE event_id = ?
            """,
            (
                classification,
                reason,
                target_task_id,
                target_role,
                1 if classification == IMMEDIATE_ESCALATE else int(bool(payload.get("requires_human"))),
                now_iso(),
                event_id,
            ),
        )
        if classification == IMMEDIATE_ESCALATE:
            return self._escalate(event_id, reason=reason)
        if classification == DASHBOARD_ONLY:
            return self._dashboard_ack(event_id, reason=reason)

        focus = self._active_focus_for_project(
            focus_scope_id, str(required["project_id"])
        )
        if focus is not None:
            checkpoint = str(focus.get("next_safe_checkpoint") or "manual").lower()
            self.conn.execute(
                "UPDATE control_plane_event_inbox SET deferred_until_checkpoint = ?, "
                "deferred_focus_task_id = ?, updated_at = ? WHERE event_id = ?",
                (checkpoint, focus["focus_task_id"], now_iso(), event_id),
            )
            return self.get(event_id)
        return self._route(event_id, reason="coordinator_idle")

    def get(self, event_id: str) -> dict[str, Any]:
        row = self._row(event_id)
        if row is None:
            raise ControlPlaneError(
                f"unknown inbox event: {event_id}", code="inbox_event_not_found"
            )
        value = dict(row)
        value["requires_human"] = bool(value["requires_human"])
        value["trace"] = [
            {
                **dict(item),
                "detail": json_loads(item["detail_json"], {}),
            }
            for item in self.conn.execute(
                "SELECT transition_id, event_id, state, actor, reason, detail_json, occurred_at "
                "FROM control_plane_event_routing_transitions WHERE event_id = ? "
                "ORDER BY occurred_at, rowid",
                (event_id,),
            ).fetchall()
        ]
        for item in value["trace"]:
            item.pop("detail_json", None)
        return value

    def list_inbox(
        self,
        *,
        project_id: str | None = None,
        target_task_id: str | None = None,
        target_role: str | None = None,
        route_status: str | None = None,
        classification: str | None = None,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        clauses: list[str] = []
        args: list[Any] = []
        for field, value in (
            ("project_id", project_id),
            ("target_task_id", target_task_id),
            ("target_role", target_role),
            ("route_status", route_status),
            ("classification", classification),
        ):
            if value:
                clauses.append(f"{field} = ?")
                args.append(value)
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = self.conn.execute(
            "SELECT * FROM control_plane_event_inbox"
            f"{where} ORDER BY CASE priority WHEN 'P0' THEN 0 WHEN 'P1' THEN 1 "
            "WHEN 'P2' THEN 2 ELSE 3 END, received_at LIMIT ?",
            [*args, max(1, min(int(limit), 1000))],
        ).fetchall()
        return [self.get(str(row["event_id"])) for row in rows]

    def summary(self, *, project_id: str | None = None) -> dict[str, Any]:
        clauses = ["route_status IN ('RECEIVED', 'VALIDATED', 'ROUTED', 'ESCALATED')"]
        args: list[Any] = []
        if project_id:
            clauses.append("project_id = ?")
            args.append(project_id)
        rows = self.conn.execute(
            f"SELECT * FROM control_plane_event_inbox WHERE {' AND '.join(clauses)}",
            args,
        ).fetchall()
        priorities = sorted(
            (str(row["priority"]) for row in rows), key=lambda value: PRIORITY_ORDER.get(value, 9)
        )
        oldest = min((_parse_time(row["received_at"]) for row in rows), default=None)
        now = datetime.now(timezone.utc)
        return {
            "pending_count": len(rows),
            "highest_priority": priorities[0] if priorities else None,
            "oldest_wait_seconds": max(0, int((now - oldest).total_seconds())) if oldest else None,
            "routed_count": sum(1 for row in rows if row["route_status"] == "ROUTED"),
            "human_required_count": sum(1 for row in rows if row["route_status"] == "ESCALATED"),
            "deferred_count": sum(1 for row in rows if row["route_status"] == "VALIDATED"),
        }

    def acknowledge(
        self, event_id: str, *, actor: str, summary: str = ""
    ) -> dict[str, Any]:
        self._begin_immediate()
        if not str(actor).strip():
            raise ControlPlaneError("ACK actor is required", code="inbox_ack_actor_required")
        current = self.get(event_id)
        if current["route_status"] == "ACKED":
            return current
        if current["route_status"] not in {"ROUTED", "ESCALATED"}:
            raise ControlPlaneError(
                f"event is not ACK-able from {current['route_status']}",
                code="inbox_ack_invalid_state",
            )
        at = now_iso()
        self.conn.execute(
            "UPDATE control_plane_event_inbox SET route_status = 'ACKED', acked_at = ?, "
            "ack_actor = ?, ack_summary = ?, updated_at = ? WHERE event_id = ?",
            (at, str(actor)[:160], str(summary or "")[:500], at, event_id),
        )
        self._transition(event_id, "ACKED", actor=str(actor), reason="destination_ack")
        result = self.get(event_id)
        self._emit_router_event(result, "INBOX_ACKED")
        return result

    def set_focus(
        self,
        *,
        scope_id: str,
        lease_owner: str,
        project_id: str | None,
        focus_task_id: str | None,
        operation: str,
        head_sha: str | None,
        critical_section: bool,
        next_safe_checkpoint: str | None,
        expires_at: str | None = None,
    ) -> dict[str, Any]:
        self._begin_immediate()
        if not scope_id or not lease_owner or not project_id or not focus_task_id:
            raise ControlPlaneError(
                "scope_id, lease_owner, project_id, and focus_task_id are required",
                code="focus_lease_invalid",
            )
        normalized_checkpoint = str(next_safe_checkpoint or "manual").lower()
        if normalized_checkpoint not in SAFE_CHECKPOINTS:
            raise ControlPlaneError(
                "unsupported next safe checkpoint", code="safe_checkpoint_invalid"
            )
        expiry = _parse_time(expires_at) if expires_at else datetime.now(timezone.utc) + timedelta(minutes=30)
        if expiry is None or expiry <= datetime.now(timezone.utc):
            raise ControlPlaneError(
                "focus lease expires_at must be in the future", code="focus_lease_invalid"
            )
        project = self.conn.execute(
            "SELECT 1 FROM control_plane_projects WHERE project_id = ?", (project_id,)
        ).fetchone()
        if project is None:
            raise ControlPlaneError(
                f"unknown project: {project_id}", code="project_not_found"
            )
        task = self.conn.execute(
            "SELECT 1 FROM control_plane_sessions WHERE project_id = ? AND task_id = ? "
            "LIMIT 1",
            (project_id, focus_task_id),
        ).fetchone()
        if task is None:
            raise ControlPlaneError(
                "focus task is not registered in the selected project",
                code="focus_task_not_found",
            )
        now = now_iso()
        self.conn.execute(
            """
            INSERT INTO control_plane_focus_leases(
                scope_id, project_id, focus_task_id, operation, head_sha,
                critical_section, next_safe_checkpoint, lease_owner,
                acquired_at, expires_at, updated_at
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(scope_id) DO UPDATE SET
                project_id = excluded.project_id,
                focus_task_id = excluded.focus_task_id,
                operation = excluded.operation,
                head_sha = excluded.head_sha,
                critical_section = excluded.critical_section,
                next_safe_checkpoint = excluded.next_safe_checkpoint,
                lease_owner = excluded.lease_owner,
                acquired_at = excluded.acquired_at,
                expires_at = excluded.expires_at,
                updated_at = excluded.updated_at
            """,
            (
                scope_id,
                project_id,
                focus_task_id,
                str(operation or "")[:200],
                str(head_sha or "")[:80] or None,
                1 if critical_section else 0,
                normalized_checkpoint,
                str(lease_owner)[:160],
                now,
                expiry.isoformat(timespec="microseconds"),
                now,
            ),
        )
        return self.get_focus(scope_id)

    def get_focus(self, scope_id: str = "main") -> dict[str, Any]:
        row = self.conn.execute(
            "SELECT * FROM control_plane_focus_leases WHERE scope_id = ?", (scope_id,)
        ).fetchone()
        if row is None:
            return {"scope_id": scope_id, "active": False, "lease": None}
        lease = dict(row)
        lease["critical_section"] = bool(lease["critical_section"])
        active = bool(
            lease.get("project_id")
            and lease.get("focus_task_id")
            and _parse_time(lease["expires_at"])
            and _parse_time(lease["expires_at"]) > datetime.now(timezone.utc)
        )
        return {"scope_id": scope_id, "active": active, "lease": lease}

    def release_focus(self, scope_id: str, *, actor: str) -> dict[str, Any]:
        self._begin_immediate()
        current = self.get_focus(scope_id)
        lease = current.get("lease") or {}
        now = now_iso()
        self.conn.execute(
            "UPDATE control_plane_focus_leases SET critical_section = 0, expires_at = ?, "
            "next_safe_checkpoint = 'idle', updated_at = ? WHERE scope_id = ?",
            (now, now, scope_id),
        )
        if lease.get("project_id") and lease.get("focus_task_id"):
            self.conn.execute(
                "UPDATE control_plane_event_inbox SET deferred_until_checkpoint = 'idle', "
                "updated_at = ? WHERE focus_scope_id = ? AND project_id = ? "
                "AND deferred_focus_task_id = ? AND classification = ? "
                "AND route_status = 'VALIDATED'",
                (
                    now,
                    scope_id,
                    lease["project_id"],
                    lease["focus_task_id"],
                    ROUTE_DEFERRED,
                ),
            )
            drained = self.drain(scope_id=scope_id, checkpoint="idle", actor=actor)
        else:
            drained = {"scope_id": scope_id, "checkpoint": "idle", "routed": []}
        return {"focus": self.get_focus(scope_id), "drained": drained}

    def drain(self, *, scope_id: str, checkpoint: str, actor: str) -> dict[str, Any]:
        self._begin_immediate()
        normalized = str(checkpoint or "").lower()
        if normalized not in SAFE_CHECKPOINTS:
            raise ControlPlaneError(
                "unsupported safe checkpoint", code="safe_checkpoint_invalid"
            )
        focus = self.get_focus(scope_id)
        lease = focus.get("lease") or {}
        project_id = str(lease.get("project_id") or "")
        focus_task_id = str(lease.get("focus_task_id") or "")
        if not project_id or not focus_task_id:
            raise ControlPlaneError(
                "checkpoint drain requires a project-bound focus task",
                code="focus_lease_invalid",
            )
        rows = self.conn.execute(
            "SELECT event_id FROM control_plane_event_inbox WHERE focus_scope_id = ? "
            "AND project_id = ? AND deferred_focus_task_id = ? "
            "AND deferred_until_checkpoint = ? AND classification = ? "
            "AND route_status = 'VALIDATED' ORDER BY received_at",
            (
                scope_id,
                project_id,
                focus_task_id,
                normalized,
                ROUTE_DEFERRED,
            ),
        ).fetchall()
        routed = [
            self._route(
                str(row["event_id"]),
                reason=f"safe_checkpoint:{normalized}",
                actor=actor,
            )
            for row in rows
        ]
        self.conn.execute(
            "UPDATE control_plane_focus_leases SET next_safe_checkpoint = ?, updated_at = ? "
            "WHERE scope_id = ? AND project_id = ? AND focus_task_id = ?",
            (normalized, now_iso(), scope_id, project_id, focus_task_id),
        )
        return {
            "scope_id": scope_id,
            "project_id": project_id,
            "focus_task_id": focus_task_id,
            "checkpoint": normalized,
            "routed": routed,
        }

    def _classify(
        self, payload: Mapping[str, Any], *, focus_scope_id: str
    ) -> tuple[str, str, str | None, str | None]:
        event_type = str(payload.get("event_type") or "")
        priority = str(payload.get("priority") or "P3")
        metadata = payload.get("metadata") if isinstance(payload.get("metadata"), Mapping) else {}
        focus = self.get_focus(focus_scope_id)
        lease = focus.get("lease") or {}
        focus_matches_project = bool(
            focus["active"] and lease.get("project_id") == payload.get("project_id")
        )
        task_id = str(payload.get("task_id") or "")
        if event_type == "AUTHORIZATION_REQUESTED":
            authorization = payload.get("authorization") if isinstance(payload.get("authorization"), Mapping) else {}
            routing = authorization.get("routing") if isinstance(authorization.get("routing"), Mapping) else {}
            level = routing.get("level")
            if (
                authorization.get("authorization_kind") == CODEX_PLATFORM_AUTHORIZATION
                or authorization.get("capability_status") == PLATFORM_MANUAL_REQUIRED
            ):
                return (
                    IMMEDIATE_ESCALATE,
                    "Codex native sandbox/tool approval has no cross-task approve API; Owner must click in the platform",
                    None,
                    None,
                )
            if level == L0_AUTO:
                source_task_id = str(
                    authorization.get("source_task_id")
                    or payload.get("source_task_id")
                    or payload.get("task_id")
                    or ""
                )
                requester_role = str(
                    authorization.get("requester_role")
                    or (payload.get("actor") or {}).get("role")
                    or "requester"
                )
                source = self.conn.execute(
                    "SELECT 1 FROM control_plane_sessions WHERE project_id = ? "
                    "AND task_id = ? LIMIT 1",
                    (payload.get("project_id"), source_task_id),
                ).fetchone()
                if source is None:
                    return (
                        IMMEDIATE_ESCALATE,
                        "L0 authorization source task has no registered session",
                        None,
                        None,
                    )
                return (
                    ROUTE_DEFERRED,
                    "L0 policy decision returned to the original source task",
                    source_task_id,
                    requester_role,
                )
            if level == L1_REVIEWER_COORDINATOR:
                target = self._resolve_target(payload, preferred_role="reviewer")
                if target is None:
                    return IMMEDIATE_ESCALATE, "authorization recipient is not deterministic", None, None
                return ROUTE_DEFERRED, "L1 authorization routed to delegated reviewer/coordinator", *target
            return IMMEDIATE_ESCALATE, "L2 or unknown authorization requires Owner decision", None, None
        if payload.get("requires_human"):
            return IMMEDIATE_ESCALATE, "event explicitly requires a human decision", None, None
        if priority == "P0" or event_type in IMMEDIATE_EVENT_TYPES:
            return IMMEDIATE_ESCALATE, "P0, security, or user instruction requires immediate attention", None, None
        if str(metadata.get("routing_policy") or "").lower() == "manual_only" or bool(metadata.get("manual_only")):
            return IMMEDIATE_ESCALATE, "manual_only event cannot be auto-routed", None, None
        if focus_matches_project and lease.get("focus_task_id") == task_id and event_type in CURRENT_ACTION_INVALIDATORS:
            return IMMEDIATE_ESCALATE, "current focus HEAD or gate was invalidated", None, None
        if event_type in ROUTABLE_EVENT_TYPES:
            target = self._resolve_target(payload, preferred_role=TARGET_ROLE[event_type])
            if target is None:
                return IMMEDIATE_ESCALATE, "event recipient cannot be determined safely", None, None
            return ROUTE_DEFERRED, f"{event_type} routed to explicit {target[1]}", *target
        return DASHBOARD_ONLY, "progress or unchanged state remains on the dashboard", "dashboard", "dashboard"

    def route_authorization_decision_to_source(
        self,
        event_id: str,
        *,
        actor: str,
        decision_status: str,
    ) -> dict[str, Any]:
        """Return an exact decision to the source task and wait for its ACK."""

        self._begin_immediate()
        current = self.get(event_id)
        target_task_id = str(current.get("source_task_id") or current.get("task_id") or "")
        if not target_task_id:
            return self._escalate(
                event_id,
                reason="authorization source task is missing; decision cannot be guessed",
            )
        source = self.conn.execute(
            "SELECT 1 FROM control_plane_sessions WHERE project_id = ? AND task_id = ? "
            "LIMIT 1",
            (current["project_id"], target_task_id),
        ).fetchone()
        if source is None:
            return self._escalate(
                event_id,
                reason="authorization source task has no registered session; decision requires human recovery",
            )
        if (
            current["route_status"] == "ROUTED"
            and current.get("target_task_id") == target_task_id
            and current.get("ack_summary") != ""
        ):
            return current
        at = now_iso()
        reason = f"authorization_decision:{str(decision_status).upper()}"
        self.conn.execute(
            """
            UPDATE control_plane_event_inbox
               SET classification = ?, route_reason = ?, route_status = 'ROUTED',
                   target_task_id = ?, target_role = 'requester', requires_human = 0,
                   deferred_until_checkpoint = NULL, deferred_focus_task_id = NULL,
                   routed_at = ?, acked_at = NULL,
                   ack_actor = NULL, ack_summary = '', updated_at = ?
             WHERE event_id = ?
            """,
            (ROUTE_DEFERRED, reason, target_task_id, at, at, event_id),
        )
        self._transition(
            event_id,
            "ROUTED",
            actor=actor,
            reason=reason,
            detail={
                "target_task_id": target_task_id,
                "target_role": "requester",
                "status": str(decision_status).upper(),
            },
        )
        result = self.get(event_id)
        self._emit_router_event(result, "INBOX_ROUTED")
        return result

    def _resolve_target(
        self, payload: Mapping[str, Any], *, preferred_role: str
    ) -> tuple[str, str] | None:
        project_id = str(payload.get("project_id") or "")
        task_id = str(payload.get("destination_task_id") or "")
        destination = payload.get("destination") if isinstance(payload.get("destination"), Mapping) else {}
        destination_session_id = str(destination.get("session_id") or "")
        if not task_id:
            task_id = str(destination.get("task_id") or "")
        if task_id:
            clauses = ["project_id = ?", "task_id = ?", "role = ?"]
            args: list[Any] = [project_id, task_id, preferred_role]
            if destination_session_id:
                clauses.append("session_id = ?")
                args.append(destination_session_id)
            row = self.conn.execute(
                "SELECT task_id FROM control_plane_sessions WHERE "
                + " AND ".join(clauses)
                + " ORDER BY updated_at DESC LIMIT 1",
                args,
            ).fetchone()
            if row is not None:
                return str(row["task_id"]), preferred_role
            return None
        if destination_session_id:
            row = self.conn.execute(
                "SELECT task_id FROM control_plane_sessions WHERE project_id = ? "
                "AND session_id = ? AND role = ? LIMIT 1",
                (project_id, destination_session_id, preferred_role),
            ).fetchone()
            if row is not None and row["task_id"]:
                return str(row["task_id"]), preferred_role
        if preferred_role == "coordinator":
            row = self.conn.execute(
                "SELECT task_id FROM control_plane_sessions WHERE project_id = ? "
                "AND role IN ('coordinator', 'pm', 'owner') ORDER BY updated_at DESC LIMIT 1",
                (project_id,),
            ).fetchone()
            if row is not None and row["task_id"]:
                return str(row["task_id"]), "coordinator"
        return None

    def _active_focus_for_project(
        self, scope_id: str, project_id: str
    ) -> dict[str, Any] | None:
        focus = self.get_focus(scope_id)
        lease = focus.get("lease") or {}
        if not focus["active"] or str(lease.get("project_id") or "") != project_id:
            return None
        if not lease.get("focus_task_id"):
            return None
        return lease

    def _route(
        self, event_id: str, *, reason: str, actor: str = "router"
    ) -> dict[str, Any]:
        current = self.get(event_id)
        if current["route_status"] == "ROUTED":
            return current
        if current["route_status"] != "VALIDATED":
            raise ControlPlaneError(
                f"event cannot route from {current['route_status']}",
                code="inbox_route_invalid_state",
            )
        at = now_iso()
        self.conn.execute(
            "UPDATE control_plane_event_inbox SET route_status = 'ROUTED', routed_at = ?, "
            "deferred_until_checkpoint = NULL, deferred_focus_task_id = NULL, "
            "route_reason = ?, updated_at = ? WHERE event_id = ?",
            (at, reason, at, event_id),
        )
        self._transition(
            event_id,
            "ROUTED",
            actor=actor,
            reason=reason,
            detail={
                "target_task_id": current.get("target_task_id"),
                "target_role": current.get("target_role"),
            },
        )
        result = self.get(event_id)
        self._emit_router_event(result, "INBOX_ROUTED")
        return result

    def _escalate(self, event_id: str, *, reason: str) -> dict[str, Any]:
        at = now_iso()
        self.conn.execute(
            "UPDATE control_plane_event_inbox SET route_status = 'ESCALATED', "
            "requires_human = 1, escalated_at = ?, updated_at = ? WHERE event_id = ?",
            (at, at, event_id),
        )
        self._transition(event_id, "ESCALATED", actor="router", reason=reason)
        result = self.get(event_id)
        self._emit_router_event(result, "INBOX_ESCALATED")
        return result

    def _dashboard_ack(self, event_id: str, *, reason: str) -> dict[str, Any]:
        at = now_iso()
        self.conn.execute(
            "UPDATE control_plane_event_inbox SET classification = COALESCE(classification, ?), "
            "route_reason = ?, route_status = 'ROUTED', target_task_id = 'dashboard', "
            "target_role = 'dashboard', routed_at = ?, updated_at = ? WHERE event_id = ?",
            (DASHBOARD_ONLY, reason, at, at, event_id),
        )
        self._transition(event_id, "ROUTED", actor="router", reason="dashboard_projection")
        self.conn.execute(
            "UPDATE control_plane_event_inbox SET route_status = 'ACKED', acked_at = ?, "
            "ack_actor = 'dashboard', ack_summary = ?, updated_at = ? WHERE event_id = ?",
            (at, reason, at, event_id),
        )
        self._transition(event_id, "ACKED", actor="dashboard", reason=reason)
        return self.get(event_id)

    def _invalidate_event(self, event_id: str, *, invalidated_by: str) -> None:
        row = self._row(event_id)
        if row is None:
            return
        at = now_iso()
        self.conn.execute(
            "UPDATE control_plane_event_inbox SET route_status = 'ACKED', acked_at = ?, "
            "ack_actor = 'router', ack_summary = ?, updated_at = ? WHERE event_id = ?",
            (at, f"superseded_by:{invalidated_by}", at, event_id),
        )
        self._transition(
            event_id,
            "ACKED",
            actor="router",
            reason=f"superseded_by:{invalidated_by}",
        )

    def _invalidate_old_head(self, payload: Mapping[str, Any]) -> None:
        revision = payload.get("revision") if isinstance(payload.get("revision"), Mapping) else {}
        new_head = str(revision.get("head_sha") or "")
        rows = self.conn.execute(
            "SELECT event_id FROM control_plane_event_inbox WHERE project_id = ? "
            "AND entity_type = ? AND entity_id = ? AND head_sha IS NOT NULL "
            "AND head_sha != ? AND event_type IN ({})".format(
                ",".join("?" for _ in OLD_HEAD_INVALIDATED_TYPES)
            ),
            (
                payload["project_id"],
                payload["entity_type"],
                payload["entity_id"],
                new_head,
                *sorted(OLD_HEAD_INVALIDATED_TYPES),
            ),
        ).fetchall()
        for row in rows:
            self._invalidate_event(
                str(row["event_id"]),
                invalidated_by=str(payload["event_id"]),
            )
        AuthorizationService(self.conn).expire_stale_head(
            project_id=str(payload["project_id"]),
            task_id=str(payload["task_id"]),
            current_head_sha=new_head,
            actor="event_router",
        )

    def _emit_router_event(self, inbox: Mapping[str, Any], event_type: str) -> None:
        route_identity = "|".join(
            [
                str(inbox.get("event_id") or ""),
                event_type,
                str(inbox.get("route_status") or ""),
                str(inbox.get("target_task_id") or ""),
                str(inbox.get("route_reason") or ""),
                str(inbox.get("ack_actor") or ""),
            ]
        )
        event_id = (
            f"router_{inbox['event_id']}_{event_type.lower()}_"
            + hashlib.sha256(route_identity.encode("utf-8")).hexdigest()[:12]
        )
        source_event = self.conn.execute(
            "SELECT event_at FROM control_plane_session_events WHERE event_id = ?",
            (inbox["event_id"],),
        ).fetchone()
        created_at = _latest_iso(
            source_event["event_at"] if source_event is not None else None,
            inbox.get("received_at"),
            inbox.get("routed_at"),
            inbox.get("acked_at"),
            inbox.get("escalated_at"),
        )
        payload = {
            "contract": "agent_event/v1",
            "event_id": event_id,
            "event_type": event_type,
            "project_id": inbox["project_id"],
            "task_id": inbox["task_id"],
            "session_id": inbox["session_id"],
            "entity_type": inbox["entity_type"],
            "entity_id": inbox["entity_id"],
            "source_task_id": inbox["source_task_id"],
            "destination_task_id": inbox.get("target_task_id"),
            "priority": inbox["priority"],
            "requires_human": bool(inbox["requires_human"]),
            "supersedes_event_id": None,
            "occurred_at": created_at,
            "created_at": created_at,
            "actor": {"id": "event-router", "role": "router"},
            "source": {"agent_id": "event-router", "task_id": inbox["task_id"]},
            "destination": {"task_id": inbox.get("target_task_id")},
            "summary": f"事件 {inbox['event_id']} 路由状态为 {inbox['route_status']}",
            "revision": {"head_sha": inbox.get("head_sha")} if inbox.get("head_sha") else {},
            "routing": {
                "source_event_id": inbox["event_id"],
                "classification": inbox.get("classification"),
                "status": inbox["route_status"],
                "target_task_id": inbox.get("target_task_id"),
                "target_role": inbox.get("target_role"),
                "reason": inbox.get("route_reason"),
            },
            "safety": {"projection": "summary_and_references", "redacted_fields": []},
        }
        digest = hashlib.sha256(
            json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        payload["payload_digest"] = digest
        payload["fingerprint_sha256"] = digest
        ControlPlaneService(self.conn).record_session_event(
            session_id=str(inbox["session_id"]),
            event_type="artifact_attached",
            idempotency_key=f"agent_event/v1:{event_id}",
            event_id=event_id,
            event_at=str(created_at),
            payload=payload,
            project_id=str(inbox["project_id"]),
            source="event_router",
            actor="event-router",
        )

    def _transition(
        self,
        event_id: str,
        state: str,
        *,
        actor: str,
        reason: str,
        detail: Mapping[str, Any] | None = None,
    ) -> None:
        identity = f"{event_id}|{state}|{reason}"
        transition_id = "route_" + hashlib.sha256(identity.encode("utf-8")).hexdigest()[:32]
        self.conn.execute(
            """
            INSERT INTO control_plane_event_routing_transitions(
                transition_id, event_id, state, actor, reason, detail_json, occurred_at
            ) VALUES(?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(transition_id) DO NOTHING
            """,
            (
                transition_id,
                event_id,
                state,
                str(actor)[:160],
                str(reason)[:500],
                json_dumps(_safe_detail(detail)),
                now_iso(),
            ),
        )

    def _row(self, event_id: str) -> sqlite3.Row | None:
        return self.conn.execute(
            "SELECT * FROM control_plane_event_inbox WHERE event_id = ?", (event_id,)
        ).fetchone()

    def _begin_immediate(self) -> None:
        if not self.conn.in_transaction:
            self.conn.execute("BEGIN IMMEDIATE")
