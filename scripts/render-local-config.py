#!/usr/bin/env python3
"""Render a machine-local config.json from the tracked config skeleton.

This keeps team topology in config.json but rewrites machine-specific paths for
this checkout. It is intentionally conservative and does not touch secrets.
"""
from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path
from typing import Any


def rewrite_path(value: Any, *, old_workspace: str, workspace: Path, work_parent: Path, prod_parent: Path) -> Any:
    if not isinstance(value, str) or not value:
        return value
    expanded = value.replace("~", str(Path.home()), 1) if value.startswith("~/") else value
    if old_workspace and expanded.startswith(old_workspace):
        suffix = expanded[len(old_workspace):].lstrip("/")
        return str((workspace / suffix).resolve()) if suffix else str(workspace)
    if "/Desktop/work/my-agent-teams" in expanded:
        suffix = expanded.split("/Desktop/work/my-agent-teams", 1)[1].lstrip("/")
        return str((workspace / suffix).resolve()) if suffix else str(workspace)
    if expanded.endswith("/Desktop/work/chiralium") or "/Desktop/work/chiralium/" in expanded:
        suffix = expanded.split("/Desktop/work/chiralium", 1)[1].lstrip("/")
        base = work_parent / "chiralium"
        return str((base / suffix).resolve()) if suffix else str(base)
    if expanded.endswith("/Desktop/prod/chiralium") or "/Desktop/prod/chiralium/" in expanded:
        suffix = expanded.split("/Desktop/prod/chiralium", 1)[1].lstrip("/")
        base = prod_parent / "chiralium"
        return str((base / suffix).resolve()) if suffix else str(base)
    if expanded.endswith("/Desktop/prod/my-agent-teams") or "/Desktop/prod/my-agent-teams/" in expanded:
        suffix = expanded.split("/Desktop/prod/my-agent-teams", 1)[1].lstrip("/")
        base = prod_parent / "my-agent-teams"
        return str((base / suffix).resolve()) if suffix else str(base)
    return value


def recursive_rewrite(obj: Any, *, old_workspace: str, workspace: Path, work_parent: Path, prod_parent: Path) -> Any:
    if isinstance(obj, dict):
        return {
            key: recursive_rewrite(value, old_workspace=old_workspace, workspace=workspace, work_parent=work_parent, prod_parent=prod_parent)
            for key, value in obj.items()
        }
    if isinstance(obj, list):
        return [recursive_rewrite(item, old_workspace=old_workspace, workspace=workspace, work_parent=work_parent, prod_parent=prod_parent) for item in obj]
    return rewrite_path(obj, old_workspace=old_workspace, workspace=workspace, work_parent=work_parent, prod_parent=prod_parent)


def apply_canonical_paths(config: dict[str, Any], *, workspace: Path, work_parent: Path, prod_parent: Path) -> None:
    config["workspace_root"] = str(workspace)
    config["tasks_root"] = str(workspace / "tasks")
    config["prompts_root"] = str(workspace / "prompts")
    config["scripts_root"] = str(workspace / "scripts")
    config["agents_root"] = str(workspace / "agents")
    shared = config.setdefault("shared_paths", {})
    shared.update({
        "workspace_root": str(workspace),
        "agents_root": str(workspace / "agents"),
        "tasks_root": str(workspace / "tasks"),
        "scripts_root": str(workspace / "scripts"),
        "prompts_root": str(workspace / "prompts"),
        "config_path": str(workspace / "config.json"),
        "root_claude_path": str(workspace / "CLAUDE.md"),
        "root_agents_path": str(workspace / "AGENTS.md"),
    })
    notifications = config.setdefault("notifications", {})
    if notifications.get("push_script"):
        notifications["push_script"] = str(workspace / "scripts" / "feishu-push.sh")
    for agent_id, payload in (config.get("agents") or {}).items():
        if not isinstance(payload, dict):
            continue
        workdir = workspace / "agents" / agent_id
        payload["workdir"] = str(workdir)
        guidance = payload.get("guidance_file") or ("CLAUDE.md" if payload.get("runtime") == "claude_code" else "AGENT.md")
        payload["guidance_file"] = guidance
        payload["guidance_path"] = str(workdir / str(guidance))
    projects = config.setdefault("projects", {})
    if "my-agent-teams" in projects:
        projects["my-agent-teams"]["dev_root"] = str(workspace)
        projects["my-agent-teams"]["prod_root"] = str(prod_parent / "my-agent-teams")
    if "chiralium" in projects:
        chiralium_root = Path(os.environ.get("CHIRALIUM_DEV_ROOT", str(work_parent / "chiralium"))).expanduser().resolve()
        chiralium_prod = Path(os.environ.get("CHIRALIUM_PROD_ROOT", str(prod_parent / "chiralium"))).expanduser().resolve()
        projects["chiralium"]["dev_root"] = str(chiralium_root)
        projects["chiralium"]["prod_root"] = str(chiralium_prod)
        deploy_script = projects["chiralium"].get("deploy_script")
        if deploy_script:
            projects["chiralium"]["deploy_script"] = str(chiralium_root / "scripts" / "deploy.sh")


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", delete=False, dir=str(path.parent), encoding="utf-8") as tmp:
        json.dump(payload, tmp, ensure_ascii=False, indent=2)
        tmp.write("\n")
        tmp_path = Path(tmp.name)
    os.replace(tmp_path, path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default="config.json")
    parser.add_argument("--output", default="config.json")
    parser.add_argument("--workspace-root", default=None)
    parser.add_argument("--work-parent", default=None)
    parser.add_argument("--prod-parent", default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    input_path = Path(args.input).expanduser().resolve()
    workspace = Path(args.workspace_root).expanduser().resolve() if args.workspace_root else input_path.parent.resolve()
    work_parent = Path(args.work_parent).expanduser().resolve() if args.work_parent else workspace.parent.resolve()
    prod_parent = Path(args.prod_parent).expanduser().resolve() if args.prod_parent else (Path.home() / "Desktop" / "prod").resolve()
    output_path = Path(args.output).expanduser().resolve()

    config = json.loads(input_path.read_text(encoding="utf-8"))
    old_workspace = str(config.get("workspace_root") or "")
    rendered = recursive_rewrite(config, old_workspace=old_workspace, workspace=workspace, work_parent=work_parent, prod_parent=prod_parent)
    apply_canonical_paths(rendered, workspace=workspace, work_parent=work_parent, prod_parent=prod_parent)
    if args.dry_run:
        print(json.dumps(rendered, ensure_ascii=False, indent=2))
    else:
        atomic_write_json(output_path, rendered)
        print(f"rendered {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
