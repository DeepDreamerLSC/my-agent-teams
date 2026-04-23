#!/bin/bash
set -euo pipefail
TASK_FILE="${1:-}"
if [ -z "$TASK_FILE" ]; then
  echo "usage: dispatch-task.sh <task.json>" >&2
  exit 2
fi
python3 - "$TASK_FILE" <<'PY'
import json
import sys
from datetime import datetime
from pathlib import Path

task_path = Path(sys.argv[1])
task = json.loads(task_path.read_text(encoding='utf-8'))
if task.get('status') != 'pending':
    raise SystemExit(f"task status is {task.get('status')}, expected pending")
now = datetime.now().astimezone().isoformat(timespec='seconds')
previous = task['status']
task['status'] = 'dispatched'
task['updated_at'] = now
task['lease_owner'] = task.get('owner_pm')
task['lease_acquired_at'] = now
task['lease_expires_at'] = now
(task_path.parent / 'transitions.jsonl').open('a', encoding='utf-8').write(json.dumps({
    'from': previous,
    'to': 'dispatched',
    'at': now,
    'reason': 'pm dispatch'
}, ensure_ascii=False) + '\n')
task_path.write_text(json.dumps(task, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(f"dispatched {task.get('id')}")
PY
