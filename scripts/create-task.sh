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
TASK_TYPE_RAW="${16:-}"
READ_ONLY_RAW="${17:-false}"
DOWNSTREAM_ACTION_RAW="${18:-}"
OWNER_APPROVAL_REQUIRED_RAW="${19:-false}"
OWNER_APPROVED_BY_RAW="${20:-}"
OWNER_APPROVED_AT_RAW="${21:-}"
CONFIG_PATH="${CONFIG_PATH:-$WORKSPACE_ROOT/config.json}"
STRICT_WRITE_SCOPE_CONFLICT="${STRICT_WRITE_SCOPE_CONFLICT:-0}"

if [ -z "$TASK_ID" ] || [ -z "$TITLE" ] || [ -z "$ASSIGNED_AGENT" ] || [ -z "$DOMAIN" ] || [ -z "$PROJECT" ]; then
  echo "usage: create-task.sh <task-id-title> <title> <assigned-agent> <domain> <project> [write-scope-csv] [review-required] [test-required] [review-authority] [execution-mode] [target-environment] [review-level] [task-level] [reviewers-csv] [review-deadline] [task-type] [read-only] [downstream-action] [owner-approval-required] [owner-approved-by] [owner-approved-at]" >&2
  echo "example: create-task.sh 修复Word生成质量问题 \"修复 Word 生成功能质量问题\" be-1 backend chiralium '' true true reviewer dev dev standard execution 'review-1' '2026-04-24T20:00:00+08:00' development false review" >&2
  exit 2
fi

TASK_DIR="$TASKS_DIR/$TASK_ID"
mkdir -p "$TASK_DIR"

python3 - "$CONFIG_PATH" "$TASK_ID" "$TITLE" "$ASSIGNED_AGENT" "$DOMAIN" "$PROJECT" "$WRITE_SCOPE_CSV" "$REVIEW_REQUIRED" "$TEST_REQUIRED" "$REVIEW_AUTHORITY" "$EXECUTION_MODE" "$TARGET_ENVIRONMENT" "$TASK_DIR" "$REVIEW_LEVEL" "$TASK_LEVEL" "$REVIEWERS_CSV" "$REVIEW_DEADLINE" "$STRICT_WRITE_SCOPE_CONFLICT" "$TASK_TYPE_RAW" "$READ_ONLY_RAW" "$DOWNSTREAM_ACTION_RAW" "$OWNER_APPROVAL_REQUIRED_RAW" "$OWNER_APPROVED_BY_RAW" "$OWNER_APPROVED_AT_RAW" <<'PY'
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
    task_type_raw,
    read_only_raw,
    downstream_action_raw,
    owner_approval_required_raw,
    owner_approved_by_raw,
    owner_approved_at_raw,
) = sys.argv[2:25]

ACTIVE_CREATE_STATUSES = {'pending', 'dispatched', 'working', 'ready_for_merge', 'blocked'}
AUTO_ASSIGNED_AGENTS = {'auto', 'auto-dev', 'unassigned'}
VALID_TASK_LEVELS = {'epic', 'domain', 'execution', 'review', 'integration', 'coordination'}
TASK_TYPE_ALIASES = {
    'investigation': 'investigation',
    'diagnosis': 'investigation',
    '排查': 'investigation',
    '诊断': 'investigation',
    'design': 'design',
    '方案': 'design',
    '架构': 'design',
    'development': 'development',
    'develop': 'development',
    '开发': 'development',
    'verification': 'verification',
    'verify': 'verification',
    '验证': 'verification',
    'qa': 'verification',
    'integration': 'integration',
    '集成': 'integration',
    'merge': 'integration',
    'deployment': 'deployment',
    'deploy': 'deployment',
    '发布': 'deployment',
    '部署': 'deployment',
}


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


def normalize_task_type(raw: str, *, execution_mode: str, target_environment: str, task_level: str) -> Optional[str]:
    stripped = raw.strip().lower()
    if stripped:
        return TASK_TYPE_ALIASES.get(stripped)
    if execution_mode == 'deploy' or target_environment == 'prod':
        return 'deployment'
    if task_level == 'integration':
        return 'integration'
    return None


def derive_claim_scope(*, agents: dict, task_type: Optional[str], domain: str, task_level: str, execution_mode: str, target_environment: str, assigned_agent_is_auto: bool) -> list[str]:
    if not assigned_agent_is_auto:
        return []
    if execution_mode != 'dev' or target_environment != 'dev':
        return []
    if task_level not in {'execution', 'review'}:
        return []
    candidates: list[str] = []
    normalized_type = (task_type or '').strip().lower()
    for agent_id, payload in (agents or {}).items():
        role = str((payload or {}).get('role') or '').strip().lower()
        if normalized_type in {'development', 'investigation'}:
            if role == 'fullstack_dev' or agent_id.startswith('dev-'):
                candidates.append(agent_id)
        elif normalized_type == 'verification' or domain == 'quality':
            if role == 'qa' or agent_id.startswith('qa-'):
                candidates.append(agent_id)
        elif normalized_type == 'design':
            if role == 'architect' or agent_id == 'arch-1':
                candidates.append(agent_id)
    return dedupe(candidates)


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
        if str(task_data.get('project') or '') != project:
            continue
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
normalized_task_level = task_level_raw.strip().lower() if task_level_raw.strip().lower() in VALID_TASK_LEVELS else cfg.get('defaults', {}).get('task_level', 'execution')
write_scope = [item.strip() for item in write_scope_csv.split(',') if item.strip()] if write_scope_csv else []
strict_conflict = parse_bool(strict_conflict_raw)
read_only = parse_bool(read_only_raw)
owner_approval_required = parse_bool(owner_approval_required_raw)

agents = cfg.get('agents', {})
assigned_agent_is_auto = assigned_agent in AUTO_ASSIGNED_AGENTS
if assigned_agent not in agents and not (assigned_agent_is_auto and execution_mode == 'dev' and target_environment == 'dev' and normalized_task_level == 'execution'):
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

if execution_mode == 'deploy' and assigned_agent != 'arch-1':
    raise SystemExit('deploy tasks can only be assigned to arch-1')

if target_environment == 'prod' and assigned_agent != 'arch-1':
    raise SystemExit('prod tasks can only be assigned to arch-1')

if normalized_task_level == 'integration' and assigned_agent != 'arch-1':
    raise SystemExit('integration tasks must be assigned to arch-1')

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
domain_policies = cfg.get('domain_policies', {})
reviewer = (
    domain_policies.get(domain, {}).get('default_reviewer')
    or domain_policies.get('development', {}).get('default_reviewer')
) if review_required else None

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
owner_approved_at = normalize_iso(owner_approved_at_raw) if owner_approved_at_raw.strip() else None
task_type = normalize_task_type(
    task_type_raw,
    execution_mode=execution_mode,
    target_environment=target_environment,
    task_level=normalized_task_level,
)
if task_type == 'deployment':
    owner_approval_required = True
claim_scope = derive_claim_scope(
    agents=agents,
    task_type=task_type,
    domain=domain,
    task_level=normalized_task_level,
    execution_mode=execution_mode,
    target_environment=target_environment,
    assigned_agent_is_auto=assigned_agent_is_auto,
)
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
    'task_level': normalized_task_level,
    'owner_pm': cfg.get('orchestration', {}).get('root_pm', 'pm-chief'),
    'domain': domain,
    'task_type': task_type,
    'read_only': read_only,
    'downstream_action': downstream_action_raw.strip() or None,
    'owner_approval_required': owner_approval_required,
    'owner_approved_by': owner_approved_by_raw.strip() or None,
    'owner_approved_at': owner_approved_at,
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
    'updated_at': created_at,
    'claim_policy': 'pull' if assigned_agent_is_auto else 'push',
    'claim_scope': claim_scope,
    'claim_max_concurrency': 1 if assigned_agent_is_auto else None,
    'dependency_policy': 'done_only' if assigned_agent_is_auto else None,
    'pool_timeout_minutes': cfg.get('task_pool', {}).get('pool_timeout_minutes', 120) if assigned_agent_is_auto else None,
    'pool_entered_at': None,
    'claimed_by': None,
    'claimed_at': None,
    'claim_reason': None,
}
Path(task_dir, 'task.json').write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
instruction_lines = [
    f'# 任务：{title}',
    '',
    '## 任务类型',
    task_type or '（待 PM 填写）',
    '',
    '## 目标',
    '（待 PM 填写）',
    '',
    '## 任务边界',
    '（待 PM 填写）',
    '',
    '## 输入事实',
    '（待 PM 填写）',
    '',
    '## 约束',
    f'- write_scope: {write_scope if write_scope else "[]"}',
    f'- read_only: {"true" if read_only else "false"}',
    f'- 依赖上游任务: 无',
    f'- target_environment: {target_environment}',
    f'- execution_mode: {execution_mode}',
    f'- owner_approval_required: {"true" if owner_approval_required else "false"}',
    '',
    '## 交付物',
    '（待 PM 填写）',
    '',
    '## 验收标准',
    '1. （待 PM 填写）',
    '',
    '## 下游动作',
    downstream_action_raw.strip() or '（待 PM 填写）',
]
if owner_approval_required:
    instruction_lines.extend([
        '',
        '## 授权状态',
        f'- owner_approved_by: {owner_approved_by_raw.strip() or "（待 PM 填写）"}',
        f'- owner_approved_at: {owner_approved_at or "（待 PM 填写）"}',
    ])
Path(task_dir, 'instruction.md').write_text('\n'.join(instruction_lines) + '\n', encoding='utf-8')
Path(task_dir, 'transitions.jsonl').write_text('', encoding='utf-8')
PY

echo "created $TASK_DIR"
