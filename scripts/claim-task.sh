#!/bin/bash
set -euo pipefail

TASK_ID="${1:-}"
REASON="${2:-}"
WORKSPACE_ROOT="${WORKSPACE_ROOT:-$HOME/Desktop/work/my-agent-teams}"
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

python3 - "$TASK_DIR" "$AGENT_ID" "$REASON" "$TASKS_ROOT" "$CONFIG_PATH" <<'PY'
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

task_path = task_dir / 'task.json'
task = json.loads(task_path.read_text(encoding='utf-8'))
config = json.loads(config_path.read_text(encoding='utf-8'))

status = str(task.get('status') or '')
if status != 'pooled':
    raise SystemExit(f'task status must be pooled to claim, got {status}')

claim_scope = [str(item).strip() for item in (task.get('claim_scope') or []) if str(item).strip()]
if claim_scope and agent_id not in claim_scope:
    raise SystemExit(f'agent {agent_id} is not in claim_scope: {claim_scope}')

policy = str(task.get('dependency_policy') or 'done_only').strip().lower()
allowed = {'done', 'cancelled'}
if policy == 'ready_for_merge_ok':
    allowed.add('ready_for_merge')
for dep in task.get('depends_on') or []:
    dep_path = tasks_root / dep / 'task.json'
    if not dep_path.exists():
        raise SystemExit(f'dependency task missing: {dep}')
    dep = json.loads(dep_path.read_text(encoding='utf-8'))
    if str(dep.get('status') or '') not in allowed:
        raise SystemExit(f'dependency not ready: {dep_path.parent.name}={dep.get("status")}')

max_concurrency = int(task.get('claim_max_concurrency') or config.get('task_pool', {}).get('default_claim_max_concurrency', 1))
active_count = 0
working_count = 0
target_scope = [str(item).strip() for item in (task.get('write_scope') or []) if str(item).strip()]
resolved_target_scope = [Path(item).expanduser().resolve() for item in target_scope]

def is_relative_to(path: Path, other: Path) -> bool:
    try:
        path.relative_to(other)
        return True
    except ValueError:
        return False

def scopes_overlap(a: Path, b: Path) -> bool:
    return a == b or is_relative_to(a, b) or is_relative_to(b, a)

for other_path in tasks_root.glob('*/task.json'):
    other = json.loads(other_path.read_text(encoding='utf-8'))
    if str(other.get('assigned_agent') or '') != agent_id:
        continue
    if str(other.get('status') or '') not in {'dispatched', 'working'}:
        continue
    active_count += 1
    if str(other.get('status') or '') == 'working':
        working_count += 1
    for raw in (other.get('write_scope') or []):
        if not str(raw).strip():
            continue
        other_scope = Path(str(raw).strip()).expanduser().resolve()
        for target_scope_item in resolved_target_scope:
            if scopes_overlap(target_scope_item, other_scope):
                raise SystemExit(f'write_scope conflict with active task: {other_path.parent.name}')

if working_count >= 1:
    raise SystemExit(f'agent {agent_id} already has a working task')
if active_count >= max_concurrency:
    raise SystemExit(f'agent {agent_id} already reached claim_max_concurrency={max_concurrency}')

claim_path = task_dir / 'claim.json'
claim_payload = {
    'task_id': str(task.get('id') or task_dir.name),
    'agent': agent_id,
    'claimed_at': datetime.now().astimezone().isoformat(timespec='seconds'),
}
if reason:
    claim_payload['reason'] = reason

lock_path = task_dir / '.claim.lock'
lock_fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o644)
try:
    import fcntl
    fcntl.flock(lock_fd, fcntl.LOCK_EX)

    task = json.loads(task_path.read_text(encoding='utf-8'))
    current_status = str(task.get('status') or '')
    if current_status != 'pooled':
        raise SystemExit(f'task status changed while claiming: {current_status}')

    with tempfile.NamedTemporaryFile('w', delete=False, dir=str(task_dir), encoding='utf-8') as tmp:
        json.dump(claim_payload, tmp, ensure_ascii=False, indent=2)
        tmp.write('\n')
    os.replace(tmp.name, claim_path)

    now = datetime.now().astimezone().isoformat(timespec='seconds')
    task['assigned_agent'] = agent_id
    task['status'] = 'dispatched'
    task['updated_at'] = now
    task['lease_owner'] = task.get('owner_pm')
    task['lease_acquired_at'] = now
    task['lease_expires_at'] = now
    task['claimed_by'] = agent_id
    task['claimed_at'] = claim_payload['claimed_at']
    task['claim_reason'] = reason or None
    task_path.write_text(json.dumps(task, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

    with (task_dir / 'transitions.jsonl').open('a', encoding='utf-8') as fp:
        fp.write(json.dumps({
            'from': 'pooled',
            'to': 'dispatched',
            'at': now,
            'reason': f'agent {agent_id} claimed pooled task',
        }, ensure_ascii=False) + '\n')
finally:
    try:
        os.close(lock_fd)
    except OSError:
        pass

print(json.dumps(claim_payload, ensure_ascii=False))
PY
