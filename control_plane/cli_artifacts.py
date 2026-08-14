from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .errors import ControlPlaneError


def add_artifact_parser(subparsers: Any) -> None:
    artifact = subparsers.add_parser("artifact")
    commands = artifact.add_subparsers(dest="artifact_command", required=True)
    attach = commands.add_parser("attach")
    attach.add_argument("--project-id", required=True)
    attach.add_argument("--kind", required=True)
    attach.add_argument("--uri", required=True)
    attach.add_argument("--summary", default="")
    attach.add_argument("--requirement-id")
    attach.add_argument("--task-id")
    attach.add_argument("--session-id")
    attach.add_argument("--environment", default="dev")
    attach.add_argument("--checksum")
    metadata = attach.add_mutually_exclusive_group()
    metadata.add_argument("--metadata-json", default="{}")
    metadata.add_argument("--metadata-file")
    list_command = commands.add_parser("list")
    list_command.add_argument("--project-id")
    list_command.add_argument("--requirement-id")
    list_command.add_argument("--task-id")


def run_artifact_command(args: argparse.Namespace, service: Any) -> Any:
    if args.artifact_command == "list":
        return service.list_artifacts(
            project_id=args.project_id,
            requirement_id=args.requirement_id,
            task_id=args.task_id,
        )
    metadata = _load_json_file(args.metadata_file) if args.metadata_file else _load_json(args.metadata_json)
    return service.attach_artifact(
        project_id=args.project_id,
        requirement_id=args.requirement_id,
        task_id=args.task_id,
        session_id=args.session_id,
        kind=args.kind,
        uri=args.uri,
        summary=args.summary,
        environment=args.environment,
        checksum=args.checksum,
        metadata=metadata,
        actor="cli",
    )


def _load_json(raw: str) -> dict[str, Any]:
    try:
        value = json.loads(raw)
    except ValueError as exc:
        raise ControlPlaneError(f"invalid JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise ControlPlaneError("JSON value must be dict")
    return value


def _load_json_file(path: str) -> dict[str, Any]:
    try:
        raw = Path(path).expanduser().read_text(encoding="utf-8")
    except OSError as exc:
        raise ControlPlaneError(f"unable to read JSON file {path}: {exc}") from exc
    return _load_json(raw)
