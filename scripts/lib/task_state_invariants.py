#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from agent_config import default_claim_scope
from task_artifacts import parse_ack
from task_quality_rules import validate_task_type_gate_template

AUTO_ASSIGN_MARKERS = {"auto", "auto-dev", "unassigned"}


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _parse_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "on"}


def _normalized_claim_scope(task: dict[str, Any], config: dict[str, Any]) -> list[str]:
    return default_claim_scope(task, config)


def _is_pull_task(task: dict[str, Any]) -> bool:
    claim_policy = str(task.get("claim_policy") or "").strip().lower()
    status = str(task.get("status") or "").strip().lower()
    return claim_policy == "pull" or status == "pooled" or bool(task.get("claimed_by") or task.get("reserved_by"))


def _is_direct_dispatch_exception(task: dict[str, Any]) -> bool:
    claim_policy = str(task.get("claim_policy") or "").strip().lower()
    return claim_policy == "pull" and bool(str(task.get("direct_dispatch_reason") or "").strip())


def _allowed_ready_for_merge_gates(task: dict[str, Any]) -> set[str]:
    review_required = _parse_bool(task.get("review_required"))
    test_required = _parse_bool(task.get("test_required"))
    quality_gate_mode = str(task.get("quality_gate_mode") or "").strip().lower()
    allowed = {"blocked", "pm_acceptance_pending"}
    if review_required:
        allowed.add("review_rejected")
    if test_required:
        allowed.add("qa_failed")
    if review_required and test_required:
        if quality_gate_mode == "parallel":
            allowed.add("quality_pending")
        else:
            allowed.update({"review_pending", "qa_pending"})
    elif review_required:
        allowed.add("review_pending")
    elif test_required:
        allowed.add("qa_pending")
    return allowed


def check_task_invariants(task_dir: Path, config_path: Path) -> dict[str, Any]:
    task = _load_json(task_dir / "task.json")
    config = _load_json(config_path) if config_path.exists() else {}
    status = str(task.get("status") or "").strip().lower()
    violations: list[dict[str, str]] = []

    if _is_pull_task(task) and not _is_direct_dispatch_exception(task):
        assigned_agent = str(task.get("assigned_agent") or "").strip()
        claimed_by = str(task.get("claimed_by") or "").strip()
        reserved_by = str(task.get("reserved_by") or "").strip()
        claim_scope = _normalized_claim_scope(task, config)
        if status in {"dispatched", "working"} and assigned_agent:
            if claimed_by and claimed_by != assigned_agent:
                violations.append({
                    "code": "assigned_claimed_mismatch",
                    "message": f"assigned_agent={assigned_agent} 与 claimed_by={claimed_by} 不一致",
                })
            if reserved_by and reserved_by != assigned_agent:
                violations.append({
                    "code": "assigned_reserved_mismatch",
                    "message": f"assigned_agent={assigned_agent} 与 reserved_by={reserved_by} 不一致",
                })
        if (
            assigned_agent
            and assigned_agent not in AUTO_ASSIGN_MARKERS
            and claim_scope
            and status in {"pooled", "dispatched", "working"}
            and assigned_agent not in claim_scope
        ):
            violations.append({
                "code": "claim_scope_missing_assignee",
                "message": f"claim_scope 未覆盖当前执行者 {assigned_agent}",
            })

    if status == "working":
        ack = parse_ack(task_dir)
        if ack.get("normalized_status") != "acknowledged" or not ack.get("is_current_round", True):
            violations.append({
                "code": "working_without_current_ack",
                "message": "status=working 但缺少当前轮 ack.json",
            })

    template_errors = validate_task_type_gate_template(
        task_type=str(task.get("task_type") or ""),
        review_required=_parse_bool(task.get("review_required")),
        test_required=_parse_bool(task.get("test_required")),
    )
    for error in template_errors:
        violations.append({
            "code": "quality_gate_template_invalid",
            "message": error,
        })

    if status == "ready_for_merge":
        merge_gate_state = str(task.get("merge_gate_state") or "").strip().lower()
        if not merge_gate_state:
            violations.append({
                "code": "merge_gate_state_missing",
                "message": "ready_for_merge 任务缺少 merge_gate_state",
            })
        elif merge_gate_state not in _allowed_ready_for_merge_gates(task):
            violations.append({
                "code": "merge_gate_state_inconsistent",
                "message": f"merge_gate_state={merge_gate_state} 与当前 quality gate 配置不一致",
            })

    if status == "done" and str(task.get("merge_gate_state") or "").strip().lower() != "closed":
        violations.append({
            "code": "done_without_closed_gate",
            "message": "status=done 但 merge_gate_state 未收敛到 closed",
        })

    signature = "|".join(sorted({item["code"] for item in violations}))
    return {
        "task_id": str(task.get("id") or task_dir.name),
        "violations": violations,
        "count": len(violations),
        "signature": signature,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Check task state invariants")
    parser.add_argument("--task-dir", required=True)
    parser.add_argument("--config", required=True)
    args = parser.parse_args()
    payload = check_task_invariants(
        Path(args.task_dir).expanduser().resolve(),
        Path(args.config).expanduser().resolve(),
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
