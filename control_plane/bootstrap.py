from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlparse

from .errors import ControlPlaneError, UnsafePath
from .models import is_relative_to, resolve_path

MANAGED_DIR = ".my-agent-teams"
MANIFEST_NAME = "control-plane.json"
AGENTS_REFERENCE = "AGENTS.control-plane.md"
HOOK_NAME = "control-plane-event.py"
SKILL_NAME = "delivery-control-plane"
ROLES_NAME = "roles.json"
BEGIN_MARKER = "<!-- BEGIN my-agent-teams control-plane reference -->"
END_MARKER = "<!-- END my-agent-teams control-plane reference -->"


def _validate_repo_root(raw: str | Path) -> Path:
    root = resolve_path(raw)
    if not root.is_dir() or not (root / ".git").exists():
        raise UnsafePath(f"target is not a Git project: {root}")
    return root


def _resolve_agents_path(root: Path, agents_file: str) -> Path:
    path = (root / agents_file).resolve()
    if not is_relative_to(path, root):
        raise UnsafePath("agents file is outside repo root")
    return path


def _render_manifest(*, project_id: str, root: Path, control_plane_url: str, roles: Iterable[str]) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "project_id": project_id,
        "repo_root": str(root),
        "control_plane_url": control_plane_url,
        "roles": list(dict.fromkeys(str(role) for role in roles if str(role).strip())),
        "generated_by": "my-agent-teams",
        "managed_paths": [
            f"{MANAGED_DIR}/{MANIFEST_NAME}",
            f"{MANAGED_DIR}/{AGENTS_REFERENCE}",
            f"{MANAGED_DIR}/{ROLES_NAME}",
            f"{MANAGED_DIR}/hooks/{HOOK_NAME}",
            f"{MANAGED_DIR}/skills/{SKILL_NAME}/SKILL.md",
        ],
    }


def _render_agents_reference() -> str:
    return (
        f"# my-agent-teams 控制面接入引用\n\n"
        f"{BEGIN_MARKER}\n\n"
        f"本项目由 `{MANAGED_DIR}/{MANIFEST_NAME}` 控制面纳管。项目标识和控制面地址以该 manifest 为准。\n"
        "业务项目原有规则继续有效；本引用只增加：\n\n"
        "- 任务必须在本项目仓库或显式 worktree 中执行；\n"
        "- 状态上报只发送项目、任务、会话、阶段、心跳和交付物引用；\n"
        "- 没有可用的 Codex/App Server 能力时必须报告 `unknown` 或 `unsupported`；\n"
        "- 生产发布、凭据和外部付费操作仍需 Owner 明确授权。\n\n"
        f"Hook 入口：`{MANAGED_DIR}/hooks/{HOOK_NAME}`。\n\n"
        f"{END_MARKER}\n"
    )


def _render_skill() -> str:
    return (
        "# delivery-control-plane\n\n"
        "Use the registered project manifest as the source of truth for project_id and control-plane URL.\n"
        "Report only metadata, summaries, and artifact references. Never copy full transcripts or business source.\n"
    )


def _render_roles(roles: Iterable[str]) -> dict[str, Any]:
    role_names = list(dict.fromkeys(str(role) for role in roles if str(role).strip()))
    return {
        "schema_version": 1,
        "roles": [
            {"id": role, "session_status_source": "control_plane_event", "write_scope_source": "project_task"}
            for role in role_names
        ],
        "review_independence_required": True,
        "owner_decision_categories": ["scope_conflict", "resource_conflict", "production_release", "security_compliance", "repeated_gate_failure"],
    }


def _render_hook() -> str:
    return (
        "#!/usr/bin/env python3\n"
        "from __future__ import annotations\n\n"
        "import json\n"
        "import os\n"
        "import sys\n"
        "import urllib.request\n"
        "from pathlib import Path\n\n"
        "manifest = json.loads((Path(__file__).resolve().parents[1] / 'control-plane.json').read_text(encoding='utf-8'))\n"
        "raw = json.load(sys.stdin) if not sys.stdin.isatty() else {}\n"
        "allowed = {'session_id', 'event_type', 'idempotency_key', 'event_id', 'event_at', 'sequence', 'status', 'current_gate', 'last_error', 'source'}\n"
        "event = {key: raw[key] for key in allowed if key in raw}\n"
        "event['project_id'] = manifest['project_id']\n"
        "event['payload'] = {'summary': raw.get('summary'), 'artifact_refs': raw.get('artifact_refs', [])}\n"
        "event.setdefault('source', 'codex_hook')\n"
        "event.setdefault('idempotency_key', event.get('event_id') or f\"hook:{event.get('session_id', 'unknown')}:{event.get('event_type', 'event')}:{event.get('event_at', '')}\")\n"
        "url = manifest['control_plane_url'].rstrip('/') + '/api/control-plane/events'\n"
        "if event.get('session_id') and event.get('event_type'):\n"
        "    body = json.dumps(event, ensure_ascii=False).encode('utf-8')\n"
        "    request = urllib.request.Request(url, data=body, headers={'Content-Type': 'application/json'}, method='POST')\n"
        "    token = os.getenv('MY_AGENT_TEAMS_CONTROL_PLANE_TOKEN')\n"
        "    if token:\n"
        "        request.add_header('Authorization', 'Bearer ' + token)\n"
        "    try:\n"
        "        with urllib.request.urlopen(request, timeout=5) as response:\n"
        "            event['delivery_status'] = 'accepted' if response.status < 300 else 'rejected'\n"
        "    except Exception as exc:\n"
        "        event['delivery_status'] = 'unknown'\n"
        "        event['delivery_error'] = str(exc)\n"
        "print(json.dumps(event, ensure_ascii=False))\n"
    )


def _agents_block(manifest: dict[str, Any]) -> str:
    return "\n".join(
        [
            BEGIN_MARKER,
            "",
            f"Use project manifest `{MANAGED_DIR}/{MANIFEST_NAME}` for control-plane registration.",
            f"Project id: `{manifest['project_id']}`.",
            "Do not copy business source or full transcripts to the control plane.",
            "",
            END_MARKER,
        ]
    )


def _inspect_agents(root: Path, agents_file: str, manifest: dict[str, Any]) -> dict[str, Any]:
    path = _resolve_agents_path(root, agents_file)
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    has_begin = BEGIN_MARKER in existing
    has_end = END_MARKER in existing
    conflicts: list[str] = []
    if has_begin != has_end:
        conflicts.append("partial managed AGENTS marker")
    if has_begin and manifest["project_id"] not in existing:
        conflicts.append("managed marker belongs to another project")
    return {
        "path": str(path),
        "exists": path.exists(),
        "managed": has_begin and has_end,
        "conflicts": conflicts,
        "can_append": not conflicts,
    }


def check_bootstrap(*, repo_root: str, agents_file: str = "AGENTS.md") -> dict[str, Any]:
    root = _validate_repo_root(repo_root)
    agents_path = _resolve_agents_path(root, agents_file)
    managed = root / MANAGED_DIR
    manifest_path = managed / MANIFEST_NAME
    manifest: dict[str, Any] = {}
    errors: list[str] = []
    if not manifest_path.exists():
        errors.append("manifest_missing")
    else:
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            errors.append("manifest_invalid_json")
    if manifest:
        if manifest.get("project_id") in (None, ""):
            errors.append("manifest_project_id_missing")
        if resolve_path(str(manifest.get("repo_root") or root)) != root:
            errors.append("manifest_repo_root_mismatch")
        parsed_url = urlparse(str(manifest.get("control_plane_url") or ""))
        if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
            errors.append("manifest_control_plane_url_invalid")
    files = {
        str(path.relative_to(root)): path.exists()
        for path in (
            manifest_path,
            managed / AGENTS_REFERENCE,
            managed / ROLES_NAME,
            managed / "hooks" / HOOK_NAME,
            managed / "skills" / SKILL_NAME / "SKILL.md",
        )
    }
    agent_check = _inspect_agents(root, agents_file, manifest) if manifest else {
        "path": str(agents_path), "managed": False, "conflicts": [], "can_append": False
    }
    if manifest and not agent_check["managed"]:
        errors.append("agents_reference_missing")
    errors.extend(agent_check["conflicts"])
    return {
        "repo_root": str(root),
        "ok": not errors,
        "errors": errors,
        "manifest": manifest,
        "files": files,
        "agents": agent_check,
        "rollback": f"Remove only {MANAGED_DIR}/ generated paths and the marked AGENTS block after reviewing git diff.",
    }


def bootstrap_project(
    *,
    repo_root: str,
    project_id: str,
    control_plane_url: str,
    apply: bool = False,
    agents_file: str = "AGENTS.md",
    roles: Iterable[str] = (),
) -> dict[str, Any]:
    root = _validate_repo_root(repo_root)
    if not project_id.strip() or not control_plane_url.strip():
        raise ControlPlaneError("project_id and control_plane_url are required")
    agents_path = _resolve_agents_path(root, agents_file)
    parsed_url = urlparse(control_plane_url)
    if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
        raise ControlPlaneError("control_plane_url must be an http(s) URL")
    role_names = list(dict.fromkeys(str(role) for role in roles if str(role).strip()))
    manifest = _render_manifest(project_id=project_id, root=root, control_plane_url=control_plane_url, roles=role_names)
    managed = root / MANAGED_DIR
    agent_check = _inspect_agents(root, agents_file, manifest)
    conflicts = list(agent_check["conflicts"])
    existing_manifest_path = managed / MANIFEST_NAME
    if existing_manifest_path.exists():
        try:
            existing_manifest = json.loads(existing_manifest_path.read_text(encoding="utf-8"))
        except ValueError:
            conflicts.append("managed manifest is invalid JSON")
        else:
            if existing_manifest.get("project_id") != project_id:
                conflicts.append("managed manifest belongs to another project")
            if resolve_path(str(existing_manifest.get("repo_root") or root)) != root:
                conflicts.append("managed manifest repo_root does not match target")
    elif managed.exists():
        partial_paths = [
            managed / AGENTS_REFERENCE,
            managed / ROLES_NAME,
            managed / "hooks" / HOOK_NAME,
            managed / "skills" / SKILL_NAME / "SKILL.md",
        ]
        if any(path.exists() for path in partial_paths):
            conflicts.append("managed files exist without a valid manifest")
    preview = {
        "repo_root": str(root),
        "apply": apply,
        "conflicts": list(dict.fromkeys(conflicts)),
        "files_to_create": [
            f"{MANAGED_DIR}/{MANIFEST_NAME}",
            f"{MANAGED_DIR}/{AGENTS_REFERENCE}",
            f"{MANAGED_DIR}/{ROLES_NAME}",
            f"{MANAGED_DIR}/hooks/{HOOK_NAME}",
            f"{MANAGED_DIR}/skills/{SKILL_NAME}/SKILL.md",
        ],
        "agents_file": str(agents_path.relative_to(root)),
        "rollback": f"Back up and remove only {MANAGED_DIR}/ plus the marked AGENTS block after reviewing git diff.",
    }
    if conflicts:
        return {**preview, "ok": False, "error": "conflict_detected"}
    if not apply:
        return {**preview, "ok": True, "status": "preview"}
    managed.mkdir(parents=True, exist_ok=True)
    (managed / "hooks").mkdir(parents=True, exist_ok=True)
    skill_dir = managed / "skills" / SKILL_NAME
    skill_dir.mkdir(parents=True, exist_ok=True)
    (managed / MANIFEST_NAME).write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (managed / AGENTS_REFERENCE).write_text(_render_agents_reference(), encoding="utf-8")
    (managed / ROLES_NAME).write_text(json.dumps(_render_roles(role_names), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    hook = managed / "hooks" / HOOK_NAME
    hook.write_text(_render_hook(), encoding="utf-8")
    hook.chmod(0o755)
    (skill_dir / "SKILL.md").write_text(_render_skill(), encoding="utf-8")
    existing = agents_path.read_text(encoding="utf-8") if agents_path.exists() else ""
    if BEGIN_MARKER not in existing:
        separator = "\n" if existing and not existing.endswith("\n") else ""
        agents_path.write_text(existing + separator + "\n" + _agents_block(manifest) + "\n", encoding="utf-8")
    return {**preview, "status": "applied", "ok": True, "manifest": manifest}


def uninstall_project(*, repo_root: str, apply: bool = False, agents_file: str = "AGENTS.md") -> dict[str, Any]:
    root = _validate_repo_root(repo_root)
    managed = root / MANAGED_DIR
    agents_path = _resolve_agents_path(root, agents_file)
    targets = [
        managed / MANIFEST_NAME,
        managed / AGENTS_REFERENCE,
        managed / ROLES_NAME,
        managed / "hooks" / HOOK_NAME,
        managed / "skills" / SKILL_NAME / "SKILL.md",
    ]
    existing = agents_path.read_text(encoding="utf-8") if agents_path.exists() else ""
    start = existing.find(BEGIN_MARKER)
    end = existing.find(END_MARKER)
    has_block = start >= 0 and end >= start
    preview = {
        "repo_root": str(root),
        "apply": apply,
        "managed_paths": [str(path.relative_to(root)) for path in targets if path.exists()],
        "agents_block": has_block,
        "status": "preview" if not apply else "applied",
        "rollback": "Restore the backup created in the managed directory if uninstall was accidental.",
    }
    if not apply:
        return preview
    backup = managed / f".uninstall-backup-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    backup.mkdir(parents=True, exist_ok=True)
    for path in targets:
        if path.exists():
            destination = backup / path.relative_to(root)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(path), str(destination))
    if has_block:
        remainder = existing[:start].rstrip() + "\n" + existing[end + len(END_MARKER):].lstrip()
        agents_path.write_text(remainder, encoding="utf-8")
    return {**preview, "backup": str(backup)}
