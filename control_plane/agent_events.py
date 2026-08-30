from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

from .authorization import AuthorizationService, prepare_authorization_request
from .collaboration_schema import initialize_collaboration_schema
from .errors import ControlPlaneError
from .models import json_dumps, json_loads, now_iso, row_to_dict
from .service import ControlPlaneService


AGENT_EVENT_CONTRACT = "agent_event/v1"

AGENT_EVENT_TYPES = {
    "TASK_CREATED",
    "TASK_STARTED",
    "TASK_PROGRESS",
    "TASK_BLOCKED",
    "TASK_COMPLETED",
    "MESSAGE_SENT",
    "MESSAGE_DELIVERED",
    "CALLBACK_RECEIVED",
    "READY_FOR_REVIEW",
    "CHANGES_REQUESTED",
    "FIX_READY",
    "APPROVED",
    "MERGE_GATE_RUNNING",
    "MERGE_READY",
    "GATE_BLOCKED",
    "MERGED",
    "ARTIFACT_CREATED",
    "LOCAL_CI_COMPLETED",
    "AUTHORIZATION_REQUESTED",
    "USER_INSTRUCTION",
    "SECURITY_ALERT",
    "STATUS_NOTIFICATION",
}

INTERNAL_AGENT_EVENT_TYPES = {
    "AUTHORIZATION_ROUTED",
    "AUTHORIZATION_GRANTED",
    "AUTHORIZATION_DENIED",
    "AUTHORIZATION_EXPIRED",
    "AUTHORIZATION_PLATFORM_MANUAL_REQUIRED",
    "AUTHORIZATION_CONSUMED",
    "INBOX_ROUTED",
    "INBOX_ACKED",
    "INBOX_ESCALATED",
}

HEAD_BOUND_EVENT_TYPES = {
    "READY_FOR_REVIEW",
    "CHANGES_REQUESTED",
    "FIX_READY",
    "APPROVED",
    "MERGE_GATE_RUNNING",
    "MERGE_READY",
    "GATE_BLOCKED",
    "MERGED",
    "LOCAL_CI_COMPLETED",
}

HEAD_ADVANCING_EVENT_TYPES = {
    "TASK_STARTED",
    "FIX_READY",
    "READY_FOR_REVIEW",
    "CHANGES_REQUESTED",
}

EVENT_STATE = {
    "TASK_CREATED": (None, None, "registered"),
    "TASK_STARTED": ("busy", "development", "status"),
    "TASK_PROGRESS": ("busy", "development", "status"),
    "TASK_BLOCKED": ("blocked", None, "status"),
    "TASK_COMPLETED": ("idle", "ready_for_review", "status"),
    "MESSAGE_SENT": (None, None, "status"),
    "MESSAGE_DELIVERED": (None, None, "status"),
    "CALLBACK_RECEIVED": (None, None, "status"),
    "READY_FOR_REVIEW": ("waiting_approval", "review", "gate_changed"),
    "CHANGES_REQUESTED": ("blocked", "fix", "gate_changed"),
    "FIX_READY": ("waiting_approval", "rereview", "gate_changed"),
    "APPROVED": ("idle", "review_approved", "gate_changed"),
    "MERGE_GATE_RUNNING": ("busy", "merge_gate", "gate_changed"),
    "MERGE_READY": ("idle", "merge_ready", "gate_changed"),
    "GATE_BLOCKED": ("blocked", "merge_blocked", "gate_changed"),
    "MERGED": ("ended", "merged", "ended"),
    "ARTIFACT_CREATED": (None, None, "artifact_attached"),
    "LOCAL_CI_COMPLETED": (None, None, "status"),
    "AUTHORIZATION_REQUESTED": (None, None, "status"),
    "USER_INSTRUCTION": (None, None, "status"),
    "SECURITY_ALERT": (None, None, "error"),
    "STATUS_NOTIFICATION": (None, None, "status"),
}

EVENT_PRIORITIES = {"P0", "P1", "P2", "P3"}

SENSITIVE_KEY_FRAGMENTS = {
    "prompt",
    "tool_input",
    "tool_output",
    "tool_payload",
    "credential",
    "password",
    "authorization_header",
    "cookie",
    "student",
    "api_key",
    "private_key",
    "secret_value",
    "access_token",
    "refresh_token",
    "body",
    "transcript",
}

AUTHORIZATION_SECRET_BODY_KEYS = {
    "secret",
    "secret_value",
    "credential",
    "credentials",
    "password",
    "api_key",
    "access_token",
    "refresh_token",
    "private_key",
    "command",
    "command_text",
    "command_output",
    "stdout",
    "stderr",
    "tool_input",
    "tool_output",
    "prompt",
    "body",
    "student_body",
}


def _parse_time(value: Any, *, field: str) -> str:
    candidate = str(value or "").strip()
    if not candidate:
        raise ControlPlaneError(f"{field} is required", code="agent_event_invalid")
    try:
        parsed = datetime.fromisoformat(candidate.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ControlPlaneError(
            f"{field} must be an ISO-8601 timestamp",
            code="agent_event_invalid",
        ) from exc
    if parsed.tzinfo is None:
        raise ControlPlaneError(
            f"{field} must include a timezone",
            code="agent_event_invalid",
        )
    return parsed.astimezone(timezone.utc).isoformat(timespec="microseconds")


def _text(value: Any, *, limit: int) -> str:
    return str(value or "").strip()[:limit]


def _actor(value: Any) -> dict[str, str]:
    if isinstance(value, str):
        value = {"id": value}
    value = value if isinstance(value, Mapping) else {}
    actor_id = _text(value.get("id") or value.get("agent_id"), limit=160)
    if not actor_id:
        raise ControlPlaneError("actor.id is required", code="agent_event_invalid")
    return {"id": actor_id, "role": _text(value.get("role") or "unknown", limit=80)}


def _endpoint(value: Any) -> dict[str, Any]:
    value = value if isinstance(value, Mapping) else {}
    result: dict[str, Any] = {}
    for key in ("agent_id", "task_id", "session_id", "delivery_id", "callback_id"):
        if value.get(key) not in (None, ""):
            result[key] = _text(value.get(key), limit=200)
    return result


def _is_sensitive_key(key: str) -> bool:
    lowered = key.lower()
    if lowered.endswith("_ref") or lowered.endswith("_refs"):
        return False
    return any(fragment in lowered for fragment in SENSITIVE_KEY_FRAGMENTS)


def _sanitize_metadata(value: Any, path: str, redacted: list[str], depth: int = 0) -> Any:
    if depth > 4:
        redacted.append(path)
        return "[depth-limited]"
    if isinstance(value, Mapping):
        result: dict[str, Any] = {}
        for raw_key, child in list(value.items())[:60]:
            key = _text(raw_key, limit=100)
            child_path = f"{path}.{key}" if path else key
            if _is_sensitive_key(key):
                redacted.append(child_path)
                continue
            result[key] = _sanitize_metadata(child, child_path, redacted, depth + 1)
        return result
    if isinstance(value, list):
        return [
            _sanitize_metadata(item, f"{path}[{index}]", redacted, depth + 1)
            for index, item in enumerate(value[:50])
        ]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return _text(value, limit=500) if isinstance(value, str) else value
    return _text(value, limit=200)


def _pick(mapping: Any, fields: Sequence[str], *, string_limit: int = 500) -> dict[str, Any]:
    mapping = mapping if isinstance(mapping, Mapping) else {}
    result: dict[str, Any] = {}
    for key in fields:
        value = mapping.get(key)
        if value in (None, "", [], {}):
            continue
        result[key] = _text(value, limit=string_limit) if isinstance(value, str) else value
    return result


def _review_projection(value: Any) -> dict[str, Any]:
    value = value if isinstance(value, Mapping) else {}
    projected = _pick(
        value,
        ("status", "decision", "approver", "owner", "round", "summary"),
        string_limit=300,
    )
    findings: list[dict[str, Any]] = []
    raw_findings = value.get("findings")
    if isinstance(raw_findings, list):
        for item in raw_findings[:100]:
            if not isinstance(item, Mapping):
                continue
            severity = _text(item.get("severity"), limit=10).upper()
            if severity not in {"P0", "P1", "P2"}:
                severity = "P2"
            findings.append(
                {
                    "id": _text(item.get("id"), limit=120),
                    "severity": severity,
                    "summary": _text(item.get("summary"), limit=300),
                    "owner": _text(item.get("owner"), limit=120),
                    "status": _text(item.get("status"), limit=40),
                    "artifact_ref": _text(item.get("artifact_ref"), limit=500),
                }
            )
    projected["findings"] = findings
    projected["finding_counts"] = {
        severity: sum(1 for finding in findings if finding["severity"] == severity)
        for severity in ("P0", "P1", "P2")
    }
    return projected


def _authorization_projection(value: Any) -> dict[str, Any]:
    value = value if isinstance(value, Mapping) else {}
    projected = _pick(
        value,
        (
            "request_id",
            "action",
            "action_type",
            "environment",
            "target_scope",
            "reason",
            "reversible",
            "expires_at",
            "head_sha",
            "authorization_kind",
            "source_task_id",
            "requester_role",
            "action_class",
            "risk_tier",
            "human_required",
            "command_or_action_digest",
            "scope",
            "capability_status",
            "platform_request_ref",
            "manual_only",
        ),
        string_limit=500,
    )
    projected["exact_targets"] = sorted(
        {
            _text(item, limit=500)
            for item in value.get("exact_targets", [])
            if str(item).strip()
        }
    ) if isinstance(value.get("exact_targets"), list) else []
    projected["secret_refs"] = sorted(
        {
            _text(item, limit=300)
            for item in value.get("secret_refs", [])
            if str(item).strip()
        }
    ) if isinstance(value.get("secret_refs"), list) else []
    exact_target = value.get("exact_target")
    if isinstance(exact_target, list):
        projected["exact_target"] = sorted(
            {_text(item, limit=500) for item in exact_target if str(item).strip()}
        )
    return projected


class AgentEventRecorder:
    """Validate and persist `agent_event/v1` in existing session events."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn
        initialize_collaboration_schema(conn)

    def record(self, envelope: Mapping[str, Any]) -> dict[str, Any]:
        if not self.conn.in_transaction:
            self.conn.execute("BEGIN IMMEDIATE")
        projected = self._project(envelope)
        event_id = projected["event_id"]
        session_id = projected["session_id"]
        if projected["event_type"] == "AUTHORIZATION_REQUESTED":
            authorization_service = AuthorizationService(self.conn)
            prepared_authorization = authorization_service.prepare_for_context(
                projected.get("authorization") or {},
                project_id=projected["project_id"],
                task_id=projected["task_id"],
                session_id=projected["session_id"],
                requester_role=projected["actor"]["role"],
                source_task_id=projected["task_id"],
            )
            projected["authorization"] = {
                **prepared_authorization,
                "routing": authorization_service.classify(prepared_authorization),
            }
        existing = self._existing(event_id)
        if existing is not None:
            return self._duplicate_result(existing, projected)

        self._validate_scope(projected)
        self._validate_delivery_transition(projected)
        stale_reason = self._stale_reason(projected)

        if stale_reason:
            event = self._insert_rejected(projected, stale_reason)
            return {
                "duplicate": False,
                "applied": False,
                "stale": stale_reason == "stale_head",
                "event": event,
                "session": ControlPlaneService(self.conn).get_session(session_id),
            }

        status, current_gate, internal_event_type = EVENT_STATE[projected["event_type"]]
        service = ControlPlaneService(self.conn)
        try:
            result = service.record_session_event(
                session_id=session_id,
                event_type=internal_event_type,
                idempotency_key=f"{AGENT_EVENT_CONTRACT}:{event_id}",
                event_id=event_id,
                event_at=projected["created_at"],
                sequence=projected.get("sequence"),
                status=status,
                current_gate=current_gate,
                last_error=projected["summary"] if projected["event_type"] in {"TASK_BLOCKED", "GATE_BLOCKED"} else None,
                payload=projected,
                project_id=projected["project_id"],
                source=f"{AGENT_EVENT_CONTRACT}:{projected.get('source', {}).get('agent_id', 'unknown')}",
                actor=projected["actor"]["id"],
            )
        except sqlite3.IntegrityError:
            existing = self._existing(event_id)
            if existing is None:
                raise
            return self._duplicate_result(existing, projected)

        if result["applied"] and projected["event_type"] in {
            "TASK_STARTED",
            "TASK_PROGRESS",
            "FIX_READY",
            "MERGE_READY",
        }:
            self.conn.execute(
                "UPDATE control_plane_sessions SET last_error = NULL WHERE session_id = ?",
                (session_id,),
            )

        if projected["event_type"] == "AUTHORIZATION_REQUESTED" and result["applied"]:
            authorization = AuthorizationService(self.conn).create_request(
                event_id=event_id,
                project_id=projected["project_id"],
                requirement_id=projected.get("requirement_id"),
                task_id=projected["task_id"],
                session_id=session_id,
                requester=projected["actor"],
                authorization=projected.get("authorization") or {},
                requested_at=projected["created_at"],
            )
            result["authorization"] = authorization
        result["event"] = event_record_to_public(
            self.conn.execute(
                "SELECT rowid AS event_rowid, * FROM control_plane_session_events WHERE event_id = ?",
                (event_id,),
            ).fetchone()
        )
        result["stale"] = False
        return result

    def _project(self, envelope: Mapping[str, Any]) -> dict[str, Any]:
        if not isinstance(envelope, Mapping):
            raise ControlPlaneError("agent event must be an object", code="agent_event_invalid")
        contract = str(envelope.get("contract") or envelope.get("schema_version") or "")
        if contract != AGENT_EVENT_CONTRACT:
            raise ControlPlaneError(
                f"unsupported event contract: {contract or '(missing)'}",
                code="agent_event_contract_unsupported",
            )
        event_type = _text(envelope.get("event_type"), limit=80).upper()
        if event_type not in AGENT_EVENT_TYPES:
            raise ControlPlaneError(
                f"unsupported agent event type: {event_type}",
                code="agent_event_type_unsupported",
            )
        authorization_input = envelope.get("authorization")
        if isinstance(authorization_input, Mapping):
            forbidden = sorted(
                str(key)
                for key in authorization_input
                if str(key).lower() in AUTHORIZATION_SECRET_BODY_KEYS
            )
            if forbidden:
                raise ControlPlaneError(
                    "authorization requests may contain secret_refs only; forbidden fields: "
                    + ", ".join(forbidden),
                    code="authorization_secret_body_forbidden",
                )
        required = {
            "event_id": _text(envelope.get("event_id"), limit=200),
            "project_id": _text(envelope.get("project_id"), limit=160),
            "task_id": _text(envelope.get("task_id"), limit=200),
            "session_id": _text(envelope.get("session_id"), limit=200),
        }
        missing = [key for key, value in required.items() if not value]
        if missing:
            raise ControlPlaneError(
                "missing agent event fields: " + ", ".join(missing),
                code="agent_event_invalid",
            )
        sequence = envelope.get("sequence")
        if sequence is not None and (not isinstance(sequence, int) or sequence < 0):
            raise ControlPlaneError(
                "sequence must be a non-negative integer",
                code="agent_event_invalid",
            )
        revision = _pick(
            envelope.get("revision"),
            (
                "pr_number",
                "pr_url",
                "pr_state",
                "mergeable",
                "source_branch",
                "base_branch",
                "head_sha",
                "base_sha",
                "merge_base_sha",
                "supersedes_head_sha",
            ),
        )
        if event_type in HEAD_BOUND_EVENT_TYPES and not revision.get("head_sha"):
            raise ControlPlaneError(
                f"{event_type} requires revision.head_sha",
                code="agent_event_revision_required",
            )
        redacted: list[str] = []
        _sanitize_metadata(envelope, "", redacted)
        source = _endpoint(envelope.get("source"))
        destination = _endpoint(envelope.get("destination"))
        declared_source_task = _text(envelope.get("source_task_id"), limit=200)
        declared_destination_task = _text(
            envelope.get("destination_task_id"), limit=200
        )
        if (
            declared_source_task
            and source.get("task_id")
            and declared_source_task != source["task_id"]
        ) or (
            declared_destination_task
            and destination.get("task_id")
            and declared_destination_task != destination["task_id"]
        ):
            raise ControlPlaneError(
                "event source/destination task identities conflict",
                code="agent_event_identity_conflict",
            )
        source_task_id = declared_source_task or source.get("task_id") or required["task_id"]
        destination_task_id = declared_destination_task or destination.get("task_id")
        if event_type == "AUTHORIZATION_REQUESTED" and source_task_id != required["task_id"]:
            raise ControlPlaneError(
                "authorization source task must be the requesting session task",
                code="authorization_source_task_mismatch",
            )
        actor = _actor(envelope.get("actor"))
        priority = _text(envelope.get("priority") or "P3", limit=10).upper()
        if priority not in EVENT_PRIORITIES:
            raise ControlPlaneError(
                "priority must be one of P0, P1, P2, P3",
                code="agent_event_priority_invalid",
            )
        requires_human = envelope.get("requires_human", False)
        if not isinstance(requires_human, bool):
            raise ControlPlaneError(
                "requires_human must be boolean",
                code="agent_event_invalid",
            )
        occurred_at = _parse_time(
            envelope.get("occurred_at") or envelope.get("created_at"),
            field="occurred_at",
        )
        entity_type = _text(envelope.get("entity_type") or "task", limit=80)
        entity_id = _text(envelope.get("entity_id") or required["task_id"], limit=200)
        authorization = _authorization_projection(authorization_input)
        if event_type == "AUTHORIZATION_REQUESTED":
            authorization = prepare_authorization_request(
                authorization,
                requester_role=actor["role"],
                source_task_id=required["task_id"],
            )
        payload: dict[str, Any] = {
            "contract": AGENT_EVENT_CONTRACT,
            "event_id": required["event_id"],
            "event_type": event_type,
            "project_id": required["project_id"],
            "requirement_id": _text(envelope.get("requirement_id"), limit=200) or None,
            "task_id": required["task_id"],
            "session_id": required["session_id"],
            "sequence": sequence,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "source_task_id": _text(source_task_id, limit=200),
            "destination_task_id": _text(destination_task_id, limit=200) or None,
            "priority": priority,
            "requires_human": requires_human,
            "supersedes_event_id": _text(envelope.get("supersedes_event_id"), limit=200) or None,
            "occurred_at": occurred_at,
            "created_at": occurred_at,
            "actor": actor,
            "source": source,
            "destination": destination,
            "summary": _text(envelope.get("summary"), limit=500),
            "revision": revision,
            "relations": _pick(
                envelope.get("relations"),
                ("parent_task_id", "root_request_id", "depends_on", "blocks"),
            ),
            "delivery": _pick(
                envelope.get("delivery"),
                (
                    "delivery_id",
                    "status",
                    "ack_id",
                    "callback_id",
                    "source_task_id",
                    "destination_task_id",
                    "error_code",
                ),
            ),
            "review": _review_projection(envelope.get("review")),
            "local_ci": _pick(
                envelope.get("local_ci"),
                ("run_id", "status", "evidence_uri", "completed_at", "head_sha", "source_revision"),
            ),
            "merge_gate": _pick(
                envelope.get("merge_gate"),
                ("state", "allowed", "blocking_checks", "owner", "checked_at"),
            ),
            "artifact": _pick(
                envelope.get("artifact"),
                ("artifact_id", "kind", "uri", "checksum", "summary"),
            ),
            "authorization": authorization,
            "metadata": _sanitize_metadata(envelope.get("metadata") or {}, "metadata", redacted),
            "safety": {
                "projection": "summary_and_references",
                "redacted_fields": sorted(set(redacted)),
            },
        }
        payload_digest = self._fingerprint(payload)
        supplied_digest = _text(envelope.get("payload_digest"), limit=128).lower()
        if supplied_digest and supplied_digest != payload_digest:
            raise ControlPlaneError(
                "payload_digest does not match the safe event projection",
                code="agent_event_payload_digest_mismatch",
            )
        payload["payload_digest"] = payload_digest
        payload["fingerprint_sha256"] = payload_digest
        return payload

    def _validate_scope(self, event: Mapping[str, Any]) -> None:
        session = self.conn.execute(
            "SELECT * FROM control_plane_sessions WHERE session_id = ?",
            (event["session_id"],),
        ).fetchone()
        if session is None:
            raise ControlPlaneError(
                f"unknown session: {event['session_id']}",
                code="session_not_found",
            )
        if str(session["project_id"]) != event["project_id"]:
            raise ControlPlaneError(
                "event project does not match session project",
                code="project_mismatch",
            )
        if session["task_id"] and str(session["task_id"]) != event["task_id"]:
            raise ControlPlaneError(
                "event task does not match session task",
                code="task_mismatch",
            )
        if event.get("requirement_id") and session["requirement_id"] and str(session["requirement_id"]) != event["requirement_id"]:
            raise ControlPlaneError(
                "event requirement does not match session requirement",
                code="requirement_mismatch",
            )
        task_table = self.conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'tasks'"
        ).fetchone()
        if task_table:
            task = self.conn.execute(
                "SELECT project FROM tasks WHERE task_id = ?",
                (event["task_id"],),
            ).fetchone()
            if task is not None and task["project"] and str(task["project"]) != event["project_id"]:
                raise ControlPlaneError(
                    "event task belongs to another project",
                    code="project_mismatch",
                )

    def _validate_delivery_transition(self, event: Mapping[str, Any]) -> None:
        event_type = event["event_type"]
        if event_type not in {"MESSAGE_SENT", "MESSAGE_DELIVERED", "CALLBACK_RECEIVED"}:
            return
        delivery = event.get("delivery") if isinstance(event.get("delivery"), Mapping) else {}
        delivery_id = str(delivery.get("delivery_id") or "")
        if not delivery_id:
            raise ControlPlaneError(
                f"{event_type} requires delivery.delivery_id",
                code="agent_event_delivery_invalid",
            )
        rows = self.conn.execute(
            "SELECT payload_json FROM control_plane_session_events "
            "WHERE project_id = ? AND applied = 1 ORDER BY rowid ASC",
            (event["project_id"],),
        ).fetchall()
        prior_types: list[str] = []
        incoming_source = str(
            delivery.get("source_task_id") or event.get("source_task_id") or ""
        )
        incoming_destination = str(
            delivery.get("destination_task_id")
            or event.get("destination_task_id")
            or ""
        )
        for row in rows:
            payload = json_loads(row["payload_json"], {})
            if not isinstance(payload, Mapping) or payload.get("contract") != AGENT_EVENT_CONTRACT:
                continue
            prior_delivery = payload.get("delivery") if isinstance(payload.get("delivery"), Mapping) else {}
            if str(prior_delivery.get("delivery_id") or "") == delivery_id:
                prior_source = str(
                    prior_delivery.get("source_task_id")
                    or payload.get("source_task_id")
                    or ""
                )
                prior_destination = str(
                    prior_delivery.get("destination_task_id")
                    or payload.get("destination_task_id")
                    or ""
                )
                if (
                    incoming_source
                    and prior_source
                    and incoming_source != prior_source
                ) or (
                    incoming_destination
                    and prior_destination
                    and incoming_destination != prior_destination
                ):
                    raise ControlPlaneError(
                        "delivery_id source/destination changed within the project",
                        code="agent_event_delivery_scope_mismatch",
                    )
                prior_types.append(str(payload.get("event_type") or ""))
        if event_type == "MESSAGE_DELIVERED" and "MESSAGE_SENT" not in prior_types:
            raise ControlPlaneError(
                "MESSAGE_DELIVERED requires a prior MESSAGE_SENT for the same delivery_id",
                code="agent_event_delivery_transition",
            )
        if event_type == "CALLBACK_RECEIVED" and "MESSAGE_DELIVERED" not in prior_types:
            raise ControlPlaneError(
                "CALLBACK_RECEIVED requires a prior MESSAGE_DELIVERED for the same delivery_id",
                code="agent_event_delivery_transition",
            )

    def _stale_reason(self, event: Mapping[str, Any]) -> str | None:
        revision = event.get("revision") if isinstance(event.get("revision"), Mapping) else {}
        incoming_head = str(revision.get("head_sha") or "")
        if not incoming_head:
            return None
        current = self._latest_head(event["project_id"], event["task_id"])
        if current is None or current["head_sha"] == incoming_head:
            return None
        if (
            event["event_type"] in HEAD_ADVANCING_EVENT_TYPES
            and str(revision.get("supersedes_head_sha") or "") == current["head_sha"]
        ):
            return None
        return "stale_head"

    def _latest_head(self, project_id: str, task_id: str) -> dict[str, Any] | None:
        rows = self.conn.execute(
            "SELECT payload_json FROM control_plane_session_events "
            "WHERE project_id = ? AND applied = 1 ORDER BY rowid DESC",
            (project_id,),
        ).fetchall()
        for row in rows:
            payload = json_loads(row["payload_json"], {})
            if not isinstance(payload, Mapping) or payload.get("contract") != AGENT_EVENT_CONTRACT:
                continue
            if payload.get("task_id") != task_id:
                continue
            revision = payload.get("revision") if isinstance(payload.get("revision"), Mapping) else {}
            if revision.get("head_sha"):
                return dict(revision)
        return None

    def _insert_rejected(self, event: Mapping[str, Any], reason: str) -> dict[str, Any]:
        self.conn.execute(
            """
            INSERT INTO control_plane_session_events(
                event_id, idempotency_key, session_id, project_id, event_type,
                event_at, observed_at, sequence, status, current_gate, last_error,
                payload_json, source, applied, rejection_reason
            ) VALUES(?, ?, ?, ?, 'status', ?, ?, ?, NULL, NULL, NULL, ?, ?, 0, ?)
            """,
            (
                event["event_id"],
                f"{AGENT_EVENT_CONTRACT}:{event['event_id']}",
                event["session_id"],
                event["project_id"],
                event["created_at"],
                now_iso(),
                event.get("sequence"),
                json_dumps(dict(event)),
                AGENT_EVENT_CONTRACT,
                reason,
            ),
        )
        return event_record_to_public(
            self.conn.execute(
                "SELECT rowid AS event_rowid, * FROM control_plane_session_events WHERE event_id = ?",
                (event["event_id"],),
            ).fetchone()
        )

    def _existing(self, event_id: str) -> sqlite3.Row | None:
        return self.conn.execute(
            "SELECT rowid AS event_rowid, * FROM control_plane_session_events "
            "WHERE event_id = ? OR idempotency_key = ?",
            (event_id, f"{AGENT_EVENT_CONTRACT}:{event_id}"),
        ).fetchone()

    def _duplicate_result(
        self, existing: sqlite3.Row, incoming: Mapping[str, Any]
    ) -> dict[str, Any]:
        existing_payload = json_loads(existing["payload_json"], {})
        if not isinstance(existing_payload, Mapping) or existing_payload.get("fingerprint_sha256") != incoming.get("fingerprint_sha256"):
            raise ControlPlaneError(
                "event_id was reused with different content",
                code="event_identity_conflict",
            )
        result = {
            "duplicate": True,
            "applied": bool(existing["applied"]),
            "stale": existing["rejection_reason"] == "stale_head",
            "event": event_record_to_public(existing),
            "session": ControlPlaneService(self.conn).get_session(str(existing["session_id"])),
        }
        if incoming.get("event_type") == "AUTHORIZATION_REQUESTED":
            request_id = str((incoming.get("authorization") or {}).get("request_id") or "")
            if request_id:
                try:
                    result["authorization"] = AuthorizationService(self.conn).get(request_id)
                except ControlPlaneError:
                    pass
        return result

    @staticmethod
    def _fingerprint(payload: Mapping[str, Any]) -> str:
        normalized = dict(payload)
        normalized.pop("fingerprint_sha256", None)
        return hashlib.sha256(
            json.dumps(normalized, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()


def event_record_to_public(row: sqlite3.Row | Mapping[str, Any] | None) -> dict[str, Any]:
    if row is None:
        return {}
    value = dict(row)
    payload = json_loads(value.pop("payload_json", "{}"), {})
    return {
        "event_id": value.get("event_id"),
        "cursor": value.get("event_id"),
        "rowid": value.get("event_rowid"),
        "project_id": value.get("project_id"),
        "session_id": value.get("session_id"),
        "event_at": value.get("event_at"),
        "observed_at": value.get("observed_at"),
        "sequence": value.get("sequence"),
        "applied": bool(value.get("applied")),
        "rejection_reason": value.get("rejection_reason"),
        "payload": payload if isinstance(payload, dict) else {},
    }


def list_agent_events(
    conn: sqlite3.Connection,
    *,
    after_event_id: str | None = None,
    project_id: str | None = None,
    task_id: str | None = None,
    limit: int = 200,
) -> dict[str, Any]:
    initialize_collaboration_schema(conn)
    cursor_reset = False
    after_rowid = 0
    if after_event_id:
        cursor = conn.execute(
            "SELECT rowid FROM control_plane_session_events WHERE event_id = ?",
            (after_event_id,),
        ).fetchone()
        if cursor is None:
            cursor_reset = True
        else:
            after_rowid = int(cursor["rowid"])
    clauses = ["rowid > ?"]
    args: list[Any] = [after_rowid]
    if project_id:
        clauses.append("project_id = ?")
        args.append(project_id)
    rows = conn.execute(
        "SELECT rowid AS event_rowid, * FROM control_plane_session_events "
        f"WHERE {' AND '.join(clauses)} ORDER BY rowid ASC LIMIT ?",
        [*args, max(1, min(int(limit), 1000))],
    ).fetchall()
    events: list[dict[str, Any]] = []
    scanned_last_event_id = after_event_id
    for row in rows:
        public = event_record_to_public(row)
        payload = public.get("payload") or {}
        if payload.get("contract") != AGENT_EVENT_CONTRACT:
            continue
        scanned_last_event_id = public["event_id"]
        if task_id and payload.get("task_id") != task_id:
            continue
        events.append(public)
    return {
        "contract": AGENT_EVENT_CONTRACT,
        "after_event_id": after_event_id,
        "cursor_reset": cursor_reset,
        "events": events,
        "last_event_id": scanned_last_event_id,
    }
