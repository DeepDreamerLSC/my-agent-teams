from __future__ import annotations

import hashlib
import json
import sqlite3
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from .authorization_policy import (
    AUTHORIZATION_POLICY_VERSION,
    AUTHORIZATION_RULES,
    L0_AUTO,
    L1_REVIEWER_COORDINATOR,
    L2_OWNER,
    classify_authorization,
)
from .collaboration_schema import initialize_collaboration_schema
from .errors import ControlPlaneError
from .models import json_dumps, json_loads, new_id, now_iso, row_to_dict
from .service import ControlPlaneService


PENDING = "PENDING"
GRANTED = "GRANTED"
DENIED = "DENIED"
EXPIRED = "EXPIRED"
CONSUMED = "CONSUMED"

TEXT_AUTHORIZATION = "text"
CODEX_PLATFORM_AUTHORIZATION = "codex_platform"
TEXT_ROUTE_AVAILABLE = "text_route_available"
PLATFORM_MANUAL_REQUIRED = "platform_manual_required"

AUTHORIZATION_KINDS = {TEXT_AUTHORIZATION, CODEX_PLATFORM_AUTHORIZATION}
AUTHORIZATION_EVENT_TYPES = {
    PENDING: "AUTHORIZATION_ROUTED",
    GRANTED: "AUTHORIZATION_GRANTED",
    DENIED: "AUTHORIZATION_DENIED",
    EXPIRED: "AUTHORIZATION_EXPIRED",
}

CODEX_NATIVE_APPROVAL_CAPABILITY = {
    "capability": "cross_task_native_sandbox_tool_approval",
    "status": PLATFORM_MANUAL_REQUIRED,
    "reason": (
        "当前 Codex App client/bridge 没有跨任务读取并 approve/deny 原生 "
        "sandbox/tool approval 的 API；消息投递不能替代平台点击。"
    ),
}

AUTHORIZATION_FORBIDDEN_BODY_KEYS = {
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
    "secret",
    "secret_value",
    "credential",
    "credentials",
    "password",
    "api_key",
    "access_token",
    "refresh_token",
    "private_key",
}

APPROVER_ROLES = {
    L1_REVIEWER_COORDINATOR: {"reviewer", "coordinator", "owner"},
    L2_OWNER: {"owner"},
}


LOGICAL_TARGET_PREFIXES = (
    "service:",
    "service://",
    "worker:",
    "worker://",
    "snapshot:",
    "snapshot://",
    "pr:",
    "pr://",
    "ci:",
    "ci://",
)


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _latest_iso(*values: str | None) -> str:
    candidates = [datetime.now(timezone.utc)]
    candidates.extend(parsed for value in values if (parsed := _parse_time(value)))
    return max(candidates).isoformat(timespec="microseconds")


def _safe_actor(value: Mapping[str, Any] | None) -> dict[str, str]:
    value = value if isinstance(value, Mapping) else {}
    return {
        "id": str(value.get("id") or value.get("agent_id") or "unknown")[:160],
        "role": str(value.get("role") or "unknown")[:80],
    }


def authorization_action_digest(request: Mapping[str, Any]) -> str:
    """Hash the exact authorized operation without persisting command bodies."""

    exact_targets = request.get("exact_targets")
    canonical = {
        "authorization_kind": str(
            request.get("authorization_kind") or TEXT_AUTHORIZATION
        ).strip().lower(),
        "action": str(request.get("action") or "").strip().upper(),
        "action_type": str(request.get("action_type") or "").strip().lower(),
        "environment": str(request.get("environment") or "").strip().lower(),
        "target_scope": str(request.get("target_scope") or "").strip().lower(),
        "exact_targets": sorted(
            {str(item).strip() for item in exact_targets if str(item).strip()}
        )
        if isinstance(exact_targets, list)
        else [],
        "head_sha": str(request.get("head_sha") or "").strip(),
        "reversible": request.get("reversible")
        if isinstance(request.get("reversible"), bool)
        else None,
        "platform_request_ref": str(request.get("platform_request_ref") or "").strip(),
    }
    return hashlib.sha256(
        json.dumps(
            canonical,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def prepare_authorization_request(
    request: Mapping[str, Any],
    *,
    requester_role: str | None = None,
    source_task_id: str | None = None,
) -> dict[str, Any]:
    """Validate and enrich the small safe authorization envelope."""

    forbidden = sorted(
        str(key)
        for key in request
        if str(key).strip().lower() in AUTHORIZATION_FORBIDDEN_BODY_KEYS
    )
    if forbidden:
        raise ControlPlaneError(
            "authorization requests accept digests/references, not sensitive command, "
            "prompt, output, credential, or data bodies: " + ", ".join(forbidden),
            code="authorization_sensitive_body_forbidden",
        )
    kind = str(request.get("authorization_kind") or TEXT_AUTHORIZATION).strip().lower()
    if kind not in AUTHORIZATION_KINDS:
        raise ControlPlaneError(
            f"unsupported authorization_kind: {kind}",
            code="authorization_kind_invalid",
        )
    prepared = dict(request)
    prepared["authorization_kind"] = kind
    prepared["source_task_id"] = str(
        source_task_id or request.get("source_task_id") or ""
    ).strip()
    prepared["requester_role"] = str(
        requester_role or request.get("requester_role") or "unknown"
    ).strip()[:80]
    prepared["action_class"] = str(
        request.get("action_class") or request.get("action_type") or ""
    ).strip()[:120]
    prepared["exact_target"] = list(request.get("exact_targets") or [])
    prepared["scope"] = str(
        request.get("scope") or request.get("target_scope") or ""
    ).strip()[:200]
    prepared["capability_status"] = (
        PLATFORM_MANUAL_REQUIRED
        if kind == CODEX_PLATFORM_AUTHORIZATION
        else TEXT_ROUTE_AVAILABLE
    )
    computed_digest = authorization_action_digest(prepared)
    supplied_digest = str(
        request.get("command_or_action_digest") or ""
    ).strip().lower()
    if supplied_digest and supplied_digest != computed_digest:
        raise ControlPlaneError(
            "command_or_action_digest does not match exact targets, environment, HEAD, or action",
            code="authorization_digest_mismatch",
        )
    prepared["command_or_action_digest"] = computed_digest
    prepared["human_required"] = bool(
        request.get("human_required")
        or kind == CODEX_PLATFORM_AUTHORIZATION
    )
    return prepared


class AuthorizationService:
    """Minimal delegated authorization with exact, expiring, one-shot grants."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn
        initialize_collaboration_schema(conn)

    def policy(self) -> dict[str, Any]:
        overrides = self._overrides()
        return {
            "policy_version": AUTHORIZATION_POLICY_VERSION,
            "default": L2_OWNER,
            "rules": [
                rule.public_dict(enabled=overrides.get(rule.rule_id, True))
                for rule in AUTHORIZATION_RULES
            ],
            "note": "未知或信息不完整请求默认路由到 L2 Owner；配置仅支持启停内置显式规则。",
            "native_platform_capability": dict(CODEX_NATIVE_APPROVAL_CAPABILITY),
        }

    def prepare_for_context(
        self,
        request: Mapping[str, Any],
        *,
        project_id: str,
        task_id: str,
        session_id: str,
        requester_role: str | None = None,
        source_task_id: str | None = None,
    ) -> dict[str, Any]:
        """Return the exact, project-bound envelope used by events and grants."""

        prepared = prepare_authorization_request(
            request,
            requester_role=requester_role,
            source_task_id=source_task_id or task_id,
        )
        prepared = self._normalize_request_targets(
            project_id=project_id,
            task_id=task_id,
            session_id=session_id,
            request=prepared,
        )
        prepared["command_or_action_digest"] = authorization_action_digest(prepared)
        return prepared

    def set_rule_enabled(
        self,
        rule_id: str,
        *,
        enabled: bool,
        actor: Mapping[str, Any],
    ) -> dict[str, Any]:
        self._begin_immediate()
        known = {rule.rule_id for rule in AUTHORIZATION_RULES}
        if rule_id not in known:
            raise ControlPlaneError(
                f"unknown authorization rule: {rule_id}",
                code="authorization_rule_not_found",
            )
        normalized_actor = _safe_actor(actor)
        if normalized_actor["role"] != "owner" or normalized_actor["id"] == "unknown":
            raise ControlPlaneError(
                "only Owner can change authorization policy overrides",
                code="authorization_policy_owner_required",
            )
        previous = self._policy_override_row(rule_id)
        updated_at = now_iso()
        self.conn.execute(
            """
            INSERT INTO control_plane_authorization_policy_overrides(
                rule_id, enabled, updated_by, updated_at
            ) VALUES(?, ?, ?, ?)
            ON CONFLICT(rule_id) DO UPDATE SET
                enabled = excluded.enabled,
                updated_by = excluded.updated_by,
                updated_at = excluded.updated_at
            """,
            (rule_id, 1 if enabled else 0, normalized_actor["id"], updated_at),
        )
        next_value = self._policy_override_row(rule_id) or {}
        self._audit(
            entity_type="authorization_policy",
            entity_id=rule_id,
            event_type="enabled" if enabled else "disabled",
            idempotency_key=f"authorization-policy:{rule_id}:{updated_at}",
            previous=previous or {},
            next_value=next_value,
            actor=normalized_actor["id"],
        )
        return self.policy()

    def classify(self, request: Mapping[str, Any]) -> dict[str, Any]:
        prepared = prepare_authorization_request(request)
        if prepared["authorization_kind"] == CODEX_PLATFORM_AUTHORIZATION:
            return {
                "level": L2_OWNER,
                "risk_level": "high",
                "matched_rule_id": None,
                "policy_version": AUTHORIZATION_POLICY_VERSION,
                "routing_reason": CODEX_NATIVE_APPROVAL_CAPABILITY["reason"],
                "incomplete_fields": [],
                "required_evidence": ["platform_owner_click"],
                "grantable": False,
                "human_required": True,
                "capability_status": PLATFORM_MANUAL_REQUIRED,
            }
        route = classify_authorization(prepared, overrides=self._overrides())
        expires_at = str(prepared.get("expires_at") or "").strip()
        if expires_at and _parse_time(expires_at) is None:
            route = {
                **route,
                "level": L2_OWNER,
                "risk_level": "unknown",
                "matched_rule_id": None,
                "routing_reason": "expires_at 无效，默认 fail-closed 路由到 Owner。",
                "incomplete_fields": sorted(
                    set([*route.get("incomplete_fields", []), "expires_at"])
                ),
                "grantable": False,
            }
        return {
            **route,
            "human_required": route["level"] != L0_AUTO,
            "capability_status": TEXT_ROUTE_AVAILABLE,
        }

    def create_request(
        self,
        *,
        event_id: str,
        project_id: str,
        requirement_id: str | None,
        task_id: str,
        session_id: str,
        requester: Mapping[str, Any],
        authorization: Mapping[str, Any],
        requested_at: str,
    ) -> dict[str, Any]:
        self._begin_immediate()
        prepared = self.prepare_for_context(
            authorization,
            project_id=project_id,
            task_id=task_id,
            session_id=session_id,
            requester_role=str(requester.get("role") or "unknown"),
            source_task_id=task_id,
        )
        request_id = str(prepared.get("request_id") or "").strip()
        if not request_id:
            raise ControlPlaneError(
                "authorization.request_id is required",
                code="authorization_request_id_required",
            )
        existing = self._row(request_id)
        if existing is not None:
            current = self._authorization(existing)
            if current["request_event_id"] != event_id:
                raise ControlPlaneError(
                    "authorization request_id belongs to another event",
                    code="authorization_request_conflict",
                )
            if current["command_or_action_digest"] != prepared["command_or_action_digest"]:
                raise ControlPlaneError(
                    "authorization request digest changed; submit a new request_id",
                    code="authorization_digest_mismatch",
                )
            return current

        route = self.classify(prepared)
        expires_at = str(prepared.get("expires_at") or "").strip() or None
        expiry = _parse_time(expires_at)
        now = datetime.now(timezone.utc)
        if expires_at and expiry is None:
            route = {
                **route,
                "level": L2_OWNER,
                "risk_level": "unknown",
                "matched_rule_id": None,
                "routing_reason": "expires_at 无效，默认 fail-closed 路由到 Owner。",
                "incomplete_fields": sorted(
                    set([*route.get("incomplete_fields", []), "expires_at"])
                ),
                "grantable": False,
            }
        status = (
            EXPIRED
            if expiry is not None and expiry <= now
            else GRANTED
            if route["level"] == L0_AUTO
            and prepared["authorization_kind"] == TEXT_AUTHORIZATION
            else PENDING
        )
        normalized_requester = _safe_actor(requester)
        approver = (
            {
                "id": f"policy:{route['matched_rule_id']}",
                "role": "policy",
                "policy_version": route["policy_version"],
            }
            if status == GRANTED
            else {}
        )
        exact_targets = prepared.get("exact_targets")
        exact_targets = sorted(
            {str(item)[:500] for item in exact_targets if str(item).strip()}
        ) if isinstance(exact_targets, list) else []
        secret_refs = prepared.get("secret_refs")
        secret_refs = sorted(
            {str(item)[:300] for item in secret_refs if str(item).strip()}
        ) if isinstance(secret_refs, list) else []
        created_at = now_iso()
        self.conn.execute(
            """
            INSERT INTO control_plane_authorizations(
                request_id, request_event_id, project_id, requirement_id, task_id,
                session_id, requester_json, action, action_type, environment,
                target_scope, exact_targets_json, head_sha, secret_refs_json, reason,
                reversible, expires_at, authorization_level, risk_level,
                matched_rule_id, routing_reason, incomplete_fields_json,
                policy_version, status, approver_json, decision_reason,
                decision_event_id, requested_at, decided_at, consumed_at,
                created_at, updated_at, authorization_kind, source_task_id,
                requester_role, action_class, command_or_action_digest,
                capability_status, human_required, platform_request_ref
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                request_id,
                event_id,
                project_id,
                requirement_id,
                task_id,
                session_id,
                json_dumps(normalized_requester),
                str(prepared.get("action") or "").upper() or None,
                str(prepared.get("action_type") or "") or None,
                str(prepared.get("environment") or "").lower() or None,
                str(prepared.get("target_scope") or "").lower() or None,
                json_dumps(exact_targets),
                str(prepared.get("head_sha") or "") or None,
                json_dumps(secret_refs),
                str(prepared.get("reason") or "")[:500],
                1 if prepared.get("reversible") is True else 0 if prepared.get("reversible") is False else None,
                expires_at,
                route["level"],
                route["risk_level"],
                route.get("matched_rule_id"),
                route["routing_reason"],
                json_dumps(route.get("incomplete_fields") or []),
                route["policy_version"],
                status,
                json_dumps(approver),
                route["routing_reason"] if status == GRANTED else "",
                None,
                requested_at,
                created_at if status in {GRANTED, EXPIRED} else None,
                None,
                created_at,
                created_at,
                prepared["authorization_kind"],
                prepared.get("source_task_id") or task_id,
                prepared["requester_role"],
                prepared.get("action_class") or None,
                prepared["command_or_action_digest"],
                prepared["capability_status"],
                1 if route.get("human_required") else 0,
                str(prepared.get("platform_request_ref") or "")[:300] or None,
            ),
        )
        row = self._row(request_id)
        payload = self._authorization(row)
        self._audit(
            entity_type="authorization",
            entity_id=request_id,
            event_type="requested",
            idempotency_key=f"authorization:{request_id}:requested",
            previous={},
            next_value=payload,
            actor=normalized_requester["id"],
        )
        event_type = (
            "AUTHORIZATION_PLATFORM_MANUAL_REQUIRED"
            if prepared["authorization_kind"] == CODEX_PLATFORM_AUTHORIZATION
            else AUTHORIZATION_EVENT_TYPES[status]
        )
        decision_event_id = self._emit_authorization_event(payload, event_type=event_type)
        self.conn.execute(
            "UPDATE control_plane_authorizations SET decision_event_id = ? WHERE request_id = ?",
            (decision_event_id, request_id),
        )
        payload = self.get(request_id, expire=False)
        return payload

    def get(self, request_id: str, *, expire: bool = True) -> dict[str, Any]:
        row = self._row(request_id)
        if row is None:
            raise ControlPlaneError(
                f"unknown authorization request: {request_id}",
                code="authorization_not_found",
            )
        if expire:
            self._expire_if_needed(row)
            row = self._row(request_id)
        return self._authorization(row)

    def list_requests(
        self,
        *,
        project_id: str | None = None,
        task_id: str | None = None,
        status: str | None = None,
        level: str | None = None,
    ) -> list[dict[str, Any]]:
        self.expire_pending()
        clauses: list[str] = []
        args: list[Any] = []
        for field, value in (
            ("project_id", project_id),
            ("task_id", task_id),
            ("status", status),
            ("authorization_level", level),
        ):
            if value:
                clauses.append(f"{field} = ?")
                args.append(value)
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = self.conn.execute(
            f"SELECT * FROM control_plane_authorizations{where} "
            "ORDER BY CASE authorization_level WHEN 'L2_OWNER' THEN 0 "
            "WHEN 'L1_REVIEWER_COORDINATOR' THEN 1 ELSE 2 END, requested_at DESC",
            args,
        ).fetchall()
        return [self._authorization(row) for row in rows]

    def decide(
        self,
        request_id: str,
        *,
        decision: str,
        approver: Mapping[str, Any],
        reason: str,
    ) -> dict[str, Any]:
        self._begin_immediate()
        current = self.get(request_id)
        if current["status"] != PENDING:
            raise ControlPlaneError(
                f"authorization is already {current['status']}",
                code="authorization_terminal",
            )
        if current["authorization_kind"] == CODEX_PLATFORM_AUTHORIZATION:
            raise ControlPlaneError(
                "Codex native sandbox/tool approval requires the user's platform click; "
                "record the observed result through platform-decision instead of treating "
                "a text message as approval",
                code="authorization_platform_manual_required",
            )
        normalized_decision = str(decision or "").upper()
        if normalized_decision not in {"GRANT", "DENY"}:
            raise ControlPlaneError(
                "decision must be GRANT or DENY",
                code="authorization_decision_invalid",
            )
        normalized_approver = _safe_actor(approver)
        if normalized_approver["id"] == "unknown":
            raise ControlPlaneError(
                "authorization approver.id is required",
                code="authorization_approver_required",
            )
        if not str(reason or "").strip():
            raise ControlPlaneError(
                "authorization decision reason is required",
                code="authorization_decision_reason_required",
            )
        allowed_roles = APPROVER_ROLES.get(current["authorization_level"], set())
        if normalized_approver["role"] not in allowed_roles:
            raise ControlPlaneError(
                f"{current['authorization_level']} requires one of {sorted(allowed_roles)}",
                code="authorization_approver_forbidden",
            )
        if normalized_decision == "GRANT":
            if current["incomplete_fields"]:
                raise ControlPlaneError(
                    "incomplete authorization request cannot be granted",
                    code="authorization_incomplete",
                )
            if current["action"] == "MERGE_PR":
                blockers = self._merge_prerequisite_blockers(current)
                if blockers:
                    raise ControlPlaneError(
                        "merge authorization prerequisites are not satisfied: " + ", ".join(blockers),
                        code="authorization_merge_gate_blocked",
                    )
        next_status = GRANTED if normalized_decision == "GRANT" else DENIED
        decided_at = now_iso()
        previous = current
        self.conn.execute(
            """
            UPDATE control_plane_authorizations
               SET status = ?, approver_json = ?, decision_reason = ?,
                   decided_at = ?, updated_at = ?
             WHERE request_id = ? AND status = 'PENDING'
            """,
            (
                next_status,
                json_dumps(normalized_approver),
                str(reason).strip()[:500],
                decided_at,
                decided_at,
                request_id,
            ),
        )
        if self.conn.execute("SELECT changes()").fetchone()[0] != 1:
            raise ControlPlaneError(
                "authorization changed concurrently",
                code="authorization_concurrent_change",
            )
        current = self.get(request_id, expire=False)
        decision_event_id = self._emit_authorization_event(
            current,
            event_type=AUTHORIZATION_EVENT_TYPES[next_status],
        )
        self.conn.execute(
            "UPDATE control_plane_authorizations SET decision_event_id = ? WHERE request_id = ?",
            (decision_event_id, request_id),
        )
        current = self.get(request_id, expire=False)
        self._audit(
            entity_type="authorization",
            entity_id=request_id,
            event_type="granted" if next_status == GRANTED else "denied",
            idempotency_key=f"authorization:{request_id}:{next_status.lower()}",
            previous=previous,
            next_value=current,
            actor=normalized_approver["id"],
        )
        self._route_decision_to_source(current, actor=normalized_approver["id"])
        return current

    def record_platform_decision(
        self,
        request_id: str,
        *,
        decision: str,
        actor: Mapping[str, Any],
        reason: str,
        observed_digest: str,
    ) -> dict[str, Any]:
        """Record a user's native Codex click without claiming to perform it."""

        self._begin_immediate()
        current = self.get(request_id)
        if current["authorization_kind"] != CODEX_PLATFORM_AUTHORIZATION:
            raise ControlPlaneError(
                "platform-decision is only valid for codex_platform requests",
                code="authorization_kind_mismatch",
            )
        if current["status"] != PENDING:
            raise ControlPlaneError(
                f"authorization is already {current['status']}",
                code="authorization_terminal",
            )
        normalized_actor = _safe_actor(actor)
        if normalized_actor["id"] == "unknown" or normalized_actor["role"] != "owner":
            raise ControlPlaneError(
                "only Owner can record a native platform approval result",
                code="authorization_platform_owner_required",
            )
        if str(observed_digest or "").strip().lower() != current["command_or_action_digest"]:
            raise ControlPlaneError(
                "platform approval digest drifted; the platform request must be re-created",
                code="authorization_digest_mismatch",
            )
        if not str(reason or "").strip():
            raise ControlPlaneError(
                "authorization decision reason is required",
                code="authorization_decision_reason_required",
            )
        normalized_decision = str(decision or "").strip().upper()
        if normalized_decision not in {"GRANT", "DENY"}:
            raise ControlPlaneError(
                "decision must be GRANT or DENY",
                code="authorization_decision_invalid",
            )
        next_status = GRANTED if normalized_decision == "GRANT" else DENIED
        decided_at = now_iso()
        previous = current
        self.conn.execute(
            """
            UPDATE control_plane_authorizations
               SET status = ?, approver_json = ?, decision_reason = ?, decided_at = ?,
                   updated_at = ?
             WHERE request_id = ? AND status = 'PENDING'
            """,
            (
                next_status,
                json_dumps(normalized_actor),
                str(reason).strip()[:500],
                decided_at,
                decided_at,
                request_id,
            ),
        )
        if self.conn.execute("SELECT changes()").fetchone()[0] != 1:
            raise ControlPlaneError(
                "authorization changed concurrently",
                code="authorization_concurrent_change",
            )
        current = self.get(request_id, expire=False)
        decision_event_id = self._emit_authorization_event(
            current,
            event_type=AUTHORIZATION_EVENT_TYPES[next_status],
        )
        self.conn.execute(
            "UPDATE control_plane_authorizations SET decision_event_id = ? WHERE request_id = ?",
            (decision_event_id, request_id),
        )
        current = self.get(request_id, expire=False)
        self._audit(
            entity_type="authorization",
            entity_id=request_id,
            event_type="platform_granted" if next_status == GRANTED else "platform_denied",
            idempotency_key=f"authorization:{request_id}:platform:{next_status.lower()}",
            previous=previous,
            next_value=current,
            actor=normalized_actor["id"],
        )
        self._route_decision_to_source(current, actor=normalized_actor["id"])
        return current

    def consume(
        self,
        request_id: str,
        *,
        requester_id: str,
        environment: str,
        exact_targets: Sequence[str],
        head_sha: str | None = None,
    ) -> dict[str, Any]:
        self._begin_immediate()
        current = self.get(request_id)
        if current["status"] != GRANTED:
            raise ControlPlaneError(
                f"authorization is not consumable: {current['status']}",
                code="authorization_not_granted",
            )
        if current["authorization_kind"] == CODEX_PLATFORM_AUTHORIZATION:
            raise ControlPlaneError(
                "the control plane records native approval results but cannot consume or "
                "execute the Codex platform action",
                code="authorization_platform_execution_manual",
            )
        if str(requester_id) != current["requester"].get("id"):
            raise ControlPlaneError(
                "authorization requester does not match",
                code="authorization_requester_mismatch",
            )
        normalized = self._normalize_request_targets(
            project_id=str(current["project_id"]),
            task_id=str(current["task_id"]),
            session_id=str(current["session_id"]),
            request={
                "action": current.get("action"),
                "action_type": current.get("action_type"),
                "environment": environment,
                "target_scope": current.get("target_scope"),
                "exact_targets": list(exact_targets),
                "head_sha": current.get("head_sha"),
            },
        )
        if normalized.get("scope_violation"):
            raise ControlPlaneError(
                str(
                    normalized.get("scope_violation_reason")
                    or "authorization exact_targets exceed registered scope"
                ),
                code="authorization_scope_changed",
            )
        expected_targets = sorted(str(item) for item in current["exact_targets"])
        supplied_targets = sorted(str(item) for item in normalized["exact_targets"])
        if supplied_targets != expected_targets:
            raise ControlPlaneError(
                "authorization exact_targets changed; submit a new request",
                code="authorization_scope_changed",
            )
        if str(environment or "").lower() != str(current.get("environment") or "").lower():
            raise ControlPlaneError(
                "authorization environment changed; submit a new request",
                code="authorization_environment_changed",
            )
        if current.get("head_sha") and str(head_sha or "") != current["head_sha"]:
            raise ControlPlaneError(
                "authorization HEAD changed; submit a new request",
                code="authorization_head_changed",
            )
        latest_head = self._latest_task_head(
            project_id=current["project_id"], task_id=current["task_id"]
        )
        if current.get("head_sha") and latest_head and latest_head != current["head_sha"]:
            raise ControlPlaneError(
                "authorization HEAD is no longer current; submit a new request",
                code="authorization_head_changed",
            )
        consumed_at = now_iso()
        previous = current
        self.conn.execute(
            """
            UPDATE control_plane_authorizations
               SET status = 'CONSUMED', consumed_at = ?, updated_at = ?
             WHERE request_id = ? AND status = 'GRANTED'
            """,
            (consumed_at, consumed_at, request_id),
        )
        if self.conn.execute("SELECT changes()").fetchone()[0] != 1:
            raise ControlPlaneError(
                "authorization was already consumed or changed",
                code="authorization_already_consumed",
            )
        current = self.get(request_id, expire=False)
        self._emit_authorization_event(current, event_type="AUTHORIZATION_CONSUMED")
        self._audit(
            entity_type="authorization",
            entity_id=request_id,
            event_type="consumed",
            idempotency_key=f"authorization:{request_id}:consumed",
            previous=previous,
            next_value=current,
            actor=str(requester_id),
        )
        return current

    def expire_pending(self) -> int:
        self._begin_immediate()
        rows = self.conn.execute(
            "SELECT * FROM control_plane_authorizations "
            "WHERE status IN ('PENDING', 'GRANTED') AND expires_at IS NOT NULL"
        ).fetchall()
        count = 0
        for row in rows:
            if self._expire_if_needed(row):
                count += 1
        return count

    def expire_stale_head(
        self,
        *,
        project_id: str,
        task_id: str,
        current_head_sha: str,
        actor: str,
    ) -> int:
        """Invalidate unconsumed authority when its exact HEAD changes."""

        if not current_head_sha:
            return 0
        self._begin_immediate()
        rows = self.conn.execute(
            "SELECT * FROM control_plane_authorizations WHERE project_id = ? "
            "AND task_id = ? AND status IN ('PENDING', 'GRANTED') "
            "AND head_sha IS NOT NULL AND head_sha != ?",
            (project_id, task_id, current_head_sha),
        ).fetchall()
        count = 0
        for row in rows:
            previous = self._authorization(row)
            at = now_iso()
            reason = f"HEAD changed to {current_head_sha}; exact authority expired"
            self.conn.execute(
                "UPDATE control_plane_authorizations SET status = 'EXPIRED', "
                "decision_reason = ?, decided_at = COALESCE(decided_at, ?), updated_at = ? "
                "WHERE request_id = ? AND status IN ('PENDING', 'GRANTED')",
                (reason, at, at, row["request_id"]),
            )
            if self.conn.execute("SELECT changes()").fetchone()[0] != 1:
                continue
            current = self.get(str(row["request_id"]), expire=False)
            event_id = self._emit_authorization_event(
                current,
                event_type="AUTHORIZATION_EXPIRED",
            )
            self.conn.execute(
                "UPDATE control_plane_authorizations SET decision_event_id = ? WHERE request_id = ?",
                (event_id, row["request_id"]),
            )
            current = self.get(str(row["request_id"]), expire=False)
            self._audit(
                entity_type="authorization",
                entity_id=str(row["request_id"]),
                event_type="expired_head_changed",
                idempotency_key=(
                    f"authorization:{row['request_id']}:expired_head:{current_head_sha}"
                ),
                previous=previous,
                next_value=current,
                actor=str(actor),
            )
            self._route_decision_to_source(current, actor=str(actor))
            count += 1
        return count

    def _expire_if_needed(self, row: sqlite3.Row) -> bool:
        expires_at = _parse_time(row["expires_at"])
        if expires_at is None or expires_at > datetime.now(timezone.utc):
            return False
        if str(row["status"]) not in {PENDING, GRANTED}:
            return False
        previous = self._authorization(row)
        updated_at = now_iso()
        self.conn.execute(
            "UPDATE control_plane_authorizations SET status = 'EXPIRED', decided_at = COALESCE(decided_at, ?), updated_at = ? "
            "WHERE request_id = ? AND status IN ('PENDING', 'GRANTED')",
            (updated_at, updated_at, row["request_id"]),
        )
        if self.conn.execute("SELECT changes()").fetchone()[0] != 1:
            return False
        current = self.get(str(row["request_id"]), expire=False)
        event_id = self._emit_authorization_event(
            current,
            event_type="AUTHORIZATION_EXPIRED",
        )
        self.conn.execute(
            "UPDATE control_plane_authorizations SET decision_event_id = ? WHERE request_id = ?",
            (event_id, row["request_id"]),
        )
        self._audit(
            entity_type="authorization",
            entity_id=str(row["request_id"]),
            event_type="expired",
            idempotency_key=f"authorization:{row['request_id']}:expired",
            previous=previous,
            next_value=current,
            actor="system",
        )
        self._route_decision_to_source(current, actor="system")
        return True

    def _merge_prerequisite_blockers(self, request: Mapping[str, Any]) -> list[str]:
        head_sha = str(request.get("head_sha") or "")
        if not head_sha:
            return ["missing_head_sha"]
        rows = self.conn.execute(
            "SELECT payload_json, event_at, applied FROM control_plane_session_events "
            "WHERE project_id = ? AND session_id IN ("
            "SELECT session_id FROM control_plane_sessions WHERE project_id = ? AND task_id = ?"
            ") ORDER BY rowid ASC",
            (request["project_id"], request["project_id"], request["task_id"]),
        ).fetchall()
        events: list[dict[str, Any]] = []
        for row in rows:
            payload = json_loads(row["payload_json"], {})
            if not isinstance(payload, dict) or payload.get("contract") != "agent_event/v1":
                continue
            if not bool(row["applied"]):
                continue
            revision = payload.get("revision") if isinstance(payload.get("revision"), dict) else {}
            if str(revision.get("head_sha") or "") != head_sha:
                continue
            events.append({**payload, "event_at": row["event_at"]})

        blockers: list[str] = []
        review_events = [
            event for event in events
            if event.get("event_type") in {"APPROVED", "CHANGES_REQUESTED"}
        ]
        if not review_events or review_events[-1].get("event_type") != "APPROVED":
            blockers.append("review_not_approved")

        ci_events = [event for event in events if event.get("event_type") == "LOCAL_CI_COMPLETED"]
        if not ci_events:
            blockers.append("local_ci_missing")
        else:
            latest_ci = ci_events[-1]
            ci = latest_ci.get("local_ci") if isinstance(latest_ci.get("local_ci"), dict) else {}
            if str(ci.get("status") or "").lower() not in {"passed", "success", "succeeded"}:
                blockers.append("local_ci_not_passed")
            completed_at = _parse_time(str(ci.get("completed_at") or latest_ci.get("created_at") or ""))
            if completed_at is None or completed_at < datetime.now(timezone.utc) - timedelta(hours=24):
                blockers.append("local_ci_stale")

        gate_events = [
            event for event in events
            if event.get("event_type") in {"MERGE_READY", "GATE_BLOCKED"}
        ]
        if not gate_events or gate_events[-1].get("event_type") != "MERGE_READY":
            blockers.append("merge_gate_not_ready")

        revision_events = [event for event in events if isinstance(event.get("revision"), dict)]
        revision = revision_events[-1].get("revision", {}) if revision_events else {}
        if str(revision.get("pr_state") or "").lower() != "open":
            blockers.append("pr_not_open")
        if revision.get("mergeable") is not True:
            blockers.append("pr_not_mergeable")

        return sorted(set(blockers))

    def _emit_authorization_event(
        self,
        authorization: Mapping[str, Any],
        *,
        event_type: str,
    ) -> str:
        status = str(authorization.get("status") or "").lower()
        event_id = f"auth_{authorization['request_id']}_{event_type.lower()}_{status}"
        actor = authorization.get("approver") if isinstance(authorization.get("approver"), dict) else {}
        requester = authorization.get("requester") if isinstance(authorization.get("requester"), dict) else {}
        payload = {
            "contract": "agent_event/v1",
            "event_id": event_id,
            "event_type": event_type,
            "project_id": authorization["project_id"],
            "requirement_id": authorization.get("requirement_id"),
            "task_id": authorization["task_id"],
            "session_id": authorization["session_id"],
            "entity_type": "authorization",
            "entity_id": authorization["request_id"],
            "source_task_id": authorization["task_id"],
            "destination_task_id": authorization.get("source_task_id")
            or authorization["task_id"],
            "priority": "P0"
            if authorization.get("risk_level") == "critical"
            else "P1"
            if authorization.get("human_required")
            else "P3",
            "requires_human": event_type
            in {"AUTHORIZATION_ROUTED", "AUTHORIZATION_PLATFORM_MANUAL_REQUIRED"}
            and bool(authorization.get("human_required")),
            "occurred_at": _latest_iso(
                str(authorization.get("requested_at") or "") or None,
                str(authorization.get("decided_at") or "") or None,
                str(authorization.get("consumed_at") or "") or None,
            ),
            "actor": actor or {"id": "system", "role": "system"},
            "source": actor or {"agent_id": "system"},
            "destination": {
                "agent_id": requester.get("id"),
                "task_id": authorization.get("source_task_id")
                or authorization["task_id"],
                "session_id": authorization["session_id"],
            },
            "summary": f"授权请求 {authorization['request_id']} 状态为 {authorization['status']}",
            "authorization": {
                "request_id": authorization["request_id"],
                "source_task_id": authorization.get("source_task_id")
                or authorization["task_id"],
                "requester_role": authorization.get("requester_role"),
                "authorization_kind": authorization.get("authorization_kind"),
                "action": authorization.get("action"),
                "action_class": authorization.get("action_class"),
                "risk_tier": authorization.get("risk_level"),
                "human_required": bool(authorization.get("human_required")),
                "exact_target": authorization.get("exact_targets") or [],
                "command_or_action_digest": authorization.get(
                    "command_or_action_digest"
                ),
                "reason": authorization.get("reason"),
                "scope": authorization.get("target_scope"),
                "status": authorization["status"],
                "authorization_level": authorization["authorization_level"],
                "policy_version": authorization["policy_version"],
                "matched_rule_id": authorization.get("matched_rule_id"),
                "exact_targets": authorization["exact_targets"],
                "environment": authorization.get("environment"),
                "head_sha": authorization.get("head_sha"),
                "expires_at": authorization.get("expires_at"),
                "approver": actor,
                "decision_actor": actor,
                "decision_time": authorization.get("decided_at"),
                "decision_reason": authorization.get("decision_reason"),
                "capability_status": authorization.get("capability_status"),
                "platform_request_ref": authorization.get("platform_request_ref"),
            },
            "safety": {"projection": "summary_and_references", "redacted_fields": []},
        }
        payload["created_at"] = payload["occurred_at"]
        payload["payload_digest"] = hashlib.sha256(
            json.dumps(
                payload,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        payload["fingerprint_sha256"] = payload["payload_digest"]
        result = ControlPlaneService(self.conn).record_session_event(
            session_id=str(authorization["session_id"]),
            event_type="status",
            idempotency_key=f"agent_event/v1:{event_id}",
            event_id=event_id,
            event_at=payload["created_at"],
            payload=payload,
            project_id=str(authorization["project_id"]),
            source="delegated_authorization",
            actor=str((actor or {"id": "system"}).get("id") or "system"),
        )
        return str((result.get("event") or {}).get("event_id") or event_id)

    def _route_decision_to_source(
        self, authorization: Mapping[str, Any], *, actor: str
    ) -> None:
        """Return text/native decision state to the original task when inbox exists."""

        exists = self.conn.execute(
            "SELECT 1 FROM control_plane_event_inbox WHERE event_id = ?",
            (authorization.get("request_event_id"),),
        ).fetchone()
        if exists is None:
            return
        # Imported lazily to keep Router -> AuthorizationService stale-HEAD handling acyclic.
        from .event_router import EventRouter

        EventRouter(self.conn).route_authorization_decision_to_source(
            str(authorization["request_event_id"]),
            actor=actor,
            decision_status=str(authorization["status"]),
        )

    def _latest_task_head(self, *, project_id: str, task_id: str) -> str | None:
        rows = self.conn.execute(
            "SELECT payload_json FROM control_plane_session_events WHERE project_id = ? "
            "AND applied = 1 ORDER BY rowid DESC",
            (project_id,),
        ).fetchall()
        for row in rows:
            payload = json_loads(row["payload_json"], {})
            if not isinstance(payload, Mapping) or payload.get("contract") != "agent_event/v1":
                continue
            if str(payload.get("task_id") or "") != task_id:
                continue
            revision = payload.get("revision")
            if isinstance(revision, Mapping) and revision.get("head_sha"):
                return str(revision["head_sha"])
        return None

    def _audit(
        self,
        *,
        entity_type: str,
        entity_id: str,
        event_type: str,
        idempotency_key: str,
        previous: Mapping[str, Any],
        next_value: Mapping[str, Any],
        actor: str,
    ) -> None:
        self.conn.execute(
            """
            INSERT INTO control_plane_state_changes(
                change_id, entity_type, entity_id, event_type, idempotency_key,
                previous_json, next_json, actor, source, occurred_at
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, 'delegated_authorization', ?)
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
                now_iso(),
            ),
        )

    def _overrides(self) -> dict[str, bool]:
        rows = self.conn.execute(
            "SELECT rule_id, enabled FROM control_plane_authorization_policy_overrides"
        ).fetchall()
        return {str(row["rule_id"]): bool(row["enabled"]) for row in rows}

    def _normalize_request_targets(
        self,
        *,
        project_id: str,
        task_id: str,
        session_id: str,
        request: Mapping[str, Any],
    ) -> dict[str, Any]:
        prepared = dict(request)
        targets = prepared.get("exact_targets")
        if not isinstance(targets, list):
            return prepared
        service = ControlPlaneService(self.conn)
        project = service.get_project(project_id)
        session = service.get_session(session_id)
        if str(session.get("project_id") or "") != project_id:
            raise ControlPlaneError(
                "authorization session belongs to another project",
                code="authorization_project_mismatch",
            )
        if session.get("task_id") and str(session.get("task_id")) != task_id:
            raise ControlPlaneError(
                "authorization session belongs to another task",
                code="authorization_task_mismatch",
            )
        target_scope = str(prepared.get("target_scope") or "").strip().lower()
        normalized_targets: list[str] = []
        scope_violation_reason: str | None = None
        for raw in targets:
            normalized, violation = self._normalize_one_target(
                project=project,
                session=session,
                service=service,
                target_scope=target_scope,
                environment=str(prepared.get("environment") or ""),
                target=str(raw),
                head_sha=str(prepared.get("head_sha") or ""),
            )
            if violation:
                scope_violation_reason = violation
                break
            normalized_targets.append(normalized)
        if scope_violation_reason:
            prepared["scope_violation"] = True
            prepared["scope_violation_reason"] = scope_violation_reason
            prepared["scope_violation_fields"] = ["target_scope"]
            return prepared
        prepared["exact_targets"] = sorted(set(normalized_targets))
        prepared["exact_target"] = list(prepared["exact_targets"])
        prepared["scope_validated"] = True
        return prepared

    def _normalize_one_target(
        self,
        *,
        project: Mapping[str, Any],
        session: Mapping[str, Any],
        service: ControlPlaneService,
        target_scope: str,
        environment: str,
        target: str,
        head_sha: str,
    ) -> tuple[str, str | None]:
        raw_target = str(target).strip()
        if not raw_target:
            return "", "authorization exact_targets cannot be empty"
        if target_scope == "task_workspace":
            return self._normalize_workspace_target(
                project=project,
                session=session,
                service=service,
                environment=environment,
                target=raw_target,
            )
        if target_scope == "temporary_directory":
            return self._normalize_temporary_target(
                project=project,
                session=session,
                service=service,
                target=raw_target,
            )
        if target_scope == "registered_test_environment":
            normalized = self._normalize_named_target(raw_target, prefixes=("service", "worker", "env"))
            if normalized is None or "prod" in normalized.lower():
                return raw_target, (
                    "authorization exact_targets must name a registered test environment target "
                    "such as service:test-api"
                )
            return normalized, None
        if target_scope == "verified_test_snapshot":
            normalized = self._normalize_named_target(raw_target, prefixes=("snapshot",))
            if normalized is None:
                return raw_target, "authorization exact_targets must name a verified test snapshot"
            return normalized, None
        if target_scope == "exact_pr_head":
            normalized = self._normalize_pr_target(raw_target, head_sha=head_sha)
            if normalized is None:
                return raw_target, "authorization exact_targets must bind one exact PR HEAD"
            return normalized, None
        if raw_target.startswith(LOGICAL_TARGET_PREFIXES):
            return raw_target, None
        return raw_target, None

    def _normalize_workspace_target(
        self,
        *,
        project: Mapping[str, Any],
        session: Mapping[str, Any],
        service: ControlPlaneService,
        environment: str,
        target: str,
    ) -> tuple[str, str | None]:
        candidate = str(Path(target).resolve())
        scope_environment = self._path_environment(environment)
        validation = service.validate_write_scope(
            str(project["project_id"]),
            [candidate],
            environment=scope_environment,
        )
        if not validation["ok"]:
            return candidate, "authorization exact_targets exceed the registered project development roots"
        workspace_roots = [
            str(Path(str(raw)).resolve())
            for raw in (session.get("worktree"), session.get("cwd"))
            if raw
        ]
        if workspace_roots and not any(
            candidate == root or candidate.startswith(f"{root}/")
            for root in workspace_roots
        ):
            return candidate, "authorization exact_targets exceed the current task workspace"
        return candidate, None

    def _normalize_temporary_target(
        self,
        *,
        project: Mapping[str, Any],
        session: Mapping[str, Any],
        service: ControlPlaneService,
        target: str,
    ) -> tuple[str, str | None]:
        candidate = str(Path(target).resolve())
        temp_root = str(Path(tempfile.gettempdir()).resolve())
        if candidate == temp_root or candidate.startswith(f"{temp_root}/"):
            return candidate, None
        return self._normalize_workspace_target(
            project=project,
            session=session,
            service=service,
            environment="dev",
            target=candidate,
        )

    @staticmethod
    def _normalize_named_target(target: str, *, prefixes: Sequence[str]) -> str | None:
        for prefix in prefixes:
            normalized_prefixes = (f"{prefix}:", f"{prefix}://")
            for candidate_prefix in normalized_prefixes:
                if target.startswith(candidate_prefix):
                    name = target[len(candidate_prefix):].strip().lstrip("/")
                    return f"{prefix}:{name}" if name else None
        return None

    @staticmethod
    def _normalize_pr_target(target: str, *, head_sha: str) -> str | None:
        if target.startswith("pr://"):
            target = f"pr:{target[len('pr://'):].lstrip('/')}"
        if not target.startswith("pr:") or "@" not in target:
            return None
        pr_ref, target_head = target.split("@", 1)
        pr_number = pr_ref.removeprefix("pr:").strip()
        normalized_head = target_head.strip()
        if not pr_number.isdigit() or not normalized_head:
            return None
        if head_sha and normalized_head != head_sha:
            return None
        return f"pr:{pr_number}@{normalized_head}"

    @staticmethod
    def _path_environment(environment: str) -> str:
        normalized = str(environment or "").strip().lower()
        if normalized in {"prod", "production"}:
            return "prod"
        return "dev"

    def _begin_immediate(self) -> None:
        if not self.conn.in_transaction:
            self.conn.execute("BEGIN IMMEDIATE")

    def _policy_override_row(self, rule_id: str) -> dict[str, Any] | None:
        row = self.conn.execute(
            "SELECT * FROM control_plane_authorization_policy_overrides WHERE rule_id = ?",
            (rule_id,),
        ).fetchone()
        return dict(row) if row is not None else None

    def _row(self, request_id: str) -> sqlite3.Row | None:
        return self.conn.execute(
            "SELECT * FROM control_plane_authorizations WHERE request_id = ?",
            (request_id,),
        ).fetchone()

    @staticmethod
    def _authorization(row: sqlite3.Row | None) -> dict[str, Any]:
        if row is None:
            return {}
        value = dict(row)
        for key, default in (
            ("requester_json", {}),
            ("exact_targets_json", []),
            ("secret_refs_json", []),
            ("incomplete_fields_json", []),
            ("approver_json", {}),
        ):
            value[key.removesuffix("_json")] = json_loads(value.pop(key), default)
        value["reversible"] = None if value["reversible"] is None else bool(value["reversible"])
        value["human_required"] = bool(value.get("human_required"))
        value["exact_target"] = list(value.get("exact_targets") or [])
        value["scope"] = value.get("target_scope")
        value["risk_tier"] = value.get("risk_level")
        value["decision_actor"] = value.get("approver") or {}
        value["decision_time"] = value.get("decided_at")
        value["grantable"] = (
            not bool(value["incomplete_fields"])
            and value.get("authorization_kind") != CODEX_PLATFORM_AUTHORIZATION
        )
        return value
