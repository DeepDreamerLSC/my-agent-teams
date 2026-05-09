#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LIB_DIR="${LIB_DIR:-$SCRIPT_DIR/lib}"

TASK_DIR=""
SUMMARY=""
REASON="manual close via close-task.sh"
DRY_RUN=0

usage() {
  cat <<'USAGE'
usage: close-task.sh --task-dir <task-dir> [--summary <summary>] [--reason <reason>] [--dry-run]

Options:
  --task-dir   任务目录绝对路径（必须包含 task.json）
  --summary    写回 task.json.result_summary 的摘要
  --reason     记录到 transitions.jsonl 的原因（默认: manual close via close-task.sh）
  --dry-run    仅展示将要执行的变更，不落盘
  -h, --help   显示帮助
USAGE
}

while [ $# -gt 0 ]; do
  case "$1" in
    --task-dir)
      TASK_DIR="${2:-}"
      shift 2
      ;;
    --summary)
      SUMMARY="${2:-}"
      shift 2
      ;;
    --reason)
      REASON="${2:-}"
      shift 2
      ;;
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [ -z "$TASK_DIR" ]; then
  echo "missing required option: --task-dir" >&2
  usage >&2
  exit 2
fi

python3 - "$TASK_DIR" "$SUMMARY" "$REASON" "$DRY_RUN" "$LIB_DIR" <<'PY'
import json
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path

sys.path.insert(0, sys.argv[5])
import task_artifacts  # type: ignore


def fail(message: str, exit_code: int = 1) -> None:
    print(message, file=sys.stderr)
    raise SystemExit(exit_code)


def load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except FileNotFoundError:
        fail(f'missing file: {path}')
    except json.JSONDecodeError as exc:
        fail(f'invalid json: {path}: {exc}')

def parse_review_state(task_dir: Path, review_level: str) -> str:
    review = task_artifacts.parse_review(task_dir)
    normalized = str(review.get('normalized_status') or '').strip().lower()
    if normalized == 'approve':
        return 'pass'
    if normalized in {'request_changes', 'blocked'}:
        return 'fail'
    if normalized in {'pending', 'missing'}:
        return 'pending'
    return 'pending'


def parse_verify_state(task_dir: Path) -> str:
    verify = task_artifacts.parse_verify(task_dir)
    normalized = str(verify.get('normalized_status') or '').strip().lower()
    if normalized == 'pass':
        return 'pass'
    if normalized in {'fail', 'blocked'}:
        return 'fail'
    if normalized in {'missing', 'pending'}:
        return 'missing'
    return 'pending'


task_dir = Path(sys.argv[1]).expanduser().resolve()
summary_arg = sys.argv[2]
reason = sys.argv[3].strip() or 'manual close via close-task.sh'
dry_run = sys.argv[4] == '1'

task_json_path = task_dir / 'task.json'
transitions_path = task_dir / 'transitions.jsonl'

if not task_dir.is_dir():
    fail(f'task directory not found: {task_dir}')
if not task_json_path.exists():
    fail(f'missing file: {task_json_path}')

task = load_json(task_json_path)
current_status = str(task.get('status') or '')
if current_status != 'ready_for_merge':
    fail(f'task status must be ready_for_merge, got: {current_status or "<empty>"}')

review_required = bool(task.get('review_required'))
test_required = bool(task.get('test_required'))
review_level = str(task.get('review_level') or '').strip().lower()
merge_gate_state = str(task.get('merge_gate_state') or '').strip()
review_state = parse_review_state(task_dir, review_level)
verify_state = parse_verify_state(task_dir)

if merge_gate_state == 'review_pending' and not (review_required and review_state == 'pass'):
    fail(f'task merge_gate_state still pending: {merge_gate_state}')
# QA pass is represented by verify.json.  task-watcher may invoke this script
# while task.json still says qa_pending, so allow that single pending gate only
# when the current verify artifact has already passed.
if merge_gate_state == 'qa_pending' and not (test_required and verify_state == 'pass'):
    fail(f'task merge_gate_state still pending: {merge_gate_state}')
if merge_gate_state in {'review_rejected', 'qa_failed'}:
    fail(f'task merge_gate_state is rejected/failed: {merge_gate_state}')
if review_required and review_state != 'pass':
    fail(f'review is not approved: {review_state}')
if test_required and verify_state != 'pass':
    fail(f'qa verify is not passed: {verify_state}')

summary = summary_arg.strip() if summary_arg.strip() else str(task.get('result_summary') or '').strip()
if not summary:
    fail('result_summary is empty; provide --summary or ensure task.json.result_summary already has a value')

now = datetime.now().astimezone().isoformat(timespec='seconds')
transition = {
    'from': 'ready_for_merge',
    'to': 'done',
    'at': now,
    'reason': reason,
}
updated_task = dict(task)
updated_task['status'] = 'done'
updated_task['updated_at'] = now
updated_task['result_summary'] = summary
updated_task['merge_gate_state'] = 'closed'
updated_task['rework_reason'] = None
updated_task['last_gate_actor'] = 'watcher' if 'watcher' in reason else 'pm-chief'
updated_task['last_gate_decision_at'] = now

preview = {
    'task_dir': str(task_dir),
    'dry_run': dry_run,
    'status_before': current_status,
    'status_after': 'done',
    'updated_at': now,
    'result_summary': summary,
    'review_state': review_state,
    'verify_state': verify_state,
    'merge_gate_state_after': 'closed',
    'transition': transition,
}
print(json.dumps(preview, ensure_ascii=False, indent=2))

if dry_run:
    raise SystemExit(0)

with tempfile.NamedTemporaryFile('w', delete=False, dir=str(task_json_path.parent), encoding='utf-8') as tmp:
    json.dump(updated_task, tmp, ensure_ascii=False, indent=2)
    tmp.write('\n')
tmp_path = Path(tmp.name)
os.replace(tmp_path, task_json_path)
with transitions_path.open('a', encoding='utf-8') as fp:
    fp.write(json.dumps(transition, ensure_ascii=False) + '\n')
PY
