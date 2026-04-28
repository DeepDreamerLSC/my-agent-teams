#!/bin/bash
set -euo pipefail

WORKSPACE_ROOT="${WORKSPACE_ROOT:-$HOME/Desktop/work/my-agent-teams}"
CHAT_ROOT="${CHAT_ROOT:-$WORKSPACE_ROOT/chat}"

CHANNEL="${1:-}"
if [ -z "$CHANNEL" ]; then
  echo "usage: send-chat.sh <general|task|announce> [task-id] <message> [--from <agent>] [--to <target>] [--type <type>] [--priority <priority>] [--reply-to <msg_id>] [--thread-id <thread_id>]" >&2
  exit 2
fi
shift

TASK_ID=""
MESSAGE=""

case "$CHANNEL" in
  general)
    MESSAGE="${1:-}"
    shift || true
    ;;
  task|announce)
    TASK_ID="${1:-}"
    MESSAGE="${2:-}"
    shift 2 || true
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

FROM_ID="${CHAT_FROM:-}"
TO_ID="all"
TYPE_OVERRIDE=""
PRIORITY=""
REPLY_TO=""
THREAD_ID=""

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
    --reply-to)
      REPLY_TO="${2:-}"
      shift 2
      ;;
    --thread-id)
      THREAD_ID="${2:-}"
      shift 2
      ;;
    *)
      echo "unknown option: $1" >&2
      exit 2
      ;;
  esac
done

if [ -z "$FROM_ID" ]; then
  case "$PWD" in
    */agents/*)
      FROM_ID="$(basename "$PWD")"
      ;;
    *)
      FROM_ID="pm-chief"
      ;;
  esac
fi

mkdir -p "$CHAT_ROOT/general" "$CHAT_ROOT/tasks"

if [ "$CHANNEL" = "general" ]; then
  TARGET_FILE="$CHAT_ROOT/general/$(date +%F).jsonl"
  DEFAULT_TYPE="text"
  THREAD_ID="${THREAD_ID:-general}"
elif [ "$CHANNEL" = "task" ]; then
  TARGET_FILE="$CHAT_ROOT/tasks/${TASK_ID}.jsonl"
  DEFAULT_TYPE="text"
  THREAD_ID="${THREAD_ID:-$TASK_ID}"
else
  TARGET_FILE="$CHAT_ROOT/tasks/${TASK_ID}.jsonl"
  DEFAULT_TYPE="task_announce"
  THREAD_ID="${THREAD_ID:-$TASK_ID}"
fi

TYPE="${TYPE_OVERRIDE:-$DEFAULT_TYPE}"

python3 - "$TARGET_FILE" "$FROM_ID" "$TO_ID" "$TYPE" "$MESSAGE" "$TASK_ID" "$PRIORITY" "$REPLY_TO" "$THREAD_ID" <<'PY'
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
reply_to = sys.argv[8]
thread_id = sys.argv[9]

if not from_id.strip():
    raise SystemExit("from is required")
if not msg.strip():
    raise SystemExit("msg is required")

ts = datetime.now().astimezone().isoformat(timespec='seconds')
scope = target_file.stem.replace(":", "-")
prefix = "general" if "general" in target_file.parts else "tasks"
if prefix == "tasks" and task_id.strip():
    scope = task_id.strip()

msg_id = f"{prefix}-{scope}-{datetime.now().strftime('%Y%m%dT%H%M%S')}-{os.getpid()}-{random.randint(1000,9999)}"

payload = {
    "msg_id": msg_id,
    "ts": ts,
    "from": from_id.strip(),
    "to": to_id.strip() or "all",
    "source_type": "human",
    "type": msg_type.strip() or "text",
    "msg": msg,
}
if task_id.strip():
    payload["task_id"] = task_id.strip()
if priority.strip():
    payload["priority"] = priority.strip()
if reply_to.strip():
    payload["reply_to"] = reply_to.strip()
if thread_id.strip():
    payload["thread_id"] = thread_id.strip()

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
PY
