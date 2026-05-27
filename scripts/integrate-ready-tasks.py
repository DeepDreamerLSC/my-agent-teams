#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
WORKSPACE_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(SCRIPT_DIR / "lib"))
import task_workspace  # type: ignore


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def parse_json_output(stdout: str, stderr: str) -> dict[str, Any]:
    for text in (stdout, stderr):
        text = (text or "").strip()
        if not text:
            continue
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            continue
    return {
        "status": "fail",
        "reason": "integration_output_invalid",
        "stdout": stdout[-4000:],
        "stderr": stderr[-4000:],
    }


def discover_task_dirs(tasks_root: Path) -> list[Path]:
    if not tasks_root.exists():
        return []
    return sorted(path.parent for path in tasks_root.glob("*/task.json"))


def queue_sort_key(item: dict[str, Any]) -> tuple[str, str]:
    entered_at = str(item.get("entered_at") or "")
    task_id = str(item.get("task_id") or "")
    return (entered_at or "9999-12-31T23:59:59", task_id)


def classify_task(task_dir: Path, task: dict[str, Any], target_override: str) -> dict[str, Any]:
    queue_item = task_workspace.derive_integration_queue_item(task)
    task_id = str(task.get("id") or task_dir.name)
    status = str(task.get("status") or "").strip()
    gate = str(task.get("merge_gate_state") or "").strip()
    target_branch = target_override or str(queue_item.get("target_branch") or "").strip()

    reason = ""
    if status != "ready_for_merge":
        reason = f"status={status or '<empty>'}"
    elif gate != "pm_acceptance_pending":
        reason = f"merge_gate_state={gate or '<empty>'}"
    elif queue_item.get("state") != "queued":
        reason = str(queue_item.get("blocker") or queue_item.get("state") or "not_queued")
    elif not target_branch:
        reason = "target_branch_missing"

    payload = {
        "task_id": task_id,
        "task_dir": str(task_dir),
        "entered_at": queue_item.get("entered_at") or str(task.get("updated_at") or ""),
        "target_branch": target_branch or None,
        "queue_state": queue_item.get("state"),
        "artifact_state": queue_item.get("artifact_state"),
    }
    if reason:
        payload.update({"selected": False, "skip_reason": reason})
    else:
        payload.update({"selected": True})
    return payload


def build_task_command(args: argparse.Namespace, task_dir: str) -> list[str]:
    command = [
        sys.executable,
        str(SCRIPT_DIR / "integrate-task.py"),
        "--task-dir",
        task_dir,
        "--config",
        str(Path(args.config).expanduser().resolve()),
        "--strategy",
        args.strategy,
        "--actor",
        args.actor,
    ]
    if args.target_branch:
        command.extend(["--target-branch", args.target_branch])
    for test_cmd in args.test_cmd or []:
        command.extend(["--test-cmd", test_cmd])
    if args.dry_run:
        command.append("--dry-run")
    if args.push:
        command.append("--push")
    return command


def run_integration(args: argparse.Namespace, task_item: dict[str, Any]) -> dict[str, Any]:
    command = build_task_command(args, str(task_item["task_dir"]))
    completed = subprocess.run(
        command,
        cwd=str(WORKSPACE_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    payload = parse_json_output(completed.stdout, completed.stderr)
    payload.setdefault("task_id", task_item.get("task_id"))
    payload["returncode"] = completed.returncode
    payload["command"] = " ".join(command)
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Serially integrate ready_for_merge tasks into their target branch.")
    parser.add_argument("--tasks-root", default=os.environ.get("TASKS_ROOT", str(WORKSPACE_ROOT / "tasks")))
    parser.add_argument("--config", default=os.environ.get("CONFIG_PATH", str(WORKSPACE_ROOT / "config.json")))
    parser.add_argument("--strategy", choices=["auto", "branch", "patch"], default="auto")
    parser.add_argument("--target-branch", default="")
    parser.add_argument("--actor", default="integrator")
    parser.add_argument("--test-cmd", action="append", default=[])
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--push", action="store_true")
    parser.add_argument("--continue-on-error", action="store_true")
    parser.add_argument("--limit", type=int, default=0)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    tasks_root = Path(args.tasks_root).expanduser().resolve()
    scanned: list[dict[str, Any]] = []
    selected: list[dict[str, Any]] = []

    for task_dir in discover_task_dirs(tasks_root):
        try:
            task = load_json(task_dir / "task.json")
            item = classify_task(task_dir, task, str(args.target_branch or "").strip())
        except Exception as exc:
            item = {
                "task_id": task_dir.name,
                "task_dir": str(task_dir),
                "selected": False,
                "skip_reason": f"task_read_error:{exc}",
            }
        scanned.append(item)
        if item.get("selected"):
            selected.append(item)

    selected.sort(key=queue_sort_key)
    if args.limit and args.limit > 0:
        selected = selected[: args.limit]

    results: list[dict[str, Any]] = []
    stopped_on_failure = False
    for item in selected:
        result = run_integration(args, item)
        results.append(result)
        if result.get("returncode") != 0 and not args.continue_on_error:
            stopped_on_failure = True
            break

    failures = [item for item in results if item.get("returncode") != 0]
    payload = {
        "status": "fail" if failures else "pass",
        "dry_run": bool(args.dry_run),
        "pushed": bool(args.push),
        "tasks_root": str(tasks_root),
        "selected_count": len(selected),
        "processed_count": len(results),
        "passed_count": len(results) - len(failures),
        "failed_count": len(failures),
        "skipped_count": len(scanned) - len([item for item in scanned if item.get("selected")]),
        "stopped_on_failure": stopped_on_failure,
        "results": results,
        "skipped": [item for item in scanned if not item.get("selected")],
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
