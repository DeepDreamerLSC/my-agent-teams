#!/bin/bash
# task_watcher_notifications.sh - task-watcher 通知与系统聊天事件模块。
#
# 本文件由 scripts/task-watcher.sh source，不单独执行。
# 依赖主脚本已定义的变量/函数：PM_SESSION、PUSH_SCRIPT、USER_ID、
# SEND_CHAT_SCRIPT、TASKS_ROOT、send_session_message、log、truncate_utf8、
# is_notified、mark_notified。

notify_pm() {
    local msg="$1"
    send_session_message "$PM_SESSION" "$msg"
}

notify_agent() {
    local session="$1"
    local msg="$2"
    send_session_message "$session" "$msg"
}

# 飞书推送（给林总工）
push_feishu() {
    local msg="$1"
    local event_label="${2:-generic}"
    local task_id="${3:-unknown}"
    if [ ! -x "$PUSH_SCRIPT" ]; then
        log "飞书推送跳过: push script 不可执行 ($PUSH_SCRIPT)"
        return 1
    fi

    local tmpfile output rc message_uuid
    tmpfile=$(mktemp)
    printf '%s\n' "$msg" > "$tmpfile"
    message_uuid=$(python3 - "$event_label" "$task_id" "$tmpfile" <<'PY_UUID' 2>/dev/null || true
import hashlib
import sys
from pathlib import Path

seed = "my-agent-teams/task-watcher/feishu/v1\0"
seed += sys.argv[1] + "\0" + sys.argv[2] + "\0"
message = Path(sys.argv[3]).read_bytes()
digest = hashlib.sha256(seed.encode('utf-8') + message).hexdigest()
print(digest)
PY_UUID
)
    output="$(FEISHU_RECEIVE_ID="$USER_ID" FEISHU_MESSAGE_UUID="$message_uuid" "$PUSH_SCRIPT" < "$tmpfile" 2>&1)"
    rc=$?
    rm -f "$tmpfile"

    if [ "$rc" -eq 0 ]; then
        log "飞书推送成功: task=${task_id} event=${event_label} $(truncate_utf8 "$output" 120)"
        return 0
    fi

    log "飞书推送失败: task=${task_id} event=${event_label} rc=${rc} $(truncate_utf8 "$output" 200)"
    return "$rc"
}

push_task_event() {
    local title="$1"
    local task_id="$2"
    local summary="${3:-}"
    local next_action="${4:-}"
    local message="${title}
任务：${task_id}"
    if [ -n "$summary" ]; then
        message="${message}
摘要：${summary}"
    fi
    if [ -n "$next_action" ]; then
        message="${message}
下一步：${next_action}"
    fi
    push_feishu "$message" "$title" "$task_id"
}

emit_system_chat_event() {
    local channel="$1"
    local task_id="$2"
    local msg="$3"
    local to_actor="${4:-all}"
    local severity="${5:-info}"
    local event_type="${6:-notify}"

    [ -n "$task_id" ] || return 0
    [ -x "$SEND_CHAT_SCRIPT" ] || return 0

    local source_name="task-watcher"
    case "$channel" in
        watcher) source_name="task-watcher" ;;
        dispatch) source_name="dispatch-task" ;;
        nudge) source_name="send-to-agent" ;;
    esac

    TASKS_ROOT="$TASKS_ROOT" "$SEND_CHAT_SCRIPT" "$channel" "$task_id" "$msg" \
        --to "$to_actor" \
        --type "$event_type" \
        --severity "$severity" \
        --source-type system \
        --source-name "$source_name" >/dev/null 2>&1 || return 1

    if [ "$channel" = "watcher" ] && [ "$to_actor" = "$PM_SESSION" ] && [ "$severity" != "info" ]; then
        TASKS_ROOT="$TASKS_ROOT" "$SEND_CHAT_SCRIPT" task "$task_id" "$msg" \
            --to "$to_actor" \
            --type "$event_type" \
            --severity "$severity" \
            --source-type system \
            --event-class system_notice \
            --source-name "$source_name" >/dev/null 2>&1 || true
    fi
}

emit_system_chat_event_once() {
    local notice_key="$1"
    shift
    if is_notified "$notice_key"; then
        return 0
    fi
    if emit_system_chat_event "$@"; then
        mark_notified "$notice_key"
        return 0
    fi
    return 1
}

