#!/bin/bash
set -euo pipefail

TASK_ID="${1:-}"
REASON="${2:-}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_ROOT="${WORKSPACE_ROOT:-$(cd "$SCRIPT_DIR/.." && pwd)}"
TASKS_ROOT="${TASKS_ROOT:-$WORKSPACE_ROOT/tasks}"
CONFIG_PATH="${CONFIG_PATH:-$WORKSPACE_ROOT/config.json}"
TASK_DIR="$TASKS_ROOT/$TASK_ID"

if [ -z "$TASK_ID" ]; then
  echo "usage: claim-task.sh <task-id> [reason]" >&2
  exit 2
fi

if [ ! -f "$TASK_DIR/task.json" ]; then
  echo "task not found: $TASK_DIR/task.json" >&2
  exit 1
fi

AGENT_ID="${CLAIM_AGENT_ID:-}"
if [ -z "$AGENT_ID" ]; then
  case "$PWD" in
    */agents/*)
      AGENT_ID="$(basename "$PWD")"
      ;;
    *)
      echo "claim-task.sh must run from an agent workdir or with CLAIM_AGENT_ID set" >&2
      exit 1
      ;;
  esac
fi

python3 - "$TASK_DIR" "$AGENT_ID" "$REASON" "$TASKS_ROOT" "$CONFIG_PATH" "$WORKSPACE_ROOT" "$SCRIPT_DIR" <<'PY'
import json
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path

task_dir = Path(sys.argv[1])
agent_id = sys.argv[2]
reason = sys.argv[3].strip()
tasks_root = Path(sys.argv[4])
config_path = Path(sys.argv[5])
workspace_root = Path(sys.argv[6])
script_dir = Path(sys.argv[7])
sys.path.insert(0, str(script_dir / 'lib'))
from task_pool_rules import pool_gate_blockers  # type: ignore
from task_workspace import ensure_task_workspace  # type: ignore

task_path = task_dir / 'task.json'
task = json.loads(task_path.read_text(encoding='utf-8'))
config = json.loads(config_path.read_text(encoding='utf-8'))

ROLE_WIP_KEYS = {
    'fullstack_dev': 'dev',
    'reviewer': 'reviewer',
    'qa': 'qa',
    'architect': 'architect',
    'pm': 'pm-chief',
}

status = str(task.get('status') or '')
if status != 'pooled':
    raise SystemExit(f'task status must be pooled to claim, got {status}')

gate_blockers = pool_gate_blockers(task, task_dir)
if gate_blockers:
    raise SystemExit('pool gate not satisfied: ' + ', '.join(gate_blockers))

task_type = str(task.get('task_type') or '').strip().lower()
execution_mode = str(task.get('execution_mode') or '').strip().lower()
target_environment = str(task.get('target_environment') or '').strip().lower()
if task_type in {'deployment', 'integration'} or execution_mode == 'deploy' or target_environment == 'prod':
    raise SystemExit('deployment/integration/prod tasks must not be claimed from the general pool')

claim_scope = [str(item).strip() for item in (task.get('claim_scope') or []) if str(item).strip()]
if not claim_scope:
    domain = str(task.get('domain') or '').strip().lower()
    for candidate_agent_id, payload in (config.get('agents') or {}).items():
        role = str((payload or {}).get('role') or '').strip().lower()
        if task_type in {'development', 'investigation'}:
            if role == 'fullstack_dev' or candidate_agent_id.startswith('dev-'):
                claim_scope.append(candidate_agent_id)
        elif task_type == 'verification' or domain == 'quality':
            if role == 'qa' or candidate_agent_id.startswith('qa-'):
                claim_scope.append(candidate_agent_id)
        elif task_type == 'design':
            if role == 'architect' or candidate_agent_id == 'arch-1':
                claim_scope.append(candidate_agent_id)
if claim_scope and agent_id not in claim_scope:
    raise SystemExit(f'agent {agent_id} is not in claim_scope: {claim_scope}')

def int_value(value, default):
    try:
        if value in (None, ''):
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


pool_config = config.get('task_pool') or {}
wip_limits = config.get('wip_limits') or {}
agent_role = str(((config.get('agents') or {}).get(agent_id) or {}).get('role') or '').strip().lower()
wip_key = ROLE_WIP_KEYS.get(agent_role)

def project_roots(payload):
    project = str(payload.get('project') or '').strip()
    project_cfg = (config.get('projects') or {}).get(project) or {}
    dev_root = project_cfg.get('dev_root')
    prod_root = project_cfg.get('prod_root')
    return (
        Path(dev_root).expanduser().resolve() if dev_root else None,
        Path(prod_root).expanduser().resolve() if prod_root else None,
    )


def resolve_scope_paths(payload):
    raw_scope = [str(item).strip() for item in (payload.get('write_scope') or []) if str(item).strip()]
    if not raw_scope:
        return []
    dev_root, prod_root = project_roots(payload)
    target_env = str(payload.get('target_environment') or 'dev').strip().lower()
    base_root = prod_root if target_env == 'prod' and prod_root is not None else dev_root
    resolved = []
    for item in raw_scope:
        path = Path(item).expanduser()
        if not path.is_absolute() and base_root is not None:
            path = base_root / path
        resolved.append(path.resolve())
    return resolved


def is_relative_to(path: Path, other: Path) -> bool:
    try:
        path.relative_to(other)
        return True
    except ValueError:
        return False

def scopes_overlap(a: Path, b: Path) -> bool:
    return a == b or is_relative_to(a, b) or is_relative_to(b, a)

claim_path = task_dir / 'claim.json'
claim_payload = {
    'task_id': str(task.get('id') or task_dir.name),
    'agent': agent_id,
    'claimed_at': datetime.now().astimezone().isoformat(timespec='seconds'),
    'reserved': True,
}
if reason:
    claim_payload['reason'] = reason

def assert_dependencies_ready(current_task):
    policy = str(current_task.get('dependency_policy') or 'done_only').strip().lower()
    allowed = {'done', 'cancelled'}
    if policy == 'ready_for_merge_ok':
        allowed.add('ready_for_merge')
    for dep in current_task.get('depends_on') or []:
        dep_path = tasks_root / dep / 'task.json'
        if not dep_path.exists():
            raise SystemExit(f'dependency task missing: {dep}')
        dep_payload = json.loads(dep_path.read_text(encoding='utf-8'))
        if str(dep_payload.get('status') or '') not in allowed:
            raise SystemExit(f'dependency not ready: {dep_path.parent.name}={dep_payload.get("status")}')


def assert_capacity_and_conflicts(current_task):
    role_limit = wip_limits.get(agent_id)
    if role_limit in (None, '') and wip_key:
        role_limit = wip_limits.get(wip_key)
    working_limit = max(1, int_value(pool_config.get('default_working_limit'), 1))
    reserved_limit = max(1, int_value(pool_config.get('default_reserved_limit'), 1))
    if role_limit not in (None, ''):
        working_limit = max(1, min(working_limit, int_value(role_limit, working_limit)))
    active_limit = working_limit + reserved_limit
    active_count = 0
    working_count = 0
    reserved_count = 0
    resolved_target_scope = resolve_scope_paths(current_task)

    for other_path in tasks_root.glob('*/task.json'):
        other = json.loads(other_path.read_text(encoding='utf-8'))
        if str(other.get('assigned_agent') or '') != agent_id:
            continue
        if str(other.get('status') or '') not in {'dispatched', 'working'}:
            continue
        active_count += 1
        if str(other.get('status') or '') == 'working':
            working_count += 1
        if str(other.get('status') or '') == 'dispatched':
            reserved_count += 1
        for other_scope in resolve_scope_paths(other):
            for target_scope_item in resolved_target_scope:
                if scopes_overlap(target_scope_item, other_scope):
                    raise SystemExit(f'write_scope conflict with active task: {other_path.parent.name}')

    if working_count > working_limit:
        raise SystemExit(f'agent {agent_id} exceeds working_limit={working_limit}')
    if reserved_count >= reserved_limit:
        raise SystemExit(f'agent {agent_id} already reached reserved_limit={reserved_limit}')
    if active_count >= active_limit:
        raise SystemExit(f'agent {agent_id} already reached active capacity={active_limit}')


agent_lock_path = workspace_root / '.runtime' / 'state' / 'task-watcher' / f'claim-agent-{agent_id}.lock'
agent_lock_path.parent.mkdir(parents=True, exist_ok=True)
agent_lock_fd = os.open(agent_lock_path, os.O_CREAT | os.O_RDWR, 0o644)
lock_path = task_dir / '.claim.lock'
lock_fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o644)
try:
    import fcntl
    fcntl.flock(agent_lock_fd, fcntl.LOCK_EX)
    fcntl.flock(lock_fd, fcntl.LOCK_EX)

    task = json.loads(task_path.read_text(encoding='utf-8'))
    current_status = str(task.get('status') or '')
    if current_status != 'pooled':
        raise SystemExit(f'task status changed while claiming: {current_status}')

    gate_blockers = pool_gate_blockers(task, task_dir)
    if gate_blockers:
        raise SystemExit('pool gate not satisfied: ' + ', '.join(gate_blockers))

    assert_dependencies_ready(task)
    assert_capacity_and_conflicts(task)

    with tempfile.NamedTemporaryFile('w', delete=False, dir=str(task_dir), encoding='utf-8') as tmp:
        json.dump(claim_payload, tmp, ensure_ascii=False, indent=2)
        tmp.write('\n')
    os.replace(tmp.name, claim_path)

    now = datetime.now().astimezone().isoformat(timespec='seconds')
    task['pre_claim_assigned_agent'] = task.get('assigned_agent')
    task['assigned_agent'] = agent_id
    task['status'] = 'dispatched'
    task['updated_at'] = now
    task['lease_owner'] = task.get('owner_pm')
    task['lease_acquired_at'] = now
    task['lease_expires_at'] = now
    task['claimed_by'] = agent_id
    task['claimed_at'] = claim_payload['claimed_at']
    task['claim_reason'] = reason or None
    task['reserved_by'] = agent_id
    task['reserved_at'] = claim_payload['claimed_at']
    task['reserved_reason'] = reason or 'manual pool claim'
    if task.get('depends_on') and not task.get('dependencies_ready_at'):
        task['dependencies_ready_at'] = now
    with tempfile.NamedTemporaryFile('w', delete=False, dir=str(task_dir), encoding='utf-8') as tmp:
        json.dump(task, tmp, ensure_ascii=False, indent=2)
        tmp.write('\n')
    os.replace(tmp.name, task_path)

    workspace_payload = ensure_task_workspace(task_dir, config_path)
    dispatch_hint = str(workspace_payload.get('dispatch_hint') or '').strip()
    if dispatch_hint:
        claim_payload['dispatch_hint'] = dispatch_hint
        refreshed_task = json.loads(task_path.read_text(encoding='utf-8'))
        if refreshed_task.get('workspace_dispatch_hint') != dispatch_hint:
            refreshed_task['workspace_dispatch_hint'] = dispatch_hint
            with tempfile.NamedTemporaryFile('w', delete=False, dir=str(task_dir), encoding='utf-8') as tmp:
                json.dump(refreshed_task, tmp, ensure_ascii=False, indent=2)
                tmp.write('\n')
            os.replace(tmp.name, task_path)

    with (task_dir / 'transitions.jsonl').open('a', encoding='utf-8') as fp:
        fp.write(json.dumps({
            'from': 'pooled',
            'to': 'dispatched',
            'at': now,
            'reason': f'agent {agent_id} claimed pooled task' + (f': {reason}' if reason else ''),
        }, ensure_ascii=False) + '\n')
finally:
    try:
        os.close(lock_fd)
    except OSError:
        pass
    try:
        os.close(agent_lock_fd)
    except OSError:
        pass

print(json.dumps(claim_payload, ensure_ascii=False))
PY
