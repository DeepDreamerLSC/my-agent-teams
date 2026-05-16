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
    from task_artifacts import parse_review, parse_verify
except Exception:  # pragma: no cover - fallback keeps the queue router usable standalone.
    parse_review = None
    parse_verify = None


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
            parsed = parse_review(task_dir)
            status = str(parsed.get("normalized_status") or "").strip().lower()
            source = str(parsed.get("source") or "").strip().lower()
        except Exception:
            status = ""
            source = ""
        if status in TERMINAL_REVIEW_STATUSES and source != "stale_json":
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
        if status in TERMINAL_REVIEW_STATUSES and not _artifact_stale_after_current_result(task_dir, artifact_path, payload):
            return True
    return False


def qa_artifact_terminal(task_dir: Path) -> bool:
    if parse_verify is not None:
        try:
            parsed = parse_verify(task_dir)
            status = str(parsed.get("normalized_status") or "").strip().lower()
            source = str(parsed.get("source") or "").strip().lower()
        except Exception:
            status = ""
            source = ""
        if status in {"pass", "fail", "blocked"} and source != "stale_json":
            return True
    artifact_path = task_dir / "verify.json"
    if not artifact_path.exists():
        return False
    try:
        payload = load_json(artifact_path)
    except Exception:
        return False
    status = str(payload.get("status") or payload.get("verdict") or "").strip().lower()
    return status in {"pass", "fail", "blocked"} and not _artifact_stale_after_current_result(task_dir, artifact_path, payload)


def _artifact_round(payload: dict) -> int | None:
    for key in ("round", "execution_round", "review_round", "resume_round"):
        value = payload.get(key)
        if value is None or value == "":
            continue
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            continue
        if parsed >= 0:
            return parsed
    return None


def _task_round(task: dict) -> int | None:
    for key in ("execution_round", "current_round", "resume_round"):
        value = task.get(key)
        if value is None or value == "":
            continue
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            continue
        if parsed >= 0:
            return parsed
    return None


def _artifact_stale_after_current_result(task_dir: Path, artifact_path: Path, payload: dict) -> bool:
    try:
        task = load_json(task_dir / "task.json")
    except Exception:
        task = {}
    artifact_round = _artifact_round(payload)
    task_round = _task_round(task)
    if artifact_round is not None and task_round is not None:
        return artifact_round < task_round

    result_path = task_dir / "result.json"
    if not result_path.exists():
        return False
    if artifact_round is not None:
        try:
            result_payload = load_json(result_path)
        except Exception:
            result_payload = {}
        result_round = _artifact_round(result_payload)
        if result_round is not None:
            return artifact_round < result_round
    if artifact_round is None:
        try:
            return artifact_path.stat().st_mtime < result_path.stat().st_mtime
        except OSError:
            return False
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
        quality_gate_mode = str(task.get("quality_gate_mode") or "").strip().lower()
        if queue_kind == "review":
            if gate not in {"review_pending", "quality_pending"}:
                continue
            if gate == "quality_pending" and quality_gate_mode != "parallel":
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
            if gate not in {"qa_pending", "quality_pending"}:
                continue
            if gate == "quality_pending" and quality_gate_mode != "parallel":
                continue
            if qa_artifact_terminal(task_path.parent):
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
