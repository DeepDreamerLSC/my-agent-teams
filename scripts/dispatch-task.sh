#!/bin/bash
set -euo pipefail

TASK_FILE="${1:-}"
WORKSPACE_ROOT="${WORKSPACE_ROOT:-$HOME/Desktop/work/my-agent-teams}"
CONFIG_PATH="${CONFIG_PATH:-$WORKSPACE_ROOT/config.json}"
SEND_SCRIPT="${SEND_SCRIPT:-$WORKSPACE_ROOT/scripts/send-to-agent.sh}"
ALLOW_WRITE_SCOPE_CONFLICT="${ALLOW_WRITE_SCOPE_CONFLICT:-0}"

if [ -z "$TASK_FILE" ]; then
  echo "usage: dispatch-task.sh <task.json>" >&2
  exit 2
fi

DISPATCH_OUTPUT=$(python3 - "$TASK_FILE" "$CONFIG_PATH" "$ALLOW_WRITE_SCOPE_CONFLICT" <<'PY'
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

ACTIVE_DISPATCH_STATUSES = {'dispatched', 'working', 'ready_for_merge', 'blocked'}


def parse_bool(raw: str) -> bool:
    return str(raw).strip().lower() in {'1', 'true', 'yes', 'y'}


def normalize_iso(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    stripped = str(value).strip()
    if not stripped:
        return None
    return datetime.fromisoformat(stripped.replace('Z', '+00:00')).astimezone().isoformat(timespec='seconds')


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
        resolved = p.resolve() if p.is_absolute() else ((prod_root if target_environment == 'prod' and prod_root is not None else dev_root) / p).resolve()
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
        if other_status not in ACTIVE_DISPATCH_STATUSES:
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


task_path = Path(sys.argv[1]).resolve()
config_path = Path(sys.argv[2]).resolve()
allow_conflicts = parse_bool(sys.argv[3])
task = json.loads(task_path.read_text(encoding='utf-8'))
config = json.loads(config_path.read_text(encoding='utf-8'))

if task.get('status') != 'pending':
    raise SystemExit(f"task status is {task.get('status')}, expected pending")

project = task.get('project')
projects = config.get('projects', {})
if project not in projects:
    raise SystemExit(f'unknown project: {project}')

agents = config.get('agents', {})
assigned_agent = task.get('assigned_agent')
if assigned_agent not in agents:
    raise SystemExit(f'unknown assigned_agent: {assigned_agent}')

execution_mode = task.get('execution_mode')
target_environment = task.get('target_environment')
if execution_mode not in {'dev', 'deploy'}:
    raise SystemExit('execution_mode invalid')
if target_environment not in {'dev', 'prod'}:
    raise SystemExit('target_environment invalid')
if execution_mode == 'dev' and target_environment != 'dev':
    raise SystemExit('execution_mode=dev requires target_environment=dev')
if execution_mode == 'deploy' and assigned_agent != 'pm-chief':
    raise SystemExit('deploy tasks can only be assigned to pm-chief in Phase 1')
if target_environment == 'prod' and assigned_agent != 'pm-chief':
    raise SystemExit('prod tasks can only be assigned to pm-chief in Phase 1')

project_cfg = projects[project]
dev_root = Path(project_cfg['dev_root']).expanduser().resolve()
prod_root_raw = project_cfg.get('prod_root')
prod_root = Path(prod_root_raw).expanduser().resolve() if prod_root_raw else None

resolved_scope = validate_and_resolve_scope(
    [item for item in (task.get('write_scope') or []) if str(item).strip()],
    dev_root=dev_root,
    prod_root=prod_root,
    target_environment=target_environment,
    assigned_agent=assigned_agent,
)
conflicts = find_scope_conflicts(task_path.parent.parent, str(task.get('id')), resolved_scope)
if conflicts and not allow_conflicts:
    raise SystemExit('write_scope conflicts with active tasks:\n- ' + '\n- '.join(conflicts))

legacy_review_required = bool(task.get('review_required'))
review_level = str(task.get('review_level') or '').strip().lower()
if review_level not in {'skip', 'standard', 'complex'}:
    review_level = 'standard' if legacy_review_required else 'skip'
task['review_level'] = review_level
task['review_required'] = review_level != 'skip'
if review_level == 'skip':
    task['reviewers'] = []
else:
    existing_reviewers = task.get('reviewers') if isinstance(task.get('reviewers'), list) else []
    if existing_reviewers:
        reviewers = dedupe([str(item).strip() for item in existing_reviewers if str(item).strip()])
    else:
        primary_reviewer = task.get('reviewer') or config.get('domain_policies', {}).get(task.get('domain'), {}).get('default_reviewer')
        reviewers = [primary_reviewer] if review_level == 'standard' and primary_reviewer else dedupe([primary_reviewer or 'review-1', 'arch-1'])
    if review_level == 'complex' and len(reviewers) < 2:
        raise SystemExit('review_level=complex requires at least two reviewers before dispatch')
    task['reviewers'] = reviewers
    if not task.get('reviewer') and reviewers:
        task['reviewer'] = reviewers[0]

task['review_deadline'] = normalize_iso(task.get('review_deadline')) if task.get('review_deadline') else None

now = datetime.now().astimezone().isoformat(timespec='seconds')
previous = task['status']
task['status'] = 'dispatched'
task['updated_at'] = now
task['lease_owner'] = task.get('owner_pm')
task['lease_acquired_at'] = now
task['lease_expires_at'] = now
with (task_path.parent / 'transitions.jsonl').open('a', encoding='utf-8') as fp:
    fp.write(json.dumps({
        'from': previous,
        'to': 'dispatched',
        'at': now,
        'reason': 'pm dispatch'
    }, ensure_ascii=False) + '\n')
task_path.write_text(json.dumps(task, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps({
    'task_id': task.get('id'),
    'assigned_agent': assigned_agent,
    'task_dir': str(task_path.parent),
    'conflicts': conflicts,
}, ensure_ascii=False))
PY
)

echo "dispatched $(python3 -c 'import json,sys; print(json.load(sys.stdin)["task_id"])' <<< "$DISPATCH_OUTPUT")"
if [ "$ALLOW_WRITE_SCOPE_CONFLICT" = "1" ]; then
  python3 -c 'import json,sys; payload=json.load(sys.stdin); conflicts=payload.get("conflicts") or []; [print(f"WARNING: {item}", file=sys.stderr) for item in conflicts]' <<< "$DISPATCH_OUTPUT"
fi

ASSIGNED_AGENT=$(python3 -c 'import json,sys; print(json.load(sys.stdin)["assigned_agent"])' <<< "$DISPATCH_OUTPUT")
TASK_DIR=$(python3 -c 'import json,sys; print(json.load(sys.stdin)["task_dir"])' <<< "$DISPATCH_OUTPUT")
if [ -x "$SEND_SCRIPT" ]; then
  MESSAGE="请读取 ${TASK_DIR}/instruction.md 并开始执行任务。完成后写 ack.json 和 result.json。"
  CONFIG_PATH="$CONFIG_PATH" "$SEND_SCRIPT" "$ASSIGNED_AGENT" "$MESSAGE"
fi
