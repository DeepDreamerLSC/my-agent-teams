#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
WORKSPACE_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(SCRIPT_DIR / "lib"))
import task_artifacts  # type: ignore


class IntegrationError(RuntimeError):
    def __init__(
        self,
        reason: str,
        message: str,
        *,
        write_failure: bool = True,
        stderr: str = "",
        tests: list[dict[str, Any]] | None = None,
    ):
        super().__init__(message)
        self.reason = reason
        self.message = message
        self.write_failure = write_failure
        self.stderr = stderr
        self.tests = tests or []


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", delete=False, dir=str(path.parent), encoding="utf-8") as tmp:
        json.dump(payload, tmp, ensure_ascii=False, indent=2)
        tmp.write("\n")
    os.replace(tmp.name, path)


def run_git(cwd: Path, *args: str, check: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(cwd), *args],
        capture_output=True,
        text=True,
        check=check,
    )


def run_shell(cwd: Path, command: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=str(cwd),
        shell=True,
        capture_output=True,
        text=True,
        check=False,
    )


def truncate(value: str, limit: int = 4000) -> str:
    value = value or ""
    return value if len(value) <= limit else value[:limit] + "...<truncated>"


def parse_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "on"}


def git_root(path: Path) -> Path:
    completed = run_git(path, "rev-parse", "--show-toplevel")
    if completed.returncode != 0:
        raise IntegrationError("repo_missing", f"not a git repository: {path}", stderr=completed.stderr)
    return Path(completed.stdout.strip()).resolve()


def ref_exists(repo: Path, ref: str) -> bool:
    completed = run_git(repo, "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}")
    return completed.returncode == 0


def resolve_ref(repo: Path, name: str) -> str | None:
    name = str(name or "").strip()
    if not name:
        return None
    candidates = [
        name,
        f"refs/heads/{name}",
        f"origin/{name}",
        f"refs/remotes/origin/{name}",
    ]
    for candidate in candidates:
        if ref_exists(repo, candidate):
            return candidate
    return None


def rev_parse(repo: Path, ref: str) -> str:
    completed = run_git(repo, "rev-parse", f"{ref}^{{commit}}")
    if completed.returncode != 0:
        raise IntegrationError("ref_missing", f"cannot resolve ref: {ref}", stderr=completed.stderr)
    return completed.stdout.strip()


def parse_worktrees(repo: Path) -> list[dict[str, str]]:
    completed = run_git(repo, "worktree", "list", "--porcelain")
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
    if current:
        entries.append(current)
    return entries


def branch_checked_out_elsewhere(repo: Path, branch: str, worktree: Path) -> Path | None:
    for entry in parse_worktrees(repo):
        if entry.get("branch") != branch:
            continue
        entry_path = Path(entry.get("path") or "").expanduser().resolve()
        if entry_path != worktree.resolve():
            return entry_path
    return None


def project_repo(task: dict[str, Any], config: dict[str, Any], config_path: Path) -> Path:
    for key in ("workspace_root", "worktree_path", "workspace_path"):
        raw = str(task.get(key) or "").strip()
        if raw:
            candidate = Path(raw).expanduser().resolve()
            if candidate.exists():
                return git_root(candidate)
    project = str(task.get("project") or "").strip()
    project_cfg = (config.get("projects") or {}).get(project) or {}
    dev_root = str(project_cfg.get("dev_root") or "").strip()
    if dev_root:
        return git_root(Path(dev_root).expanduser().resolve())
    return git_root(config_path.parent)


def task_ready_for_integration(task_dir: Path, task: dict[str, Any]) -> None:
    status = str(task.get("status") or "").strip()
    if status != "ready_for_merge":
        raise IntegrationError(
            "task_not_ready",
            f"task status must be ready_for_merge, got {status or '<empty>'}",
            write_failure=False,
        )
    result = task_artifacts.parse_result(task_dir)
    if result.get("normalized_status") != "success" or not result.get("is_current_round", True):
        raise IntegrationError("result_not_ready", "current result.json is not successful", write_failure=False)

    gate = str(task.get("merge_gate_state") or "").strip()
    pending_gates = {"review_pending", "qa_pending", "quality_pending"}
    rejected_gates = {"review_rejected", "qa_failed", "blocked"}
    if gate in pending_gates:
        raise IntegrationError("quality_gate_pending", f"quality gate is still pending: {gate}", write_failure=False)
    if gate in rejected_gates:
        raise IntegrationError("quality_gate_blocked", f"quality gate blocks integration: {gate}", write_failure=False)
    if gate != "pm_acceptance_pending":
        raise IntegrationError(
            "quality_gate_not_accepted",
            f"quality gate must be pm_acceptance_pending before integration, got {gate or '<empty>'}",
            write_failure=False,
        )

    if parse_bool(task.get("review_required")):
        review = task_artifacts.parse_review(task_dir)
        if review.get("normalized_status") != "approve":
            raise IntegrationError("review_not_approved", "review is not approved", write_failure=False)
    if parse_bool(task.get("test_required")):
        verify = task_artifacts.parse_verify(task_dir)
        if verify.get("normalized_status") != "pass":
            raise IntegrationError("qa_not_passed", "QA verify is not passed", write_failure=False)


def select_source(repo: Path, task: dict[str, Any], strategy: str) -> dict[str, str]:
    branch = str(task.get("workspace_branch") or task.get("result_branch") or "").strip()
    patch_path = str(task.get("patch_path") or "").strip()
    branch_ref = resolve_ref(repo, branch) if branch else None
    patch_exists = bool(patch_path and Path(patch_path).expanduser().exists())

    if strategy in {"auto", "branch"} and branch_ref:
        return {"source_type": "branch", "source_ref": branch_ref, "workspace_branch": branch}
    if strategy == "branch":
        raise IntegrationError("integration_source_missing", f"workspace_branch not found: {branch or '<empty>'}")
    if strategy in {"auto", "patch"} and patch_exists:
        return {"source_type": "patch", "patch_path": str(Path(patch_path).expanduser().resolve())}
    raise IntegrationError("integration_source_missing", "missing usable workspace_branch or patch_path")


def prepare_worktree(repo: Path, target_ref: str, requested: str) -> tuple[Path, bool]:
    if requested:
        worktree = Path(requested).expanduser().resolve()
        if worktree.exists() and any(worktree.iterdir()):
            raise IntegrationError("integration_worktree_not_empty", f"integration worktree is not empty: {worktree}")
        worktree.parent.mkdir(parents=True, exist_ok=True)
        temporary = False
    else:
        worktree = Path(tempfile.mkdtemp(prefix="integration-worktree.")).resolve()
        temporary = True
    completed = run_git(repo, "worktree", "add", "--detach", str(worktree), target_ref)
    if completed.returncode != 0:
        if temporary:
            shutil.rmtree(worktree, ignore_errors=True)
        raise IntegrationError("worktree_prepare_failed", "failed to prepare integration worktree", stderr=completed.stderr)
    return worktree, temporary


def cleanup_worktree(repo: Path, worktree: Path, temporary: bool, keep: bool) -> None:
    if keep or not temporary:
        return
    run_git(repo, "worktree", "remove", "--force", str(worktree))
    shutil.rmtree(worktree, ignore_errors=True)


def conflict_files(worktree: Path, stderr: str) -> list[str]:
    files: set[str] = set()
    status = run_git(worktree, "status", "--porcelain")
    if status.returncode == 0:
        for line in status.stdout.splitlines():
            if len(line) >= 4 and line[:2].strip() in {"UU", "AA", "DD", "AU", "UA", "DU", "UD"}:
                files.add(line[3:].strip())
    for pattern in (
        r"CONFLICT .* in (.+)",
        r"error: patch failed: ([^:]+):",
        r"error: ([^:]+): patch does not apply",
    ):
        for match in re.finditer(pattern, stderr or ""):
            files.add(match.group(1).strip())
    return sorted(item for item in files if item)


def apply_source(worktree: Path, source: dict[str, str]) -> None:
    if source["source_type"] == "branch":
        completed = run_git(worktree, "merge", "--no-ff", "--no-commit", source["source_ref"])
        if completed.returncode != 0:
            raise IntegrationError("merge_conflict", "branch merge failed", stderr=completed.stderr or completed.stdout)
        return
    completed = run_git(worktree, "apply", "--3way", "--index", source["patch_path"])
    if completed.returncode != 0:
        raise IntegrationError("patch_apply_failed", "patch apply failed", stderr=completed.stderr or completed.stdout)


def staged_or_working_changes(worktree: Path) -> bool:
    staged = run_git(worktree, "diff", "--cached", "--quiet")
    working = run_git(worktree, "diff", "--quiet")
    return staged.returncode != 0 or working.returncode != 0


def run_tests(worktree: Path, commands: list[str]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for command in commands:
        completed = run_shell(worktree, command)
        item = {
            "command": command,
            "returncode": completed.returncode,
            "stdout": truncate(completed.stdout, 2000),
            "stderr": truncate(completed.stderr, 2000),
        }
        results.append(item)
        if completed.returncode != 0:
            raise IntegrationError(
                "integration_test_failed",
                f"integration test failed: {command}",
                stderr=completed.stderr or completed.stdout,
                tests=results,
            )
    return results


def commit_integration(worktree: Path, task_id: str, source: dict[str, str], target_branch: str) -> str:
    if not staged_or_working_changes(worktree):
        return rev_parse(worktree, "HEAD")
    run_git(worktree, "add", "-A")
    message = (
        f"Integrate task {task_id}\n\n"
        f"Source: {source.get('workspace_branch') or source.get('patch_path') or source.get('source_ref')}\n"
        f"Target: {target_branch}\n"
    )
    completed = run_git(worktree, "commit", "-m", message)
    if completed.returncode != 0:
        raise IntegrationError("integration_commit_failed", "failed to create integration commit", stderr=completed.stderr)
    return rev_parse(worktree, "HEAD")


def update_target_branch(repo: Path, target_branch: str, commit_hash: str, worktree: Path) -> None:
    checked_out = branch_checked_out_elsewhere(repo, target_branch, worktree)
    if checked_out:
        raise IntegrationError(
            "target_branch_checked_out",
            f"target branch {target_branch} is checked out at {checked_out}; use a dedicated integration branch/worktree",
        )
    completed = run_git(repo, "branch", "-f", target_branch, commit_hash)
    if completed.returncode != 0:
        raise IntegrationError("target_update_failed", f"failed to update {target_branch}", stderr=completed.stderr)


def push_target(repo: Path, target_branch: str) -> None:
    completed = run_git(repo, "push", "origin", target_branch)
    if completed.returncode != 0:
        raise IntegrationError("target_push_failed", f"failed to push {target_branch}", stderr=completed.stderr)


def append_transition(task_dir: Path, old_status: str, new_status: str, reason: str, actor: str, at: str) -> None:
    transitions_path = task_dir / "transitions.jsonl"
    with transitions_path.open("a", encoding="utf-8") as fp:
        fp.write(json.dumps({
            "from": old_status,
            "to": new_status,
            "at": at,
            "reason": reason,
            "actor": actor,
        }, ensure_ascii=False) + "\n")


def write_success(task_dir: Path, task: dict[str, Any], payload: dict[str, Any], actor: str) -> None:
    at = payload["integrated_at"]
    atomic_write_json(task_dir / "integration.json", payload)
    task_path = task_dir / "task.json"
    old_status = str(task.get("status") or "")
    updated = dict(task)
    updated["status"] = "done"
    updated["updated_at"] = at
    updated["merge_gate_state"] = "closed"
    updated["integration_status"] = "pass"
    updated["integration_commit"] = payload.get("integration_commit")
    updated["integrated_at"] = at
    updated["integrated_by"] = actor
    updated["last_gate_actor"] = actor
    updated["last_gate_decision_at"] = at
    summary = str(updated.get("result_summary") or "").strip()
    integration_summary = str(payload.get("summary") or "").strip()
    updated["result_summary"] = f"{summary}（{integration_summary}）" if summary and integration_summary else integration_summary or summary
    atomic_write_json(task_path, updated)
    if old_status != "done":
        append_transition(task_dir, old_status, "done", "integrate-task: integration pass", actor, at)


def write_failure(task_dir: Path, task: dict[str, Any], payload: dict[str, Any], actor: str) -> None:
    at = payload["integrated_at"]
    atomic_write_json(task_dir / "integration.json", payload)
    task_path = task_dir / "task.json"
    old_status = str(task.get("status") or "")
    updated = dict(task)
    updated["status"] = "blocked"
    updated["updated_at"] = at
    updated["merge_gate_state"] = "blocked"
    updated["integration_status"] = "fail"
    updated["integration_error"] = payload.get("reason")
    updated["integration_conflict_files"] = payload.get("conflict_files") or []
    updated["rework_reason"] = payload.get("summary") or payload.get("reason")
    updated["last_gate_actor"] = actor
    updated["last_gate_decision_at"] = at
    atomic_write_json(task_path, updated)
    if old_status != "blocked":
        append_transition(task_dir, old_status, "blocked", f"integrate-task: {payload.get('reason')}", actor, at)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Integrate a ready task branch/patch into its target branch.")
    parser.add_argument("--task-dir", required=True)
    parser.add_argument("--config", default=os.environ.get("CONFIG_PATH", str(WORKSPACE_ROOT / "config.json")))
    parser.add_argument("--strategy", choices=["auto", "branch", "patch"], default="auto")
    parser.add_argument("--target-branch", default="")
    parser.add_argument("--integration-worktree", default="")
    parser.add_argument("--actor", default="integrator")
    parser.add_argument("--test-cmd", action="append", default=[])
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--push", action="store_true")
    parser.add_argument("--keep-worktree", action="store_true")
    return parser


def integrate(args: argparse.Namespace) -> dict[str, Any]:
    task_dir = Path(args.task_dir).expanduser().resolve()
    task_path = task_dir / "task.json"
    if not task_path.exists():
        raise IntegrationError("task_missing", f"missing task.json: {task_path}", write_failure=False)
    task = load_json(task_path)
    config_path = Path(args.config).expanduser().resolve()
    config = load_json(config_path) if config_path.exists() else {}
    task_id = str(task.get("id") or task_dir.name)
    actor = str(args.actor or "integrator").strip() or "integrator"

    task_ready_for_integration(task_dir, task)
    target_branch = str(args.target_branch or task.get("integration_target_branch") or task.get("target_branch") or "").strip()
    source: dict[str, str] = {}
    repo: Path | None = None
    worktree: Path | None = None
    temporary = False
    test_results: list[dict[str, Any]] = []
    try:
        repo = project_repo(task, config, config_path)
        if not target_branch:
            raise IntegrationError("target_branch_missing", "missing integration target branch")
        target_ref = resolve_ref(repo, target_branch)
        if not target_ref:
            raise IntegrationError("target_branch_missing", f"target branch/ref not found: {target_branch}")
        source = select_source(repo, task, args.strategy)
        worktree, temporary = prepare_worktree(repo, target_ref, args.integration_worktree)
        apply_source(worktree, source)
        test_results = run_tests(worktree, list(args.test_cmd or []))
        current_head = rev_parse(worktree, "HEAD")
        if args.dry_run:
            return {
                "task_id": task_id,
                "status": "pass",
                "dry_run": True,
                "source": source,
                "target_branch": target_branch,
                "target_ref": target_ref,
                "would_update_from": current_head,
                "tests": test_results,
                "summary": f"dry-run: {task_id} can integrate into {target_branch}",
            }
        commit_hash = commit_integration(worktree, task_id, source, target_branch)
        update_target_branch(repo, target_branch, commit_hash, worktree)
        if args.push:
            push_target(repo, target_branch)
        payload = {
            "task_id": task_id,
            "status": "pass",
            "source_type": source["source_type"],
            "source_ref": source.get("workspace_branch") or source.get("source_ref") or source.get("patch_path"),
            "target_branch": target_branch,
            "integration_commit": commit_hash,
            "integrated_by": actor,
            "integrated_at": now_iso(),
            "pushed": bool(args.push),
            "tests": test_results,
            "summary": f"已合入 {target_branch}: {commit_hash[:12]}",
        }
        write_success(task_dir, task, payload, actor)
        return payload
    except IntegrationError as exc:
        if exc.tests:
            test_results = exc.tests
        conflict = conflict_files(worktree, exc.stderr) if worktree else []
        payload = {
            "task_id": task_id,
            "status": "fail",
            "reason": exc.reason,
            "target_branch": target_branch,
            "source_type": source.get("source_type"),
            "source_ref": source.get("workspace_branch") or source.get("source_ref") or source.get("patch_path"),
            "integrated_by": actor,
            "integrated_at": now_iso(),
            "conflict_files": conflict,
            "stderr": truncate(exc.stderr),
            "tests": test_results,
            "summary": exc.message,
        }
        if not args.dry_run and exc.write_failure:
            write_failure(task_dir, task, payload, actor)
        raise IntegrationError(exc.reason, json.dumps(payload, ensure_ascii=False), write_failure=False) from exc
    finally:
        if repo is not None and worktree is not None:
            cleanup_worktree(repo, worktree, temporary, bool(args.keep_worktree))


def main() -> int:
    args = build_parser().parse_args()
    try:
        payload = integrate(args)
    except IntegrationError as exc:
        try:
            parsed = json.loads(exc.message)
            print(json.dumps(parsed, ensure_ascii=False, indent=2), file=sys.stderr)
        except Exception:
            print(json.dumps({"status": "fail", "reason": exc.reason, "summary": exc.message}, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
