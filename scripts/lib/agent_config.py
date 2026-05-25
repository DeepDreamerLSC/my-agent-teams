#!/usr/bin/env python3
"""Small helpers for resolving agent metadata from config.json."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


FALLBACK_AGENTS: dict[str, dict[str, str]] = {
    "pm-chief": {"role": "pm", "tmux_session": "pm-chief"},
    "arch-1": {"role": "architect", "tmux_session": "arch-1"},
    "dev-1": {"role": "fullstack_dev", "tmux_session": "dev-1"},
    "dev-2": {"role": "fullstack_dev", "tmux_session": "dev-2"},
    "qa-1": {"role": "qa", "tmux_session": "qa-1"},
    "review-1": {"role": "reviewer", "tmux_session": "review-1"},
}

ROLE_LABELS = {
    "pm": "PM",
    "architect": "架构师",
    "fullstack_dev": "开发者",
    "developer": "开发者",
    "qa": "测试",
    "reviewer": "审查",
}

DAILY_ROLE_LABELS = {
    "pm": "🤵 PM",
    "architect": "🏗  架构",
    "fullstack_dev": "💻 开发",
    "developer": "💻 开发",
    "qa": "🧪 测试",
    "reviewer": "🔍 审查",
}

DEVELOPMENT_ROLES = {"fullstack_dev", "developer"}
QA_ROLES = {"qa"}
DESIGN_ROLES = {"architect"}
REVIEW_ROLES = {"reviewer"}
PM_ROLES = {"pm"}


def clean(value: Any) -> str:
    return "" if value is None else str(value).strip()


def load_config(path: str | Path) -> dict[str, Any]:
    config_path = Path(path).expanduser()
    if not config_path.exists():
        return {}
    try:
        payload = json.loads(config_path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def resolve_agent(config: dict[str, Any], target: str) -> tuple[str, dict[str, Any]]:
    target = clean(target)
    agents = config.get("agents") or {}
    if isinstance(agents, dict):
        payload = agents.get(target)
        if isinstance(payload, dict):
            return target, payload
        for agent_id, metadata in agents.items():
            if not isinstance(metadata, dict):
                continue
            if clean(metadata.get("tmux_session")) == target:
                return clean(agent_id), metadata
    return target, {}


def agent_metadata(config: dict[str, Any]) -> dict[str, dict[str, Any]]:
    agents = config.get("agents") or {}
    if isinstance(agents, dict) and agents:
        return {clean(agent_id): payload for agent_id, payload in agents.items() if clean(agent_id) and isinstance(payload, dict)}
    return dict(FALLBACK_AGENTS)


def role_label(payload: dict[str, Any], *, style: str = "plain") -> str:
    role = clean(payload.get("role"))
    labels = DAILY_ROLE_LABELS if style == "daily" else ROLE_LABELS
    return labels.get(role, role)


def role_labels(config: dict[str, Any], *, style: str = "plain", include_id: bool = False) -> dict[str, str]:
    labels = {}
    for agent_id, payload in agent_metadata(config).items():
        label = role_label(payload, style=style) or agent_id
        labels[agent_id] = f"{label} {agent_id}" if include_id else label
    return labels


def unique_preserve(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        value = clean(value)
        if not value or value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def _role_or_legacy_prefix_matches(agent_id: str, payload: dict[str, Any], roles: set[str], prefixes: tuple[str, ...]) -> bool:
    role = clean(payload.get("role")).lower()
    return role in roles or agent_id.startswith(prefixes)


def default_claim_scope(task: dict[str, Any], config: dict[str, Any]) -> list[str]:
    existing = task.get("claim_scope")
    if isinstance(existing, list) and existing:
        return unique_preserve([clean(item) for item in existing])

    task_type = clean(task.get("task_type")).lower()
    domain = clean(task.get("domain")).lower()
    candidates: list[str] = []
    for agent_id, payload in agent_metadata(config).items():
        if task_type in {"development", "investigation"}:
            if _role_or_legacy_prefix_matches(agent_id, payload, DEVELOPMENT_ROLES, ("dev-",)):
                candidates.append(agent_id)
        elif task_type == "verification" or domain == "quality":
            if _role_or_legacy_prefix_matches(agent_id, payload, QA_ROLES, ("qa-",)):
                candidates.append(agent_id)
        elif task_type == "design":
            if _role_or_legacy_prefix_matches(agent_id, payload, DESIGN_ROLES, ("arch-",)):
                candidates.append(agent_id)
    return unique_preserve(candidates)


def agent_ids_by_role_or_prefix(config: dict[str, Any], roles: set[str], prefixes: tuple[str, ...]) -> list[str]:
    candidates: list[str] = []
    for agent_id, payload in agent_metadata(config).items():
        if _role_or_legacy_prefix_matches(agent_id, payload, roles, prefixes):
            candidates.append(agent_id)
    return unique_preserve(candidates)


def development_agent_ids(config: dict[str, Any]) -> list[str]:
    return agent_ids_by_role_or_prefix(config, DEVELOPMENT_ROLES, ("dev-",))


def review_agent_ids(config: dict[str, Any]) -> list[str]:
    return agent_ids_by_role_or_prefix(config, REVIEW_ROLES | DESIGN_ROLES, ("review-", "arch-"))


def qa_agent_ids(config: dict[str, Any]) -> list[str]:
    return agent_ids_by_role_or_prefix(config, QA_ROLES, ("qa-",))


def pool_agent_ids(config: dict[str, Any]) -> list[str]:
    candidates: list[str] = []
    pool_roles = DEVELOPMENT_ROLES | QA_ROLES | DESIGN_ROLES | REVIEW_ROLES
    for agent_id, payload in agent_metadata(config).items():
        role = clean(payload.get("role")).lower()
        if role in PM_ROLES or agent_id.startswith("pm-"):
            continue
        if _role_or_legacy_prefix_matches(agent_id, payload, pool_roles, ("dev-", "qa-", "arch-", "review-")):
            candidates.append(agent_id)
    return unique_preserve(candidates)


def root_pm(config: dict[str, Any]) -> str:
    configured = clean((config.get("orchestration") or {}).get("root_pm"))
    if configured:
        return configured
    for agent_id, payload in agent_metadata(config).items():
        if clean(payload.get("role")) == "pm":
            return agent_id
    return next(iter(agent_metadata(config)), "")


def _first_agent_id(config: dict[str, Any], roles: set[str], prefixes: tuple[str, ...], fallback: str = "") -> str:
    ids = agent_ids_by_role_or_prefix(config, roles, prefixes)
    return ids[0] if ids else fallback


def integration_owner(config: dict[str, Any]) -> str:
    configured = clean((config.get("orchestration") or {}).get("integration_owner"))
    if configured:
        return configured
    return _first_agent_id(config, DESIGN_ROLES, ("arch-",), "arch-1")


def default_reviewer(config: dict[str, Any], domain: str = "") -> str:
    policies = config.get("domain_policies") or {}
    domain = clean(domain)
    for key in (domain, "development"):
        policy = policies.get(key) if isinstance(policies, dict) else None
        if isinstance(policy, dict):
            reviewer = clean(policy.get("default_reviewer"))
            if reviewer:
                return reviewer
    reviewer = _first_agent_id(config, REVIEW_ROLES, ("review-",), "")
    return reviewer or integration_owner(config)


def default_reviewers(config: dict[str, Any], domain: str = "", review_level: str = "standard") -> list[str]:
    primary = default_reviewer(config, domain)
    if clean(review_level).lower() == "complex":
        return unique_preserve([primary, integration_owner(config)])
    return unique_preserve([primary])


def default_tester(config: dict[str, Any], domain: str = "") -> str:
    policies = config.get("domain_policies") or {}
    domain = clean(domain)
    for key in (domain, "development"):
        policy = policies.get(key) if isinstance(policies, dict) else None
        if isinstance(policy, dict):
            tester = clean(policy.get("default_tester"))
            if tester:
                return tester
    return _first_agent_id(config, QA_ROLES, ("qa-",), "qa-1")


def resolve_session(config: dict[str, Any], target: str) -> str:
    agent_id, payload = resolve_agent(config, target)
    return clean(payload.get("tmux_session")) or agent_id


def resolve_runtime(config: dict[str, Any], target: str) -> str:
    _, payload = resolve_agent(config, target)
    return clean(payload.get("runtime")) or "unknown"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        choices=[
            "resolve-session",
            "resolve-runtime",
            "resolve-target",
            "list-agent-ids",
            "list-dev-agent-ids",
            "list-review-agent-ids",
            "list-qa-agent-ids",
            "list-pool-agent-ids",
            "default-reviewer",
            "default-reviewers",
            "default-tester",
            "integration-owner",
            "role-labels-json",
            "root-pm",
        ],
    )
    parser.add_argument("target", nargs="?")
    parser.add_argument("--config", default="config.json")
    parser.add_argument("--domain", default="")
    parser.add_argument("--review-level", default="standard")
    parser.add_argument("--style", choices=["plain", "daily"], default="plain")
    parser.add_argument("--include-id", action="store_true")
    args = parser.parse_args()

    config = load_config(args.config)
    if args.command == "list-agent-ids":
        print(",".join(agent_metadata(config)))
        return 0
    if args.command == "list-dev-agent-ids":
        print("\n".join(development_agent_ids(config)))
        return 0
    if args.command == "list-review-agent-ids":
        print("\n".join(review_agent_ids(config)))
        return 0
    if args.command == "list-qa-agent-ids":
        print("\n".join(qa_agent_ids(config)))
        return 0
    if args.command == "list-pool-agent-ids":
        print("\n".join(pool_agent_ids(config)))
        return 0
    if args.command == "default-reviewer":
        print(default_reviewer(config, args.domain))
        return 0
    if args.command == "default-reviewers":
        print("\n".join(default_reviewers(config, args.domain, args.review_level)))
        return 0
    if args.command == "default-tester":
        print(default_tester(config, args.domain))
        return 0
    if args.command == "integration-owner":
        print(integration_owner(config))
        return 0
    if args.command == "role-labels-json":
        print(json.dumps(role_labels(config, style=args.style, include_id=args.include_id), ensure_ascii=False))
        return 0
    if args.command == "root-pm":
        print(root_pm(config))
        return 0
    if not args.target:
        parser.error(f"{args.command} requires target")
    agent_id, payload = resolve_agent(config, args.target)
    session = clean(payload.get("tmux_session")) or agent_id
    runtime = clean(payload.get("runtime")) or "unknown"
    if args.command == "resolve-session":
        print(session)
    elif args.command == "resolve-runtime":
        print(runtime)
    else:
        print("\t".join([agent_id, session, runtime]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
