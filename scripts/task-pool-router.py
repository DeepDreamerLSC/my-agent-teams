#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent


def _load_pool_rows(tasks_root: str, config: str, agent: str) -> list[dict]:
    completed = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_DIR / "task-pool-view.py"),
            "--json",
            "--tasks-root",
            tasks_root,
            "--config",
            config,
            "--agent",
            agent,
        ],
        cwd=str(SCRIPT_DIR.parent),
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(completed.stdout)


def _pick_agent_diagnostic(row: dict | None, agent: str) -> dict | None:
    if not row:
        return None
    for item in row.get("by_agent") or []:
        if item.get("agent_id") == agent:
            return item
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Select the next pooled task for an agent")
    parser.add_argument("--tasks-root", default=str(Path.home() / "Desktop/work/my-agent-teams/tasks"))
    parser.add_argument("--config", default=str(Path.home() / "Desktop/work/my-agent-teams/config.json"))
    parser.add_argument("--agent", required=True)
    parser.add_argument("--next", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--explain", default="")
    args = parser.parse_args()

    rows = _load_pool_rows(args.tasks_root, args.config, args.agent)
    if args.explain:
        rows = [row for row in rows if row["task_id"] == args.explain]
    next_row = next((row for row in rows if args.agent in (row.get("eligible_agents") or [])), None)
    next_diag = _pick_agent_diagnostic(next_row, args.agent)
    next_task = dict(next_row) if next_row else None
    if next_task and next_diag:
        next_task["selected_agent"] = args.agent
        next_task["selected_agent_busy_diagnostic"] = next_diag

    payload = {
        "agent": args.agent,
        "next_task_id": next_row["task_id"] if next_row else None,
        "next_task": next_task,
        "next_task_busy_level": next_diag.get("busy_level") if next_diag else None,
        "next_task_busy_primary_reason": next_diag.get("busy_primary_reason") if next_diag else None,
        "next_task_busy_reason_codes": next_diag.get("busy_reason_codes") if next_diag else None,
        "next_task_busy_hard_reason_codes": next_diag.get("busy_hard_reason_codes") if next_diag else None,
        "next_task_busy_soft_reason_codes": next_diag.get("busy_soft_reason_codes") if next_diag else None,
        "next_task_delivery_route": next_diag.get("busy_execute_route") if next_diag else None,
        "next_task_remind_route": next_diag.get("busy_remind_route") if next_diag else None,
        "next_task_preheat_route": next_diag.get("busy_preheat_route") if next_diag else None,
        "next_task_can_direct_execute": next_diag.get("busy_can_direct_execute") if next_diag else None,
        "next_task_can_direct_remind": next_diag.get("busy_can_direct_remind") if next_diag else None,
        "next_task_queue_only": next_diag.get("busy_queue_only") if next_diag else None,
        "next_task_non_interrupt": bool(next_diag and next_diag.get("busy_level") != "idle") if next_diag else None,
        "next_task_busy_diagnostic": next_diag,
        "rows": rows if args.json or args.explain else None,
    }

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    elif args.next:
        if next_row:
            print(next_row["task_id"])
    elif args.explain:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        if next_row:
            print(next_row["task_id"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
