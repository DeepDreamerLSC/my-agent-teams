#!/bin/bash
set -euo pipefail

WORKSPACE_ROOT="${WORKSPACE_ROOT:-$HOME/Desktop/work/my-agent-teams}"
CHAT_ROOT="${CHAT_ROOT:-$WORKSPACE_ROOT/chat}"
CHANNEL="${1:-}"
if [ -z "$CHANNEL" ]; then
  echo "usage: read-chat.sh <general|task|watcher|dispatch|nudge> [task-id] [--date YYYY-MM-DD] [--limit N] [--raw]" >&2
  exit 2
fi
shift || true

TASK_ID=""
DATE_OVERRIDE="$(date +%F)"
LIMIT="20"
RAW="false"

case "$CHANNEL" in
  general)
    ;;
  task)
    TASK_ID="${1:-}"
    if [ -z "$TASK_ID" ]; then
      echo "task channel requires <task-id>" >&2
      exit 2
    fi
    shift || true
    ;;
  watcher|dispatch|nudge)
    ;;
  *)
    echo "unknown channel: $CHANNEL" >&2
    exit 2
    ;;
esac

while [ $# -gt 0 ]; do
  case "$1" in
    --date)
      DATE_OVERRIDE="${2:-}"
      shift 2
      ;;
    --limit)
      LIMIT="${2:-}"
      shift 2
      ;;
    --raw)
      RAW="true"
      shift
      ;;
    *)
      echo "unknown option: $1" >&2
      exit 2
      ;;
  esac
done

case "$CHANNEL" in
  general)
    TARGET_FILE="$CHAT_ROOT/general/${DATE_OVERRIDE}.jsonl"
    ;;
  task)
    TARGET_FILE="$CHAT_ROOT/tasks/${TASK_ID}.jsonl"
    ;;
  watcher)
    TARGET_FILE="$CHAT_ROOT/system/watcher/${DATE_OVERRIDE}.jsonl"
    ;;
  dispatch)
    TARGET_FILE="$CHAT_ROOT/system/dispatch/${DATE_OVERRIDE}.jsonl"
    ;;
  nudge)
    TARGET_FILE="$CHAT_ROOT/system/direct_nudge/${DATE_OVERRIDE}.jsonl"
    ;;
esac

python3 - "$TARGET_FILE" "$LIMIT" "$RAW" <<'PY'
import json
import sys
from pathlib import Path

target = Path(sys.argv[1])
limit = max(1, int(sys.argv[2]))
raw = sys.argv[3].strip().lower() == 'true'

if not target.exists():
    raise SystemExit(f'chat file not found: {target}')

lines = [line for line in target.read_text(encoding='utf-8').splitlines() if line.strip()]
rows = []
for idx, line in enumerate(lines, start=1):
    try:
        row = json.loads(line)
    except json.JSONDecodeError as exc:
        raise SystemExit(f'invalid json at line {idx}: {exc}') from exc
    rows.append(row)

rows = rows[-limit:]
if raw:
    for row in rows:
        print(json.dumps(row, ensure_ascii=False))
    raise SystemExit(0)

for row in rows:
    header = f"[{row.get('ts','?')}] {row.get('from','?')} -> {row.get('to','?')} type={row.get('type','text')}"
    if row.get('source_type'):
        header += f" source={row['source_type']}"
    if row.get('event_class'):
        header += f" class={row['event_class']}"
    if row.get('priority'):
        header += f" priority={row['priority']}"
    if row.get('severity'):
        header += f" severity={row['severity']}"
    if row.get('task_id'):
        header += f" task={row['task_id']}"
    print(header)
    if row.get('schema_version') is not None:
        print(f"  schema_version: {row['schema_version']}")
    if row.get('channel'):
        print(f"  channel: {row['channel']}")
    if row.get('source_name'):
        print(f"  source_name: {row['source_name']}")
    if row.get('source_msg_id'):
        print(f"  source_msg_id: {row['source_msg_id']}")
    if row.get('reply_to'):
        print(f"  reply_to: {row['reply_to']}")
    print(f"  {row.get('msg','')}")
    print()
PY
