#!/bin/bash
set -euo pipefail

TASK_DIR=""
WORKSPACE_ROOT="${WORKSPACE_ROOT:-$HOME/Desktop/work/my-agent-teams}"
TASKS_ROOT="${TASKS_ROOT:-$WORKSPACE_ROOT/tasks}"
BOARD_SYNC_SCRIPT="${BOARD_SYNC_SCRIPT:-$WORKSPACE_ROOT/scripts/task-board-sync.py}"

usage() {
  cat <<'EOF'
usage: archive-task.sh --task-dir <task-dir>
EOF
}

while [ $# -gt 0 ]; do
  case "$1" in
    --task-dir) TASK_DIR="${2:-}"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
done

if [ -z "$TASK_DIR" ]; then
  usage >&2
  exit 2
fi

python3 - "$TASK_DIR" "$TASKS_ROOT" "$BOARD_SYNC_SCRIPT" <<'PY'
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding='utf-8'))


def atomic_write(path: Path, payload: dict) -> None:
    with tempfile.NamedTemporaryFile('w', delete=False, dir=str(path.parent), encoding='utf-8') as tmp:
        json.dump(payload, tmp, ensure_ascii=False, indent=2)
        tmp.write('\n')
    os.replace(tmp.name, path)


task_dir = Path(sys.argv[1]).expanduser().resolve()
tasks_root = Path(sys.argv[2]).expanduser().resolve()
board_sync_script = Path(sys.argv[3]).expanduser().resolve()
task_path = task_dir / 'task.json'
transitions_path = task_dir / 'transitions.jsonl'
if not task_path.exists():
    raise SystemExit(f'missing task.json: {task_path}')

task = load_json(task_path)
status = str(task.get('status') or '')
if status not in {'done', 'cancelled', 'archived'}:
    raise SystemExit(f'task status must be done/cancelled/archived to archive, got {status}')

task_id = str(task.get('id') or task_dir.name)
now = datetime.now().astimezone()
now_iso = now.isoformat(timespec='seconds')
archive_bucket = now.strftime('%Y-%m')
archive_root = tasks_root / '_archive' / archive_bucket
archive_root.mkdir(parents=True, exist_ok=True)
archive_dir = archive_root / task_id
if archive_dir.exists():
    raise SystemExit(f'archive target already exists: {archive_dir}')

old_status = status
task['status'] = 'archived'
task['updated_at'] = now_iso
task['last_gate_actor'] = task.get('last_gate_actor') or 'pm-chief'
task['last_gate_decision_at'] = task.get('last_gate_decision_at') or now_iso
atomic_write(task_path, task)
with transitions_path.open('a', encoding='utf-8') as fp:
    fp.write(json.dumps({'from': old_status, 'to': 'archived', 'at': now_iso, 'reason': 'archive-task'}, ensure_ascii=False) + '\n')

shutil.move(str(task_dir), str(archive_dir))

index_dir = tasks_root / '_index'
index_dir.mkdir(parents=True, exist_ok=True)
index_path = index_dir / 'archived-tasks.jsonl'
with index_path.open('a', encoding='utf-8') as fp:
    fp.write(json.dumps({
        'task_id': task_id,
        'title': task.get('title') or task_id,
        'project': task.get('project'),
        'status': 'archived',
        'archived_at': now_iso,
        'archive_path': str(archive_dir),
        'final_summary': task.get('result_summary') or '',
    }, ensure_ascii=False) + '\n')

warning = None
if board_sync_script.exists():
    try:
        subprocess.run(
            [sys.executable, str(board_sync_script), 'sync-task', '--task-dir', str(archive_dir)],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        warning = f'archive synced to filesystem but dashboard db update failed: {exc.stderr or exc.stdout or exc}'

print(json.dumps({'task_id': task_id, 'archive_path': str(archive_dir), 'archived_at': now_iso, 'warning': warning}, ensure_ascii=False))
PY
