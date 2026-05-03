#!/bin/bash
set -euo pipefail

WORKSPACE_ROOT="${WORKSPACE_ROOT:-$HOME/Desktop/work/my-agent-teams}"
CHAT_ROOT="${CHAT_ROOT:-$WORKSPACE_ROOT/chat}"
DAYS="1"
LIMIT="20"
SHOW_ALL="false"

while [ $# -gt 0 ]; do
  case "$1" in
    --days)
      DAYS="${2:-1}"
      shift 2
      ;;
    --limit)
      LIMIT="${2:-20}"
      shift 2
      ;;
    --all)
      SHOW_ALL="true"
      shift
      ;;
    *)
      echo "unknown option: $1" >&2
      exit 2
      ;;
  esac
done

python3 - "$CHAT_ROOT" "$DAYS" "$LIMIT" "$SHOW_ALL" <<'PY'
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

chat_root = Path(sys.argv[1])
days = max(1, int(sys.argv[2]))
limit = max(1, int(sys.argv[3]))
show_all = sys.argv[4].strip().lower() == 'true'
cutoff = datetime.now().astimezone() - timedelta(days=days)

files = []
for path in sorted((chat_root / 'general').glob('*.jsonl')):
    files.append(path)
for path in sorted((chat_root / 'tasks').glob('*.jsonl')):
    if datetime.fromtimestamp(path.stat().st_mtime).astimezone() >= cutoff:
        files.append(path)

items = []
for path in files:
    for idx, line in enumerate(path.read_text(encoding='utf-8').splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        row['_file'] = str(path)
        row['_line'] = idx
        ts = row.get('ts')
        try:
            row['_ts_dt'] = datetime.fromisoformat(ts.replace('Z', '+00:00')).astimezone() if ts else cutoff
        except Exception:
            row['_ts_dt'] = cutoff
        items.append(row)

items.sort(key=lambda row: row.get('_ts_dt'))

def is_actionable(row):
    if show_all:
        return True
    if row.get('to') == 'pm-chief':
        return True
    msg = str(row.get('msg') or '')
    if '@pm-chief' in msg:
        return True
    if row.get('priority') == 'critical':
        return True
    if row.get('type') == 'decision':
        return True
    if row.get('type') in {'question', 'task_done'} and row.get('task_id'):
        return True
    return False

filtered = [row for row in items if row.get('_ts_dt') >= cutoff and is_actionable(row)]
filtered = filtered[-limit:]

print(f'PM Chat Check | days={days} | actionable={len(filtered)}')
for row in filtered:
    location = f"{Path(row['_file']).name}:{row['_line']}"
    header = f"[{row.get('ts','?')}] {row.get('from','?')} -> {row.get('to','?')} type={row.get('type','text')}"
    if row.get('priority'):
        header += f" priority={row['priority']}"
    if row.get('task_id'):
        header += f" task={row['task_id']}"
    print(header)
    print(f"  file: {location}")
    print(f"  {row.get('msg','')}")
    print()
PY
