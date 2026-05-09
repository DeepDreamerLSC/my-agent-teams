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

    payload = {
        "agent": args.agent,
        "next_task_id": next_row["task_id"] if next_row else None,
        "next_task": next_row,
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
