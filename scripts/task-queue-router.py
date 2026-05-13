#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

PRIORITY_RANK = {"critical": 4, "urgent": 4, "high": 3, "medium": 2, "low": 1}
TERMINAL_REVIEW_STATUSES = {"approve", "request_changes", "blocked"}
LIB_DIR = Path(__file__).resolve().parent / "lib"
if str(LIB_DIR) not in sys.path:
    sys.path.insert(0, str(LIB_DIR))
try:
    from task_artifacts import parse_review
except Exception:  # pragma: no cover - fallback keeps the queue router usable standalone.
    parse_review = None


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def parse_iso(value: str | None) -> datetime:
    if not value:
        return datetime.max
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        return datetime.max


def review_artifact_terminal(task_dir: Path) -> bool:
    if parse_review is not None:
        try:
            status = str(parse_review(task_dir).get("normalized_status") or "").strip().lower()
        except Exception:
            status = ""
        if status in TERMINAL_REVIEW_STATUSES:
            return True
    for artifact_name in ("review.json", "design-review.json"):
        artifact_path = task_dir / artifact_name
        if not artifact_path.exists():
            continue
        try:
            payload = load_json(artifact_path)
        except Exception:
            continue
        status = str(payload.get("status") or "").strip().lower()
        if status in TERMINAL_REVIEW_STATUSES:
            return True
    return False


def candidate_rows(tasks_root: Path, queue_kind: str, agent: str) -> list[dict]:
    rows = []
    for task_path in tasks_root.glob("*/task.json"):
        try:
            task = load_json(task_path)
        except Exception:
            continue
        if str(task.get("status") or "") != "ready_for_merge":
            continue
        gate = str(task.get("merge_gate_state") or "")
        if queue_kind == "review":
            if gate != "review_pending":
                continue
            if review_artifact_terminal(task_path.parent):
                continue
            reviewers = task.get("reviewers") if isinstance(task.get("reviewers"), list) else []
            reviewers = [str(item).strip() for item in reviewers if str(item).strip()]
            if not reviewers:
                reviewer = str(task.get("reviewer") or "").strip()
                if reviewer:
                    reviewers = [reviewer]
            if reviewers and agent not in reviewers:
                continue
            queued_at = str(task.get("updated_at") or task.get("created_at") or "")
        else:
            if gate != "qa_pending":
                continue
            claim_scope = task.get("claim_scope") if isinstance(task.get("claim_scope"), list) else []
            scope = [str(item).strip() for item in claim_scope if str(item).strip()]
            if scope and agent not in scope:
                continue
            queued_at = str(task.get("last_gate_decision_at") or task.get("updated_at") or task.get("created_at") or "")
        rows.append({
            "task_id": str(task.get("id") or task_path.parent.name),
            "priority": str(task.get("priority") or "medium").strip().lower(),
            "queued_at": queued_at,
            "title": str(task.get("title") or task_path.parent.name),
        })
    rows.sort(key=lambda row: (-PRIORITY_RANK.get(row["priority"], 0), parse_iso(row["queued_at"]), row["task_id"]))
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description="Select next review/QA queue candidate")
    parser.add_argument("--tasks-root", default=str(Path.home() / "Desktop/work/my-agent-teams/tasks"))
    parser.add_argument("--queue", choices=["review", "qa"], required=True)
    parser.add_argument("--agent", required=True)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--next", action="store_true")
    args = parser.parse_args()

    rows = candidate_rows(Path(args.tasks_root).expanduser().resolve(), args.queue, args.agent)
    payload = {
        "agent": args.agent,
        "queue": args.queue,
        "next_task_id": rows[0]["task_id"] if rows else None,
        "rows": rows,
    }
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    elif args.next:
        if rows:
            print(rows[0]["task_id"])
    else:
        if rows:
            print(rows[0]["task_id"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
