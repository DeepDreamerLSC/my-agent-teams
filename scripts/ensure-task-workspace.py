#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


SCRIPT_DIR = Path(__file__).resolve().parent
WORKSPACE_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(SCRIPT_DIR / "lib"))
from task_workspace import ensure_task_workspace  # type: ignore


def _resolve_task_dir(task_ref: str, tasks_root: Path) -> Path:
    candidate = Path(task_ref).expanduser()
    if candidate.is_absolute() and (candidate / "task.json").exists():
        return candidate.resolve()
    if candidate.exists() and (candidate / "task.json").exists():
        return candidate.resolve()
    return (tasks_root / task_ref).resolve()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Ensure per-task workspace/worktree metadata exists.")
    parser.add_argument("task_ref", help="Task id or task directory path")
    parser.add_argument("--tasks-root", default=str(WORKSPACE_ROOT / "tasks"))
    parser.add_argument("--config", default=str(WORKSPACE_ROOT / "config.json"))
    return parser


def main() -> int:
    args = build_parser().parse_args()
    tasks_root = Path(args.tasks_root).expanduser().resolve()
    config_path = Path(args.config).expanduser().resolve()
    task_dir = _resolve_task_dir(args.task_ref, tasks_root)
    if not (task_dir / "task.json").exists():
        raise SystemExit(f"task not found: {task_dir / 'task.json'}")
    payload = ensure_task_workspace(task_dir, config_path)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
