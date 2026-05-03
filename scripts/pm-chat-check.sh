#!/bin/bash
set -euo pipefail

WORKSPACE_ROOT="${WORKSPACE_ROOT:-$HOME/Desktop/work/my-agent-teams}"
CHAT_ROOT="${CHAT_ROOT:-$WORKSPACE_ROOT/chat}"
DAYS="1"
LIMIT="20"
SHOW_ALL="false"
SEVERITY_FILTER=""
INCLUDE_SYSTEM="true"
SHOW_METRICS="true"

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
    --severity)
      SEVERITY_FILTER="${2:-}"
      shift 2
      ;;
    --no-system)
      INCLUDE_SYSTEM="false"
      shift
      ;;
    --no-metrics)
      SHOW_METRICS="false"
      shift
      ;;
    *)
      echo "unknown option: $1" >&2
      exit 2
      ;;
  esac
done

if [ "$SHOW_METRICS" = "true" ] && [ -x "$WORKSPACE_ROOT/scripts/chat-metrics.py" ]; then
  "$WORKSPACE_ROOT/scripts/chat-metrics.py" --chat-root "$CHAT_ROOT" --days "$DAYS"
  echo
fi

python3 - "$CHAT_ROOT" "$DAYS" "$LIMIT" "$SHOW_ALL" "$SEVERITY_FILTER" "$INCLUDE_SYSTEM" <<'PY'
import json
import sys
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

chat_root = Path(sys.argv[1])
days = max(1, int(sys.argv[2]))
limit = max(1, int(sys.argv[3]))
show_all = sys.argv[4].strip().lower() == 'true'
severity_filter = sys.argv[5].strip()
include_system = sys.argv[6].strip().lower() == 'true'
cutoff = datetime.now().astimezone() - timedelta(days=days)

bases = [chat_root / 'general', chat_root / 'tasks']
if include_system:
    bases.extend([
        chat_root / 'system' / 'watcher',
        chat_root / 'system' / 'dispatch',
        chat_root / 'system' / 'direct_nudge',
    ])

items = []
for base in bases:
    if not base.exists():
        continue
    for path in sorted(base.rglob('*.jsonl')):
        for idx, line in enumerate(path.read_text(encoding='utf-8').splitlines(), start=1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            ts = row.get('ts')
            try:
                row['_ts_dt'] = datetime.fromisoformat(ts.replace('Z', '+00:00')).astimezone() if ts else cutoff
            except Exception:
                row['_ts_dt'] = cutoff
            if row['_ts_dt'] < cutoff:
                continue
            row['_file'] = str(path)
            row['_line'] = idx
            items.append(row)

items.sort(key=lambda row: row.get('_ts_dt'))
answer_reply_ids = {str(row.get('reply_to')) for row in items if row.get('type') == 'answer' and row.get('reply_to')}

summary = Counter()
for row in items:
    if row.get('source_type') == 'system':
        summary['system_event_count'] += 1
    else:
        summary['human_event_count'] += 1
    if row.get('severity') == 'critical':
        summary['critical_event_count'] += 1
    if row.get('type') == 'question' and str(row.get('msg_id')) not in answer_reply_ids:
        summary['unanswered_question_count'] += 1


def is_actionable(row):
    if severity_filter and row.get('severity') != severity_filter:
        return False
    if show_all:
        return True
    if row.get('to') == 'pm-chief':
        return True
    msg = str(row.get('msg') or '')
    if '@pm-chief' in msg:
        return True
    if row.get('priority') == 'critical':
        return True
    if row.get('severity') == 'critical':
        return True
    if row.get('type') == 'decision':
        return True
    if row.get('source_type') == 'system' and row.get('severity') in {'degraded', 'critical'}:
        return True
    if row.get('type') in {'question', 'task_done'} and row.get('task_id'):
        return True
    return False

filtered = [row for row in items if is_actionable(row)]
filtered = filtered[-limit:]

print(f'PM Chat Check | days={days} | actionable={len(filtered)} | human={summary["human_event_count"]} | system={summary["system_event_count"]} | unanswered={summary["unanswered_question_count"]}')
for row in filtered:
    location = f"{Path(row['_file']).name}:{row['_line']}"
    header = f"[{row.get('ts','?')}] {row.get('from','?')} -> {row.get('to','?')} type={row.get('type','text')}"
    if row.get('priority'):
        header += f" priority={row['priority']}"
    if row.get('severity'):
        header += f" severity={row['severity']}"
    if row.get('task_id'):
        header += f" task={row['task_id']}"
    print(header)
    print(f"  file: {location}")
    if row.get('source_name'):
        print(f"  source_name: {row['source_name']}")
    print(f"  {row.get('msg','')}")
    print()
PY
