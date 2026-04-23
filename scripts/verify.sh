#!/bin/bash
set -euo pipefail

TASK_FILE="${1:-}"
if [ -z "$TASK_FILE" ]; then
  echo "usage: verify.sh <task.json>" >&2
  exit 2
fi

python3 - "$TASK_FILE" <<'PY'
import json
import sys
from datetime import datetime
from fnmatch import fnmatch
from pathlib import Path


def load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except FileNotFoundError:
        raise SystemExit(f"missing file: {path}")
    except json.JSONDecodeError as exc:
        raise SystemExit(f"invalid json: {path}: {exc}")


def is_iso8601(value: str) -> bool:
    try:
        datetime.fromisoformat(value.replace('Z', '+00:00'))
        return True
    except Exception:
        return False


def path_allowed(path: str, patterns: list[str]) -> bool:
    normalized = path.strip()
    if not normalized:
        return False
    for pattern in patterns:
        if fnmatch(normalized, pattern) or normalized == pattern:
            return True
    return False


task_path = Path(sys.argv[1]).resolve()
task_dir = task_path.parent
ack_path = task_dir / 'ack.json'
result_path = task_dir / 'result.json'
verify_path = task_dir / 'verify.json'

task = load_json(task_path)
ack = load_json(ack_path)
result = load_json(result_path)

errors: list[str] = []
notes: list[str] = []

required_task = [
    'id', 'title', 'status', 'task_level', 'owner_pm', 'assigned_agent',
    'domain', 'write_scope', 'depends_on', 'blocks', 'artifacts',
    'review_required', 'reviewer', 'test_required'
]
for key in required_task:
    if key not in task:
        errors.append(f'task missing field: {key}')

if ack.get('task_id') != task.get('id'):
    errors.append('ack.task_id mismatch')
if ack.get('agent') != task.get('assigned_agent'):
    errors.append('ack.agent mismatch with assigned_agent')
if not isinstance(ack.get('acked_at'), str) or not is_iso8601(ack['acked_at']):
    errors.append('ack.acked_at invalid')

if result.get('task_id') != task.get('id'):
    errors.append('result.task_id mismatch')
if result.get('agent') != task.get('assigned_agent'):
    errors.append('result.agent mismatch with assigned_agent')
if result.get('status') not in {'ready_for_merge', 'blocked', 'failed'}:
    errors.append('result.status invalid')
if not isinstance(result.get('summary'), str) or not result['summary'].strip():
    errors.append('result.summary missing')
files_modified = result.get('files_modified')
if not isinstance(files_modified, list):
    errors.append('result.files_modified must be array')
    files_modified = []

write_scope = task.get('write_scope') or []
if not isinstance(write_scope, list):
    errors.append('task.write_scope must be array')
    write_scope = []

for changed in files_modified:
    if not isinstance(changed, str) or not changed.strip():
        errors.append('result.files_modified contains invalid item')
        continue
    if not path_allowed(changed, write_scope):
        errors.append(f'write_scope violation: {changed}')

if task.get('review_required') and not (task.get('reviewer') or '').strip():
    errors.append('review_required=true but reviewer missing')

ok = not errors
if ok:
    notes.append('ack exists and matches assigned_agent')
    notes.append('result structure valid')
    notes.append('files_modified within write_scope')

verify = {
    'task_id': task.get('id'),
    'verified_at': datetime.now().astimezone().isoformat(timespec='seconds'),
    'ok': ok,
    'actual_files': files_modified,
    'diff_base': task.get('base_commit'),
    'notes': notes if ok else errors
}
verify_path.write_text(json.dumps(verify, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

if ok:
    print(f'OK {task.get("id")}')
    sys.exit(0)
print(f'FAILED {task.get("id")}')
for item in errors:
    print(f'- {item}')
sys.exit(1)
PY
