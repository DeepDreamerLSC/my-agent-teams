#!/bin/bash
set -euo pipefail

TASK_DIR=""
AGENT_ID=""
REASON=""
KEEP_RESULT_HISTORY=0
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_ROOT="${WORKSPACE_ROOT:-$(cd "$SCRIPT_DIR/.." && pwd)}"
STATE_DIR="${STATE_DIR:-$WORKSPACE_ROOT/.runtime/state/task-watcher}"
CONFIG_PATH="${CONFIG_PATH:-$WORKSPACE_ROOT/config.json}"
LIB_DIR="${LIB_DIR:-$SCRIPT_DIR/lib}"

usage() {
  cat <<'EOF'
usage: reassign-task.sh --task-dir <task-dir> --agent <agent-id> --reason <reason> [--keep-result-history]
EOF
}

while [ $# -gt 0 ]; do
  case "$1" in
    --task-dir) TASK_DIR="${2:-}"; shift 2 ;;
    --agent) AGENT_ID="${2:-}"; shift 2 ;;
    --reason) REASON="${2:-}"; shift 2 ;;
    --keep-result-history) KEEP_RESULT_HISTORY=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
done

if [ -z "$TASK_DIR" ] || [ -z "$AGENT_ID" ] || [ -z "$REASON" ]; then
  usage >&2
  exit 2
fi

python3 - "$TASK_DIR" "$AGENT_ID" "$REASON" "$STATE_DIR" "$KEEP_RESULT_HISTORY" "$CONFIG_PATH" "$LIB_DIR" <<'PY'
import json
import os
import shutil
import sys
import tempfile
from datetime import datetime
from pathlib import Path


def load_json(path: Path):
    return json.loads(path.read_text(encoding='utf-8'))


def atomic_write(path: Path, payload: dict):
    with tempfile.NamedTemporaryFile('w', delete=False, dir=str(path.parent), encoding='utf-8') as tmp:
        json.dump(payload, tmp, ensure_ascii=False, indent=2)
        tmp.write('\n')
    os.replace(tmp.name, path)


task_dir = Path(sys.argv[1]).expanduser().resolve()
agent_id = sys.argv[2]
reason = sys.argv[3].strip()
state_dir = Path(sys.argv[4]).expanduser().resolve()
keep_result_history = sys.argv[5] == '1'
config_path = Path(sys.argv[6]).expanduser().resolve()
lib_dir = Path(sys.argv[7]).expanduser().resolve()
sys.path.insert(0, str(lib_dir))
from agent_config import load_config, root_pm  # type: ignore

config = load_config(config_path)
root_pm_id = root_pm(config)

task_path = task_dir / 'task.json'
transitions_path = task_dir / 'transitions.jsonl'
if not task_path.exists():
    raise SystemExit(f'missing task.json: {task_path}')

task = load_json(task_path)
old_status = str(task.get('status') or '')
if old_status in {'done', 'cancelled', 'archived'}:
    raise SystemExit(f'task status {old_status} is not reassignable')

previous_agent = str(task.get('assigned_agent') or '')
if previous_agent and previous_agent == agent_id:
    raise SystemExit('reassign target must differ from current assigned_agent')

now = datetime.now().astimezone()
now_iso = now.isoformat(timespec='seconds')
stamp = now.strftime('%Y%m%dT%H%M%S')
history_dir = task_dir / 'history'
history_dir.mkdir(parents=True, exist_ok=True)

record = {
    'task_id': str(task.get('id') or task_dir.name),
    'reassigned_at': now_iso,
    'reassigned_by': 'task-watcher',
    'from_agent': previous_agent,
    'to_agent': agent_id,
    'reason': reason,
    'archived_files': [],
}

archive_names = [
    'ack.json',
    'claim.json',
    'review.json',
    'design-review.json',
    'review.md',
    'design-review.md',
    'verify.json',
]
for name in archive_names:
    src = task_dir / name
    if not src.exists():
        continue
    dst = history_dir / f"{src.stem}.{stamp}{src.suffix}"
    shutil.move(str(src), str(dst))
    record['archived_files'].append(dst.name)

result_path = task_dir / 'result.json'
if result_path.exists():
    dst = history_dir / f"{result_path.stem}.{stamp}{result_path.suffix}"
    if keep_result_history:
        shutil.copy2(str(result_path), str(dst))
        result_path.unlink()
    else:
        shutil.move(str(result_path), str(dst))
    record['archived_files'].append(dst.name)

atomic_write(history_dir / f'reassign.{stamp}.json', record)

prefix = f"{task.get('id') or task_dir.name}_"
clear_keys = {
    f'{prefix}ack',
    f'{prefix}result_route',
    f'{prefix}review_route',
    f'{prefix}verify_route',
    f'{prefix}working_timeout_notice',
    f'{prefix}working_timeout_push',
    f'{prefix}working_timeout_grace_started',
    f'{prefix}review_queue_waiting_notice',
    f'{prefix}qa_queue_waiting_notice',
    f'{prefix}done_notice',
    f'{prefix}resend',
    f'{prefix}control_plane_notice',
    f'{prefix}state_invariant_notice',
    f'{prefix}auto_close_retry',
}
if state_dir.exists():
    for path in state_dir.iterdir():
        base_name = path.name[:-6] if path.name.endswith('.retry') else path.name
        if base_name in clear_keys:
            path.unlink(missing_ok=True)
            continue
        if path.name.startswith(('review-queue-', 'qa-queue-')):
            try:
                payload = load_json(path)
            except Exception:
                path.unlink(missing_ok=True)
                continue
            if str(payload.get('task_id') or '') == record['task_id']:
                path.unlink(missing_ok=True)

resume_round = int(task.get('resume_round') or 0) + 1
reassign_count = int(task.get('reassign_count') or 0) + 1
task['status'] = 'dispatched'
task['assigned_agent'] = agent_id
task['claimed_by'] = agent_id
task['claimed_at'] = now_iso
task['claim_reason'] = f'reassign: {reason}'
task['reserved_by'] = agent_id
task['reserved_at'] = now_iso
task['reserved_reason'] = f'reassign: {reason}'
task['updated_at'] = now_iso
task['merge_gate_state'] = None
task['rework_reason'] = reason
task['last_gate_actor'] = 'task-watcher'
task['last_gate_decision_at'] = now_iso
task['resume_round'] = resume_round
task['last_reassigned_at'] = now_iso
task['last_reassigned_by'] = 'task-watcher'
task['last_reassigned_from'] = previous_agent
task['last_reassigned_reason'] = reason
task['reassign_count'] = reassign_count
task['lease_owner'] = task.get('owner_pm') or root_pm_id
task['lease_acquired_at'] = now_iso
task['lease_expires_at'] = now_iso
task['dispatch_delivery_attempt_count'] = 0
task['dispatch_delivery_retry_count'] = 0
task['dispatch_delivery_consecutive_failures'] = 0
task['last_delivery_attempt_at'] = None
task['last_delivery_error'] = None
task['last_delivery_state'] = None
task['session_health'] = None
task['control_plane_state'] = 'reassigned'
task['control_plane_updated_at'] = now_iso
task['state_invariant_violations'] = []
task['state_invariant_signature'] = ''
task['state_invariant_checked_at'] = now_iso
atomic_write(task_path, task)

with transitions_path.open('a', encoding='utf-8') as fp:
    fp.write(json.dumps({
        'from': old_status,
        'to': 'dispatched',
        'at': now_iso,
        'reason': f'reassign-task: {reason}',
        'actor': 'task-watcher',
    }, ensure_ascii=False) + '\n')

print(json.dumps({
    'task_id': record['task_id'],
    'from_agent': previous_agent,
    'to_agent': agent_id,
    'resume_round': resume_round,
    'archived_files': record['archived_files'],
}, ensure_ascii=False))
PY
