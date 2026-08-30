from __future__ import annotations

import json
import os
import sqlite3
import time
from contextlib import closing
from typing import Any, Callable

try:
    from flask import Blueprint, Response, current_app, jsonify, request, stream_with_context
except ImportError:  # pragma: no cover - the dashboard already reports this dependency.
    Blueprint = None
    Response = None
    current_app = None
    jsonify = None
    request = None
    stream_with_context = None

from control_plane.agent_events import AgentEventRecorder, list_agent_events
from control_plane.authorization import AuthorizationService
from control_plane.errors import ControlPlaneError
from control_plane.event_router import EventRouter

from .collaboration_query import (
    build_collaboration_overview,
    build_collaboration_task_detail,
)
from .db import connect_db


def _json_body() -> dict[str, Any]:
    body = request.get_json(silent=True)
    return body if isinstance(body, dict) else {}


def _error(exc: Exception):
    if isinstance(exc, ControlPlaneError):
        code = exc.code
        status = 404 if code.endswith("_not_found") else 409 if any(
            marker in code for marker in ("conflict", "concurrent", "terminal")
        ) else 403 if any(
            marker in code for marker in ("forbidden", "owner_required")
        ) else 400
        return jsonify({"error": {"code": code, "message": str(exc)}}), status
    if isinstance(exc, sqlite3.IntegrityError):
        return jsonify({"error": {"code": "integrity_error", "message": str(exc)}}), 409
    raise exc


def _local_or_token_denied():
    expected = os.getenv("MY_AGENT_TEAMS_CONTROL_PLANE_TOKEN", "").strip()
    if expected:
        if request.headers.get("Authorization", "") != f"Bearer {expected}":
            return jsonify(
                {
                    "error": {
                        "code": "unauthorized",
                        "message": "control-plane event token is invalid",
                    }
                }
            ), 401
        return None
    if request.remote_addr not in {None, "127.0.0.1", "::1"}:
        return jsonify(
            {
                "error": {
                    "code": "local_operator_required",
                    "message": "without a configured token this endpoint is localhost-only",
                }
            }
        ), 403
    return None


def _with_connection(callback: Callable[[sqlite3.Connection], Any], *, write: bool = False):
    with closing(connect_db(current_app.config["TASK_BOARD_DB_PATH"], initialize=False)) as conn:
        try:
            if write:
                with conn:
                    payload = callback(conn)
            else:
                payload = callback(conn)
            return jsonify(payload)
        except (ControlPlaneError, sqlite3.IntegrityError) as exc:
            return _error(exc)


def create_collaboration_blueprint():
    if Blueprint is None:
        raise RuntimeError("Flask is required for collaboration dashboard routes")
    blueprint = Blueprint("collaboration", __name__)

    @blueprint.get("/api/collaboration/overview")
    def overview():
        return _with_connection(
            lambda conn: build_collaboration_overview(
                conn,
                project=request.args.get("project"),
                role=request.args.get("role"),
                status=request.args.get("status"),
                pr=request.args.get("pr"),
                risk=request.args.get("risk"),
            )
        )

    @blueprint.get("/api/collaboration/tasks/<task_id>")
    def task_detail(task_id: str):
        project_id = str(request.args.get("project") or "").strip()
        if not project_id:
            return jsonify(
                {"error": {"code": "project_required", "message": "project is required"}}
            ), 400

        def load(conn: sqlite3.Connection):
            payload = build_collaboration_task_detail(
                conn, project_id=project_id, task_id=task_id
            )
            if payload is None:
                raise ControlPlaneError(
                    f"unknown collaboration task: {project_id}/{task_id}",
                    code="collaboration_task_not_found",
                )
            return payload

        return _with_connection(load)

    @blueprint.get("/api/collaboration/event-log")
    def event_log():
        return _with_connection(
            lambda conn: list_agent_events(
                conn,
                after_event_id=request.args.get("after_event_id")
                or request.headers.get("Last-Event-ID"),
                project_id=request.args.get("project"),
                task_id=request.args.get("task"),
                limit=request.args.get("limit", type=int) or 200,
            )
        )

    @blueprint.get("/api/collaboration/events")
    def event_stream():
        initial_cursor = request.args.get("after_event_id") or request.headers.get(
            "Last-Event-ID"
        )
        project_id = request.args.get("project")
        task_id = request.args.get("task")
        once = request.args.get("once") in {"1", "true", "yes"}
        db_path = current_app.config["TASK_BOARD_DB_PATH"]

        @stream_with_context
        def generate():
            cursor = initial_cursor
            last_keepalive = time.monotonic()
            while True:
                with closing(connect_db(db_path, initialize=False)) as conn:
                    batch = list_agent_events(
                        conn,
                        after_event_id=cursor,
                        project_id=project_id,
                        task_id=task_id,
                        limit=200,
                    )
                if batch["cursor_reset"]:
                    yield "event: cursor_reset\ndata: {}\n\n"
                for event in batch["events"]:
                    cursor = event["event_id"]
                    yield (
                        f"id: {cursor}\n"
                        "event: agent_event\n"
                        f"data: {json.dumps(event, ensure_ascii=False, separators=(',', ':'))}\n\n"
                    )
                cursor = batch.get("last_event_id") or cursor
                if once:
                    if not batch["events"]:
                        yield ": no new events\n\n"
                    return
                if time.monotonic() - last_keepalive >= 15:
                    yield ": keepalive\n\n"
                    last_keepalive = time.monotonic()
                time.sleep(1)

        return Response(
            generate(),
            mimetype="text/event-stream",
            headers={
                "Cache-Control": "no-cache, no-transform",
                "X-Accel-Buffering": "no",
                "Connection": "keep-alive",
            },
        )

    @blueprint.post("/api/control-plane/agent-events")
    def record_agent_event():
        denied = _local_or_token_denied()
        if denied:
            return denied
        def record_and_route(conn: sqlite3.Connection):
            result = AgentEventRecorder(conn).record(_json_body())
            result["inbox"] = EventRouter(conn).accept(
                result["event"], duplicate=bool(result.get("duplicate"))
            )
            return result

        return _with_connection(record_and_route, write=True)

    @blueprint.get("/api/collaboration/inbox")
    def inbox():
        def load(conn: sqlite3.Connection):
            router = EventRouter(conn)
            return {
                "summary": router.summary(project_id=request.args.get("project")),
                "focus": router.get_focus(request.args.get("scope") or "main"),
                "items": router.list_inbox(
                    project_id=request.args.get("project"),
                    target_task_id=request.args.get("target_task"),
                    target_role=request.args.get("target_role"),
                    route_status=request.args.get("status"),
                    classification=request.args.get("classification"),
                    limit=request.args.get("limit", type=int) or 200,
                ),
            }

        return _with_connection(load)

    @blueprint.get("/api/collaboration/inbox/<event_id>")
    def inbox_event(event_id: str):
        return _with_connection(lambda conn: EventRouter(conn).get(event_id))

    @blueprint.post("/api/collaboration/inbox/<event_id>/ack")
    def acknowledge_inbox_event(event_id: str):
        denied = _local_or_token_denied()
        if denied:
            return denied
        body = _json_body()
        return _with_connection(
            lambda conn: EventRouter(conn).acknowledge(
                event_id,
                actor=str(body.get("actor") or ""),
                summary=str(body.get("summary") or ""),
            ),
            write=True,
        )

    @blueprint.get("/api/collaboration/focus")
    def focus():
        return _with_connection(
            lambda conn: EventRouter(conn).get_focus(
                request.args.get("scope") or "main"
            )
        )

    @blueprint.post("/api/collaboration/focus")
    def set_focus():
        denied = _local_or_token_denied()
        if denied:
            return denied
        body = _json_body()
        return _with_connection(
            lambda conn: EventRouter(conn).set_focus(
                scope_id=str(body.get("scope_id") or "main"),
                lease_owner=str(body.get("lease_owner") or ""),
                project_id=str(body.get("project_id") or "") or None,
                focus_task_id=str(body.get("focus_task_id") or "") or None,
                operation=str(body.get("operation") or ""),
                head_sha=str(body.get("head_sha") or "") or None,
                critical_section=bool(body.get("critical_section")),
                next_safe_checkpoint=str(body.get("next_safe_checkpoint") or "")
                or None,
                expires_at=str(body.get("expires_at") or "") or None,
            ),
            write=True,
        )

    @blueprint.post("/api/collaboration/focus/<scope_id>/release")
    def release_focus(scope_id: str):
        denied = _local_or_token_denied()
        if denied:
            return denied
        body = _json_body()
        return _with_connection(
            lambda conn: EventRouter(conn).release_focus(
                scope_id, actor=str(body.get("actor") or "operator")
            ),
            write=True,
        )

    @blueprint.post("/api/collaboration/inbox/checkpoints")
    def drain_inbox_checkpoint():
        denied = _local_or_token_denied()
        if denied:
            return denied
        body = _json_body()
        return _with_connection(
            lambda conn: EventRouter(conn).drain(
                scope_id=str(body.get("scope_id") or "main"),
                checkpoint=str(body.get("checkpoint") or ""),
                actor=str(body.get("actor") or "operator"),
            ),
            write=True,
        )

    @blueprint.get("/api/collaboration/authorizations")
    def list_authorizations():
        return _with_connection(
            lambda conn: {
                "authorizations": AuthorizationService(conn).list_requests(
                    project_id=request.args.get("project"),
                    task_id=request.args.get("task"),
                    status=request.args.get("status"),
                    level=request.args.get("level"),
                )
            },
            write=True,
        )

    @blueprint.get("/api/collaboration/authorization-policy")
    def authorization_policy():
        return _with_connection(lambda conn: AuthorizationService(conn).policy())

    @blueprint.post("/api/collaboration/authorization-policy/<rule_id>")
    def update_authorization_policy(rule_id: str):
        denied = _local_or_token_denied()
        if denied:
            return denied
        body = _json_body()
        if not isinstance(body.get("enabled"), bool):
            return jsonify(
                {"error": {"code": "enabled_required", "message": "enabled must be boolean"}}
            ), 400
        return _with_connection(
            lambda conn: AuthorizationService(conn).set_rule_enabled(
                rule_id,
                enabled=body["enabled"],
                actor=body.get("actor") if isinstance(body.get("actor"), dict) else {},
            ),
            write=True,
        )

    @blueprint.post("/api/collaboration/authorizations/<request_id>/decision")
    def decide_authorization(request_id: str):
        denied = _local_or_token_denied()
        if denied:
            return denied
        body = _json_body()
        return _with_connection(
            lambda conn: AuthorizationService(conn).decide(
                request_id,
                decision=str(body.get("decision") or ""),
                approver=body.get("approver")
                if isinstance(body.get("approver"), dict)
                else {},
                reason=str(body.get("reason") or ""),
            ),
            write=True,
        )

    @blueprint.post(
        "/api/collaboration/authorizations/<request_id>/platform-decision"
    )
    def record_platform_authorization_decision(request_id: str):
        denied = _local_or_token_denied()
        if denied:
            return denied
        body = _json_body()
        return _with_connection(
            lambda conn: AuthorizationService(conn).record_platform_decision(
                request_id,
                decision=str(body.get("decision") or ""),
                actor=body.get("actor")
                if isinstance(body.get("actor"), dict)
                else body.get("approver")
                if isinstance(body.get("approver"), dict)
                else {},
                reason=str(body.get("reason") or ""),
                observed_digest=str(
                    body.get("observed_digest")
                    or body.get("command_or_action_digest")
                    or ""
                ),
            ),
            write=True,
        )

    @blueprint.post("/api/control-plane/authorizations/<request_id>/consume")
    def consume_authorization(request_id: str):
        denied = _local_or_token_denied()
        if denied:
            return denied
        body = _json_body()
        targets = body.get("exact_targets")
        if not isinstance(targets, list):
            return jsonify(
                {
                    "error": {
                        "code": "exact_targets_required",
                        "message": "exact_targets must be an array",
                    }
                }
            ), 400
        return _with_connection(
            lambda conn: AuthorizationService(conn).consume(
                request_id,
                requester_id=str(body.get("requester_id") or ""),
                environment=str(body.get("environment") or ""),
                exact_targets=[str(item) for item in targets],
                head_sha=body.get("head_sha"),
            ),
            write=True,
        )

    return blueprint
