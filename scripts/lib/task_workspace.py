from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any


TERMINAL_INTEGRATION_STATES = {"done", "merged", "archived", "cancelled", "failed", "timeout"}


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def parse_bool(value: Any) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", delete=False, dir=str(path.parent), encoding="utf-8") as tmp:
        json.dump(payload, tmp, ensure_ascii=False, indent=2)
        tmp.write("\n")
    os.replace(tmp.name, path)


def _workspace_root(config: dict[str, Any], config_path: Path) -> Path:
    explicit = str(config.get("workspace_root") or "").strip()
    if explicit:
        return Path(explicit).expanduser().resolve()
    return config_path.resolve().parent


def _task_slug(task_id: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9._-]+", "-", str(task_id or "").strip()).strip("-._")
    digest = hashlib.sha1(str(task_id or "task").encode("utf-8")).hexdigest()[:8]
    if not normalized:
        normalized = "task"
    return f"{normalized[:40]}-{digest}"


def _branch_slug(task_id: str) -> str:
    return f"task/{_task_slug(task_id)}"


def _run_git(cwd: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(cwd), *args],
        capture_output=True,
        text=True,
        check=check,
    )


def _repo_root(dev_root: Path) -> Path:
    completed = _run_git(dev_root, "rev-parse", "--show-toplevel")
    return Path(completed.stdout.strip()).resolve()


def _current_branch(cwd: Path) -> str | None:
    completed = _run_git(cwd, "rev-parse", "--abbrev-ref", "HEAD", check=False)
    if completed.returncode != 0:
        return None
    branch = completed.stdout.strip()
    return branch or None


def _ref_exists(repo_root: Path, ref: str) -> bool:
    completed = _run_git(repo_root, "show-ref", "--verify", "--quiet", ref, check=False)
    return completed.returncode == 0


def _resolve_base_ref(repo_root: Path, target_branch: str | None) -> str:
    candidate = str(target_branch or "").strip()
    if candidate:
        if _ref_exists(repo_root, f"refs/heads/{candidate}"):
            return candidate
        if _ref_exists(repo_root, f"refs/remotes/origin/{candidate}"):
            return f"origin/{candidate}"
    return "HEAD"


def _parse_worktree_list(repo_root: Path) -> list[dict[str, str]]:
    completed = _run_git(repo_root, "worktree", "list", "--porcelain", check=False)
    if completed.returncode != 0:
        return []
    entries: list[dict[str, str]] = []
    current: dict[str, str] = {}
    for raw_line in completed.stdout.splitlines():
        line = raw_line.strip()
        if not line:
            if current:
                entries.append(current)
                current = {}
            continue
        key, _, value = line.partition(" ")
        if key == "worktree":
            current["path"] = value.strip()
        elif key == "branch":
            branch = value.strip()
            if branch.startswith("refs/heads/"):
                branch = branch[len("refs/heads/"):]
            current["branch"] = branch
        elif key == "HEAD":
            current["head"] = value.strip()
    if current:
        entries.append(current)
    return entries


def _existing_worktree_for_branch(repo_root: Path, branch: str) -> Path | None:
    for entry in _parse_worktree_list(repo_root):
        if entry.get("branch") == branch and entry.get("path"):
            return Path(entry["path"]).expanduser().resolve()
    return None


def _active_workspace_path(task: dict[str, Any], dev_root: Path) -> Path:
    candidate = str(task.get("workspace_path") or task.get("worktree_path") or "").strip()
    if candidate:
        return Path(candidate).expanduser().resolve()
    return dev_root


def _default_patch_path(task_dir: Path, task_id: str) -> Path:
    slug = _task_slug(task_id)
    return (task_dir / "artifacts" / f"{slug}.patch").resolve()


def _ensure_patch_artifact(task: dict[str, Any], task_dir: Path, patch_path: Path) -> list[dict[str, Any]]:
    existing = task.get("artifacts") if isinstance(task.get("artifacts"), list) else []
    artifacts: list[dict[str, Any]] = [item for item in existing if isinstance(item, dict)]
    normalized_path = str(patch_path)
    if not any(str(item.get("type") or "") == "patch" and str(item.get("path") or "") == normalized_path for item in artifacts):
        artifacts.append({
            "type": "patch",
            "path": normalized_path,
            "description": "任务 worktree/branch 的补丁快照",
        })
    return artifacts


def task_requires_worktree(task: dict[str, Any]) -> bool:
    workspace_mode = str(task.get("workspace_mode") or "main").strip().lower()
    execution_mode = str(task.get("execution_mode") or "").strip().lower()
    target_environment = str(task.get("target_environment") or "").strip().lower()
    read_only = parse_bool(task.get("read_only"))
    write_scope = task.get("write_scope") if isinstance(task.get("write_scope"), list) else []
    return (
        workspace_mode == "worktree"
        and execution_mode == "dev"
        and target_environment == "dev"
        and not read_only
        and any(str(item).strip() for item in write_scope)
    )


def derive_workspace_plan(task: dict[str, Any], *, task_dir: Path, config: dict[str, Any], config_path: Path) -> dict[str, Any]:
    project = str(task.get("project") or "").strip()
    projects = config.get("projects") or {}
    if project not in projects:
        raise ValueError(f"unknown project: {project}")

    project_cfg = projects[project]
    dev_root = Path(project_cfg["dev_root"]).expanduser().resolve()
    workspace_mode = str(task.get("workspace_mode") or (config.get("defaults") or {}).get("workspace_mode") or "main").strip().lower()
    target_branch = str(task.get("target_branch") or (config.get("defaults") or {}).get("target_branch") or "").strip() or None
    task_id = str(task.get("id") or task_dir.name)

    if not task_requires_worktree(task):
        try:
            repo_root = _repo_root(dev_root)
            current_branch = _current_branch(dev_root)
        except Exception:
            repo_root = dev_root
            current_branch = None
        workspace_path = dev_root
        branch = current_branch
        status = "main" if workspace_mode == "main" else "not_applicable"
        hint = f"默认主工作区：{workspace_path}"
        if branch:
            hint += f"（branch: {branch}）"
        return {
            "workspace_mode": workspace_mode,
            "workspace_status": status,
            "workspace_root": str(repo_root),
            "workspace_path": str(workspace_path),
            "worktree_path": None,
            "workspace_branch": branch,
            "workspace_base_ref": _resolve_base_ref(repo_root, target_branch or current_branch),
            "patch_path": str(_default_patch_path(task_dir, task_id)),
            "workspace_error": None,
            "workspace_prepared_at": None,
            "dispatch_hint": hint,
            "integration_target_branch": target_branch or current_branch,
        }

    repo_root = _repo_root(dev_root)
    current_branch = _current_branch(dev_root)
    base_ref = _resolve_base_ref(repo_root, target_branch)
    worktree_root_raw = (
        ((config.get("workspace_management") or {}).get("worktree_root"))
        or config.get("worktree_root")
        or str(_workspace_root(config, config_path) / ".runtime" / "worktrees")
    )
    worktree_root = Path(str(worktree_root_raw)).expanduser().resolve() / project
    desired_path = Path(str(task.get("worktree_path") or "")).expanduser().resolve() if str(task.get("worktree_path") or "").strip() else (worktree_root / _task_slug(task_id))
    branch = str(task.get("workspace_branch") or "").strip() or _branch_slug(task_id)
    patch_path = Path(str(task.get("patch_path") or "")).expanduser().resolve() if str(task.get("patch_path") or "").strip() else _default_patch_path(task_dir, task_id)
    existing_path = _existing_worktree_for_branch(repo_root, branch)
    active_path = existing_path or desired_path

    return {
        "workspace_mode": workspace_mode,
        "workspace_status": "pending",
        "workspace_root": str(repo_root),
        "workspace_path": str(active_path),
        "worktree_path": str(active_path),
        "workspace_branch": branch,
        "workspace_base_ref": base_ref,
        "patch_path": str(patch_path),
        "workspace_error": None,
        "workspace_prepared_at": None,
        "dispatch_hint": f"请在 {active_path} 工作（branch: {branch}，目标基线: {base_ref}）",
        "integration_target_branch": target_branch or current_branch,
    }


def ensure_task_workspace(task_dir: Path, config_path: Path) -> dict[str, Any]:
    task_path = task_dir / "task.json"
    task = load_json(task_path)
    config = load_json(config_path)
    task_id = str(task.get("id") or task_dir.name)

    try:
        plan = derive_workspace_plan(task, task_dir=task_dir, config=config, config_path=config_path)
        desired_worktree = str(plan.get("worktree_path") or "").strip()
        if plan["workspace_status"] == "pending" and desired_worktree:
            repo_root = Path(str(plan["workspace_root"])).resolve()
            branch = str(plan["workspace_branch"] or "").strip()
            worktree_path = Path(desired_worktree).resolve()
            patch_path = Path(str(plan["patch_path"])).resolve()
            worktree_path.parent.mkdir(parents=True, exist_ok=True)
            patch_path.parent.mkdir(parents=True, exist_ok=True)
            if not (worktree_path / ".git").exists():
                existing_path = _existing_worktree_for_branch(repo_root, branch)
                if existing_path and existing_path != worktree_path:
                    worktree_path = existing_path
                else:
                    if _ref_exists(repo_root, f"refs/heads/{branch}"):
                        _run_git(repo_root, "worktree", "add", "--force", str(worktree_path), branch)
                    else:
                        _run_git(repo_root, "worktree", "add", "--force", "-b", branch, str(worktree_path), str(plan["workspace_base_ref"]))
            actual_branch = _current_branch(worktree_path) or branch
            plan["workspace_status"] = "prepared"
            plan["workspace_path"] = str(worktree_path)
            plan["worktree_path"] = str(worktree_path)
            plan["workspace_branch"] = actual_branch
            plan["workspace_prepared_at"] = now_iso()
            plan["dispatch_hint"] = (
                f"请在 {worktree_path} 工作（branch: {actual_branch}，目标分支: {plan.get('integration_target_branch') or plan.get('workspace_base_ref') or 'HEAD'}）。"
                f" 补丁建议输出到 {plan['patch_path']}。"
            )
        else:
            plan.setdefault("workspace_prepared_at", None)
    except Exception as exc:
        config = load_json(config_path)
        project_cfg = (config.get("projects") or {}).get(str(task.get("project") or ""), {})
        fallback_root = Path(str(project_cfg.get("dev_root") or task_dir.parent.parent)).expanduser().resolve()
        target_branch = str(task.get("target_branch") or (config.get("defaults") or {}).get("target_branch") or "").strip() or None
        current_branch = _current_branch(fallback_root)
        patch_path = str(task.get("patch_path") or _default_patch_path(task_dir, task_id))
        plan = {
            "workspace_mode": str(task.get("workspace_mode") or "main").strip().lower(),
            "workspace_status": "error",
            "workspace_root": str(fallback_root),
            "workspace_path": str(fallback_root),
            "worktree_path": str(task.get("worktree_path") or "") or None,
            "workspace_branch": str(task.get("workspace_branch") or "") or current_branch,
            "workspace_base_ref": str(task.get("workspace_base_ref") or target_branch or current_branch or ""),
            "patch_path": patch_path,
            "workspace_error": str(exc),
            "workspace_prepared_at": None,
            "dispatch_hint": f"worktree 准备失败，临时回退主工作区 {fallback_root}。原因：{exc}",
            "integration_target_branch": target_branch or current_branch,
        }

    updated_task = dict(task)
    for key, value in plan.items():
        if key == "dispatch_hint":
            continue
        updated_task[key] = value
    updated_task["artifacts"] = _ensure_patch_artifact(updated_task, task_dir, Path(str(plan["patch_path"])))
    if updated_task != task:
        updated_task["updated_at"] = now_iso()
        atomic_write_json(task_path, updated_task)
    return {
        "task_id": task_id,
        "changed": updated_task != task,
        "workspace_mode": plan.get("workspace_mode"),
        "workspace_status": plan.get("workspace_status"),
        "workspace_path": plan.get("workspace_path"),
        "worktree_path": plan.get("worktree_path"),
        "workspace_branch": plan.get("workspace_branch"),
        "workspace_base_ref": plan.get("workspace_base_ref"),
        "patch_path": plan.get("patch_path"),
        "workspace_error": plan.get("workspace_error"),
        "integration_target_branch": plan.get("integration_target_branch"),
        "dispatch_hint": plan.get("dispatch_hint"),
    }


def derive_integration_queue_item(task: dict[str, Any]) -> dict[str, Any]:
    current_status = str(task.get("current_status") or task.get("status") or "").strip()
    read_only = parse_bool(task.get("read_only"))
    workspace_status = str(task.get("workspace_status") or "").strip()
    branch = str(task.get("workspace_branch") or "").strip()
    patch_path = str(task.get("patch_path") or "").strip()
    patch_exists = bool(patch_path and Path(patch_path).exists())
    worktree_path = str(task.get("worktree_path") or task.get("workspace_path") or "").strip()
    target_branch = str(task.get("integration_target_branch") or task.get("target_branch") or "").strip()
    control_plane_state = str(task.get("control_plane_state") or "").strip()

    if read_only:
        state = "not_applicable"
    elif workspace_status == "error":
        state = "workspace_error"
    elif current_status == "ready_for_merge":
        state = "queued" if branch or patch_exists else "metadata_missing"
    elif current_status == "blocked":
        state = "blocked"
    elif current_status == "done":
        state = "accepted"
    elif current_status in {"merged", "archived"}:
        state = "merged"
    elif current_status in {"working", "dispatched"} and (branch or worktree_path):
        state = "in_progress"
    elif current_status in TERMINAL_INTEGRATION_STATES:
        state = "closed"
    else:
        state = "pending"

    artifact_state = "branch+patch" if branch and patch_exists else "branch_only" if branch else "patch_only" if patch_exists else "missing"
    blocker = (
        str(task.get("workspace_error") or "").strip()
        or str(task.get("patch_capture_error") or "").strip()
        or ("缺少 branch/patch 元数据" if state == "metadata_missing" else "")
        or (f"控制面异常: {control_plane_state}" if control_plane_state and control_plane_state not in {"", "reassigned"} else "")
    )
    entered_at = (
        str(task.get("integration_queue_entered_at") or "").strip()
        or (str(task.get("completed_at") or "").strip() if state in {"queued", "metadata_missing"} else "")
        or (str(task.get("current_status_at") or "").strip() if state in {"accepted", "merged", "blocked", "workspace_error"} else "")
    )
    include = state in {"queued", "metadata_missing", "workspace_error", "accepted", "merged", "blocked", "in_progress"}
    return {
        "state": state,
        "include": include,
        "entered_at": entered_at or None,
        "workspace_status": workspace_status or None,
        "workspace_path": str(task.get("workspace_path") or "").strip() or None,
        "worktree_path": worktree_path or None,
        "workspace_branch": branch or None,
        "patch_path": patch_path or None,
        "patch_exists": patch_exists,
        "target_branch": target_branch or None,
        "artifact_state": artifact_state,
        "blocker": blocker or None,
        "control_plane_state": control_plane_state or None,
    }
