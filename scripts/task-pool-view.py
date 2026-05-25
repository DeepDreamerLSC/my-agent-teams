#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR / "lib"))
import task_artifacts  # type: ignore
from task_pool_rules import pool_gate_blockers  # type: ignore

PRIORITY_RANK = {"critical": 4, "urgent": 4, "high": 3, "medium": 2, "low": 1}
TERMINAL_STATUSES = {"done", "merged", "archived", "cancelled"}
REQUIRED_INSTRUCTION_SECTIONS = ["任务类型", "目标", "任务边界", "输入事实", "约束", "交付物", "验收标准", "下游动作"]


def parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            return parsed.astimezone()
        return parsed.astimezone()
    except Exception:
        return None


def age_minutes(value: str | None, now: datetime) -> int:
    dt = parse_iso(value)
    if not dt:
        return 0
    return max(0, int((now - dt).total_seconds() // 60))


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def default_busy_diagnostic(agent_id: str, *, error: str | None = None) -> dict:
    diag = {
        "agent_id": agent_id,
        "role": "",
        "busy_level": "idle",
        "primary_reason": "idle",
        "reason_codes": [],
        "hard_reason_codes": [],
        "soft_reason_codes": [],
        "hard_task_ids": [],
        "soft_task_ids": [],
        "hard_task_count": 0,
        "soft_task_count": 0,
        "counts": {},
        "capacity": {},
        "routes": {
            "execute": "direct",
            "remind": "direct",
            "preheat": "direct",
            "broadcast": "direct",
            "critical": "override",
        },
        "can_direct_execute": True,
        "can_direct_remind": True,
        "queue_only": False,
    }
    if error:
        diag["helper_error"] = error
    return diag


def load_agent_busy_diagnostic(agent_id: str, tasks_root: Path, config_path: Path) -> dict:
    helper_path = SCRIPT_DIR / "lib" / "agent_availability.sh"
    if not helper_path.exists():
        return default_busy_diagnostic(agent_id, error="helper_missing")
    try:
        completed = subprocess.run(
            [
                "bash",
                str(helper_path),
                "json",
                agent_id,
                str(tasks_root),
                str(config_path),
            ],
            cwd=str(SCRIPT_DIR.parent),
            capture_output=True,
            text=True,
            check=True,
        )
        payload = json.loads(completed.stdout)
        if not isinstance(payload, dict):
            return default_busy_diagnostic(agent_id, error="helper_non_dict")
        return payload
    except Exception as exc:
        return default_busy_diagnostic(agent_id, error=f"helper_error:{exc.__class__.__name__}")


def load_task_records(tasks_root: Path) -> list[tuple[Path, dict]]:
    records: list[tuple[Path, dict]] = []
    for task_path in sorted(tasks_root.glob("*/task.json")):
        try:
            payload = load_json(task_path)
        except Exception:
            continue
        records.append((task_path.parent, payload))
    return records


def default_claim_scope(task: dict, agents: dict[str, dict]) -> list[str]:
    claim_scope = task.get("claim_scope")
    if isinstance(claim_scope, list) and claim_scope:
        return [str(item).strip() for item in claim_scope if str(item).strip()]
    task_type = str(task.get("task_type") or "").strip().lower()
    domain = str(task.get("domain") or "").strip().lower()
    output: list[str] = []
    for agent_id, payload in agents.items():
        role = str((payload or {}).get("role") or "").strip().lower()
        if task_type in {"development", "investigation"}:
            if role == "fullstack_dev" or agent_id.startswith("dev-"):
                output.append(agent_id)
        elif task_type == "verification" or domain == "quality":
            if role == "qa" or agent_id.startswith("qa-"):
                output.append(agent_id)
        elif task_type == "design":
            if role == "architect" or agent_id == "arch-1":
                output.append(agent_id)
    return output


def is_relative_to(path: Path, other: Path) -> bool:
    try:
        path.relative_to(other)
        return True
    except ValueError:
        return False


def scopes_overlap(a: Path, b: Path) -> bool:
    return a == b or is_relative_to(a, b) or is_relative_to(b, a)


def project_roots(task: dict, config: dict) -> tuple[Path | None, Path | None]:
    project = str(task.get("project") or "").strip()
    project_cfg = (config.get("projects") or {}).get(project) or {}
    dev_root_raw = project_cfg.get("dev_root")
    prod_root_raw = project_cfg.get("prod_root")
    dev_root = Path(dev_root_raw).expanduser().resolve() if dev_root_raw else None
    prod_root = Path(prod_root_raw).expanduser().resolve() if prod_root_raw else None
    return dev_root, prod_root


def resolve_scope_paths(task: dict, config: dict) -> list[Path]:
    raw_scope = [str(item).strip() for item in (task.get("write_scope") or []) if str(item).strip()]
    if not raw_scope:
        return []
    dev_root, prod_root = project_roots(task, config)
    target_environment = str(task.get("target_environment") or "dev").strip().lower()
    base_root = prod_root if target_environment == "prod" and prod_root is not None else dev_root
    resolved: list[Path] = []
    for item in raw_scope:
        path = Path(item).expanduser()
        if not path.is_absolute() and base_root is not None:
            path = base_root / path
        resolved.append(path.resolve())
    return resolved


def active_tasks_by_agent(task_records: list[tuple[Path, dict]] | Path) -> dict[str, list[dict]]:
    if isinstance(task_records, Path):
        task_records = load_task_records(task_records)
    result: dict[str, list[dict]] = {}
    for task_dir, payload in task_records:
        if str(payload.get("status") or "") not in {"dispatched", "working"}:
            continue
        agent = str(payload.get("assigned_agent") or "").strip()
        if not agent:
            continue
        result.setdefault(agent, []).append({"id": payload.get("id") or task_dir.name, "task": payload})
    return result


def _int_value(value: object, default: int) -> int:
    try:
        if value in (None, ""):
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def capacity_limits(agent_id: str, agents: dict[str, dict], config: dict) -> tuple[int, int, int]:
    pool_config = config.get("task_pool") or {}
    working_limit = max(1, _int_value(pool_config.get("default_working_limit"), 1))
    reserved_limit = max(1, _int_value(pool_config.get("default_reserved_limit"), 1))

    role = str((agents.get(agent_id) or {}).get("role") or "").strip().lower()
    role_limits = {
        "fullstack_dev": "dev",
        "reviewer": "reviewer",
        "qa": "qa",
        "architect": "architect",
        "pm": "pm-chief",
    }
    wip_limits = config.get("wip_limits") or {}
    mapped = role_limits.get(role, agent_id if agent_id in wip_limits else "")
    role_limit = wip_limits.get(agent_id)
    if role_limit is None and mapped:
        role_limit = wip_limits.get(mapped)
    if role_limit not in (None, ""):
        working_limit = max(1, min(working_limit, _int_value(role_limit, working_limit)))
    return working_limit, reserved_limit, working_limit + reserved_limit


def dependency_blockers(task: dict, tasks_root: Path) -> list[str]:
    blockers: list[str] = []
    policy = str(task.get("dependency_policy") or "done_only").strip().lower()
    allowed = {"done", "cancelled"}
    if policy == "ready_for_merge_ok":
        allowed.add("ready_for_merge")
    for dep in task.get("depends_on") or []:
        dep_path = tasks_root / dep / "task.json"
        if not dep_path.exists():
            blockers.append(f"dependency_missing:{dep}")
            continue
        dep_task = load_json(dep_path)
        dep_status = str(dep_task.get("status") or "")
        if dep_status not in allowed:
            blockers.append(f"dependency_not_ready:{dep}={dep_status}")
    return blockers


def no_progress_repool_blockers(task: dict, agent_id: str, now: datetime) -> list[str]:
    blockers: list[str] = []
    if str(task.get("status") or "") != "pooled":
        return blockers
    if str(task.get("last_no_progress_repool_agent") or "").strip() != agent_id:
        return blockers
    until = parse_iso(str(task.get("no_progress_repool_until") or "").strip())
    if not until:
        return blockers
    if now < until:
        blockers.append(f"no_progress_cooldown_until:{until.isoformat(timespec='seconds')}")
    return blockers


def scope_conflicts(task: dict, agent_id: str, active_by_agent: dict[str, list[dict]], config: dict) -> list[str]:
    resolved_target = resolve_scope_paths(task, config)
    if not resolved_target:
        return []
    conflicts: list[str] = []
    for payload in active_by_agent.get(agent_id, []):
        other_task = payload["task"]
        for other in resolve_scope_paths(other_task, config):
            for target in resolved_target:
                if scopes_overlap(target, other):
                    conflicts.append(f"write_scope_conflict:{payload['id']}")
                    break
    return conflicts


def agent_acceptance(task: dict, task_dir: Path, agent_id: str, agents: dict[str, dict], active_by_agent: dict[str, list[dict]], tasks_root: Path, default_concurrency: int, config: dict) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    reasons.extend(pool_gate_blockers(task, task_dir))
    claim_scope = default_claim_scope(task, agents)
    if claim_scope and agent_id not in claim_scope:
        reasons.append("not_in_claim_scope")
    reasons.extend(dependency_blockers(task, tasks_root))
    reasons.extend(no_progress_repool_blockers(task, agent_id, datetime.now().astimezone()))
    reasons.extend(scope_conflicts(task, agent_id, active_by_agent, config))
    active = active_by_agent.get(agent_id, [])
    working_count = sum(1 for item in active if str(item["task"].get("status") or "") == "working")
    reserved_count = sum(1 for item in active if str(item["task"].get("status") or "") == "dispatched")
    working_limit, reserved_limit, active_limit = capacity_limits(agent_id, agents, config)
    if working_count > working_limit:
        reasons.append(f"working_limit_exceeded:{working_limit}")
    if reserved_count >= reserved_limit:
        reasons.append(f"reserved_limit_reached:{reserved_limit}")
    if len(active) >= active_limit:
        reasons.append(f"active_capacity_reached:{active_limit}")
    return not reasons, sorted(set(reasons))


def pooled_tasks(tasks_root: Path) -> list[tuple[Path, dict]]:
    rows = []
    for task_path in tasks_root.glob("*/task.json"):
        try:
            payload = load_json(task_path)
        except Exception:
            continue
        if str(payload.get("status") or "") != "pooled":
            continue
        rows.append((task_path.parent, payload))
    return rows


def is_pool_agent(agent_id: str, payload: dict) -> bool:
    role = str((payload or {}).get("role") or "").strip().lower()
    if role == "pm" or agent_id.startswith("pm-"):
        return False
    return role in {"fullstack_dev", "reviewer", "qa", "architect"} or agent_id.startswith(("dev-", "review-", "qa-", "arch-"))


def artifact_invalid_count(tasks_root: Path) -> int:
    count = 0
    for task_path in tasks_root.glob("*/task.json"):
        task_dir = task_path.parent
        try:
            task = load_json(task_path)
        except Exception:
            continue
        if str(task.get("status") or "") in TERMINAL_STATUSES:
            continue
        for parser in (
            task_artifacts.parse_result,
            task_artifacts.parse_review,
            task_artifacts.parse_verify,
            task_artifacts.parse_ack,
        ):
            try:
                parsed = parser(task_dir)
            except Exception:
                continue
            if parsed.get("valid") is False and parsed.get("errors"):
                count += 1
                break
    return count


def instruction_mature(task_dir: Path) -> bool:
    instruction_path = task_dir / "instruction.md"
    if not instruction_path.exists():
        return False
    text = instruction_path.read_text(encoding="utf-8", errors="ignore")
    if "待 PM 填写" in text:
        return False
    return all(f"## {name}" in text for name in REQUIRED_INSTRUCTION_SECTIONS)


def mature_pending_count(tasks_root: Path) -> int:
    count = 0
    for task_path in tasks_root.glob("*/task.json"):
        try:
            task = load_json(task_path)
        except Exception:
            continue
        if str(task.get("status") or "") == "pending" and instruction_mature(task_path.parent):
            count += 1
    return count


def build_summary(rows: list[dict], agents: dict[str, dict], active_by_agent: dict[str, list[dict]], tasks_root: Path, busy_map: dict[str, dict]) -> dict:
    pool_agents = sorted(agent_id for agent_id, payload in agents.items() if is_pool_agent(agent_id, payload or {}))
    busy_level_counts = {"idle": 0, "soft_busy": 0, "hard_busy": 0}
    deferred_agents: list[str] = []
    digest_agents: list[str] = []
    queue_only_agents: list[str] = []
    for agent_id in pool_agents:
        diag = busy_map.get(agent_id) or {}
        level = str(diag.get("busy_level") or "idle")
        busy_level_counts[level] = busy_level_counts.get(level, 0) + 1
        routes = diag.get("routes") or {}
        if level != "idle":
            deferred_agents.append(agent_id)
        if str(routes.get("remind") or "") == "digest":
            digest_agents.append(agent_id)
        if str(routes.get("execute") or "") == "queue_only":
            queue_only_agents.append(agent_id)
    idle_agents = [agent_id for agent_id in pool_agents if (busy_map.get(agent_id) or {}).get("busy_level") == "idle"]
    active_rows = [item for items in active_by_agent.values() for item in items]
    reserved_count = sum(1 for item in active_rows if str((item.get("task") or {}).get("status") or "") == "dispatched")
    working_count = sum(1 for item in active_rows if str((item.get("task") or {}).get("status") or "") == "working")
    waiting_dependency_count = sum(
        1
        for row in rows
        if any(str(reason).startswith("dependency_") for reason in (row.get("blocked_reasons") or []))
    )
    ready_count = sum(1 for row in rows if row.get("eligible_agents"))
    return {
        "pooled_count": len(rows),
        "pool_ready_count": ready_count,
        "pool_waiting_dependency_count": waiting_dependency_count,
        "pool_blocked_count": len(rows) - ready_count,
        "definition_blocked_count": sum(1 for row in rows if row.get("definition_blockers")),
        "idle_agents": idle_agents,
        "idle_agent_count": len(idle_agents),
        "busy_level_counts": busy_level_counts,
        "soft_busy_agent_count": busy_level_counts.get("soft_busy", 0),
        "hard_busy_agent_count": busy_level_counts.get("hard_busy", 0),
        "deferred_agents": deferred_agents,
        "deferred_agent_count": len(deferred_agents),
        "digest_agents": digest_agents,
        "digest_agent_count": len(digest_agents),
        "queue_only_agents": queue_only_agents,
        "queue_only_agent_count": len(queue_only_agents),
        "reserved_count": reserved_count,
        "working_count": working_count,
        "artifact_invalid_count": artifact_invalid_count(tasks_root),
        "mature_pending_count": mature_pending_count(tasks_root),
        "oldest_pool_wait_minutes": max((int(row.get("pool_wait_minutes") or 0) for row in rows), default=0),
    }


def build_row(task_dir: Path, task: dict, agents: dict[str, dict], active_by_agent: dict[str, list[dict]], busy_map: dict[str, dict], tasks_root: Path, default_concurrency: int, now: datetime, config: dict) -> dict:
    scope = default_claim_scope(task, agents)
    by_agent = []
    eligible = []
    blocked_reasons: set[str] = set()
    definition_blockers = pool_gate_blockers(task, task_dir)
    for agent_id in scope:
        can_claim, reasons = agent_acceptance(task, task_dir, agent_id, agents, active_by_agent, tasks_root, default_concurrency, config)
        busy_diag = busy_map.get(agent_id) or default_busy_diagnostic(agent_id)
        by_agent.append({
            "agent_id": agent_id,
            "can_claim": can_claim,
            "reasons": reasons,
            "busy_level": busy_diag.get("busy_level", "idle"),
            "busy_primary_reason": busy_diag.get("primary_reason", "idle"),
            "busy_reason_codes": busy_diag.get("reason_codes", []),
            "busy_hard_reason_codes": busy_diag.get("hard_reason_codes", []),
            "busy_soft_reason_codes": busy_diag.get("soft_reason_codes", []),
            "busy_hard_task_ids": busy_diag.get("hard_task_ids", []),
            "busy_soft_task_ids": busy_diag.get("soft_task_ids", []),
            "busy_execute_route": (busy_diag.get("routes") or {}).get("execute", "direct"),
            "busy_remind_route": (busy_diag.get("routes") or {}).get("remind", "direct"),
            "busy_preheat_route": (busy_diag.get("routes") or {}).get("preheat", "direct"),
            "busy_broadcast_route": (busy_diag.get("routes") or {}).get("broadcast", "direct"),
            "busy_critical_route": (busy_diag.get("routes") or {}).get("critical", "override"),
            "busy_can_direct_execute": bool(busy_diag.get("can_direct_execute", False)),
            "busy_can_direct_remind": bool(busy_diag.get("can_direct_remind", False)),
            "busy_queue_only": bool(busy_diag.get("queue_only", False)),
        })
        if can_claim:
            eligible.append(agent_id)
        else:
            blocked_reasons.update(reasons)
    wait = age_minutes(str(task.get("pool_entered_at") or task.get("created_at") or ""), now)
    priority = str(task.get("priority") or "medium").strip().lower()
    claim_busy_counts = {"idle": 0, "soft_busy": 0, "hard_busy": 0}
    claim_deferred_agents: list[str] = []
    claim_digest_agents: list[str] = []
    claim_queue_only_agents: list[str] = []
    for item in by_agent:
        level = str(item.get("busy_level") or "idle")
        claim_busy_counts[level] = claim_busy_counts.get(level, 0) + 1
        if level != "idle":
            claim_deferred_agents.append(item["agent_id"])
        if str(item.get("busy_remind_route") or "") == "digest":
            claim_digest_agents.append(item["agent_id"])
        if str(item.get("busy_execute_route") or "") == "queue_only":
            claim_queue_only_agents.append(item["agent_id"])

    if definition_blockers:
        next_action = "定义未完成，需 PM 补齐 Pool Gate"
        gate_stage = "definition"
    elif eligible:
        active = active_by_agent.get(eligible[0], [])
        has_working = any(str(item["task"].get("status") or "") == "working" for item in active)
        action = "可预留" if has_working else "可认领"
        selected_diag = next((item for item in by_agent if item["agent_id"] == eligible[0]), {})
        next_action = (
            f"{eligible[0]} {action}，busy_level={selected_diag.get('busy_level', 'idle')} "
            f"execute={selected_diag.get('busy_execute_route', 'direct')} "
            f"remind={selected_diag.get('busy_remind_route', 'direct')}，等待自动续推或手动 claim"
        )
        gate_stage = "claim_ready"
    elif blocked_reasons:
        next_action = "不可认领，需处理：" + ",".join(sorted(blocked_reasons))
        if any(str(reason).startswith("dependency_") for reason in blocked_reasons):
            gate_stage = "dependency"
        elif any(str(reason).startswith("no_progress_cooldown_until:") for reason in blocked_reasons):
            gate_stage = "claim_cooldown"
        elif any("write_scope_conflict" in str(reason) for reason in blocked_reasons):
            gate_stage = "scope_conflict"
        else:
            gate_stage = "capacity_or_scope"
    else:
        next_action = "无 claim_scope，需 PM 补齐"
        gate_stage = "definition"
    return {
        "task_id": str(task.get("id") or task_dir.name),
        "title": str(task.get("title") or task_dir.name),
        "priority": priority,
        "pool_wait_minutes": wait,
        "pool_timeout_minutes": int(task.get("pool_timeout_minutes") or 0),
        "claim_scope": scope,
        "eligible_agents": eligible,
        "by_agent": by_agent,
        "claim_scope_busy_level_counts": claim_busy_counts,
        "claim_scope_deferred_agents": claim_deferred_agents,
        "claim_scope_deferred_agent_count": len(claim_deferred_agents),
        "claim_scope_digest_agents": claim_digest_agents,
        "claim_scope_digest_agent_count": len(claim_digest_agents),
        "claim_scope_queue_only_agents": claim_queue_only_agents,
        "claim_scope_queue_only_agent_count": len(claim_queue_only_agents),
        "definition_blockers": definition_blockers,
        "blocked_reasons": sorted(blocked_reasons),
        "gate_stage": gate_stage,
        "next_action": next_action,
        "task_dir": str(task_dir),
    }


def human_print(rows: list[dict], agent_filter: str | None, summary: dict | None = None) -> None:
    pooled = len(rows)
    blocked = sum(1 for row in rows if not row["eligible_agents"])
    timed_out = sum(
        1
        for row in rows
        if int(row.get("pool_timeout_minutes") or 0) > 0 and int(row.get("pool_wait_minutes") or 0) > int(row.get("pool_timeout_minutes") or 0)
    )
    print(f"任务池 | 可认领 {pooled - blocked} | 阻塞 {blocked} | 超时 {timed_out}")
    if summary:
        busy_counts = summary.get("busy_level_counts") or {}
        print(
            f"池健康 | idle {busy_counts.get('idle', summary.get('idle_agent_count', 0))} | "
            f"soft_busy {busy_counts.get('soft_busy', summary.get('soft_busy_agent_count', 0))} | "
            f"hard_busy {busy_counts.get('hard_busy', summary.get('hard_busy_agent_count', 0))} | "
            f"deferred {summary.get('deferred_agent_count', 0)} | digest {summary.get('digest_agent_count', 0)} | "
            f"queue_only {summary.get('queue_only_agent_count', 0)} | reserved {summary.get('reserved_count', 0)} | "
            f"working {summary.get('working_count', 0)} | dependency_wait {summary.get('pool_waiting_dependency_count', 0)} | "
            f"definition_blocked {summary.get('definition_blocked_count', 0)} | artifact_invalid {summary.get('artifact_invalid_count', 0)}"
        )
    print()
    for row in rows:
        if agent_filter:
            agent_view = next((item for item in row["by_agent"] if item["agent_id"] == agent_filter), None)
            if not agent_view:
                continue
            state = "可认领" if agent_view["can_claim"] else "不可认领（" + ",".join(agent_view["reasons"]) + ")"
            print(f"[{row['priority']}] {row['title']}")
            print(f"  scope: {', '.join(row['claim_scope']) or '[]'}")
            print(f"  wait: {row['pool_wait_minutes']}m")
            print(
                f"  {agent_filter}: {state} | busy_level={agent_view['busy_level']} | "
                f"execute={agent_view['busy_execute_route']} | remind={agent_view['busy_remind_route']}"
            )
            if agent_view["busy_level"] != "idle":
                print(f"  non-interrupt: {agent_view['busy_primary_reason']} / {', '.join(agent_view['busy_reason_codes']) or 'idle'}")
            print(f"  next: {row['next_action']}")
            print()
        else:
            print(f"[{row['priority']}] {row['title']}")
            print(f"  scope: {', '.join(row['claim_scope']) or '[]'}")
            print(f"  wait: {row['pool_wait_minutes']}m")
            if row["eligible_agents"]:
                candidates = []
                for item in row["by_agent"]:
                    mark = "可认领" if item["can_claim"] else "不可认领"
                    candidates.append(
                        f"{item['agent_id']}[{mark}|busy_level={item['busy_level']}|execute={item['busy_execute_route']}|remind={item['busy_remind_route']}]"
                    )
                print(f"  candidates: {'; '.join(candidates)}")
            else:
                print(f"  blocked: {', '.join(row['blocked_reasons']) or 'no_eligible_agent'}")
            print(f"  next: {row['next_action']}")
            print()


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only pooled task view")
    parser.add_argument("--tasks-root", default=str(Path.home() / "Desktop/work/my-agent-teams/tasks"))
    parser.add_argument("--config", default=str(Path.home() / "Desktop/work/my-agent-teams/config.json"))
    parser.add_argument("--agent", default="")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--summary-json", action="store_true")
    parser.add_argument("--blocked-only", action="store_true")
    parser.add_argument("--explain", default="")
    args = parser.parse_args()

    tasks_root = Path(args.tasks_root).expanduser().resolve()
    config_path = Path(args.config).expanduser().resolve()
    config = load_json(config_path)
    agents = config.get("agents") or {}
    default_concurrency = int((config.get("task_pool") or {}).get("default_claim_max_concurrency", 1))
    task_records = load_task_records(tasks_root)
    active_by_agent = active_tasks_by_agent(task_records)
    now = datetime.now().astimezone()
    pool_agents = sorted(agent_id for agent_id, payload in agents.items() if is_pool_agent(agent_id, payload or {}))
    busy_map = {agent_id: load_agent_busy_diagnostic(agent_id, tasks_root, config_path) for agent_id in pool_agents}

    rows = []
    for task_dir, task in task_records:
        if str(task.get("status") or "") != "pooled":
            continue
        rows.append(build_row(task_dir, task, agents, active_by_agent, busy_map, tasks_root, default_concurrency, now, config))
    rows.sort(key=lambda row: (-PRIORITY_RANK.get(row["priority"], 0), -row["pool_wait_minutes"], row["task_id"]))
    summary = build_summary(rows, agents, active_by_agent, tasks_root, busy_map)

    if args.explain:
        rows = [row for row in rows if row["task_id"] == args.explain]
    if args.agent:
        rows = [row for row in rows if args.agent in row["claim_scope"] or not row["claim_scope"]]
    if args.blocked_only:
        rows = [row for row in rows if not row["eligible_agents"]]

    if args.summary_json:
        print(json.dumps({"summary": summary, "items": rows}, ensure_ascii=False, indent=2))
    elif args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
    else:
        human_print(rows, args.agent or None, summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
