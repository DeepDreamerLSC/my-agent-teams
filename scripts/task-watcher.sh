#!/bin/bash
# task-watcher.sh - 监控 tasks/ 目录下的任务状态变更，通知 PM
# 检测 result.json 新增 → 通知 PM 验收
# 检测 ack.json 新增 → 更新 task.json 状态为 working
# 检测 verify.json 新增 → 通知 PM 或推进下游任务

TASKS_ROOT="/Users/lin/Desktop/work/my-agent-teams/tasks"
PM_SESSION="pm-chief"
PUSH_SCRIPT="/Users/lin/.openclaw/workspace/scripts/feishu-push.sh"
USER_ID="ou_f95ee559a38a607c5f312e7b64304143"
STATE_DIR="/Users/lin/.openclaw/workspace/.task-watcher"
INTERVAL=5

mkdir -p "$STATE_DIR"

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') $*"
}

# 通知 PM（通过 tmux send-keys）
notify_pm() {
    local msg="$1"
    tmux send-keys -t "$PM_SESSION" -l -- "$msg" 2>/dev/null
    sleep 0.1
    tmux send-keys -t "$PM_SESSION" Enter 2>/dev/null
    log "通知 PM: $msg"
}

# 飞书推送（给林总工）
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

# 检查 task.json 中的 status
get_task_status() {
    local task_dir="$1"
    python3 -c "import json; print(json.load(open('$task_dir/task.json')).get('status','unknown'))" 2>/dev/null
}

# 更新 task.json status
set_task_status() {
    local task_dir="$1"
    local new_status="$2"
    python3 -c "
import json, sys
f = '$task_dir/task.json'
d = json.load(open(f))
old = d.get('status','')
d['status'] = '$new_status'
json.dump(d, open(f,'w'), indent=2, ensure_ascii=False)
print(f'status: {old} -> $new_status')
" 2>/dev/null
}

# 记录已处理的事件（避免重复通知）
is_notified() {
    local key="$1"
    local flag="$STATE_DIR/$key"
    [ -f "$flag" ]
}

mark_notified() {
    local key="$1"
    echo "$(date +%s)" > "$STATE_DIR/$key"
}

log "task-watcher 启动，间隔 ${INTERVAL}s"

while true; do
    [ -d "$TASKS_ROOT" ] || { sleep "$INTERVAL"; continue; }

    for task_dir in "$TASKS_ROOT"/*/; do
        [ -d "$task_dir" ] || continue
        task_id=$(basename "$task_dir")
        [ -f "$task_dir/task.json" ] || continue

        current_status=$(get_task_status "$task_dir")

        # 兜底：dispatched 状态超 60 秒无 ack → 重新发送指令
        if [ "$current_status" = "dispatched" ] && [ ! -f "$task_dir/ack.json" ]; then
            dispatch_time=$(python3 -c "
import json
d = json.load(open('$task_dir/task.json'))
t = d.get('lease_acquired_at','') or d.get('updated_at','')
from datetime import datetime
try:
    dt = datetime.fromisoformat(t)
    print(int(dt.timestamp()))
except: print(0)
" 2>/dev/null)
            now=$(date +%s)
            if [ -n "$dispatch_time" ] && [ "$dispatch_time" -gt 0 ] && [ $(( now - dispatch_time )) -gt 60 ]; then
                resend_key="${task_id}_resend"
                last_resend=$(cat "$STATE_DIR/$resend_key" 2>/dev/null)
                if [ -z "$last_resend" ] || [ $(( now - last_resend )) -gt 120 ]; then
                    agent_session=$(python3 -c "import json; print(json.load(open('$task_dir/task.json')).get('assigned_agent',''))" 2>/dev/null)
                    if [ -n "$agent_session" ] && tmux has-session -t "$agent_session" 2>/dev/null; then
                        # Codex 需要 i 进入输入模式
                        is_codex=$(python3 -c "
import json
cfg = json.load(open('/Users/lin/Desktop/work/my-agent-teams/config.json'))
agents = cfg.get('agents', {})
a = agents.get('$agent_session', {})
# Codex agents: arch-1, be-1, review-1
print('1' if '$agent_session' in ('arch-1','be-1','review-1') else '0')
" 2>/dev/null)
                        if [ "$is_codex" = "1" ]; then
                            tmux send-keys -t "$agent_session" i 2>/dev/null
                            sleep 0.5
                        fi
                        instruction="$task_dir/instruction.md"
                        if [ -f "$instruction" ]; then
                            msg="请读取 ${task_dir}instruction.md 并开始执行任务。完成后写 ack.json 和 result.json。"
                            tmux send-keys -t "$agent_session" -l -- "$msg" 2>/dev/null
                            sleep 0.1
                            tmux send-keys -t "$agent_session" Enter 2>/dev/null
                            log "$task_id: 兜底重发指令给 $agent_session"
                            push_feishu "🔄 $task_id 超时未确认，已重新发送给 $agent_session"
                        fi
                        echo "$now" > "$STATE_DIR/$resend_key"
                    fi
                fi
            fi
        fi

        # 检测 ack.json → 状态应为 working
        if [ -f "$task_dir/ack.json" ] && [ "$current_status" = "dispatched" ]; then
            ack_key="${task_id}_ack"
            if ! is_notified "$ack_key"; then
                agent=$(python3 -c "import json; print(json.load(open('$task_dir/ack.json')).get('agent','?'))" 2>/dev/null)
                set_task_status "$task_dir" "working"
                log "$task_id: agent $agent 已确认，状态 working"
                mark_notified "$ack_key"
            fi
        fi

        # 检测 result.json → 通知 PM
        if [ -f "$task_dir/result.json" ]; then
            result_key="${task_id}_result"
            if ! is_notified "$result_key"; then
                agent=$(python3 -c "import json; print(json.load(open('$task_dir/result.json')).get('agent','?'))" 2>/dev/null)
                result_status=$(python3 -c "import json; print(json.load(open('$task_dir/result.json')).get('status','?'))" 2>/dev/null)
                summary=$(python3 -c "import json; print(json.load(open('$task_dir/result.json')).get('summary','')[:100])" 2>/dev/null)

                if [ "$result_status" = "done" ]; then
                    set_task_status "$task_dir" "ready_for_merge"
                    notify_pm "[task-watcher] $task_id 已完成（agent: $agent）。摘要：$summary。请验收并决定是否推进下游任务。"
                    push_feishu "📋 $task_id 完成: $summary"
                elif [ "$result_status" = "blocked" ]; then
                    set_task_status "$task_dir" "blocked"
                    notify_pm "[task-watcher] $task_id 被 agent $agent 标记为 blocked。摘要：$summary。请处理。"
                    push_feishu "⚠️ $task_id 阻塞: $summary"
                else
                    notify_pm "[task-watcher] $task_id 有 result.json（status=$result_status），请检查。"
                fi

                mark_notified "$result_key"
            fi
        fi

        # 检测 review.md → 通知 PM 审查完成
        if [ -f "$task_dir/review.md" ]; then
            review_key="${task_id}_review"
            if ! is_notified "$review_key"; then
                review_pass=$(grep -qi '通过\|approve' "$task_dir/review.md" && echo "pass" || echo "fail")
                review_fail=$(grep -qi '不通过\|未通过\|驳回\|reject\|block\|不接受' "$task_dir/review.md" && echo "fail" || echo "")
                if [ "$review_pass" = "pass" ] && [ -z "$review_fail" ]; then
                    review_conclusion=$(grep -i '通过\|approve' "$task_dir/review.md" | head -1)
                    notify_pm "[task-watcher] $task_id 审查已完成（通过），请验收并决定是否推进下游任务。"
                    push_feishu "✅ $task_id 审查通过: $review_conclusion"
                else
                    review_conclusion=$(grep -i '不通过\|未通过\|驳回\|reject\|block\|不接受' "$task_dir/review.md" | head -1)
                    notify_pm "[task-watcher] $task_id 审查未通过，需要修改。请安排修复。"
                    push_feishu "❌ $task_id 审查未通过: $review_conclusion"
                fi
                mark_notified "$review_key"
            fi
        fi

        # 检测 verify.json → 通知 PM 审查结果
        if [ -f "$task_dir/verify.json" ]; then
            verify_key="${task_id}_verify"
            if ! is_notified "$verify_key"; then
                verify_pass=$(python3 -c "import json; print(json.load(open('$task_dir/verify.json')).get('pass', False))" 2>/dev/null)
                if [ "$verify_pass" = "True" ]; then
                    notify_pm "[task-watcher] $task_id verify 通过，可以合并。"
                else
                    notify_pm "[task-watcher] $task_id verify 未通过，请检查 verify.json。"
                fi
                mark_notified "$verify_key"
            fi
        fi
    done

    sleep "$INTERVAL"
done
