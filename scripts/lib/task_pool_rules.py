from __future__ import annotations

from pathlib import Path
from typing import Any

REQUIRED_INSTRUCTION_SECTIONS = [
    "任务类型",
    "目标",
    "任务边界",
    "输入事实",
    "约束",
    "交付物",
    "验收标准",
    "下游动作",
]

POOL_EXCLUDED_TASK_TYPES = {"deployment", "integration"}
POOL_WRITE_SCOPE_OPTIONAL_TYPES = {"design", "verification"}
VALID_TASK_TYPES = {
    "investigation",
    "design",
    "development",
    "verification",
    "integration",
    "deployment",
}


def parse_boolish(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "on"}


def normalize_task_type(value: Any) -> str:
    return str(value or "").strip().lower()


def normalized_write_scope(task: dict[str, Any]) -> list[str]:
    return [str(item).strip() for item in (task.get("write_scope") or []) if str(item).strip()]


def instruction_gate_blockers(task_dir: Path) -> list[str]:
    instruction_path = task_dir / "instruction.md"
    if not instruction_path.exists():
        return ["instruction_missing"]
    text = instruction_path.read_text(encoding="utf-8", errors="ignore")
    blockers: list[str] = []
    for name in REQUIRED_INSTRUCTION_SECTIONS:
        marker = f"## {name}"
        if marker not in text:
            blockers.append(f"instruction_missing_section:{name}")
            continue
        section = text.split(marker, 1)[1].split("## ", 1)[0]
        if "待 PM 填写" in section:
            blockers.append(f"instruction_placeholder:{name}")
    return blockers


def task_requires_write_scope(task: dict[str, Any]) -> bool:
    if parse_boolish(task.get("read_only")):
        return False
    task_type = normalize_task_type(task.get("task_type"))
    return task_type not in POOL_WRITE_SCOPE_OPTIONAL_TYPES


def pool_gate_blockers(
    task: dict[str, Any],
    task_dir: Path,
    *,
    require_instruction: bool = True,
) -> list[str]:
    blockers: list[str] = []
    if require_instruction:
        blockers.extend(instruction_gate_blockers(task_dir))

    task_type = normalize_task_type(task.get("task_type"))
    if task_type not in VALID_TASK_TYPES:
        blockers.append("task_type_missing_or_invalid")

    execution_mode = str(task.get("execution_mode") or "").strip().lower()
    target_environment = str(task.get("target_environment") or "").strip().lower()
    task_level = str(task.get("task_level") or "").strip().lower()
    if (
        task_type in POOL_EXCLUDED_TASK_TYPES
        or execution_mode == "deploy"
        or target_environment == "prod"
        or task_level == "integration"
    ):
        blockers.append("special_task_not_poolable")

    write_scope = normalized_write_scope(task)
    read_only = parse_boolish(task.get("read_only"))
    if read_only and write_scope:
        blockers.append("read_only_write_scope_mismatch")
    elif task_requires_write_scope(task) and not write_scope:
        blockers.append("write_scope_missing")

    if parse_boolish(task.get("owner_approval_required")):
        approved_by = str(task.get("owner_approved_by") or "").strip()
        approved_at = str(task.get("owner_approved_at") or "").strip()
        if not approved_by or not approved_at:
            blockers.append("owner_approval_pending")

    return sorted(set(blockers))
