#!/usr/bin/env python3
"""CLI for the cross-project Codex delivery control plane."""

from __future__ import annotations

import argparse
import json
import sys
from contextlib import closing
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from control_plane.bootstrap import bootstrap_project, check_bootstrap, uninstall_project
from control_plane.backends.registry import BackendRegistry
from control_plane.errors import ControlPlaneError
from control_plane.service import ControlPlaneService
from dashboard.db import connect_db, resolve_db_path


def _json(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True))


def _service(db_path: str | None) -> tuple[Any, ControlPlaneService]:
    conn = connect_db(resolve_db_path(db_path), initialize=True)
    return conn, ControlPlaneService(conn)


def _add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--db", default=None, help="control-plane SQLite path")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    _add_common(parser)
    sub = parser.add_subparsers(dest="command", required=True)

    project = sub.add_parser("project")
    project_sub = project.add_subparsers(dest="project_command", required=True)
    register = project_sub.add_parser("register")
    register.add_argument("--id", required=True, dest="project_id")
    register.add_argument("--name", required=True)
    register.add_argument("--repo-root", required=True)
    register.add_argument("--prod-root")
    register.add_argument("--branch", default="main", dest="default_branch")
    register.add_argument("--control-plane-url")
    register.add_argument("--allowed-root", action="append", default=[])
    register.add_argument("--metadata-json", default="{}")
    project_sub.add_parser("list")
    check = project_sub.add_parser("check")
    check.add_argument("project_id")
    import_legacy = project_sub.add_parser("import-legacy")
    import_legacy.add_argument("--config", required=True)
    bootstrap = project_sub.add_parser("bootstrap")
    bootstrap.add_argument("--project-id", required=True)
    bootstrap.add_argument("--repo-root", required=True)
    bootstrap.add_argument("--control-plane-url", required=True)
    bootstrap.add_argument("--apply", action="store_true")
    bootstrap.add_argument("--agents-file", default="AGENTS.md")
    bootstrap.add_argument("--role", action="append", default=["pm", "architect", "critic", "developer", "reviewer", "qa"])
    boot_check = project_sub.add_parser("bootstrap-check")
    boot_check.add_argument("--repo-root", required=True)
    boot_check.add_argument("--agents-file", default="AGENTS.md")
    uninstall = project_sub.add_parser("uninstall")
    uninstall.add_argument("--repo-root", required=True)
    uninstall.add_argument("--apply", action="store_true")
    uninstall.add_argument("--agents-file", default="AGENTS.md")

    requirement = sub.add_parser("requirement")
    requirement_sub = requirement.add_subparsers(dest="requirement_command", required=True)
    submit = requirement_sub.add_parser("submit")
    submit.add_argument("--project-id", required=True)
    submit.add_argument("--title", required=True)
    submit.add_argument("--description", default="")
    submit.add_argument("--acceptance-json", default="[]")
    submit.add_argument("--priority", default="medium")
    submit.add_argument("--owner-id")
    list_req = requirement_sub.add_parser("list")
    list_req.add_argument("--project-id")
    list_req.add_argument("--status")

    session = sub.add_parser("session")
    session_sub = session.add_subparsers(dest="session_command", required=True)
    session_register = session_sub.add_parser("register")
    session_register.add_argument("--project-id", required=True)
    session_register.add_argument("--session-id")
    session_register.add_argument("--requirement-id")
    session_register.add_argument("--task-id")
    session_register.add_argument("--thread-id")
    session_register.add_argument("--parent-thread-id")
    session_register.add_argument("--role", required=True)
    session_register.add_argument("--backend", required=True, dest="execution_backend")
    session_register.add_argument("--cwd")
    session_register.add_argument("--environment")
    session_register.add_argument("--worktree")
    session_register.add_argument("--branch")
    session_register.add_argument("--status", default="unknown", dest="session_status")
    session_register.add_argument("--gate", dest="current_gate")
    session_register.add_argument("--capabilities-json", default="{}")
    session_register.add_argument("--external-ref")
    session_list = session_sub.add_parser("list")
    session_list.add_argument("--project-id")
    session_list.add_argument("--requirement-id")
    session_list.add_argument("--task-id")
    bind = session_sub.add_parser("bind")
    bind.add_argument("session_id")
    bind.add_argument("--requirement-id")
    bind.add_argument("--task-id")
    heartbeat = session_sub.add_parser("heartbeat")
    heartbeat.add_argument("session_id")
    heartbeat.add_argument("--idempotency-key", required=True)
    heartbeat.add_argument("--sequence", type=int)
    heartbeat.add_argument("--status")
    heartbeat.add_argument("--capabilities-json", default="{}")
    events = session_sub.add_parser("events")
    events.add_argument("session_id")
    probe = session_sub.add_parser("probe")
    probe.add_argument("session_id")
    probe.add_argument("--backend", required=True)

    event = sub.add_parser("event")
    event.add_argument("--session-id", required=True)
    event.add_argument("--type", required=True, dest="event_type")
    event.add_argument("--idempotency-key", required=True)
    event.add_argument("--event-id")
    event.add_argument("--event-at")
    event.add_argument("--sequence", type=int)
    event.add_argument("--status")
    event.add_argument("--gate")
    event.add_argument("--last-error")
    event.add_argument("--payload-json", default="{}")
    event.add_argument("--source", default="cli")

    gate = sub.add_parser("gate")
    gate_sub = gate.add_subparsers(dest="gate_command", required=True)
    decide = gate_sub.add_parser("decide")
    decide.add_argument("--requirement-id", required=True)
    decide.add_argument("--stage", required=True)
    decide.add_argument("--status", required=True)
    decide.add_argument("--actor", required=True)
    decide.add_argument("--output-json", default="{}")
    decide.add_argument("--rejection-reason")
    decide.add_argument("--task-id")
    decide.add_argument("--round", type=int, dest="round_number")
    gates = gate_sub.add_parser("list")
    gates.add_argument("requirement_id")

    owner = sub.add_parser("owner")
    owner_sub = owner.add_subparsers(dest="owner_command", required=True)
    owner_list = owner_sub.add_parser("list")
    owner_list.add_argument("--project-id")
    owner_list.add_argument("--status", default="open")
    owner_open = owner_sub.add_parser("open")
    owner_open.add_argument("--project-id", required=True)
    owner_open.add_argument("--category", required=True)
    owner_open.add_argument("--summary", required=True)
    owner_open.add_argument("--options-json", default="[]")
    owner_open.add_argument("--impact", default="")
    owner_open.add_argument("--recommendation", default="")
    owner_open.add_argument("--due-at")
    owner_open.add_argument("--requirement-id")
    owner_open.add_argument("--task-id")
    owner_resolve = owner_sub.add_parser("resolve")
    owner_resolve.add_argument("decision_id")
    owner_resolve.add_argument("--decision-json", required=True)

    overview = sub.add_parser("overview")
    overview.add_argument("--project-id")
    return parser


def _load_json(raw: str, *, expected: type | None = None) -> Any:
    try:
        value = json.loads(raw)
    except ValueError as exc:
        raise ControlPlaneError(f"invalid JSON: {exc}") from exc
    if expected is not None and not isinstance(value, expected):
        raise ControlPlaneError(f"JSON value must be {expected.__name__}")
    return value


def run(args: argparse.Namespace) -> Any:
    if args.command == "project" and args.project_command == "bootstrap":
        return bootstrap_project(
            repo_root=args.repo_root,
            project_id=args.project_id,
            control_plane_url=args.control_plane_url,
            apply=args.apply,
            agents_file=args.agents_file,
            roles=args.role,
        )
    if args.command == "project" and args.project_command == "bootstrap-check":
        return check_bootstrap(repo_root=args.repo_root, agents_file=args.agents_file)
    if args.command == "project" and args.project_command == "uninstall":
        return uninstall_project(repo_root=args.repo_root, apply=args.apply, agents_file=args.agents_file)
    conn, service = _service(args.db)
    try:
        with conn:
            if args.command == "project":
                if args.project_command == "register":
                    metadata = _load_json(args.metadata_json, expected=dict)
                    if args.allowed_root:
                        metadata["allowed_roots"] = args.allowed_root
                    return service.register_project(
                        project_id=args.project_id,
                        name=args.name,
                        repo_root=args.repo_root,
                        prod_root=args.prod_root,
                        default_branch=args.default_branch,
                        control_plane_url=args.control_plane_url,
                        metadata=metadata,
                    )
                if args.project_command == "list":
                    return service.list_projects()
                if args.project_command == "check":
                    return service.check_project(args.project_id)
                if args.project_command == "import-legacy":
                    config = json.loads(Path(args.config).expanduser().read_text(encoding="utf-8"))
                    return service.import_legacy_projects(config)
            if args.command == "requirement":
                if args.requirement_command == "submit":
                    return service.create_requirement(
                        project_id=args.project_id,
                        title=args.title,
                        description=args.description,
                        acceptance=_load_json(args.acceptance_json, expected=list),
                        priority=args.priority,
                        owner_id=args.owner_id,
                    )
                return service.list_requirements(project_id=args.project_id, status=args.status)
            if args.command == "session":
                if args.session_command == "register":
                    return service.register_session(
                        project_id=args.project_id,
                        session_id=args.session_id,
                        requirement_id=args.requirement_id,
                        task_id=args.task_id,
                        thread_id=args.thread_id,
                        parent_thread_id=args.parent_thread_id,
                        role=args.role,
                        execution_backend=args.execution_backend,
                        cwd=args.cwd,
                        environment=args.environment,
                        worktree=args.worktree,
                        branch=args.branch,
                        session_status=args.session_status,
                        current_gate=args.current_gate,
                        capabilities=_load_json(args.capabilities_json, expected=dict),
                        external_ref=args.external_ref,
                    )
                if args.session_command == "list":
                    return service.list_sessions(project_id=args.project_id, requirement_id=args.requirement_id, task_id=args.task_id)
                if args.session_command == "bind":
                    return service.bind_session(args.session_id, requirement_id=args.requirement_id, task_id=args.task_id)
                if args.session_command == "heartbeat":
                    return service.heartbeat(
                        args.session_id,
                        idempotency_key=args.idempotency_key,
                        sequence=args.sequence,
                        status=args.status,
                        capabilities=_load_json(args.capabilities_json, expected=dict),
                    )
                if args.session_command == "probe":
                    return service.probe_session(args.session_id, BackendRegistry().get(args.backend))
                return service.list_session_events(args.session_id)
            if args.command == "event":
                return service.record_session_event(
                    session_id=args.session_id,
                    event_type=args.event_type,
                    idempotency_key=args.idempotency_key,
                    event_id=args.event_id,
                    event_at=args.event_at,
                    sequence=args.sequence,
                    status=args.status,
                    current_gate=args.gate,
                    last_error=args.last_error,
                    payload=_load_json(args.payload_json, expected=dict),
                    source=args.source,
                )
            if args.command == "gate":
                if args.gate_command == "decide":
                    return service.decide_gate(
                        requirement_id=args.requirement_id,
                        stage=args.stage,
                        status=args.status,
                        actor=args.actor,
                        output=_load_json(args.output_json, expected=dict),
                        rejection_reason=args.rejection_reason,
                        task_id=args.task_id,
                        round_number=args.round_number,
                    )
                return service.list_gates(args.requirement_id)
            if args.command == "owner":
                if args.owner_command == "list":
                    return service.list_owner_decisions(status=args.status, project_id=args.project_id)
                if args.owner_command == "open":
                    return service.create_owner_decision(
                        project_id=args.project_id,
                        category=args.category,
                        summary=args.summary,
                        options=_load_json(args.options_json, expected=list),
                        impact=args.impact,
                        recommendation=args.recommendation,
                        due_at=args.due_at,
                        requirement_id=args.requirement_id,
                        task_id=args.task_id,
                    )
                return service.resolve_owner_decision(
                    args.decision_id,
                    decision=_load_json(args.decision_json, expected=dict),
                )
            if args.command == "overview":
                return service.overview(project_id=args.project_id)
    finally:
        conn.close()
    raise ControlPlaneError("unsupported command")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    try:
        _json(run(parser.parse_args(argv)))
    except (ControlPlaneError, OSError, ValueError) as exc:
        _json({"error": {"code": getattr(exc, "code", "command_failed"), "message": str(exc)}})
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
