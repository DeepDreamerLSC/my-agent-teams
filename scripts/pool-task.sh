#!/bin/bash
set -euo pipefail

TASK_FILE="${1:-}"
WORKSPACE_ROOT="${WORKSPACE_ROOT:-$HOME/Desktop/work/my-agent-teams}"
CONFIG_PATH="${CONFIG_PATH:-$WORKSPACE_ROOT/config.json}"
SEND_CHAT_SCRIPT="${SEND_CHAT_SCRIPT:-$WORKSPACE_ROOT/scripts/send-chat.sh}"
SEND_SCRIPT="${SEND_SCRIPT:-$WORKSPACE_ROOT/scripts/send-to-agent.sh}"
FORCE_RESET_ACTIVE="${FORCE_RESET_ACTIVE:-0}"

if [ -z "$TASK_FILE" ]; then
  echo "usage: pool-task.sh <task.json>" >&2
  exit 2
fi

POOL_OUTPUT=$(python3 - "$TASK_FILE" "$CONFIG_PATH" "$FORCE_RESET_ACTIVE" <<'PY'
import json
import os
import sys
from datetime import datetime
from pathlib import Path

AUTO_ASSIGNED = {'auto', 'auto-dev', 'unassigned'}

task_path = Path(sys.argv[1]).resolve()
config_path = Path(sys.argv[2]).resolve()
force_reset_active = str(sys.argv[3]).strip().lower() in {'1', 'true', 'yes', 'y'}
task = json.loads(task_path.read_text(encoding='utf-8'))
config = json.loads(config_path.read_text(encoding='utf-8'))
task_dir = task_path.parent

instruction_path = task_dir / 'instruction.md'
if not instruction_path.exists():
    raise SystemExit(f'missing instruction.md: {instruction_path}')
instruction_text = instruction_path.read_text(encoding='utf-8')
required_sections = ['任务类型', '目标', '任务边界', '输入事实', '约束', '交付物', '验收标准', '下游动作']
for name in required_sections:
    marker = f'## {name}'
    if marker not in instruction_text:
        raise SystemExit(f'instruction.md missing required section: {name}')
    if '待 PM 填写' in instruction_text.split(marker, 1)[1].split('## ', 1)[0]:
        raise SystemExit(f'instruction.md contains placeholder in section: {name}')

current_status = str(task.get('status') or '')
if current_status not in {'pending', 'dispatched', 'working', 'blocked'}:
    raise SystemExit(f'task status must be pending/dispatched/working/blocked to enter pool, got {current_status}')

task_type = str(task.get('task_type') or '').strip().lower()
execution_mode = str(task.get('execution_mode') or '').strip().lower()
target_environment = str(task.get('target_environment') or '').strip().lower()
task_level = str(task.get('task_level') or '').strip().lower()
assigned_agent = str(task.get('assigned_agent') or '').strip()

if task_type in {'deployment', 'integration'} or execution_mode == 'deploy' or target_environment == 'prod' or task_level == 'integration':
    raise SystemExit('special tasks (deployment/integration/prod) must not enter the general claim pool')

if task.get('claim_policy') == 'push' and assigned_agent not in AUTO_ASSIGNED:
    raise SystemExit('direct-push task must not enter pool without switching assigned_agent to auto/auto-dev')

if current_status in {'dispatched', 'working', 'blocked'} and not force_reset_active:
    raise SystemExit(f'task is {current_status}; set FORCE_RESET_ACTIVE=1 to requeue active task')

now = datetime.now().astimezone().isoformat(timespec='seconds')
archived = []
if force_reset_active:
    for name in ('ack.json', 'claim.json'):
        src = task_dir / name
        if src.exists():
            dst = task_dir / f'{name}.requeued-{datetime.now().strftime("%Y%m%dT%H%M%S")}'
            os.replace(src, dst)
            archived.append(str(dst.name))

if assigned_agent not in AUTO_ASSIGNED:
    task['assigned_agent'] = 'auto'

if not task.get('claim_scope'):
    if task_type == 'verification':
        task['claim_scope'] = ['qa-1']
    elif task_type == 'design':
        task['claim_scope'] = ['arch-1']
    else:
        task['claim_scope'] = ['dev-1', 'dev-2']

task['claim_policy'] = 'pull'
task['claim_max_concurrency'] = int(task.get('claim_max_concurrency') or config.get('task_pool', {}).get('default_claim_max_concurrency', 1))
task['dependency_policy'] = str(task.get('dependency_policy') or 'done_only')
task['pool_timeout_minutes'] = int(task.get('pool_timeout_minutes') or config.get('task_pool', {}).get('default_pool_timeout_minutes', 120))
task['pool_entered_at'] = now
task['claimed_by'] = None
task['claimed_at'] = None
task['claim_reason'] = None
task['status'] = 'pooled'
task['updated_at'] = now

with (task_dir / 'transitions.jsonl').open('a', encoding='utf-8') as fp:
    fp.write(json.dumps({
        'from': current_status,
        'to': 'pooled',
        'at': now,
        'reason': 'pm queued task into claim pool',
    }, ensure_ascii=False) + '\n')
task_path.write_text(json.dumps(task, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps({
    'task_id': task.get('id') or task_dir.name,
    'task_dir': str(task_dir),
    'claim_scope': task.get('claim_scope') or [],
    'priority': task.get('priority') or '',
    'archived': archived,
}, ensure_ascii=False))
PY
)

TASK_ID=$(python3 -c 'import json,sys; print(json.load(sys.stdin)["task_id"])' <<< "$POOL_OUTPUT")
TASK_DIR=$(python3 -c 'import json,sys; print(json.load(sys.stdin)["task_dir"])' <<< "$POOL_OUTPUT")
PRIORITY=$(python3 -c 'import json,sys; print(json.load(sys.stdin)["priority"])' <<< "$POOL_OUTPUT")
echo "pooled ${TASK_ID}"

if [ -x "$SEND_CHAT_SCRIPT" ]; then
  TITLE=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1], encoding="utf-8")).get("title") or "")' "$TASK_DIR/task.json")
  ANNOUNCE_MESSAGE="任务入池：${TITLE}（待认领）"
  TASKS_ROOT="${WORKSPACE_ROOT}/tasks" CHAT_FROM="pm-chief" "$SEND_CHAT_SCRIPT" announce "$TASK_ID" "$ANNOUNCE_MESSAGE" --priority "${PRIORITY:-medium}" >/dev/null 2>&1 || true
fi

if [ -x "$SEND_SCRIPT" ] && [ "$PRIORITY" = "critical" ]; then
  while IFS= read -r agent; do
    [ -n "$agent" ] || continue
    CONFIG_PATH="$CONFIG_PATH" "$SEND_SCRIPT" "$agent" "任务池有 critical 任务待认领：${TASK_ID}。请检查 ${TASK_DIR}/instruction.md 与 claim_scope 后决定是否认领。" >/dev/null 2>&1 || true
  done < <(python3 -c 'import json,sys; [print(x) for x in (json.load(sys.stdin).get("claim_scope") or [])]' <<< "$POOL_OUTPUT")
fi
