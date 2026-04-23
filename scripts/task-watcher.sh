#!/bin/bash
set -euo pipefail

WORKSPACE_ROOT="${WORKSPACE_ROOT:-$HOME/Desktop/work/my-agent-teams}"
CONFIG_PATH="${CONFIG_PATH:-$WORKSPACE_ROOT/config.json}"
TASKS_DIR="${TASKS_DIR:-$WORKSPACE_ROOT/tasks}"
SYSTEM_DIR="$TASKS_DIR/_system"
STATE_DIR="$SYSTEM_DIR/watcher-state"
NOTIFY_LOG="$SYSTEM_DIR/notifications.jsonl"
LOCK_FILE="$SYSTEM_DIR/task-watcher.lock"
SCAN_INTERVAL="${SCAN_INTERVAL:-5}"
NOTIFY_DRY_RUN="${NOTIFY_DRY_RUN:-false}"

mkdir -p "$STATE_DIR" "$SYSTEM_DIR/inbox"

if command -v flock >/dev/null 2>&1; then
  exec 200>"$LOCK_FILE"
  flock -n 200 || {
    echo "task-watcher already running"
    exit 0
  }
else
  mkdir "$LOCK_FILE.dir" 2>/dev/null || {
    echo "task-watcher already running"
    exit 0
  }
  trap 'rmdir "$LOCK_FILE.dir"' EXIT
fi

json_get() {
  local file="$1"
  local expr="$2"
  jq -r "$expr" "$file" 2>/dev/null || true
}

file_sig() {
  [ -f "$1" ] || return 0
  shasum -a 256 "$1" | awk '{print $1}'
}

now_iso() {
  python3 - <<'PY'
from datetime import datetime
print(datetime.now().astimezone().isoformat(timespec='seconds'))
PY
}

append_transition() {
  local task_dir="$1"
  local from="$2"
  local to="$3"
  local reason="$4"
  local ts
  ts=$(now_iso)
  FROM_STATE="$from" TO_STATE="$to" REASON="$reason" TS="$ts" python3 - <<'PY2' >> "$task_dir/transitions.jsonl"
import json, os
print(json.dumps({
    "from": os.environ["FROM_STATE"],
    "to": os.environ["TO_STATE"],
    "at": os.environ["TS"],
    "reason": os.environ["REASON"],
}, ensure_ascii=False))
PY2
}

update_task_status() {
  local task_file="$1"
  local new_status="$2"
  local reason="$3"
  python3 - "$task_file" "$new_status" "$reason" <<'PY'
import json
import sys
from datetime import datetime
from pathlib import Path
p = Path(sys.argv[1])
new_status = sys.argv[2]
reason = sys.argv[3]
obj = json.loads(p.read_text(encoding='utf-8'))
old = obj.get('status')
if old == new_status:
    print(old)
    sys.exit(0)
now = datetime.now().astimezone().isoformat(timespec='seconds')
obj['status'] = new_status
obj['updated_at'] = now
obj['lease_expires_at'] = now
p.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(old)
PY
}

notify_pm() {
  local task_id="$1"
  local kind="$2"
  local message="$3"
  local ts push_script receive_id
  ts=$(now_iso)
  TASK_ID="$task_id" KIND="$kind" MESSAGE="$message" TS="$ts" NOTIFY_LOG="$NOTIFY_LOG" python3 - <<'PY2'
import json, os
record = json.dumps({
    "at": os.environ["TS"],
    "task_id": os.environ["TASK_ID"],
    "kind": os.environ["KIND"],
    "message": os.environ["MESSAGE"],
}, ensure_ascii=False)
with open(os.environ["NOTIFY_LOG"], "a", encoding="utf-8") as fh:
    fh.write(record + "\n")
PY2

  if [ "$NOTIFY_DRY_RUN" = "true" ]; then
    return 0
  fi

  push_script=$(json_get "$CONFIG_PATH" '.notifications.push_script // empty')
  receive_id=$(json_get "$CONFIG_PATH" '.notifications.feishu_open_id // empty')
  if [ -n "$push_script" ] && [ -x "$push_script" ]; then
    FEISHU_RECEIVE_ID="$receive_id" "$push_script" "$message" >/dev/null 2>&1
    return $?
  fi
  return 0
}

write_state() {
  local state_file="$1"
  local status="$2"
  local ack_sig="$3"
  local result_sig="$4"
  local verify_sig="$5"
  local last_notified_status="$6"
  local last_notified_ack_sig="$7"
  local last_notified_result_sig="$8"
  local last_notified_verify_sig="$9"
  python3 - <<PY > "$state_file.tmp"
import json
print(json.dumps({
  "status": "$status",
  "ack_sig": "$ack_sig",
  "result_sig": "$result_sig",
  "verify_sig": "$verify_sig",
  "last_notified_status": "$last_notified_status",
  "last_notified_ack_sig": "$last_notified_ack_sig",
  "last_notified_result_sig": "$last_notified_result_sig",
  "last_notified_verify_sig": "$last_notified_verify_sig"
}, ensure_ascii=False, indent=2))
PY
  mv "$state_file.tmp" "$state_file"
}

validate_ack() {
  local task_file="$1"
  local ack_file="$2"
  python3 - "$task_file" "$ack_file" <<'PY'
import json, sys
from pathlib import Path

task = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
ack = json.loads(Path(sys.argv[2]).read_text(encoding='utf-8'))
if ack.get('task_id') != task.get('id'):
    raise SystemExit(1)
if ack.get('agent') != task.get('assigned_agent'):
    raise SystemExit(1)
print('ok')
PY
}

process_result() {
  local task_dir="$1"
  local task_file="$task_dir/task.json"
  local result_file="$task_dir/result.json"
  local current_status result_status old_status review_required test_required

  current_status=$(json_get "$task_file" '.status // empty')
  result_status=$(json_get "$result_file" '.status // empty')
  [ -n "$result_status" ] || return 0

  if [ "$current_status" != "$result_status" ]; then
    old_status=$(update_task_status "$task_file" "$result_status" 'result received')
    if [ "$old_status" != "$result_status" ]; then
      append_transition "$task_dir" "$old_status" "$result_status" 'result received'
    fi
  fi

  if [ "$result_status" = "ready_for_merge" ]; then
    if "$WORKSPACE_ROOT/scripts/verify.sh" "$task_file" >/dev/null 2>&1; then
      review_required=$(json_get "$task_file" '.review_required')
      test_required=$(json_get "$task_file" '.test_required')
      if [ "$review_required" = "false" ] && [ "$test_required" = "false" ]; then
        old_status=$(update_task_status "$task_file" 'done' 'verify passed')
        if [ "$old_status" != 'done' ]; then
          append_transition "$task_dir" "$old_status" 'done' 'verify passed'
        fi
      fi
    else
      old_status=$(update_task_status "$task_file" 'failed' 'verify failed')
      if [ "$old_status" != 'failed' ]; then
        append_transition "$task_dir" "$old_status" 'failed' 'verify failed'
      fi
    fi
  fi
}

reconcile_task() {
  local task_dir="$1"
  local task_file="$task_dir/task.json"
  [ -f "$task_file" ] || return 0

  local task_id state_file status title ack_sig result_sig verify_sig
  local last_notified_status last_notified_ack_sig last_notified_result_sig last_notified_verify_sig
  local agent summary

  task_id=$(json_get "$task_file" '.id // empty')
  [ -n "$task_id" ] || return 0
  state_file="$STATE_DIR/$task_id.json"

  status=$(json_get "$task_file" '.status // empty')
  title=$(json_get "$task_file" '.title // "unnamed-task"')
  ack_sig=$(file_sig "$task_dir/ack.json")
  result_sig=$(file_sig "$task_dir/result.json")
  verify_sig=$(file_sig "$task_dir/verify.json")

  last_notified_status=$(json_get "$state_file" '.last_notified_status // empty')
  last_notified_ack_sig=$(json_get "$state_file" '.last_notified_ack_sig // empty')
  last_notified_result_sig=$(json_get "$state_file" '.last_notified_result_sig // empty')
  last_notified_verify_sig=$(json_get "$state_file" '.last_notified_verify_sig // empty')

  if [ -n "$ack_sig" ] && [ "$ack_sig" != "$last_notified_ack_sig" ]; then
    if validate_ack "$task_file" "$task_dir/ack.json" >/dev/null 2>&1; then
      agent=$(json_get "$task_dir/ack.json" '.agent // "unknown"')
      if notify_pm "$task_id" "ack" "$task_id 已由 $agent 确认接收"; then
        last_notified_ack_sig="$ack_sig"
      fi
      if [ "$status" = "dispatched" ]; then
        old_status=$(update_task_status "$task_file" 'working' 'ack received')
        if [ "$old_status" != 'working' ]; then
          append_transition "$task_dir" "$old_status" 'working' 'ack received'
        fi
        status=$(json_get "$task_file" '.status // empty')
      fi
    elif notify_pm "$task_id" "ack_error" "$task_id 的 ack.json 不合规"; then
      last_notified_ack_sig="$ack_sig"
    fi
  fi

  if [ -n "$result_sig" ] && [ "$result_sig" != "$last_notified_result_sig" ]; then
    summary=$(json_get "$task_dir/result.json" '.summary // "无摘要"')
    if notify_pm "$task_id" "result" "$task_id 上报结果：$summary"; then
      last_notified_result_sig="$result_sig"
    fi
    process_result "$task_dir"
    status=$(json_get "$task_file" '.status // empty')
    verify_sig=$(file_sig "$task_dir/verify.json")
  fi

  if [ -n "$status" ] && [ "$status" != "$last_notified_status" ]; then
    if notify_pm "$task_id" "status" "$task_id [$title] 状态变更为 $status"; then
      last_notified_status="$status"
    fi
  fi

  if [ -n "$verify_sig" ] && [ "$verify_sig" != "$last_notified_verify_sig" ]; then
    if [ "$(json_get "$task_dir/verify.json" '.ok // false')" = "true" ]; then
      if [ "$status" = "done" ]; then
        if notify_pm "$task_id" "verify" "$task_id verify 通过，任务已完成"; then
          last_notified_verify_sig="$verify_sig"
        fi
      else
        if notify_pm "$task_id" "verify" "$task_id verify 通过，等待 review/test"; then
          last_notified_verify_sig="$verify_sig"
        fi
      fi
    else
      if notify_pm "$task_id" "verify" "$task_id verify 失败，请关注 verify.json"; then
        last_notified_verify_sig="$verify_sig"
      fi
    fi
  fi

  write_state "$state_file" "$status" "$ack_sig" "$result_sig" "$verify_sig" "$last_notified_status" "$last_notified_ack_sig" "$last_notified_result_sig" "$last_notified_verify_sig"
}

reconcile_once() {
  local dir
  for dir in "$TASKS_DIR"/*; do
    [ -d "$dir" ] || continue
    [ "$(basename "$dir")" = "_system" ] && continue
    [ "$(basename "$dir")" = "_templates" ] && continue
    reconcile_task "$dir"
  done
}

reconcile_once
while true; do
  sleep "$SCAN_INTERVAL"
  reconcile_once
done
