#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

APPROVE_PATTERNS = (
    re.compile(r"\bapprove(?:d)?\b", re.IGNORECASE),
    re.compile(r"\blgtm\b", re.IGNORECASE),
    re.compile(r"\bship\s+it\b", re.IGNORECASE),
    re.compile(r"通过|同意合入|批准|可以合入"),
)
REJECT_PATTERNS = (
    re.compile(r"\brequest\s+changes\b", re.IGNORECASE),
    re.compile(r"\bchanges\s+requested\b", re.IGNORECASE),
    re.compile(r"\breject(?:ed)?\b", re.IGNORECASE),
    re.compile(r"驳回|不通过|未通过|不接受|请求修改|要求修改"),
)
CONCLUSION_LABEL_RE = re.compile(
    r"^\s*(?:#{1,6}\s*)?"
    r"(?:审查结论|复审结论|最终结论|最终意见|结论|review conclusion|conclusion|verdict|decision)"
    r"\s*(?:[:：\-—]\s*)?(.*)$",
    re.IGNORECASE,
)


@dataclass
class TaskContext:
    task_dir: Path
    task: dict[str, Any]
    resume_epoch: int


def _workspace_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _control_config_path() -> Path:
    env_path = os.environ.get("TASK_CONTROL_CONFIG_PATH")
    if env_path:
        return Path(env_path).expanduser().resolve()
    return (_workspace_root() / "config.json").resolve()


def load_control_config() -> dict[str, Any]:
    path = _control_config_path()
    if not path.exists():
        return {}
    payload, error = load_json(path)
    if error or not isinstance(payload, dict):
        return {}
    return payload


def sha256_file(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def iso_to_epoch(value: Any) -> int:
    if not value:
        return 0
    text = str(value).strip()
    if not text:
        return 0
    try:
        return int(datetime.fromisoformat(text.replace("Z", "+00:00")).timestamp())
    except Exception:
        return 0


def mtime_epoch(path: Path) -> int:
    try:
        return int(path.stat().st_mtime)
    except Exception:
        return 0


def load_json(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    if not path.exists():
        return None, "missing"
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except json.JSONDecodeError as exc:
        return None, f"json_decode_error:{exc}"
    except Exception as exc:
        return None, f"read_error:{exc}"


def task_context(task_dir: Path) -> TaskContext:
    task, _ = load_json(task_dir / "task.json")
    task = task or {}
    resume_epoch = max(
        iso_to_epoch(task.get("last_resumed_at")),
        _latest_resume_transition_epoch(task_dir / "transitions.jsonl"),
    )
    return TaskContext(task_dir=task_dir, task=task, resume_epoch=resume_epoch)


def review_json_required_for_task(task: dict[str, Any]) -> bool:
    config = load_control_config()
    artifact_contract = config.get("artifact_contract") or {}
    threshold = artifact_contract.get("new_tasks_require_review_json_after")
    if not threshold:
        return False
    created_epoch = iso_to_epoch(task.get("created_at"))
    threshold_epoch = iso_to_epoch(threshold)
    return bool(created_epoch and threshold_epoch and created_epoch >= threshold_epoch and task.get("review_required"))


def _latest_resume_transition_epoch(path: Path) -> int:
    if not path.exists():
        return 0
    latest = 0
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except Exception:
            continue
        if str(payload.get("from") or "") != "blocked" or str(payload.get("to") or "") != "dispatched":
            continue
        latest = max(latest, iso_to_epoch(payload.get("at")))
    return latest


def _base_result(path: Path, kind: str, ctx: TaskContext) -> dict[str, Any]:
    mtime = mtime_epoch(path)
    current_round = True
    if ctx.resume_epoch and mtime and mtime < ctx.resume_epoch:
        current_round = False
    return {
        "kind": kind,
        "path": str(path),
        "exists": path.exists(),
        "artifact_hash": sha256_file(path),
        "mtime_epoch": mtime,
        "is_current_round": current_round,
        "resume_epoch": ctx.resume_epoch,
        "errors": [],
        "warnings": [],
    }


def parse_ack(task_dir: Path) -> dict[str, Any]:
    ctx = task_context(task_dir)
    path = task_dir / "ack.json"
    result = _base_result(path, "ack", ctx)
    payload, error = load_json(path)
    if error == "missing":
        result.update({"valid": False, "normalized_status": "missing"})
        return result
    if error:
        result.update({"valid": False, "normalized_status": "invalid"})
        result["errors"].append(error)
        return result
    result.update({"task_id": payload.get("task_id"), "agent": payload.get("agent") or payload.get("agent_id")})
    raw_status = str(payload.get("status") or "acknowledged").strip().lower()
    if payload.get("task_id") not in (None, ctx.task.get("id")):
        result["errors"].append("task_id_mismatch")
    if ctx.task.get("assigned_agent") and result.get("agent") not in (None, ctx.task.get("assigned_agent")):
        result["errors"].append("agent_mismatch")
    if raw_status not in {"acknowledged", "working", "ack"}:
        result["errors"].append("unknown_status")
    result.update({
        "valid": not result["errors"],
        "normalized_status": "acknowledged" if not result["errors"] else "invalid",
        "acked_at": payload.get("acked_at") or payload.get("acknowledged_at") or payload.get("acked_at") or payload.get("acknowledged_at"),
        "summary": payload.get("summary") or payload.get("message") or "",
    })
    return result


def parse_claim(task_dir: Path) -> dict[str, Any]:
    ctx = task_context(task_dir)
    path = task_dir / "claim.json"
    result = _base_result(path, "claim", ctx)
    payload, error = load_json(path)
    if error == "missing":
        result.update({"valid": False, "normalized_status": "missing"})
        return result
    if error:
        result.update({"valid": False, "normalized_status": "invalid"})
        result["errors"].append(error)
        return result
    result.update({
        "valid": True,
        "normalized_status": "claimed",
        "task_id": payload.get("task_id"),
        "agent": payload.get("agent") or payload.get("agent_id"),
        "claimed_at": payload.get("claimed_at"),
        "summary": payload.get("reason") or "",
    })
    if payload.get("task_id") not in (None, ctx.task.get("id")):
        result["valid"] = False
        result["normalized_status"] = "invalid"
        result["errors"].append("task_id_mismatch")
    return result


def _normalize_result_status(value: Any) -> tuple[str, bool]:
    normalized = str(value or "").strip().lower()
    mapping = {
        "success": "success",
        "done": "success",
        "failed": "failed",
        "fail": "failed",
        "blocked": "blocked",
    }
    return mapping.get(normalized, "invalid"), normalized == "done"


def parse_result(task_dir: Path) -> dict[str, Any]:
    ctx = task_context(task_dir)
    path = task_dir / "result.json"
    result = _base_result(path, "result", ctx)
    payload, error = load_json(path)
    if error == "missing":
        result.update({"valid": False, "normalized_status": "missing"})
        return result
    if error:
        result.update({"valid": False, "normalized_status": "invalid"})
        result["errors"].append(error)
        return result
    norm_status, legacy_mapped = _normalize_result_status(payload.get("status"))
    result.update({
        "task_id": payload.get("task_id"),
        "agent": payload.get("agent") or payload.get("agent_id"),
        "summary": payload.get("summary") or payload.get("message") or "",
        "legacy_mapped": legacy_mapped,
        "finished_at": payload.get("finished_at") or payload.get("completed_at") or payload.get("reported_at"),
    })
    if payload.get("task_id") not in (None, ctx.task.get("id")):
        result["errors"].append("task_id_mismatch")
    if ctx.task.get("assigned_agent") and result.get("agent") not in (None, ctx.task.get("assigned_agent")):
        result["errors"].append("agent_mismatch")
    if norm_status == "invalid":
        result["errors"].append("unknown_or_missing_status")
    if not isinstance(result.get("summary"), str) or not result.get("summary", "").strip():
        result["warnings"].append("summary_missing")
    if not result["is_current_round"]:
        result["warnings"].append("stale_round")
    result.update({
        "valid": not result["errors"],
        "normalized_status": norm_status if not result["errors"] else "invalid",
    })
    return result


def _normalize_verify_status(payload: dict[str, Any]) -> str:
    values = [
        payload.get("status"),
        payload.get("result"),
        payload.get("verdict"),
        payload.get("conclusion"),
        payload.get("ok"),
        payload.get("pass"),
    ]
    for value in values:
        if isinstance(value, bool):
            return "pass" if value else "fail"
        if value is None:
            continue
        normalized = str(value).strip().lower()
        if normalized in {"pass", "passed", "approve", "approved", "ok", "true", "1", "success", "done"}:
            return "pass"
        if normalized in {"fail", "failed", "false", "0", "reject", "rejected", "error", "qa_failed"}:
            return "fail"
        if normalized == "blocked":
            return "blocked"
    return "invalid"


def parse_verify(task_dir: Path) -> dict[str, Any]:
    ctx = task_context(task_dir)
    path = task_dir / "verify.json"
    result = _base_result(path, "verify", ctx)
    payload, error = load_json(path)
    if error == "missing":
        result.update({"valid": False, "normalized_status": "missing"})
        return result
    if error:
        result.update({"valid": False, "normalized_status": "invalid"})
        result["errors"].append(error)
        return result
    status = _normalize_verify_status(payload)
    result.update({
        "task_id": payload.get("task_id"),
        "agent": payload.get("tester") or payload.get("agent") or payload.get("agent_id") or payload.get("tested_by"),
        "summary": payload.get("summary") or payload.get("notes") or payload.get("message") or "",
        "verified_at": payload.get("verified_at") or payload.get("completed_at") or payload.get("reported_at"),
    })
    if payload.get("task_id") not in (None, ctx.task.get("id")):
        result["errors"].append("task_id_mismatch")
    if status == "invalid":
        result["errors"].append("unknown_or_missing_status")
    if not result["is_current_round"]:
        result["warnings"].append("stale_round")
    result.update({
        "valid": not result["errors"],
        "normalized_status": status if not result["errors"] else "invalid",
    })
    return result


def _classify_review_snippet(snippet: str) -> str:
    if not snippet.strip():
        return "pending"
    if any(pattern.search(snippet) for pattern in REJECT_PATTERNS):
        return "request_changes"
    if any(pattern.search(snippet) for pattern in APPROVE_PATTERNS):
        return "approve"
    return "pending"


def _parse_review_markdown(path: Path) -> str:
    if not path.exists():
        return "missing"
    text = path.read_text(encoding="utf-8", errors="ignore")
    lines = text.splitlines()
    for index, line in enumerate(lines[:60]):
        match = CONCLUSION_LABEL_RE.match(line)
        if not match:
            continue
        snippets: list[str] = []
        suffix = match.group(1).strip()
        if suffix:
            snippets.append(suffix)
        for following in lines[index + 1:index + 8]:
            stripped = following.strip()
            if not stripped:
                continue
            if stripped.startswith("#") and snippets:
                break
            snippets.append(stripped)
            if len(snippets) >= 4:
                break
        state = _classify_review_snippet("\n".join(snippets))
        if state != "pending":
            return state
    return _classify_review_snippet("\n".join(line.strip() for line in lines[:20] if line.strip()))


def _parse_review_json(path: Path, ctx: TaskContext) -> dict[str, Any]:
    result = _base_result(path, path.name, ctx)
    payload, error = load_json(path)
    if error == "missing":
        result.update({"valid": False, "normalized_status": "missing"})
        return result
    if error:
        result.update({"valid": False, "normalized_status": "invalid"})
        result["errors"].append(error)
        return result
    status = str(payload.get("status") or "").strip().lower()
    if status not in {"approve", "request_changes", "blocked"}:
        result["errors"].append("unknown_or_missing_status")
    result.update({
        "task_id": payload.get("task_id"),
        "reviewer": payload.get("reviewer") or payload.get("agent") or payload.get("agent_id"),
        "summary": payload.get("summary") or "",
        "reviewed_at": payload.get("reviewed_at") or payload.get("completed_at") or payload.get("reported_at"),
    })
    if payload.get("task_id") not in (None, ctx.task.get("id")):
        result["errors"].append("task_id_mismatch")
    if not result["is_current_round"]:
        result["warnings"].append("stale_round")
    result.update({
        "valid": not result["errors"],
        "normalized_status": status if not result["errors"] else "invalid",
    })
    return result


def parse_review(task_dir: Path) -> dict[str, Any]:
    ctx = task_context(task_dir)
    review_level = str(ctx.task.get("review_level") or "").strip().lower() or "standard"
    review_json = _parse_review_json(task_dir / "review.json", ctx)
    design_json = _parse_review_json(task_dir / "design-review.json", ctx)
    review_md = _parse_review_markdown(task_dir / "review.md")
    design_md = _parse_review_markdown(task_dir / "design-review.md")

    result = {
        "kind": "review",
        "task_dir": str(task_dir),
        "review_level": review_level,
        "sources": {
            "review_json": review_json,
            "design_review_json": design_json,
            "review_markdown": review_md,
            "design_review_markdown": design_md,
        },
        "errors": [],
        "warnings": [],
    }

    json_sources = [review_json]
    if review_level == "complex":
        json_sources.append(design_json)

    if any(src["normalized_status"] == "invalid" for src in json_sources if src["exists"]):
        result["errors"].append("invalid_review_json")
        result.update({"valid": False, "normalized_status": "invalid", "source": "json"})
        return result

    existing_json_sources = [src for src in json_sources if src["exists"]]
    if existing_json_sources:
        statuses = [src["normalized_status"] for src in existing_json_sources]
        if "blocked" in statuses:
            status = "blocked"
        elif "request_changes" in statuses:
            status = "request_changes"
        elif statuses and all(item == "approve" for item in statuses):
            status = "approve"
        else:
            status = "pending"
        result.update({"valid": True, "normalized_status": status, "source": "json"})
        if any(not src["is_current_round"] for src in existing_json_sources):
            result["warnings"].append("stale_round")
        return result

    if review_json_required_for_task(ctx.task):
        result["errors"].append("review_json_required_for_new_task")
        result.update({"valid": False, "normalized_status": "missing", "source": "json_required"})
        return result

    if review_level == "complex":
        statuses = [review_md, design_md]
        if "request_changes" in statuses:
            status = "request_changes"
        elif "blocked" in statuses:
            status = "blocked"
        elif all(item in {"approve", "missing"} for item in statuses) and any(item == "approve" for item in statuses):
            status = "approve"
        else:
            status = "pending"
    else:
        status = review_md
    if status == "missing":
        result.update({"valid": False, "normalized_status": "missing", "source": "none"})
    else:
        result.update({"valid": True, "normalized_status": status, "source": "markdown_fallback"})
        result["warnings"].append("markdown_fallback")
    return result


def parse_task(task_dir: Path) -> dict[str, Any]:
    ctx = task_context(task_dir)
    return {
        "kind": "task",
        "path": str(task_dir / 'task.json'),
        "task": ctx.task,
        "resume_epoch": ctx.resume_epoch,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Parse task artifacts into normalized machine-readable payloads")
    parser.add_argument("artifact", choices=["ack", "claim", "result", "review", "verify", "task"])
    parser.add_argument("--task-dir", required=True)
    args = parser.parse_args()
    task_dir = Path(args.task_dir).expanduser().resolve()

    if args.artifact == "ack":
        payload = parse_ack(task_dir)
    elif args.artifact == "claim":
        payload = parse_claim(task_dir)
    elif args.artifact == "result":
        payload = parse_result(task_dir)
    elif args.artifact == "review":
        payload = parse_review(task_dir)
    elif args.artifact == "verify":
        payload = parse_verify(task_dir)
    else:
        payload = parse_task(task_dir)

    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
