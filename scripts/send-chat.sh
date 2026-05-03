#!/bin/bash
set -euo pipefail

WORKSPACE_ROOT="${WORKSPACE_ROOT:-$HOME/Desktop/work/my-agent-teams}"
CHAT_ROOT="${CHAT_ROOT:-$WORKSPACE_ROOT/chat}"
TASKS_ROOT="${TASKS_ROOT:-$WORKSPACE_ROOT/tasks}"

CHANNEL="${1:-}"
if [ -z "$CHANNEL" ]; then
  echo "usage: send-chat.sh <general|task|announce|watcher|dispatch|nudge> [task-id] <message> [--from <actor>] [--to <target>] [--type <type>] [--priority <priority>] [--severity <severity>] [--reply-to <msg_id>] [--thread-id <thread_id>] [--schema-version <n>] [--source-type <human|system>] [--event-class <class>] [--source-name <name>] [--source-msg-id <id>]" >&2
  exit 2
fi
shift

TASK_ID=""
MESSAGE=""
FILE_CHANNEL=""
DEFAULT_TYPE=""
DEFAULT_SOURCE_TYPE=""
DEFAULT_EVENT_CLASS=""
DEFAULT_SOURCE_NAME=""

case "$CHANNEL" in
  general)
    MESSAGE="${1:-}"
    shift || true
    FILE_CHANNEL="general"
    DEFAULT_TYPE="text"
    DEFAULT_SOURCE_TYPE="human"
    DEFAULT_EVENT_CLASS="message"
    ;;
  task)
    TASK_ID="${1:-}"
    MESSAGE="${2:-}"
    shift 2 || true
    FILE_CHANNEL="task"
    DEFAULT_TYPE="text"
    DEFAULT_SOURCE_TYPE="human"
    DEFAULT_EVENT_CLASS="message"
    ;;
  announce)
    TASK_ID="${1:-}"
    MESSAGE="${2:-}"
    shift 2 || true
    FILE_CHANNEL="task"
    DEFAULT_TYPE="task_announce"
    DEFAULT_SOURCE_TYPE="human"
    DEFAULT_EVENT_CLASS="task_marker"
    ;;
  watcher)
    TASK_ID="${1:-}"
    MESSAGE="${2:-}"
    shift 2 || true
    FILE_CHANNEL="watcher"
    DEFAULT_TYPE="notify"
    DEFAULT_SOURCE_TYPE="system"
    DEFAULT_EVENT_CLASS="system_notice"
    DEFAULT_SOURCE_NAME="task-watcher"
    ;;
  dispatch)
    TASK_ID="${1:-}"
    MESSAGE="${2:-}"
    shift 2 || true
    FILE_CHANNEL="dispatch"
    DEFAULT_TYPE="dispatch"
    DEFAULT_SOURCE_TYPE="system"
    DEFAULT_EVENT_CLASS="system_notice"
    DEFAULT_SOURCE_NAME="dispatch-task"
    ;;
  nudge)
    TASK_ID="${1:-}"
    MESSAGE="${2:-}"
    shift 2 || true
    FILE_CHANNEL="direct_nudge"
    DEFAULT_TYPE="nudge"
    DEFAULT_SOURCE_TYPE="system"
    DEFAULT_EVENT_CLASS="delivery"
    DEFAULT_SOURCE_NAME="send-to-agent"
    ;;
  *)
    echo "unknown channel: $CHANNEL" >&2
    exit 2
    ;;
esac

if [ -z "$MESSAGE" ]; then
  echo "message is required" >&2
  exit 2
fi

if { [ "$CHANNEL" = "task" ] || [ "$CHANNEL" = "announce" ] || [ "$CHANNEL" = "watcher" ] || [ "$CHANNEL" = "dispatch" ] || [ "$CHANNEL" = "nudge" ]; } && [ -z "$TASK_ID" ]; then
  echo "channel $CHANNEL requires <task-id>" >&2
  exit 2
fi

FROM_ID="${CHAT_FROM:-}"
TO_ID="all"
TYPE_OVERRIDE=""
PRIORITY=""
SEVERITY=""
REPLY_TO=""
THREAD_ID=""
SCHEMA_VERSION="1"
SOURCE_TYPE="$DEFAULT_SOURCE_TYPE"
EVENT_CLASS="$DEFAULT_EVENT_CLASS"
SOURCE_NAME="$DEFAULT_SOURCE_NAME"
SOURCE_MSG_ID=""

while [ $# -gt 0 ]; do
  case "$1" in
    --from)
      FROM_ID="${2:-}"
      shift 2
      ;;
    --to)
      TO_ID="${2:-}"
      shift 2
      ;;
    --type)
      TYPE_OVERRIDE="${2:-}"
      shift 2
      ;;
    --priority)
      PRIORITY="${2:-}"
      shift 2
      ;;
    --severity)
      SEVERITY="${2:-}"
      shift 2
      ;;
    --reply-to)
      REPLY_TO="${2:-}"
      shift 2
      ;;
    --thread-id)
      THREAD_ID="${2:-}"
      shift 2
      ;;
    --schema-version)
      SCHEMA_VERSION="${2:-}"
      shift 2
      ;;
    --source-type)
      SOURCE_TYPE="${2:-}"
      shift 2
      ;;
    --event-class)
      EVENT_CLASS="${2:-}"
      shift 2
      ;;
    --source-name)
      SOURCE_NAME="${2:-}"
      shift 2
      ;;
    --source-msg-id)
      SOURCE_MSG_ID="${2:-}"
      shift 2
      ;;
    *)
      echo "unknown option: $1" >&2
      exit 2
      ;;
  esac
done

if [ -z "$FROM_ID" ]; then
  case "$SOURCE_TYPE" in
    system)
      FROM_ID="${SOURCE_NAME:-system}"
      ;;
    *)
      case "$PWD" in
        */agents/*)
          FROM_ID="$(basename "$PWD")"
          ;;
        *)
          FROM_ID="pm-chief"
          ;;
      esac
      ;;
  esac
fi

if [ -z "$SEVERITY" ] && [ "$SOURCE_TYPE" = "system" ]; then
  SEVERITY="info"
fi

mkdir -p "$CHAT_ROOT/general" "$CHAT_ROOT/tasks" "$CHAT_ROOT/system/watcher" "$CHAT_ROOT/system/dispatch" "$CHAT_ROOT/system/direct_nudge"

if [ "$CHANNEL" = "general" ]; then
  TARGET_FILE="$CHAT_ROOT/general/$(date +%F).jsonl"
  THREAD_ID="${THREAD_ID:-general}"
elif [ "$CHANNEL" = "task" ] || [ "$CHANNEL" = "announce" ]; then
  TARGET_FILE="$CHAT_ROOT/tasks/${TASK_ID}.jsonl"
  THREAD_ID="${THREAD_ID:-$TASK_ID}"
else
  TARGET_FILE="$CHAT_ROOT/system/${FILE_CHANNEL}/$(date +%F).jsonl"
  THREAD_ID="${THREAD_ID:-$TASK_ID}"
fi

TYPE="${TYPE_OVERRIDE:-$DEFAULT_TYPE}"

python3 - "$TARGET_FILE" "$FROM_ID" "$TO_ID" "$TYPE" "$MESSAGE" "$TASK_ID" "$PRIORITY" "$SEVERITY" "$REPLY_TO" "$THREAD_ID" "$CHANNEL" "$TASKS_ROOT" "$SCHEMA_VERSION" "$SOURCE_TYPE" "$EVENT_CLASS" "$SOURCE_NAME" "$SOURCE_MSG_ID" <<'PY'
import json
import os
import random
import sys
from datetime import datetime
from pathlib import Path

target_file = Path(sys.argv[1])
from_id = sys.argv[2]
to_id = sys.argv[3]
msg_type = sys.argv[4]
msg = sys.argv[5]
task_id = sys.argv[6]
priority = sys.argv[7]
severity = sys.argv[8]
reply_to = sys.argv[9]
thread_id = sys.argv[10]
channel = sys.argv[11]
tasks_root = Path(sys.argv[12])
schema_version_raw = sys.argv[13]
source_type = sys.argv[14]
event_class = sys.argv[15]
source_name = sys.argv[16]
source_msg_id = sys.argv[17]

PLACEHOLDER_MARKERS = {'（待 PM 填写）', '(待 PM 填写)', '待 PM 填写'}
ALLOWED_TYPES = {'text', 'task_announce', 'task_done', 'question', 'answer', 'decision', 'notify', 'dispatch', 'nudge'}
ALLOWED_SOURCE_TYPES = {'human', 'system'}
ALLOWED_PRIORITIES = {'low', 'medium', 'high', 'critical'}
ALLOWED_SEVERITIES = {'info', 'degraded', 'critical'}
ALLOWED_EVENT_CLASSES = {'message', 'task_marker', 'system_notice', 'delivery'}


def extract_sections(markdown: str) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {}
    current = None
    for raw_line in markdown.splitlines():
        line = raw_line.rstrip('\n')
        if line.startswith('## '):
            current = line[3:].strip()
            sections.setdefault(current, [])
            continue
        if current is not None:
            sections[current].append(line)
    return sections


def compact_section(lines: list[str]) -> str:
    return '\n'.join(line.strip() for line in lines if line.strip()).strip()


def is_placeholder_text(value: str) -> bool:
    stripped = value.strip()
    if not stripped:
        return True
    return any(marker in stripped for marker in PLACEHOLDER_MARKERS)


if not from_id.strip():
    raise SystemExit("from is required")
if not msg.strip():
    raise SystemExit("msg is required")
if msg_type.strip() not in ALLOWED_TYPES:
    raise SystemExit(f'invalid type: {msg_type}')
if source_type.strip() not in ALLOWED_SOURCE_TYPES:
    raise SystemExit(f'invalid source_type: {source_type}')
if event_class.strip() not in ALLOWED_EVENT_CLASSES:
    raise SystemExit(f'invalid event_class: {event_class}')
if priority.strip() and priority.strip() not in ALLOWED_PRIORITIES:
    raise SystemExit(f'invalid priority: {priority}')
if severity.strip() and severity.strip() not in ALLOWED_SEVERITIES:
    raise SystemExit(f'invalid severity: {severity}')
if msg_type.strip() == 'answer' and not reply_to.strip():
    raise SystemExit('answer requires --reply-to <msg_id>')
if msg_type.strip() in {'task_announce', 'task_done', 'decision', 'notify', 'dispatch', 'nudge'} and not task_id.strip():
    raise SystemExit(f'{msg_type.strip()} requires task_id')

try:
    schema_version = int(str(schema_version_raw).strip())
except ValueError as exc:
    raise SystemExit(f'invalid schema_version: {schema_version_raw}') from exc
if schema_version < 1:
    raise SystemExit('schema_version must be >= 1')

if source_type == 'system':
    if not source_name.strip():
        raise SystemExit('system event requires --source-name')
    if not severity.strip():
        raise SystemExit('system event requires --severity')

task_meta = {}
if channel == 'announce':
    if not task_id.strip():
        raise SystemExit('announce channel requires task_id')
    task_dir = tasks_root / task_id.strip()
    task_json = task_dir / 'task.json'
    instruction_md = task_dir / 'instruction.md'
    if not task_json.exists() or not instruction_md.exists():
        raise SystemExit(f'announce target task missing required files: {task_dir}')
    task_meta = json.loads(task_json.read_text(encoding='utf-8'))
    sections = extract_sections(instruction_md.read_text(encoding='utf-8'))
    for name in ['任务类型', '目标', '任务边界', '验收标准', '下游动作']:
        if name not in sections or is_placeholder_text(compact_section(sections[name])):
            raise SystemExit(f'task_announce blocked: instruction.md section `{name}` is missing or still placeholder')
    if str(task_meta.get('status') or '').strip() not in {'dispatched', 'working', 'ready_for_merge', 'blocked'}:
        raise SystemExit(f'task_announce blocked: task status must be dispatched/working/ready_for_merge/blocked, got {task_meta.get("status")}')

ts = datetime.now().astimezone().isoformat(timespec='seconds')
prefix = {
    'general': 'general',
    'task': 'tasks',
    'announce': 'tasks',
    'watcher': 'watcher',
    'dispatch': 'dispatch',
    'nudge': 'direct_nudge',
}.get(channel, channel)
scope = target_file.stem.replace(':', '-')
if task_id.strip():
    scope = task_id.strip()
msg_id = f"{prefix}-{scope}-{datetime.now().strftime('%Y%m%dT%H%M%S')}-{os.getpid()}-{random.randint(1000,9999)}"

payload = {
    "schema_version": schema_version,
    "msg_id": msg_id,
    "ts": ts,
    "channel": {
        'announce': 'task',
        'nudge': 'direct_nudge',
    }.get(channel, channel),
    "event_class": event_class.strip(),
    "from": from_id.strip(),
    "to": to_id.strip() or "all",
    "source_type": source_type.strip(),
    "type": msg_type.strip() or "text",
    "msg": msg,
}
if source_type == 'human' and event_class == 'message' and msg_type.strip() in {'task_announce', 'task_done'}:
    payload["event_class"] = 'task_marker'
if task_id.strip():
    payload["task_id"] = task_id.strip()
if priority.strip():
    payload["priority"] = priority.strip()
if severity.strip():
    payload["severity"] = severity.strip()
if reply_to.strip():
    payload["reply_to"] = reply_to.strip()
if thread_id.strip():
    payload["thread_id"] = thread_id.strip()
if source_name.strip():
    payload["source_name"] = source_name.strip()
if source_msg_id.strip():
    payload["source_msg_id"] = source_msg_id.strip()
if task_meta:
    if task_meta.get('task_type'):
        payload['task_type'] = task_meta.get('task_type')
    if task_meta.get('target_environment'):
        payload['target_environment'] = task_meta.get('target_environment')
    if task_meta.get('review_level'):
        payload['review_level'] = task_meta.get('review_level')
    if task_meta.get('downstream_action'):
        payload['next_action'] = task_meta.get('downstream_action')
    if 'owner_approval_required' in task_meta:
        payload['owner_approval_required'] = bool(task_meta.get('owner_approval_required'))

target_file.parent.mkdir(parents=True, exist_ok=True)
lock_path = target_file.with_suffix(target_file.suffix + ".lock")
tmp_path = target_file.with_suffix(target_file.suffix + ".tmp")

import fcntl

with lock_path.open("w", encoding="utf-8") as lock_fp:
    fcntl.flock(lock_fp.fileno(), fcntl.LOCK_EX)
    existing = target_file.read_text(encoding="utf-8") if target_file.exists() else ""
    content = existing + ("" if not existing or existing.endswith("\n") else "\n") + json.dumps(payload, ensure_ascii=False) + "\n"
    tmp_path.write_text(content, encoding="utf-8")
    tmp_path.replace(target_file)

print(json.dumps({"ok": True, "file": str(target_file), "msg_id": msg_id}, ensure_ascii=False))
if payload["type"] in {"decision", "task_done", "answer"} and payload.get("task_id"):
    print(
        "REMINDER: 关键结论已发到 chat，请同步回写 feature 上下文（decisions.log / notes/*.md），不要只留在聊天里。",
        file=sys.stderr,
    )
PY
