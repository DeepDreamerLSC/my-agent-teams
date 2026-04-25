#!/bin/bash
set -euo pipefail

WORKSPACE_ROOT="${WORKSPACE_ROOT:-$HOME/Desktop/work/my-agent-teams}"
TASKS_DIR="${TASKS_DIR:-$WORKSPACE_ROOT/tasks}"
TASK_ID="${1:-}"
TITLE="${2:-}"
ASSIGNED_AGENT="${3:-}"
DOMAIN="${4:-}"
PROJECT="${5:-}"
WRITE_SCOPE_CSV="${6:-}"
REVIEW_REQUIRED="${7:-false}"
TEST_REQUIRED="${8:-false}"
REVIEW_AUTHORITY="${9:-reviewer}"
EXECUTION_MODE="${10:-dev}"
TARGET_ENVIRONMENT="${11:-dev}"
REVIEW_LEVEL="${12:-}"
TASK_LEVEL="${13:-}"
REVIEWERS_CSV="${14:-}"
REVIEW_DEADLINE="${15:-}"
CONFIG_PATH="${CONFIG_PATH:-$WORKSPACE_ROOT/config.json}"
STRICT_WRITE_SCOPE_CONFLICT="${STRICT_WRITE_SCOPE_CONFLICT:-0}"

if [ -z "$TASK_ID" ] || [ -z "$TITLE" ] || [ -z "$ASSIGNED_AGENT" ] || [ -z "$DOMAIN" ] || [ -z "$PROJECT" ]; then
  echo "usage: create-task.sh <task-id-title> <title> <assigned-agent> <domain> <project> [write-scope-csv] [review-required] [test-required] [review-authority] [execution-mode] [target-environment] [review-level] [task-level] [reviewers-csv] [review-deadline]" >&2
  echo "example: create-task.sh 修复Word生成质量问题 \"修复 Word 生成功能质量问题\" be-1 backend chiralium '' true true reviewer dev dev standard execution 'review-1' '2026-04-24T20:00:00+08:00'" >&2
  exit 2
fi

TASK_DIR="$TASKS_DIR/$TASK_ID"
mkdir -p "$TASK_DIR"

python3 - "$CONFIG_PATH" "$TASK_ID" "$TITLE" "$ASSIGNED_AGENT" "$DOMAIN" "$PROJECT" "$WRITE_SCOPE_CSV" "$REVIEW_REQUIRED" "$TEST_REQUIRED" "$REVIEW_AUTHORITY" "$EXECUTION_MODE" "$TARGET_ENVIRONMENT" "$TASK_DIR" "$REVIEW_LEVEL" "$TASK_LEVEL" "$REVIEWERS_CSV" "$REVIEW_DEADLINE" "$STRICT_WRITE_SCOPE_CONFLICT" <<'PY'
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

cfg_path = Path(sys.argv[1])
(
    task_id,
    title,
    assigned_agent,
    domain,
    project,
    write_scope_csv,
    review_required_raw,
    test_required_raw,
    review_authority,
    execution_mode,
    target_environment,
    task_dir,
    review_level_raw,
    task_level_raw,
    reviewers_csv,
    review_deadline_raw,
    strict_conflict_raw,
) = sys.argv[2:18]

ACTIVE_CREATE_STATUSES = {'pending', 'dispatched', 'working', 'ready_for_merge', 'blocked'}


def parse_bool(raw: str) -> bool:
    return raw.strip().lower() in {'1', 'true', 'yes', 'y'}


def normalize_iso(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    stripped = value.strip()
    if not stripped:
        return None
    try:
        return datetime.fromisoformat(stripped.replace('Z', '+00:00')).astimezone().isoformat(timespec='seconds')
    except ValueError as exc:
        raise SystemExit(f'invalid iso8601 datetime: {value}') from exc


def dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        output.append(value)
    return output


def is_relative_to(path: Path, other: Path) -> bool:
    try:
        path.relative_to(other)
        return True
    except ValueError:
        return False


def scopes_overlap(path_a: Path, path_b: Path) -> bool:
    return path_a == path_b or is_relative_to(path_a, path_b) or is_relative_to(path_b, path_a)


def validate_and_resolve_scope(raw_paths: list[str], *, dev_root: Path, prod_root: Optional[Path], target_environment: str, assigned_agent: str) -> list[tuple[str, Path]]:
    resolved_scope: list[tuple[str, Path]] = []
    for raw_path in raw_paths:
        p = Path(raw_path).expanduser()
        if p.is_absolute():
            resolved = p.resolve()
        else:
            base = prod_root if target_environment == 'prod' and prod_root is not None else dev_root
            resolved = (base / p).resolve()
        if prod_root is not None and str(resolved).startswith(str(prod_root)):
            if assigned_agent != 'pm-chief':
                raise SystemExit(f'prod write_scope requires pm-chief: {raw_path}')
        elif not str(resolved).startswith(str(dev_root)):
            raise SystemExit(f'write_scope outside project dev_root: {raw_path}')
        resolved_scope.append((raw_path, resolved))
    return resolved_scope


def find_scope_conflicts(tasks_root: Path, current_task_id: str, candidate_scope: list[tuple[str, Path]]) -> list[str]:
    conflicts: list[str] = []
    if not candidate_scope:
        return conflicts
    for task_json in sorted(tasks_root.glob('*/task.json')):
        task_data = json.loads(task_json.read_text(encoding='utf-8'))
        other_id = str(task_data.get('id') or task_json.parent.name)
        if other_id == current_task_id:
            continue
        other_status = str(task_data.get('status') or '')
        if other_status not in ACTIVE_CREATE_STATUSES:
            continue
        other_raw_scope = [item.strip() for item in (task_data.get('write_scope') or []) if str(item).strip()]
        other_resolved_scope = validate_and_resolve_scope(
            other_raw_scope,
            dev_root=dev_root,
            prod_root=prod_root,
            target_environment=str(task_data.get('target_environment') or 'dev'),
            assigned_agent=str(task_data.get('assigned_agent') or ''),
        )
        for raw_a, resolved_a in candidate_scope:
            for raw_b, resolved_b in other_resolved_scope:
                if scopes_overlap(resolved_a, resolved_b):
                    conflicts.append(f'{other_id} [{other_status}] {raw_a} ↔ {raw_b}')
    return conflicts


invalid_chars = set('/\\')
if any(ch in invalid_chars for ch in task_id) or any(ch.isspace() for ch in task_id):
    raise SystemExit(
        "invalid task id: 请使用不含空格和路径分隔符的中文标题式名称，例如 '修复Word生成质量问题' 或 'Agent目录隔离方案'"
    )

if task_id.upper().startswith('T-') and any(ch.isdigit() for ch in task_id):
    raise SystemExit(
        f"invalid task id: '{task_id}' 属于旧编号风格。新任务必须使用中文标题式名称，例如 '修复Word生成质量问题' 或 'Agent目录隔离方案'"
    )

if not re.search(r'[\u4e00-\u9fff]', task_id):
    raise SystemExit(
        f"invalid task id: '{task_id}' 不包含中文。新任务必须使用中文标题式名称，例如 '修复Word生成质量问题' 或 'Agent目录隔离方案'"
    )

cfg = json.loads(cfg_path.read_text(encoding='utf-8'))
legacy_review_required = parse_bool(review_required_raw)
test_required = parse_bool(test_required_raw)
review_authority = review_authority if review_authority in {'reviewer', 'owner'} else 'reviewer'
execution_mode = execution_mode if execution_mode in {'dev', 'deploy'} else 'dev'
target_environment = target_environment if target_environment in {'dev', 'prod'} else 'dev'
write_scope = [item.strip() for item in write_scope_csv.split(',') if item.strip()] if write_scope_csv else []
strict_conflict = parse_bool(strict_conflict_raw)

agents = cfg.get('agents', {})
if assigned_agent not in agents:
    raise SystemExit(f'unknown assigned_agent: {assigned_agent}')

projects = cfg.get('projects', {})
if project not in projects:
    raise SystemExit(f'unknown project: {project}')
project_cfg = projects[project]
dev_root = Path(project_cfg['dev_root']).expanduser().resolve()
prod_root_raw = project_cfg.get('prod_root')
prod_root = Path(prod_root_raw).expanduser().resolve() if prod_root_raw else None

if execution_mode == 'dev' and target_environment != 'dev':
    raise SystemExit('execution_mode=dev requires target_environment=dev')

if execution_mode == 'deploy' and assigned_agent != 'pm-chief':
    raise SystemExit('deploy tasks can only be assigned to pm-chief in Phase 1')

if target_environment == 'prod' and assigned_agent != 'pm-chief':
    raise SystemExit('prod tasks can only be assigned to pm-chief in Phase 1')

resolved_scope = validate_and_resolve_scope(
    write_scope,
    dev_root=dev_root,
    prod_root=prod_root,
    target_environment=target_environment,
    assigned_agent=assigned_agent,
)

review_level = review_level_raw.strip().lower() if review_level_raw.strip() else ''
if review_level not in {'skip', 'standard', 'complex'}:
    review_level = 'standard' if legacy_review_required else 'skip'
review_required = review_level != 'skip'
reviewer = cfg.get('domain_policies', {}).get(domain, {}).get('default_reviewer') if review_required else None

explicit_reviewers = dedupe([item.strip() for item in reviewers_csv.split(',') if item.strip()]) if reviewers_csv.strip() else []
for reviewer_id in explicit_reviewers:
    if reviewer_id not in agents:
        raise SystemExit(f'unknown reviewer in reviewers: {reviewer_id}')

if explicit_reviewers:
    reviewers = explicit_reviewers
else:
    if review_level == 'complex':
        reviewers = dedupe([reviewer or 'review-1', 'arch-1'])
    elif review_level == 'standard':
        reviewers = [reviewer] if reviewer else []
    else:
        reviewers = []

if review_level == 'skip':
    reviewers = []
elif not reviewers:
    raise SystemExit(f'review_level={review_level} requires at least one reviewer')
elif review_level == 'complex' and len(reviewers) < 2:
    raise SystemExit('review_level=complex requires at least two reviewers')

review_deadline = normalize_iso(review_deadline_raw)
conflicts = find_scope_conflicts(Path(task_dir).parent, task_id, resolved_scope)
if conflicts:
    message = 'write_scope conflicts detected with existing active tasks:\n- ' + '\n- '.join(conflicts)
    if strict_conflict:
        raise SystemExit(message)
    print(f'WARNING: {message}', file=sys.stderr)

created_at = datetime.now().astimezone().isoformat(timespec='seconds')
obj = {
    'id': task_id,
    'title': title,
    'project': project,
    'execution_mode': execution_mode,
    'target_environment': target_environment,
    'assigned_agent': assigned_agent,
    'review_required': review_required,
    'review_authority': review_authority,
    'reviewer': reviewer,
    'review_level': review_level,
    'reviewers': reviewers,
    'review_deadline': review_deadline,
    'review_round': 0,
    'max_review_rounds': 3,
    'test_required': test_required,
    'status': 'pending',
    'task_level': task_level_raw.strip().lower() if task_level_raw.strip() and task_level_raw.strip().lower() in {'epic', 'domain', 'execution', 'review', 'integration', 'coordination'} else cfg.get('defaults', {}).get('task_level', 'execution'),
    'owner_pm': cfg.get('orchestration', {}).get('root_pm', 'pm-chief'),
    'domain': domain,
    'write_scope': write_scope,
    'depends_on': [],
    'blocks': [],
    'artifacts': [
        {
            'type': 'instruction',
            'path': f'tasks/{task_id}/instruction.md',
            'description': 'PM 生成的任务指令'
        }
    ],
    'root_request_id': task_id,
    'parent_task_id': None,
    'integration_owner': cfg.get('orchestration', {}).get('integration_owner'),
    'priority': 'medium',
    'timeout_minutes': cfg.get('defaults', {}).get('timeout_minutes', 30),
    'lease_owner': cfg.get('orchestration', {}).get('root_pm', 'pm-chief'),
    'lease_acquired_at': created_at,
    'lease_expires_at': created_at,
    'workspace_mode': cfg.get('defaults', {}).get('workspace_mode', 'main'),
    'target_branch': cfg.get('defaults', {}).get('target_branch', 'integration'),
    'result_summary': None,
    'last_error': None,
    'created_at': created_at,
    'updated_at': created_at
}
Path(task_dir, 'task.json').write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
Path(task_dir, 'instruction.md').write_text(f'# 任务：{title}\n\n## 目标\n（待 PM 填写）\n', encoding='utf-8')
Path(task_dir, 'transitions.jsonl').write_text('', encoding='utf-8')
PY

echo "created $TASK_DIR"
