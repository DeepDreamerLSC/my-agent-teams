#!/bin/bash
set -euo pipefail

WORKSPACE_ROOT="${WORKSPACE_ROOT:-$HOME/Desktop/work/my-agent-teams}"
CHAT_ROOT="${CHAT_ROOT:-$WORKSPACE_ROOT/chat}"
CONFIG_PATH="${CONFIG_PATH:-$WORKSPACE_ROOT/config.json}"
TARGET="${1:-$CHAT_ROOT}"

python3 - "$TARGET" "$CONFIG_PATH" <<'PY'
import json
import sys
from datetime import datetime
from pathlib import Path

ALLOWED_TYPES = {'text', 'task_announce', 'task_done', 'question', 'answer', 'decision'}
ALLOWED_SOURCE_TYPES = {'human', 'system'}
ALLOWED_PRIORITIES = {'low', 'medium', 'high', 'critical'}
REQUIRED_FIELDS = {'msg_id', 'ts', 'from', 'to', 'source_type', 'type', 'msg'}

root = Path(sys.argv[1]).resolve()
config_path = Path(sys.argv[2]).resolve()
agent_ids = {'pm-chief'}
if config_path.exists():
    cfg = json.loads(config_path.read_text(encoding='utf-8'))
    agent_ids.update((cfg.get('agents') or {}).keys())
agent_ids.update({'all', 'kael', 'linsceo'})

files = []
if root.is_file():
    files = [root]
elif root.is_dir():
    files = sorted(root.rglob('*.jsonl'))
else:
    raise SystemExit(f'chat path not found: {root}')

errors = []
for file_path in files:
    seen_ids = set()
    expected_task_id = file_path.stem if 'tasks' in file_path.parts else None
    for idx, line in enumerate(file_path.read_text(encoding='utf-8').splitlines(), start=1):
        if not line.strip():
            continue
        location = f'{file_path}:{idx}'
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append(f'{location}: invalid json ({exc})')
            continue
        missing = REQUIRED_FIELDS - row.keys()
        if missing:
            errors.append(f'{location}: missing required fields {sorted(missing)}')
            continue
        if row['msg_id'] in seen_ids:
            errors.append(f'{location}: duplicate msg_id {row["msg_id"]}')
        seen_ids.add(row['msg_id'])
        try:
            datetime.fromisoformat(str(row['ts']).replace('Z', '+00:00'))
        except Exception:
            errors.append(f'{location}: invalid ts {row["ts"]}')
        if row['source_type'] not in ALLOWED_SOURCE_TYPES:
            errors.append(f'{location}: invalid source_type {row["source_type"]}')
        if row['type'] not in ALLOWED_TYPES:
            errors.append(f'{location}: invalid type {row["type"]}')
        if row.get('priority') and row['priority'] not in ALLOWED_PRIORITIES:
            errors.append(f'{location}: invalid priority {row["priority"]}')
        if row['type'] == 'answer' and not row.get('reply_to'):
            errors.append(f'{location}: answer requires reply_to')
        if row['type'] in {'task_announce', 'task_done', 'decision'} and not row.get('task_id'):
            errors.append(f'{location}: {row["type"]} requires task_id')
        if expected_task_id and row.get('task_id') and row.get('task_id') != expected_task_id:
            errors.append(f'{location}: task_id {row.get("task_id")} does not match file {expected_task_id}')
        for field in ('from', 'to'):
            if str(row.get(field, '')).strip() not in agent_ids:
                errors.append(f'{location}: unknown {field} {row.get(field)}')

if errors:
    print('Chat lint failed:')
    for item in errors:
        print(f'- {item}')
    raise SystemExit(1)

print(f'Chat lint passed ({len(files)} file(s) checked)')
PY
