#!/bin/bash
# tmux-watcher.sh - 实时监控 tmux agent 确认提示并自动处理
# 每 3 秒轮询所有活跃 session，跳过 omx-detached 和自己
# 使用 session ID 操作，避免中文名在 list-sessions 中显示为 ____ 的问题

PUSH_SCRIPT="/Users/lin/.openclaw/workspace/scripts/feishu-push.sh"
USER_ID="ou_f95ee559a38a607c5f312e7b64304143"
KEYWORDS=("Do you want to " "Allow this tool" "Allow the " "Allow for this session" "Yes, proceed" "enter to confirm" "requires approval" "Permission requested" "MCP server to run tool" "Allow the omx" "Allow the omx_wiki" "Allow the omx_memory")
INTERVAL=3
STATE_DIR="/Users/lin/.openclaw/workspace/.tmux-watcher"
mkdir -p "$STATE_DIR"

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') $*"
}

push_feishu() {
    local msg="$1"
    if [ -x "$PUSH_SCRIPT" ]; then
        tmpfile=$(mktemp)
        echo "$msg" > "$tmpfile"
        FEISHU_RECEIVE_ID="$USER_ID" "$PUSH_SCRIPT" < "$tmpfile" 2>/dev/null &
        disown
        rm -f "$tmpfile"
    fi
}

log "tmux-watcher 启动，间隔 ${INTERVAL}s"

while true; do
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
        case "$sname" in omx-lin-detached*) continue ;; esac

        # 用 session ID 操作（避免中文名 ____ 问题）
        content=$(tmux capture-pane -t "$sname" -p -S -30 2>/dev/null)
        [ -z "$content" ] && continue

        # 检查底部 15 行是否包含确认关键字（Claude Code 底部有 UI 状态栏，确认提示会被推到中间）
        bottom_lines=$(echo "$content" | tail -15)
        matched=0
        for kw in "${KEYWORDS[@]}"; do
            if echo "$bottom_lines" | grep -q "$kw"; then
                matched=1
                break
            fi
        done

        [ "$matched" -eq 0 ] && continue

        # 用 session 级别冷却时间去重（默认 60 秒内不重复触发）
        safe_sid=$(echo "$sid" | tr '$' 'S')
        cooldown_file="$STATE_DIR/${safe_sid}.last_action"
        now=$(date +%s)
        last_action=$(cat "$cooldown_file" 2>/dev/null)
        if [ -n "$last_action" ] && [ $(( now - last_action )) -lt 10 ]; then
            continue
        fi
        echo "$now" > "$cooldown_file"

        # 新的确认项，静默自动确认
        tmux send-keys -t "$sname" Enter
    done < "$SESSIONS_FILE"
    rm -f "$SESSIONS_FILE"

    sleep "$INTERVAL"
done
