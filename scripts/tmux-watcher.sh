#!/bin/bash
# tmux-watcher.sh - 实时监控 tmux agent 确认提示并自动处理
# 每 3 秒轮询所有活跃 session，跳过 omx-detached 和自己
# 使用 session ID 操作，避免中文名在 list-sessions 中显示为 ____ 的问题

KEYWORDS=(
    "Do you want to "
    "Allow this tool"
    "Allow the "
    "Allow for this session"
    "Yes, proceed"
    "Press enter to confirm"
    "enter to confirm"
    "requires approval"
    "Permission requested"
    "MCP server to run tool"
    "Allow the omx"
    "Allow the omx_wiki"
    "Allow the omx_memory"
)
DANGEROUS_KEYWORDS=(
    "make the following edits"
    "Would you like to make the following edits?"
)
INTERVAL=3
STATE_DIR="/Users/lin/.openclaw/workspace/.tmux-watcher"
PID_FILE="${PID_FILE:-$STATE_DIR/tmux-watcher.pid}"
HEARTBEAT_FILE="${HEARTBEAT_FILE:-$STATE_DIR/tmux-watcher-heartbeat.json}"
LOG_DIR="${LOG_DIR:-/Users/lin/.openclaw/workspace/logs}"
LOG_FILE="${LOG_FILE:-$LOG_DIR/tmux-watcher.log}"
MATCH_LINES="${MATCH_LINES:-40}"
mkdir -p "$STATE_DIR" "$LOG_DIR"

log() {
    local line
    line="$(date '+%Y-%m-%d %H:%M:%S') $*"
    echo "$line"
    printf '%s\n' "$line" >> "$LOG_FILE" 2>/dev/null || true
}

write_heartbeat() {
    python3 - "$HEARTBEAT_FILE" "$$" "$INTERVAL" <<'PY'
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

heartbeat_path = Path(sys.argv[1])
payload = {
    "pid": int(sys.argv[2]),
    "interval_seconds": int(sys.argv[3]),
    "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    "updated_ts": int(datetime.now(timezone.utc).timestamp()),
}
heartbeat_path.parent.mkdir(parents=True, exist_ok=True)
with tempfile.NamedTemporaryFile("w", delete=False, dir=str(heartbeat_path.parent), encoding="utf-8") as tmp:
    json.dump(payload, tmp, ensure_ascii=False, indent=2)
    tmp.write("\n")
tmp_path = Path(tmp.name)
os.replace(tmp_path, heartbeat_path)
PY
}

ensure_single_instance() {
    local existing_pid=""
    existing_pid=$(cat "$PID_FILE" 2>/dev/null || true)
    if [ -n "$existing_pid" ] && [ "$existing_pid" != "$$" ] && kill -0 "$existing_pid" 2>/dev/null; then
        log "tmux-watcher 已在运行（pid=$existing_pid），当前实例退出"
        exit 0
    fi
    printf '%s\n' "$$" > "$PID_FILE"
}

cleanup_tmux_watcher_runtime() {
    local existing_pid=""
    existing_pid=$(cat "$PID_FILE" 2>/dev/null || true)
    if [ "$existing_pid" = "$$" ]; then
        rm -f "$PID_FILE"
    fi
}

trap cleanup_tmux_watcher_runtime EXIT INT TERM

ensure_single_instance
log "tmux-watcher 启动，间隔 ${INTERVAL}s"

while true; do
    write_heartbeat
    # 获取所有 session 的 id 和 name
    my_session_name="$(tmux display-message -p '#{session_name}' 2>/dev/null)"

    SESSIONS_FILE=$(mktemp)
    tmux list-sessions -F '#{session_id}|#{session_name}' 2>/dev/null > "$SESSIONS_FILE"
    while IFS='|' read -r sid sname; do
        # 跳过空行
        [ -z "$sname" ] && continue
        # 跳过自己
        [ "$sname" = "$my_session_name" ] && continue
        # 跳过 omx-detached 残留
        case "$sname" in
            omx-lin-detached*|tmux-watcher|task-watcher)
                continue
                ;;
        esac

        # 用 session ID 操作（避免中文名 ____ 问题）
        content=$(tmux capture-pane -t "$sname" -p -S -80 2>/dev/null)
        [ -z "$content" ] && continue

        # 检查底部若干行是否包含确认关键字（提示可能不总在最后 15 行）
        bottom_lines=$(printf '%s\n' "$content" | tail -"$MATCH_LINES")
        matched=0
        matched_kw=""
        for kw in "${KEYWORDS[@]}"; do
            if printf '%s\n' "$bottom_lines" | grep -Fq "$kw"; then
                matched=1
                matched_kw="$kw"
                break
            fi
        done

        [ "$matched" -eq 0 ] && continue

        # 判断确认弹窗是否还是活跃状态：只有当 approved 行出现在 confirm 行之后才算已处理
        # 找最后一个 "Press enter to confirm" 的行号
        confirm_line=0
        line_num=0
        while IFS= read -r aline; do
            line_num=$((line_num + 1))
            case "$aline" in
                *"Press enter to confirm"*|*"enter to confirm"*)
                    confirm_line=$line_num
                    ;;
            esac
        done <<< "$bottom_lines"

        # 找 confirm 行之后有没有 approved 行
        already_approved=0
        if [ "$confirm_line" -gt 0 ]; then
            tail_after=$(printf '%s\n' "$bottom_lines" | tail -n +$((confirm_line + 1)))
            if printf '%s\n' "$tail_after" | grep -Eq '✔.*(approved)'; then
                already_approved=1
            fi
        fi

        if [ "$already_approved" -eq 1 ]; then
            continue
        fi

        dangerous_match=0
        dangerous_kw=""
        for danger_kw in "${DANGEROUS_KEYWORDS[@]}"; do
            if printf '%s\n' "$bottom_lines" | grep -Fq "$danger_kw"; then
                dangerous_match=1
                dangerous_kw="$danger_kw"
                break
            fi
        done
        if [ "$dangerous_match" -eq 1 ]; then
            log "检测到需要人工确认的高风险提示 $sname（sid=$sid，keyword=$dangerous_kw），跳过自动确认"
            continue
        fi

        # 用 session 级别冷却时间去重（默认 60 秒内不重复触发）
        safe_sid=$(echo "$sid" | tr '$' 'S')
        cooldown_file="$STATE_DIR/${safe_sid}.last_action"
        now=$(date +%s)
        last_action=$(cat "$cooldown_file" 2>/dev/null)
        if [ -n "$last_action" ] && [ $(( now - last_action )) -lt 10 ]; then
            continue
        fi
        echo "$now" > "$cooldown_file"

        log "自动确认 $sname（sid=$sid，keyword=$matched_kw）"
        tmux send-keys -t "$sname" Enter
    done < "$SESSIONS_FILE"
    rm -f "$SESSIONS_FILE"

    sleep "$INTERVAL"
done
