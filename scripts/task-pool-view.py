#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

PRIORITY_RANK = {"critical": 4, "urgent": 4, "high": 3, "medium": 2, "low": 1}


def parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        return None


def age_minutes(value: str | None, now: datetime) -> int:
    dt = parse_iso(value)
    if not dt:
        return 0
    return max(0, int((now - dt).total_seconds() // 60))


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


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


def active_tasks_by_agent(tasks_root: Path) -> dict[str, list[dict]]:
    result: dict[str, list[dict]] = {}
    for task_path in tasks_root.glob("*/task.json"):
        try:
            payload = load_json(task_path)
        except Exception:
            continue
        if str(payload.get("status") or "") not in {"dispatched", "working"}:
            continue
        agent = str(payload.get("assigned_agent") or "").strip()
        if not agent:
            continue
        result.setdefault(agent, []).append({"id": payload.get("id") or task_path.parent.name, "task": payload})
    return result


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


def scope_conflicts(task: dict, agent_id: str, active_by_agent: dict[str, list[dict]]) -> list[str]:
    target_scope = [str(item).strip() for item in (task.get("write_scope") or []) if str(item).strip()]
    if not target_scope:
        return []
    resolved_target = [Path(item).expanduser().resolve() for item in target_scope]
    conflicts: list[str] = []
    for payload in active_by_agent.get(agent_id, []):
        other_task = payload["task"]
        for raw in other_task.get("write_scope") or []:
            if not str(raw).strip():
                continue
            other = Path(str(raw).strip()).expanduser().resolve()
            for target in resolved_target:
                if scopes_overlap(target, other):
                    conflicts.append(f"write_scope_conflict:{payload['id']}:{raw}")
                    break
    return conflicts


def agent_acceptance(task: dict, agent_id: str, agents: dict[str, dict], active_by_agent: dict[str, list[dict]], tasks_root: Path, default_concurrency: int) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    claim_scope = default_claim_scope(task, agents)
    if claim_scope and agent_id not in claim_scope:
        reasons.append("not_in_claim_scope")
    reasons.extend(dependency_blockers(task, tasks_root))
    reasons.extend(scope_conflicts(task, agent_id, active_by_agent))
    active = active_by_agent.get(agent_id, [])
    working_count = sum(1 for item in active if str(item["task"].get("status") or "") == "working")
    if working_count > 0:
        reasons.append("agent_has_working_task")
    max_concurrency = int(task.get("claim_max_concurrency") or default_concurrency or 1)
    role = str((agents.get(agent_id) or {}).get("role") or "").strip().lower()
    role_limits = {
        "fullstack_dev": "dev",
        "reviewer": "reviewer",
        "qa": "qa",
        "architect": "architect",
        "pm": "pm-chief",
    }
    wip_limits = task.get("__wip_limits__") or {}
    mapped = role_limits.get(role, agent_id if agent_id in wip_limits else '')
    role_limit = wip_limits.get(agent_id)
    if role_limit is None and mapped:
        role_limit = wip_limits.get(mapped)
    if role_limit not in (None, ''):
        max_concurrency = min(max_concurrency, int(role_limit))
    if len(active) >= max_concurrency:
        reasons.append(f"claim_max_concurrency_reached:{max_concurrency}")
    return not reasons, reasons


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


def build_row(task_dir: Path, task: dict, agents: dict[str, dict], active_by_agent: dict[str, list[dict]], tasks_root: Path, default_concurrency: int, now: datetime) -> dict:
    scope = default_claim_scope(task, agents)
    by_agent = []
    eligible = []
    blocked_reasons: set[str] = set()
    for agent_id in scope:
        can_claim, reasons = agent_acceptance(task, agent_id, agents, active_by_agent, tasks_root, default_concurrency)
        by_agent.append({"agent_id": agent_id, "can_claim": can_claim, "reasons": reasons})
        if can_claim:
            eligible.append(agent_id)
        else:
            blocked_reasons.update(reasons)
    wait = age_minutes(str(task.get("pool_entered_at") or task.get("created_at") or ""), now)
    priority = str(task.get("priority") or "medium").strip().lower()
    if eligible:
        next_action = f"{eligible[0]} 可认领，等待自动续推或手动 claim"
    elif blocked_reasons:
        next_action = "不可认领，需处理：" + ",".join(sorted(blocked_reasons))
    else:
        next_action = "无 claim_scope，需 PM 补齐"
    return {
        "task_id": str(task.get("id") or task_dir.name),
        "title": str(task.get("title") or task_dir.name),
        "priority": priority,
        "pool_wait_minutes": wait,
        "pool_timeout_minutes": int(task.get("pool_timeout_minutes") or 0),
        "claim_scope": scope,
        "eligible_agents": eligible,
        "by_agent": by_agent,
        "blocked_reasons": sorted(blocked_reasons),
        "next_action": next_action,
        "task_dir": str(task_dir),
    }


def human_print(rows: list[dict], agent_filter: str | None) -> None:
    pooled = len(rows)
    blocked = sum(1 for row in rows if not row["eligible_agents"])
    timed_out = sum(
        1
        for row in rows
        if int(row.get("pool_timeout_minutes") or 0) > 0 and int(row.get("pool_wait_minutes") or 0) > int(row.get("pool_timeout_minutes") or 0)
    )
    print(f"任务池 | 可认领 {pooled - blocked} | 阻塞 {blocked} | 超时 {timed_out}")
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
            print(f"  {agent_filter}: {state}")
            print(f"  next: {row['next_action']}")
            print()
        else:
            print(f"[{row['priority']}] {row['title']}")
            print(f"  scope: {', '.join(row['claim_scope']) or '[]'}")
            print(f"  wait: {row['pool_wait_minutes']}m")
            if row["eligible_agents"]:
                print(f"  candidates: {', '.join(row['eligible_agents'])}")
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
    parser.add_argument("--blocked-only", action="store_true")
    parser.add_argument("--explain", default="")
    args = parser.parse_args()

    tasks_root = Path(args.tasks_root).expanduser().resolve()
    config = load_json(Path(args.config).expanduser().resolve())
    agents = config.get("agents") or {}
    default_concurrency = int((config.get("task_pool") or {}).get("default_claim_max_concurrency", 1))
    wip_limits = config.get("wip_limits") or {}
    active_by_agent = active_tasks_by_agent(tasks_root)
    now = datetime.now().astimezone()

    rows = []
    for task_dir, task in pooled_tasks(tasks_root):
        task["__wip_limits__"] = wip_limits
        rows.append(build_row(task_dir, task, agents, active_by_agent, tasks_root, default_concurrency, now))
    rows.sort(key=lambda row: (-PRIORITY_RANK.get(row["priority"], 0), -row["pool_wait_minutes"], row["task_id"]))

    if args.explain:
        rows = [row for row in rows if row["task_id"] == args.explain]
    if args.agent:
        rows = [row for row in rows if args.agent in row["claim_scope"] or not row["claim_scope"]]
    if args.blocked_only:
        rows = [row for row in rows if not row["eligible_agents"]]

    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
    else:
        human_print(rows, args.agent or None)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
