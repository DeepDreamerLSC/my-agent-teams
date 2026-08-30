from __future__ import annotations

import json
import sqlite3
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable, Mapping

from control_plane.agent_events import AGENT_EVENT_CONTRACT, event_record_to_public
from control_plane.authorization_policy import L0_AUTO, L1_REVIEWER_COORDINATOR, L2_OWNER
from control_plane.collaboration_schema import initialize_collaboration_schema
from control_plane.event_router import EventRouter
from control_plane.models import json_loads, now_iso


ACTIVE_STAGES = {"development", "fix", "rereview", "merge_gate"}
REVIEW_STAGES = {"review", "rereview", "review_approved"}
TERMINAL_STAGES = {"merged", "completed"}
PASSED_CI = {"passed", "success", "succeeded"}
STUCK_ACTIVE_AFTER = timedelta(minutes=30)
STUCK_BLOCKED_AFTER = timedelta(minutes=15)
CI_FRESH_FOR = timedelta(hours=24)

EVENT_STAGE = {
    "TASK_CREATED": "created",
    "TASK_STARTED": "development",
    "TASK_PROGRESS": "development",
    "TASK_BLOCKED": "blocked",
    "TASK_COMPLETED": "review",
    "READY_FOR_REVIEW": "review",
    "CHANGES_REQUESTED": "fix",
    "FIX_READY": "rereview",
    "APPROVED": "review_approved",
    "MERGE_GATE_RUNNING": "merge_gate",
    "MERGE_READY": "merge_ready",
    "GATE_BLOCKED": "merge_blocked",
    "MERGED": "merged",
}


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (name,)
    ).fetchone() is not None


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


def _latest_time(values: Iterable[Any]) -> str | None:
    parsed = [(item, _parse_time(item)) for item in values if item]
    parsed = [item for item in parsed if item[1] is not None]
    return max(parsed, key=lambda item: item[1])[0] if parsed else None


def _duration_seconds(start: Any, end: Any, now: datetime) -> int | None:
    started = _parse_time(start)
    if started is None:
        return None
    finished = _parse_time(end) or now
    return max(0, int((finished - started).total_seconds()))


def _safe_json(value: Any, default: Any) -> Any:
    parsed = json_loads(value, default)
    return parsed if isinstance(parsed, type(default)) else default


def _safe_artifact(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "artifact_id": row.get("artifact_id"),
        "kind": row.get("kind"),
        "uri": row.get("uri"),
        "checksum": row.get("checksum"),
        "summary": str(row.get("summary") or "")[:500],
        "created_at": row.get("created_at"),
    }


def _load_agent_events(
    conn: sqlite3.Connection,
    *,
    project_id: str | None = None,
    task_id: str | None = None,
) -> list[dict[str, Any]]:
    clauses: list[str] = []
    args: list[Any] = []
    if project_id:
        clauses.append("project_id = ?")
        args.append(project_id)
    where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = conn.execute(
        "SELECT rowid AS event_rowid, * FROM control_plane_session_events"
        f"{where} ORDER BY rowid ASC",
        args,
    ).fetchall()
    events: list[dict[str, Any]] = []
    for row in rows:
        public = event_record_to_public(row)
        payload = public.get("payload") or {}
        if payload.get("contract") != AGENT_EVENT_CONTRACT:
            continue
        if task_id and payload.get("task_id") != task_id:
            continue
        events.append(public)
    return events


def _load_deliveries(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    if not _table_exists(conn, "control_plane_deliveries"):
        return []
    columns = {
        row["name"] for row in conn.execute("PRAGMA table_info(control_plane_deliveries)")
    }
    allowed = [
        name
        for name in (
            "delivery_id",
            "project_id",
            "requirement_id",
            "task_id",
            "session_id",
            "execution_backend",
            "execution_kind",
            "status",
            "requested_at",
            "deadline_at",
            "sent_at",
            "acknowledged_at",
            "started_at",
            "completed_at",
            "updated_at",
            "result_uri",
            "summary",
            "last_error",
        )
        if name in columns
    ]
    if not allowed:
        return []
    return [
        {key: row[key] for key in allowed}
        for row in conn.execute(
            f"SELECT {', '.join(allowed)} FROM control_plane_deliveries ORDER BY rowid"
        ).fetchall()
    ]


def _authorization_rows(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    if not _table_exists(conn, "control_plane_authorizations"):
        return []
    now = datetime.now(timezone.utc)
    results: list[dict[str, Any]] = []
    for row in conn.execute(
        "SELECT * FROM control_plane_authorizations ORDER BY requested_at DESC"
    ).fetchall():
        value = dict(row)
        status = str(value.get("status") or "")
        expiry = _parse_time(value.get("expires_at"))
        if status in {"PENDING", "GRANTED"} and expiry is not None and expiry <= now:
            status = "EXPIRED"
        results.append(
            {
                "request_id": value.get("request_id"),
                "project_id": value.get("project_id"),
                "requirement_id": value.get("requirement_id"),
                "task_id": value.get("task_id"),
                "session_id": value.get("session_id"),
                "requester": _safe_json(value.get("requester_json"), {}),
                "action": value.get("action"),
                "action_type": value.get("action_type"),
                "environment": value.get("environment"),
                "target_scope": value.get("target_scope"),
                "exact_targets": _safe_json(value.get("exact_targets_json"), []),
                "head_sha": value.get("head_sha"),
                "secret_refs": _safe_json(value.get("secret_refs_json"), []),
                "reason": value.get("reason"),
                "reversible": None
                if value.get("reversible") is None
                else bool(value.get("reversible")),
                "expires_at": value.get("expires_at"),
                "authorization_level": value.get("authorization_level"),
                "risk_level": value.get("risk_level"),
                "matched_rule_id": value.get("matched_rule_id"),
                "routing_reason": value.get("routing_reason"),
                "incomplete_fields": _safe_json(
                    value.get("incomplete_fields_json"), []
                ),
                "policy_version": value.get("policy_version"),
                "status": status,
                "approver": _safe_json(value.get("approver_json"), {}),
                "decision_reason": value.get("decision_reason"),
                "requested_at": value.get("requested_at"),
                "decided_at": value.get("decided_at"),
                "consumed_at": value.get("consumed_at"),
                "authorization_kind": value.get("authorization_kind") or "text",
                "source_task_id": value.get("source_task_id") or value.get("task_id"),
                "requester_role": value.get("requester_role") or "unknown",
                "action_class": value.get("action_class") or value.get("action_type"),
                "command_or_action_digest": value.get("command_or_action_digest"),
                "capability_status": value.get("capability_status")
                or "text_route_available",
                "human_required": bool(value.get("human_required")),
                "platform_request_ref": value.get("platform_request_ref"),
                "exact_target": _safe_json(value.get("exact_targets_json"), []),
                "scope": value.get("target_scope"),
                "risk_tier": value.get("risk_level"),
                "decision_actor": _safe_json(value.get("approver_json"), {}),
                "decision_time": value.get("decided_at"),
            }
        )
    return results


def _message_flow(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for event in events:
        payload = event["payload"]
        if payload.get("event_type") not in {
            "MESSAGE_SENT",
            "MESSAGE_DELIVERED",
            "CALLBACK_RECEIVED",
        }:
            continue
        delivery = payload.get("delivery") or {}
        delivery_id = str(delivery.get("delivery_id") or event["event_id"])
        item = grouped.setdefault(
            delivery_id,
            {
                "delivery_id": delivery_id,
                "source": payload.get("source") or {},
                "destination": payload.get("destination") or {},
                "summary": payload.get("summary") or "",
                "sent_at": None,
                "delivered_at": None,
                "callback_at": None,
                "ack_id": None,
                "callback_id": None,
                "status": "pending",
            },
        )
        event_type = payload.get("event_type")
        if event_type == "MESSAGE_SENT":
            item["sent_at"] = payload.get("created_at")
            item["status"] = "sent"
        elif event_type == "MESSAGE_DELIVERED":
            item["delivered_at"] = payload.get("created_at")
            item["ack_id"] = delivery.get("ack_id")
            item["status"] = "delivered"
        else:
            item["callback_at"] = payload.get("created_at")
            item["callback_id"] = delivery.get("callback_id")
            item["status"] = "completed"
    return sorted(grouped.values(), key=lambda item: item.get("sent_at") or "")


def _native_delivery_projection(
    deliveries: list[dict[str, Any]], *, project_id: str, task_id: str
) -> list[dict[str, Any]]:
    projected: list[dict[str, Any]] = []
    for row in deliveries:
        if row.get("project_id") != project_id or row.get("task_id") != task_id:
            continue
        projected.append(
            {
                "delivery_id": row.get("delivery_id"),
                "source": {"session_id": row.get("session_id")},
                "destination": {},
                "summary": str(row.get("summary") or "")[:500],
                "sent_at": row.get("sent_at") or row.get("requested_at"),
                "delivered_at": row.get("acknowledged_at"),
                "callback_at": row.get("completed_at"),
                "status": row.get("status"),
                "deadline_at": row.get("deadline_at"),
                "last_error": str(row.get("last_error") or "")[:300],
                "result_uri": row.get("result_uri"),
            }
        )
    return projected


def _latest_for_head(
    events: list[dict[str, Any]], event_types: set[str], head_sha: str | None
) -> dict[str, Any] | None:
    candidates: list[dict[str, Any]] = []
    for event in events:
        if not event.get("applied"):
            continue
        payload = event["payload"]
        if payload.get("event_type") not in event_types:
            continue
        revision = payload.get("revision") or {}
        event_head = revision.get("head_sha") or (payload.get("local_ci") or {}).get(
            "head_sha"
        )
        if head_sha and event_head and event_head != head_sha:
            continue
        candidates.append(event)
    return candidates[-1] if candidates else None


def _stage_segments(events: list[dict[str, Any]], now: datetime) -> list[dict[str, Any]]:
    transitions: list[tuple[str, str]] = []
    for event in events:
        if not event.get("applied"):
            continue
        payload = event["payload"]
        stage = EVENT_STAGE.get(str(payload.get("event_type") or ""))
        if stage and (not transitions or transitions[-1][1] != stage):
            transitions.append((str(payload.get("created_at") or event.get("event_at")), stage))
    segments: list[dict[str, Any]] = []
    for index, (started_at, stage) in enumerate(transitions):
        end_at = transitions[index + 1][0] if index + 1 < len(transitions) else None
        if stage in TERMINAL_STAGES:
            end_at = started_at
        segments.append(
            {
                "stage": stage,
                "started_at": started_at,
                "ended_at": end_at,
                "duration_seconds": _duration_seconds(started_at, end_at, now),
            }
        )
    return segments


def _risk_for(findings: Mapping[str, Any], authorizations: list[dict[str, Any]]) -> str:
    counts = findings.get("finding_counts") or {}
    if counts.get("P0"):
        return "critical"
    if counts.get("P1"):
        return "high"
    pending_risks = {
        item.get("risk_level")
        for item in authorizations
        if item.get("status") == "PENDING"
    }
    if "critical" in pending_risks:
        return "critical"
    if "high" in pending_risks:
        return "high"
    if counts.get("P2") or "medium" in pending_risks:
        return "medium"
    return "low"


def _matches_filters(task: Mapping[str, Any], filters: Mapping[str, str | None]) -> bool:
    if filters.get("project") and task.get("project_id") != filters["project"]:
        return False
    if filters.get("role"):
        roles = {item.get("role") for item in task.get("agents", [])}
        if filters["role"] not in roles:
            return False
    if filters.get("status") and task.get("stage") != filters["status"]:
        return False
    if filters.get("risk") and task.get("risk_level") != filters["risk"]:
        return False
    pr_filter = filters.get("pr")
    revision = task.get("revision") or {}
    if pr_filter == "has_pr" and not revision.get("pr_number"):
        return False
    if pr_filter == "missing" and revision.get("pr_number"):
        return False
    if pr_filter == "open" and str(revision.get("pr_state") or "").lower() != "open":
        return False
    if pr_filter == "mergeable" and revision.get("mergeable") is not True:
        return False
    return True


def build_collaboration_overview(
    conn: sqlite3.Connection,
    *,
    project: str | None = None,
    role: str | None = None,
    status: str | None = None,
    pr: str | None = None,
    risk: str | None = None,
) -> dict[str, Any]:
    initialize_collaboration_schema(conn)
    now = datetime.now(timezone.utc)
    projects = {
        row["project_id"]: dict(row)
        for row in conn.execute("SELECT * FROM control_plane_projects ORDER BY name")
    }
    requirements = {
        row["requirement_id"]: dict(row)
        for row in conn.execute("SELECT * FROM control_plane_requirements")
    }
    sessions = [dict(row) for row in conn.execute("SELECT * FROM control_plane_sessions")]
    events = _load_agent_events(conn)
    artifacts = [
        dict(row)
        for row in conn.execute("SELECT * FROM control_plane_artifacts ORDER BY created_at")
    ]
    native_gates = [
        dict(row) for row in conn.execute("SELECT * FROM control_plane_gates ORDER BY entered_at")
    ]
    deliveries = _load_deliveries(conn)
    authorizations = _authorization_rows(conn)
    router = EventRouter(conn)
    inbox_items = router.list_inbox(project_id=project, limit=200)
    inbox_summary = router.summary(project_id=project)
    focus = router.get_focus("main")

    records: dict[tuple[str, str], dict[str, Any]] = {}
    if _table_exists(conn, "tasks"):
        for row in conn.execute("SELECT * FROM tasks"):
            value = dict(row)
            project_id = str(value.get("project") or "unassigned")
            task_id = str(value.get("task_id") or "")
            if task_id:
                records[(project_id, task_id)] = value
    for session in sessions:
        if session.get("task_id"):
            records.setdefault(
                (str(session["project_id"]), str(session["task_id"])), {}
            )
    for event in events:
        payload = event["payload"]
        records.setdefault(
            (str(payload["project_id"]), str(payload["task_id"])), {}
        )

    sessions_by_task: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for session in sessions:
        if session.get("task_id"):
            sessions_by_task[(str(session["project_id"]), str(session["task_id"]))].append(
                session
            )
    events_by_task: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for event in events:
        payload = event["payload"]
        events_by_task[(str(payload["project_id"]), str(payload["task_id"]))].append(event)
    auth_by_task: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for item in authorizations:
        auth_by_task[(str(item["project_id"]), str(item["task_id"]))].append(item)

    tasks: list[dict[str, Any]] = []
    for key, legacy in records.items():
        project_id, task_id = key
        task_sessions = sessions_by_task[key]
        task_events = events_by_task[key]
        applied_events = [item for item in task_events if item.get("applied")]
        payloads = [item["payload"] for item in applied_events]
        latest_payload = payloads[-1] if payloads else {}
        requirement_id = next(
            (
                str(item.get("requirement_id"))
                for item in reversed(payloads)
                if item.get("requirement_id")
            ),
            next(
                (
                    str(item.get("requirement_id"))
                    for item in task_sessions
                    if item.get("requirement_id")
                ),
                "",
            ),
        )
        requirement = requirements.get(requirement_id, {})
        revision = next(
            (
                dict(item.get("revision") or {})
                for item in reversed(payloads)
                if (item.get("revision") or {}).get("head_sha")
            ),
            {},
        )
        head_sha = revision.get("head_sha")
        review_event = _latest_for_head(
            task_events, {"READY_FOR_REVIEW", "CHANGES_REQUESTED", "APPROVED"}, head_sha
        )
        ci_event = _latest_for_head(task_events, {"LOCAL_CI_COMPLETED"}, head_sha)
        gate_event = _latest_for_head(
            task_events, {"MERGE_GATE_RUNNING", "MERGE_READY", "GATE_BLOCKED"}, head_sha
        )
        review = dict((review_event or {}).get("payload", {}).get("review") or {})
        if review_event:
            review["event_type"] = review_event["payload"].get("event_type")
            review["event_at"] = review_event["payload"].get("created_at")
        local_ci = dict((ci_event or {}).get("payload", {}).get("local_ci") or {})
        if ci_event:
            completed_at = local_ci.get("completed_at") or ci_event["payload"].get(
                "created_at"
            )
            completed = _parse_time(completed_at)
            local_ci["fresh"] = bool(
                completed
                and completed >= now - CI_FRESH_FOR
                and str(local_ci.get("status") or "").lower() in PASSED_CI
                and (
                    not head_sha
                    or not local_ci.get("head_sha")
                    or local_ci.get("head_sha") == head_sha
                )
            )
            local_ci["freshness_hours"] = 24
        merge_gate = dict((gate_event or {}).get("payload", {}).get("merge_gate") or {})
        if gate_event:
            merge_gate["event_type"] = gate_event["payload"].get("event_type")
            merge_gate["event_at"] = gate_event["payload"].get("created_at")

        stage = next(
            (
                EVENT_STAGE[str(item.get("event_type") or "")]
                for item in reversed(payloads)
                if str(item.get("event_type") or "") in EVENT_STAGE
            ),
            None,
        )
        if not stage:
            stage = next(
                (str(item.get("current_gate")) for item in task_sessions if item.get("current_gate")),
                None,
            )
        if not stage:
            stage = str(legacy.get("board_status") or legacy.get("current_status") or "unknown")
        started_at = next(
            (
                item.get("created_at")
                for item in payloads
                if item.get("event_type") == "TASK_STARTED"
            ),
            legacy.get("ack_at") or legacy.get("dispatched_at"),
        )
        completed_at = next(
            (
                item.get("created_at")
                for item in reversed(payloads)
                if item.get("event_type") in {"TASK_COMPLETED", "MERGED"}
            ),
            legacy.get("completed_at"),
        )
        last_activity_at = _latest_time(
            [
                legacy.get("updated_at"),
                *[item.get("updated_at") or item.get("last_seen_at") for item in task_sessions],
                *[item["payload"].get("created_at") for item in task_events],
            ]
        )
        agents = [
            {
                "agent_id": item.get("external_ref") or item.get("thread_id") or item.get("session_id"),
                "session_id": item.get("session_id"),
                "role": item.get("role"),
                "status": item.get("session_status"),
                "last_seen_at": item.get("last_seen_at"),
            }
            for item in task_sessions
        ]
        if legacy.get("assigned_agent") and not any(
            item["agent_id"] == legacy.get("assigned_agent") for item in agents
        ):
            agents.append(
                {
                    "agent_id": legacy.get("assigned_agent"),
                    "session_id": None,
                    "role": "developer",
                    "status": stage,
                    "last_seen_at": legacy.get("updated_at"),
                }
            )
        if legacy.get("reviewer") and not any(
            item["agent_id"] == legacy.get("reviewer") for item in agents
        ):
            agents.append(
                {
                    "agent_id": legacy.get("reviewer"),
                    "session_id": None,
                    "role": "reviewer",
                    "status": stage,
                    "last_seen_at": legacy.get("updated_at"),
                }
            )

        relations: dict[str, Any] = {}
        for payload in payloads:
            candidate = payload.get("relations") or {}
            if candidate:
                relations.update(candidate)
        if legacy.get("parent_task_id") and not relations.get("parent_task_id"):
            relations["parent_task_id"] = legacy["parent_task_id"]
        for key_name in ("depends_on", "blocks"):
            if not isinstance(relations.get(key_name), list):
                relations[key_name] = []

        event_messages = _message_flow(task_events)
        native_messages = _native_delivery_projection(
            deliveries, project_id=project_id, task_id=task_id
        )
        messages = native_messages or event_messages
        task_artifacts = [
            _safe_artifact(row)
            for row in artifacts
            if row.get("project_id") == project_id and row.get("task_id") == task_id
        ]
        for payload in payloads:
            if payload.get("event_type") == "ARTIFACT_CREATED" and payload.get("artifact"):
                item = dict(payload["artifact"])
                item["created_at"] = payload.get("created_at")
                task_artifacts.append(_safe_artifact(item))
        task_auth = auth_by_task[key]
        blockers: list[str] = []
        if not review_event or review_event["payload"].get("event_type") != "APPROVED":
            blockers.append("独立审查尚未批准当前 HEAD")
        if not local_ci or not local_ci.get("fresh"):
            blockers.append("当前 HEAD 缺少 24 小时内通过的 Local CI")
        if not gate_event or gate_event["payload"].get("event_type") != "MERGE_READY":
            blockers.append("merge-gate 尚未就绪")
        if str(revision.get("pr_state") or "").lower() != "open":
            blockers.append("PR 不是 open")
        if revision.get("mergeable") is not True:
            blockers.append("PR mergeable 尚未确认")
        if isinstance(merge_gate.get("blocking_checks"), list):
            blockers.extend(str(item)[:200] for item in merge_gate["blocking_checks"] if item)
        merge_gate["blocking_checks"] = sorted(set(blockers))
        merge_gate["allowed"] = not blockers

        age_seconds = _duration_seconds(last_activity_at, None, now)
        stuck_reasons: list[str] = []
        threshold = None
        if stage in {"blocked", "merge_blocked"}:
            threshold = STUCK_BLOCKED_AFTER
            if age_seconds is not None and age_seconds >= threshold.total_seconds():
                stuck_reasons.append("阻塞状态超过 15 分钟无新活动")
        elif stage in ACTIVE_STAGES | REVIEW_STAGES:
            threshold = STUCK_ACTIVE_AFTER
            if age_seconds is not None and age_seconds >= threshold.total_seconds():
                stuck_reasons.append("活动或等待阶段超过 30 分钟无新事件")
        for message in messages:
            deadline = _parse_time(message.get("deadline_at"))
            if deadline and deadline < now and message.get("status") not in {
                "completed",
                "acknowledged",
                "delivered",
            }:
                stuck_reasons.append(f"消息 {message.get('delivery_id')} 已超过 ACK 截止时间")

        task = {
            "task_id": task_id,
            "title": legacy.get("title") or requirement.get("title") or task_id,
            "project_id": project_id,
            "project_name": (projects.get(project_id) or {}).get("name") or project_id,
            "requirement_id": requirement_id or None,
            "requirement_title": requirement.get("title"),
            "stage": stage,
            "runtime_status": next(
                (
                    item.get("session_status")
                    for item in task_sessions
                    if item.get("session_status") in {"busy", "blocked", "waiting_approval"}
                ),
                "idle" if stage in TERMINAL_STAGES | {"merge_ready"} else stage,
            ),
            "started_at": started_at,
            "completed_at": completed_at,
            "duration_seconds": _duration_seconds(started_at, completed_at, now),
            "last_activity_at": last_activity_at,
            "agents": agents,
            "relations": relations,
            "revision": revision,
            "review": review,
            "local_ci": local_ci,
            "merge_gate": merge_gate,
            "messages": messages,
            "artifacts": task_artifacts,
            "authorizations": task_auth,
            "authorization_pending": sum(
                1 for item in task_auth if item.get("status") == "PENDING"
            ),
            "risk_level": _risk_for(review, task_auth),
            "stuck": bool(stuck_reasons),
            "stuck_reasons": sorted(set(stuck_reasons)),
            "stuck_facts": {
                "last_activity_at": last_activity_at,
                "age_seconds": age_seconds,
                "threshold_seconds": int(threshold.total_seconds()) if threshold else None,
            },
            "event_count": len(task_events),
            "stale_event_count": sum(
                1 for item in task_events if item.get("rejection_reason") == "stale_head"
            ),
            "segments": _stage_segments(task_events, now),
        }
        tasks.append(task)

    filtered = [
        task
        for task in tasks
        if _matches_filters(
            task,
            {"project": project, "role": role, "status": status, "pr": pr, "risk": risk},
        )
    ]
    filtered.sort(key=lambda item: (item["project_id"], item["stage"], item["task_id"]))
    filtered_ids = {(item["project_id"], item["task_id"]) for item in filtered}

    topology_nodes: list[dict[str, Any]] = []
    topology_edges: list[dict[str, Any]] = []
    project_node_ids: set[str] = set()
    requirement_node_ids: set[str] = set()
    agent_node_ids: set[str] = set()
    for task in filtered:
        project_node = f"project:{task['project_id']}"
        if project_node not in project_node_ids:
            topology_nodes.append(
                {"id": project_node, "label": task["project_name"], "kind": "project"}
            )
            project_node_ids.add(project_node)
        requirement_node = None
        if task.get("requirement_id"):
            requirement_node = f"requirement:{task['requirement_id']}"
            if requirement_node not in requirement_node_ids:
                topology_nodes.append(
                    {
                        "id": requirement_node,
                        "label": task.get("requirement_title") or task["requirement_id"],
                        "kind": "requirement",
                    }
                )
                requirement_node_ids.add(requirement_node)
                topology_edges.append(
                    {"source": project_node, "target": requirement_node, "kind": "contains"}
                )
        task_node = f"task:{task['project_id']}:{task['task_id']}"
        topology_nodes.append(
            {
                "id": task_node,
                "label": task["title"],
                "kind": "task",
                "stage": task["stage"],
                "risk_level": task["risk_level"],
                "stuck": task["stuck"],
            }
        )
        topology_edges.append(
            {
                "source": requirement_node or project_node,
                "target": task_node,
                "kind": "contains",
            }
        )
        relations = task.get("relations") or {}
        parent = relations.get("parent_task_id")
        if parent and (task["project_id"], str(parent)) in filtered_ids:
            topology_edges.append(
                {
                    "source": f"task:{task['project_id']}:{parent}",
                    "target": task_node,
                    "kind": "parent",
                }
            )
        for dependency in relations.get("depends_on") or []:
            if (task["project_id"], str(dependency)) in filtered_ids:
                topology_edges.append(
                    {
                        "source": f"task:{task['project_id']}:{dependency}",
                        "target": task_node,
                        "kind": "depends_on",
                    }
                )
        for agent in task.get("agents") or []:
            agent_id = str(agent.get("agent_id") or "")
            if not agent_id:
                continue
            agent_node = f"agent:{agent_id}"
            if agent_node not in agent_node_ids:
                topology_nodes.append(
                    {"id": agent_node, "label": agent_id, "kind": "agent"}
                )
                agent_node_ids.add(agent_node)
            topology_edges.append(
                {
                    "source": agent_node,
                    "target": task_node,
                    "kind": str(agent.get("role") or "agent"),
                }
            )

    summary = {
        "task_count": len(filtered),
        "running_count": sum(1 for item in filtered if item["stage"] in ACTIVE_STAGES),
        "review_count": sum(1 for item in filtered if item["stage"] in REVIEW_STAGES),
        "blocked_count": sum(
            1 for item in filtered if item["stage"] in {"blocked", "merge_blocked"}
        ),
        "merge_ready_count": sum(
            1 for item in filtered if item["merge_gate"].get("allowed")
        ),
        "stuck_count": sum(1 for item in filtered if item["stuck"]),
        "pending_authorization_count": sum(
            item["authorization_pending"] for item in filtered
        ),
        "pending_event_count": inbox_summary["pending_count"],
        "human_decision_count": inbox_summary["human_required_count"],
    }
    status_counts: dict[str, int] = defaultdict(int)
    for task in filtered:
        status_counts[task["stage"]] += 1
    dependency_waits = sum(
        1
        for task in filtered
        for dependency in (task.get("relations") or {}).get("depends_on", [])
        if (task["project_id"], str(dependency)) in filtered_ids
        and next(
            (
                item["stage"]
                for item in filtered
                if item["project_id"] == task["project_id"]
                and item["task_id"] == str(dependency)
            ),
            "merged",
        )
        not in TERMINAL_STAGES | {"merge_ready"}
    )

    selected_auth = [
        item
        for item in authorizations
        if (not project or item.get("project_id") == project)
        and (item.get("project_id"), item.get("task_id")) in filtered_ids
    ]
    recent_event_ids = {item["task_id"] for item in filtered}
    recent_events = [
        event
        for event in reversed(events)
        if event["payload"].get("task_id") in recent_event_ids
        and (not project or event["payload"].get("project_id") == project)
    ][:50]
    return {
        "generated_at": now_iso(),
        "source": {
            "type": "sqlite_control_plane",
            "tables": [
                "tasks",
                "control_plane_projects",
                "control_plane_requirements",
                "control_plane_sessions",
                "control_plane_session_events",
                "control_plane_gates",
                "control_plane_artifacts",
                "control_plane_authorizations",
                "control_plane_event_inbox",
                "control_plane_event_routing_transitions",
                "control_plane_focus_leases",
            ],
            "freshness": max(
                (item.get("last_activity_at") or "" for item in filtered), default=""
            )
            or None,
        },
        "read_only": True,
        "summary": summary,
        "filters": {
            "projects": sorted({item["project_id"] for item in tasks}),
            "roles": sorted(
                {
                    str(agent.get("role"))
                    for item in tasks
                    for agent in item.get("agents", [])
                    if agent.get("role")
                }
            ),
            "statuses": sorted({item["stage"] for item in tasks}),
            "risks": ["low", "medium", "high", "critical"],
            "pr": ["has_pr", "open", "mergeable", "missing"],
        },
        "rules": {
            "stuck": [
                "development/fix/rereview/merge-gate/review 阶段 30 分钟无事件",
                "blocked/merge-blocked 阶段 15 分钟无事件",
                "消息超过明确 ACK deadline 且未完成",
            ],
            "merge_ready": "当前 HEAD 已批准 + 24 小时内 Local CI 通过 + merge-gate ready + PR open/mergeable + 无阻断检查",
            "authorization": {
                L0_AUTO: "仅显式白名单的低风险、可逆、非生产操作自动放行",
                L1_REVIEWER_COORDINATOR: "Reviewer/Coordinator 可在精确范围和现有门禁内委托批准",
                L2_OWNER: "生产、高风险、未知或信息不完整请求必须由 Owner 批准",
            },
        },
        "tasks": filtered,
        "authorizations": selected_auth,
        "inbox": {
            "summary": inbox_summary,
            "focus": focus,
            "items": inbox_items,
            "auto_forwarded": [
                item
                for item in inbox_items
                if item.get("classification") == "route_deferred"
                and item.get("route_status") in {"ROUTED", "ACKED"}
            ],
            "human_decisions": [
                item for item in inbox_items if item.get("route_status") == "ESCALATED"
            ],
        },
        "topology": {"nodes": topology_nodes, "edges": topology_edges},
        "timeline": [
            {
                "project_id": item["project_id"],
                "task_id": item["task_id"],
                "title": item["title"],
                "started_at": item["started_at"],
                "completed_at": item["completed_at"],
                "segments": item["segments"],
            }
            for item in filtered
        ],
        "bottlenecks": {
            "by_stage": dict(sorted(status_counts.items())),
            "dependency_wait_count": dependency_waits,
            "stuck_tasks": [
                {
                    "project_id": item["project_id"],
                    "task_id": item["task_id"],
                    "title": item["title"],
                    "reasons": item["stuck_reasons"],
                    "facts": item["stuck_facts"],
                }
                for item in filtered
                if item["stuck"]
            ],
        },
        "recent_events": recent_events,
        "native_gate_count": len(native_gates),
    }


def build_collaboration_task_detail(
    conn: sqlite3.Connection, *, project_id: str, task_id: str
) -> dict[str, Any] | None:
    overview = build_collaboration_overview(conn, project=project_id)
    task = next(
        (item for item in overview["tasks"] if item["task_id"] == task_id), None
    )
    if task is None:
        return None
    events = _load_agent_events(conn, project_id=project_id, task_id=task_id)
    router = EventRouter(conn)
    inbox = [
        item
        for item in router.list_inbox(project_id=project_id, limit=500)
        if task_id
        in {
            str(item.get("task_id") or ""),
            str(item.get("source_task_id") or ""),
            str(item.get("target_task_id") or ""),
        }
    ]
    safe_events = [
        {
            "event_id": item["event_id"],
            "event_type": item["payload"].get("event_type"),
            "created_at": item["payload"].get("created_at"),
            "actor": item["payload"].get("actor") or {},
            "source": item["payload"].get("source") or {},
            "destination": item["payload"].get("destination") or {},
            "summary": item["payload"].get("summary") or "",
            "applied": item["applied"],
            "rejection_reason": item["rejection_reason"],
            "revision": item["payload"].get("revision") or {},
            "safety": item["payload"].get("safety") or {},
        }
        for item in events
    ]
    audit = []
    if _table_exists(conn, "control_plane_state_changes"):
        rows = conn.execute(
            "SELECT entity_type, entity_id, event_type, actor, source, occurred_at "
            "FROM control_plane_state_changes WHERE entity_id = ? "
            "OR (entity_type = 'authorization' AND entity_id IN ("
            "SELECT request_id FROM control_plane_authorizations WHERE project_id = ? AND task_id = ?"
            ")) ORDER BY occurred_at DESC LIMIT 100",
            (task_id, project_id, task_id),
        ).fetchall()
        audit = [dict(row) for row in rows]
    return {
        "generated_at": now_iso(),
        "read_only": True,
        "task": task,
        "events": safe_events,
        "messages": task["messages"],
        "review": task["review"],
        "local_ci": task["local_ci"],
        "merge_gate": task["merge_gate"],
        "artifacts": task["artifacts"],
        "authorizations": task["authorizations"],
        "inbox": inbox,
        "audit": audit,
        "privacy": {
            "projection": "summary_and_references",
            "excluded": [
                "完整 prompt",
                "消息正文",
                "工具输入输出",
                "凭据与密钥正文",
                "学生数据",
            ],
        },
    }
