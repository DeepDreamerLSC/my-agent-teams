#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
WORKSPACE_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(SCRIPT_DIR / "lib"))
import task_artifacts  # type: ignore

ARTIFACT_FILES = {
    "ack": "ack.json",
    "result": "result.json",
    "review": "review.json",
    "verify": "verify.json",
}

STATUS_CHOICES = {
    "ack": {"acknowledged", "working", "ack"},
    "result": {"done", "failed", "blocked"},
    "review": {"approve", "request_changes", "blocked"},
    "verify": {"pass", "fail", "blocked"},
}

DEFAULT_STATUS = {
    "ack": "acknowledged",
    "result": "done",
    "review": "approve",
    "verify": "pass",
}


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _task_round(task: dict[str, Any]) -> int | None:
    for key in ("execution_round", "current_round", "resume_round"):
        value = task.get(key)
        if value in (None, ""):
            continue
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            continue
        if parsed >= 0:
            return parsed
    return None


def _agent_from_cwd() -> str | None:
    cwd = Path.cwd().resolve()
    parts = cwd.parts
    if "agents" not in parts:
        return None
    index = len(parts) - 1 - list(reversed(parts)).index("agents")
    if index + 1 >= len(parts):
        return None
    return parts[index + 1]


def _resolve_task_dir(task_ref: str, tasks_root: Path) -> Path:
    candidate = Path(task_ref).expanduser()
    if candidate.is_absolute() and (candidate / "task.json").exists():
        return candidate.resolve()
    if candidate.exists() and (candidate / "task.json").exists():
        return candidate.resolve()
    return (tasks_root / task_ref).resolve()


def _resolve_actor(artifact: str, task: dict[str, Any], args: argparse.Namespace) -> str:
    explicit = args.agent or args.reviewer or args.tester
    if explicit:
        return explicit
    if artifact == "review":
        return str(task.get("reviewer") or _agent_from_cwd() or "review-1")
    if artifact == "verify":
        return str(_agent_from_cwd() or task.get("tester") or "qa-1")
    return str(task.get("assigned_agent") or _agent_from_cwd() or "")


def _build_payload(artifact: str, task: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    status = (args.status or DEFAULT_STATUS[artifact]).strip()
    if status not in STATUS_CHOICES[artifact]:
        allowed = ", ".join(sorted(STATUS_CHOICES[artifact]))
        raise SystemExit(f"invalid {artifact} status: {status}; expected one of {allowed}")

    task_id = str(task.get("id") or args.task_ref)
    summary = args.summary or ""
    now = _now_iso()
    round_value = _task_round(task)
    actor = _resolve_actor(artifact, task, args)
    payload: dict[str, Any] = {
        "task_id": task_id,
        "status": status,
        "summary": summary,
    }
    if round_value is not None:
        payload["round"] = round_value

    if artifact == "ack":
        payload.update({
            "agent": actor,
            "acked_at": now,
        })
    elif artifact == "result":
        payload.update({
            "agent": actor,
            "finished_at": now,
        })
    elif artifact == "review":
        payload.update({
            "reviewer": actor,
            "reviewed_at": now,
        })
    elif artifact == "verify":
        payload.update({
            "tester": actor,
            "verified_at": now,
        })
    return payload


def _parse_artifact(artifact: str, task_dir: Path) -> dict[str, Any]:
    if artifact == "ack":
        return task_artifacts.parse_ack(task_dir)
    if artifact == "result":
        return task_artifacts.parse_result(task_dir)
    if artifact == "review":
        return task_artifacts.parse_review(task_dir)
    if artifact == "verify":
        return task_artifacts.parse_verify(task_dir)
    raise AssertionError(artifact)


def _artifact_valid(artifact: str, parsed: dict[str, Any]) -> bool:
    if parsed.get("valid"):
        return True
    if artifact == "review":
        review_json = ((parsed.get("sources") or {}).get("review_json") or {})
        return bool(review_json.get("valid"))
    return False


def _validate_payload(artifact: str, task_dir: Path, payload: dict[str, Any]) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix=".artifact-validate-", dir=str(task_dir)) as tmp:
        validation_dir = Path(tmp)
        shutil.copy2(task_dir / "task.json", validation_dir / "task.json")
        for optional_name in ("result.json",):
            optional_path = task_dir / optional_name
            if optional_path.exists() and optional_name != ARTIFACT_FILES[artifact]:
                shutil.copy2(optional_path, validation_dir / optional_name)
        (validation_dir / ARTIFACT_FILES[artifact]).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        parsed = _parse_artifact(artifact, validation_dir)
        if not _artifact_valid(artifact, parsed):
            detail = parsed.get("errors") or parsed.get("warnings") or parsed
            raise SystemExit(f"{artifact} artifact validation failed: {detail}")
        return parsed


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", delete=False, dir=str(path.parent), encoding="utf-8") as tmp:
        json.dump(payload, tmp, ensure_ascii=False, indent=2)
        tmp.write("\n")
    os.replace(tmp.name, path)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Write normalized task artifacts atomically.")
    parser.add_argument("artifact", choices=sorted(ARTIFACT_FILES))
    parser.add_argument("task_ref", help="Task id or task directory path")
    parser.add_argument("--tasks-root", default=str(WORKSPACE_ROOT / "tasks"))
    parser.add_argument("--status", default="")
    parser.add_argument("--summary", default="")
    parser.add_argument("--agent", default="")
    parser.add_argument("--reviewer", default="")
    parser.add_argument("--tester", default="")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    tasks_root = Path(args.tasks_root).expanduser().resolve()
    task_dir = _resolve_task_dir(args.task_ref, tasks_root)
    task_path = task_dir / "task.json"
    if not task_path.exists():
        raise SystemExit(f"task not found: {task_path}")

    task = _load_json(task_path)
    payload = _build_payload(args.artifact, task, args)
    _validate_payload(args.artifact, task_dir, payload)
    artifact_path = task_dir / ARTIFACT_FILES[args.artifact]
    _atomic_write_json(artifact_path, payload)
    parsed = _parse_artifact(args.artifact, task_dir)
    print(json.dumps({
        "task_id": payload["task_id"],
        "artifact": args.artifact,
        "path": str(artifact_path),
        "status": payload["status"],
        "normalized_status": parsed.get("normalized_status"),
        "valid": bool(parsed.get("valid")),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
