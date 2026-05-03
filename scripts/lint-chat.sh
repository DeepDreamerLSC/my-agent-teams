#!/bin/bash
set -euo pipefail

WORKSPACE_ROOT="${WORKSPACE_ROOT:-$HOME/Desktop/work/my-agent-teams}"
CHAT_ROOT="${CHAT_ROOT:-$WORKSPACE_ROOT/chat}"
CONFIG_PATH="${CONFIG_PATH:-$WORKSPACE_ROOT/config.json}"
TARGET="${1:-$CHAT_ROOT}"
STRICT_SCHEMA="${STRICT_SCHEMA:-0}"

python3 - "$TARGET" "$CONFIG_PATH" "$STRICT_SCHEMA" <<'PY'
import json
import sys
from datetime import datetime
from pathlib import Path

ALLOWED_TYPES = {'text', 'task_announce', 'task_done', 'question', 'answer', 'decision', 'notify', 'dispatch', 'nudge'}
ALLOWED_SOURCE_TYPES = {'human', 'system'}
ALLOWED_PRIORITIES = {'low', 'medium', 'high', 'critical'}
ALLOWED_SEVERITIES = {'info', 'degraded', 'critical'}
ALLOWED_EVENT_CLASSES = {'message', 'task_marker', 'system_notice', 'delivery'}
REQUIRED_FIELDS = {'msg_id', 'ts', 'from', 'to', 'source_type', 'type', 'msg'}
SYSTEM_ACTORS = {'system', 'task-watcher', 'dispatch-task', 'send-to-agent', 'chat-metrics'}

root = Path(sys.argv[1]).resolve()
config_path = Path(sys.argv[2]).resolve()
strict_schema = str(sys.argv[3]).strip() in {'1', 'true', 'yes'}
agent_ids = {'pm-chief', 'all', 'kael', 'linsceo'}
if config_path.exists():
    cfg = json.loads(config_path.read_text(encoding='utf-8'))
    agent_ids.update((cfg.get('agents') or {}).keys())
agent_ids.update(SYSTEM_ACTORS)

files = []
if root.is_file():
    files = [root]
elif root.is_dir():
    files = sorted(root.rglob('*.jsonl'))
else:
    raise SystemExit(f'chat path not found: {root}')

errors = []
warnings = []

def infer_channel(path: Path) -> str:
    parts = path.parts
    if 'general' in parts:
        return 'general'
    if 'tasks' in parts:
        return 'task'
    if 'watcher' in parts:
        return 'watcher'
    if 'dispatch' in parts:
        return 'dispatch'
    if 'direct_nudge' in parts:
        return 'direct_nudge'
    return 'unknown'

for file_path in files:
    seen_ids = set()
    expected_task_id = file_path.stem if 'tasks' in file_path.parts else None
    inferred_channel = infer_channel(file_path)
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
        if row.get('severity') and row['severity'] not in ALLOWED_SEVERITIES:
            errors.append(f'{location}: invalid severity {row["severity"]}')
        if row.get('event_class') and row['event_class'] not in ALLOWED_EVENT_CLASSES:
            errors.append(f'{location}: invalid event_class {row["event_class"]}')
        if row['type'] == 'answer' and not row.get('reply_to'):
            errors.append(f'{location}: answer requires reply_to')
        if row['type'] in {'task_announce', 'task_done', 'decision', 'notify', 'dispatch', 'nudge'} and not row.get('task_id'):
            errors.append(f'{location}: {row["type"]} requires task_id')
        if expected_task_id and row.get('task_id') and row.get('task_id') != expected_task_id:
            errors.append(f'{location}: task_id {row.get("task_id")} does not match file {expected_task_id}')

        schema_version = row.get('schema_version')
        if schema_version is None:
            message = f'{location}: missing schema_version (legacy v0 tolerated)'
            if strict_schema or row.get('source_type') == 'system':
                errors.append(message)
            else:
                warnings.append(message)
        else:
            if not isinstance(schema_version, int) or schema_version < 1:
                errors.append(f'{location}: invalid schema_version {schema_version!r}')

        if row.get('channel'):
            expected_channel = inferred_channel
            if row['channel'] != expected_channel and not (row['channel'] == 'task' and inferred_channel == 'task'):
                errors.append(f'{location}: channel {row["channel"]} does not match path channel {expected_channel}')
        elif strict_schema:
            errors.append(f'{location}: missing channel')
        else:
            warnings.append(f'{location}: missing channel (legacy tolerated)')

        if row['source_type'] == 'system':
            if not row.get('source_name'):
                errors.append(f'{location}: system event requires source_name')
            if not row.get('severity'):
                errors.append(f'{location}: system event requires severity')
            if not row.get('event_class'):
                errors.append(f'{location}: system event requires event_class')
            elif row['event_class'] not in {'system_notice', 'delivery'}:
                errors.append(f'{location}: system event_class must be system_notice or delivery')
        else:
            if row.get('event_class') and row['event_class'] not in {'message', 'task_marker'}:
                errors.append(f'{location}: human event_class must be message or task_marker')

        for field in ('from', 'to'):
            value = str(row.get(field, '')).strip()
            if row['source_type'] == 'system' and field == 'from':
                if value not in agent_ids and not row.get('source_name'):
                    errors.append(f'{location}: unknown system from {value}')
                continue
            if value not in agent_ids:
                errors.append(f'{location}: unknown {field} {row.get(field)}')

        if inferred_channel in {'watcher', 'dispatch', 'direct_nudge'}:
            if row['source_type'] != 'system':
                errors.append(f'{location}: system channel requires source_type=system')
            if not row.get('task_id'):
                errors.append(f'{location}: system channel requires task_id')

if errors:
    print('Chat lint failed:')
    for item in errors:
        print(f'- {item}')
    if warnings:
        print('Warnings:')
        for item in warnings:
            print(f'- {item}')
    raise SystemExit(1)

print(f'Chat lint passed ({len(files)} file(s) checked)')
if warnings:
    print('Warnings:')
    for item in warnings:
        print(f'- {item}')
PY
