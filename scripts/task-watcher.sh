#!/bin/bash
# task-watcher.sh - 监控 tasks/ 目录下的任务状态变更，通知 PM，并同步任务看板 SQLite 数据。
# 检测 result.json 新增 → 通知 PM 验收
# 检测 ack.json 新增 → 更新 task.json 状态为 working
# 检测 verify.json 新增 → 通知 PM 或推进下游任务

TASKS_ROOT="${TASKS_ROOT:-/Users/lin/Desktop/work/my-agent-teams/tasks}"
PM_SESSION="${PM_SESSION:-pm-chief}"
PUSH_SCRIPT="${PUSH_SCRIPT:-/Users/lin/.openclaw/workspace/scripts/feishu-push.sh}"
USER_ID="${USER_ID:-ou_f95ee559a38a607c5f312e7b64304143}"
STATE_DIR="${STATE_DIR:-/Users/lin/.openclaw/workspace/.task-watcher}"
BOARD_SYNC_SCRIPT="${BOARD_SYNC_SCRIPT:-/Users/lin/Desktop/work/my-agent-teams/scripts/task-board-sync.py}"
INTERVAL="${INTERVAL:-5}"

mkdir -p "$STATE_DIR"

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') $*"
}

# 安全截断 UTF-8 字符串（按字符数，避免截断多字节字符）
truncate_utf8() {
    local str="$1"
    local max_len="${2:-60}"
    python3 -c "import sys; s=sys.stdin.read(); print(s[:$max_len] if len(s)>$max_len else s)" <<< "$str" 2>/dev/null
}

# 通知 PM（通过 tmux send-keys，带 timeout 防阻塞）
notify_pm() {
    local msg="$1"
    # PM 是 Codex（omx），需要先按 i 进入插入模式
    tmux send-keys -t "$PM_SESSION" i 2>/dev/null &
    local pid=$!
    sleep 0.3
    kill $pid 2>/dev/null; wait $pid 2>/dev/null

    tmux send-keys -t "$PM_SESSION" -l -- "$msg" 2>/dev/null &
    pid=$!
    sleep 2
    kill $pid 2>/dev/null; wait $pid 2>/dev/null

    tmux send-keys -t "$PM_SESSION" Enter 2>/dev/null &
    pid=$!
    sleep 0.5
    kill $pid 2>/dev/null; wait $pid 2>/dev/null

    log "通知 PM: $msg"
}

# 通知 agent（带 timeout 防阻塞）
notify_agent() {
    local session="$1"
    local msg="$2"
    # 判断是否 Codex
    local is_codex=0
    case "$session" in
        arch-1|be-1|be-2|review-1|pm-chief) is_codex=1 ;;
    esac

    if [ "$is_codex" = "1" ]; then
        tmux send-keys -t "$session" i 2>/dev/null &
        local pid=$!
        sleep 0.3
        kill $pid 2>/dev/null; wait $pid 2>/dev/null
    fi

    tmux send-keys -t "$session" -l -- "$msg" 2>/dev/null &
    local pid=$!
    sleep 2
    kill $pid 2>/dev/null; wait $pid 2>/dev/null

    tmux send-keys -t "$session" Enter 2>/dev/null &
    pid=$!
    sleep 0.5
    kill $pid 2>/dev/null; wait $pid 2>/dev/null

    log "通知 $session: $msg"
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

json_pick() {
    local json_file="$1"
    shift
    python3 - "$json_file" "$@" <<'PY'
import json
import sys
from pathlib import Path

json_path = Path(sys.argv[1])
keys = sys.argv[2:]
if not json_path.exists():
    raise SystemExit(0)
try:
    payload = json.loads(json_path.read_text(encoding='utf-8'))
except Exception:
    raise SystemExit(0)

for key in keys:
    value = payload.get(key)
    if value not in (None, ''):
        print(value)
        raise SystemExit(0)
PY
}

sync_task_board() {
    local task_dir="$1"
    local source="${2:-watcher}"
    if [ -f "$BOARD_SYNC_SCRIPT" ]; then
        python3 "$BOARD_SYNC_SCRIPT" sync-task --task-dir "$task_dir" --source "$source" >/dev/null 2>&1 || \
            log "任务看板同步失败: $task_dir ($source)"
    fi
}

sync_if_changed() {
    local task_dir="$1"
    local artifact_path="$2"
    local label="$3"
    [ -f "$artifact_path" ] || return

    local state_key="$(basename "$task_dir")_${label}_mtime"
    local state_file="$STATE_DIR/$state_key"
    local current_mtime
    current_mtime=$(stat -f %m "$artifact_path" 2>/dev/null || echo "")
    local last_mtime
    last_mtime=$(cat "$state_file" 2>/dev/null)

    if [ -n "$current_mtime" ] && [ "$current_mtime" != "$last_mtime" ]; then
        sync_task_board "$task_dir" "${label}-mtime-change"
        echo "$current_mtime" > "$state_file"
    fi
}

# 更新 task.json status，并追加 transitions.jsonl 记录
set_task_status() {
    local task_dir="$1"
    local new_status="$2"
    local reason="${3:-watcher status update}"
    python3 - "$task_dir" "$new_status" "$reason" <<'PY'
import json
import sys
from datetime import datetime
from pathlib import Path

task_dir = Path(sys.argv[1])
new_status = sys.argv[2]
reason = sys.argv[3]
task_path = task_dir / 'task.json'
transitions_path = task_dir / 'transitions.jsonl'
task = json.loads(task_path.read_text(encoding='utf-8'))
old_status = task.get('status', '')
now = datetime.now().astimezone().isoformat(timespec='seconds')

if old_status == new_status:
    print(f'status unchanged: {new_status}')
    raise SystemExit(0)

task['status'] = new_status
task['updated_at'] = now
task_path.write_text(json.dumps(task, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
with transitions_path.open('a', encoding='utf-8') as fp:
    fp.write(json.dumps({
        'from': old_status,
        'to': new_status,
        'at': now,
        'reason': reason,
    }, ensure_ascii=False) + '\n')
print(f'status: {old_status} -> {new_status}')
PY
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

# Check if a file has been updated since last notification
is_file_newer_than_notified() {
    local key="$1"
    local file="$2"
    local flag="$STATE_DIR/$key"
    [ -f "$flag" ] || return 0
    local notified_ts
    notified_ts=$(cat "$flag" 2>/dev/null)
    [ -n "$notified_ts" ] || return 0
    local file_ts
    file_ts=$(stat -f %m "$file" 2>/dev/null)
    [ -n "$file_ts" ] || return 0
    [ "$file_ts" -gt "$notified_ts" ]
}

log "task-watcher 启动，间隔 ${INTERVAL}s"

while true; do
    [ -d "$TASKS_ROOT" ] || { sleep "$INTERVAL"; continue; }

    for task_dir in "$TASKS_ROOT"/*/; do
        [ -d "$task_dir" ] || continue
        task_id=$(basename "$task_dir")
        [ -f "$task_dir/task.json" ] || continue

        current_status=$(get_task_status "$task_dir")

        # 已关闭任务不再通知，但仍需在文件变更后同步到任务看板 SQLite，避免 ready_for_merge -> done 后数据库残留旧状态
        case "$current_status" in
            done|cancelled|archived)
                sync_if_changed "$task_dir" "$task_dir/task.json" "taskjson"
                sync_if_changed "$task_dir" "$task_dir/transitions.jsonl" "transitions"
                sync_if_changed "$task_dir" "$task_dir/result.json" "result"
                sync_if_changed "$task_dir" "$task_dir/review.md" "review"
                sync_if_changed "$task_dir" "$task_dir/verify.json" "verify"
                continue
                ;;
        esac

        # 兜底：dispatched 状态超 60 秒无 ack → 重新发送指令
        if [ "$current_status" = "dispatched" ] && [ ! -f "$task_dir/ack.json" ]; then
            dispatch_time=$(python3 -c "
import json
from datetime import datetime

d = json.load(open('$task_dir/task.json'))
t = d.get('lease_acquired_at','') or d.get('updated_at','')
try:
    dt = datetime.fromisoformat(t)
    print(int(dt.timestamp()))
except Exception:
    print(0)
" 2>/dev/null)
            now=$(date +%s)
            if [ -n "$dispatch_time" ] && [ "$dispatch_time" -gt 0 ] && [ $(( now - dispatch_time )) -gt 60 ]; then
                resend_key="${task_id}_resend"
                # 检查 agent 是否正在工作（pane 输出含 Working），工作中不重发
                agent_session=$(python3 -c "import json; print(json.load(open('$task_dir/task.json')).get('assigned_agent',''))" 2>/dev/null)
                is_working=0
                if [ -n "$agent_session" ] && tmux has-session -t "$agent_session" 2>/dev/null; then
                    is_working=$(tmux capture-pane -t "$agent_session" -p 2>/dev/null | grep -c 'Working\|• Working' || true)
                fi
                [ "$is_working" -gt 0 ] && continue
                last_resend=$(cat "$STATE_DIR/$resend_key" 2>/dev/null)
                if [ -z "$last_resend" ] || [ $(( now - last_resend )) -gt 300 ]; then
                    if [ -n "$agent_session" ] && tmux has-session -t "$agent_session" 2>/dev/null; then
                        instruction="$task_dir/instruction.md"
                        if [ -f "$instruction" ]; then
                            msg="请读取 ${task_dir}instruction.md 并开始执行任务。完成后写 ack.json 和 result.json。"
                            notify_agent "$agent_session" "$msg"
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
                agent=$(json_pick "$task_dir/ack.json" agent agent_id)
                set_task_status "$task_dir" "working" "watcher observed ack.json"
                log "$task_id: agent ${agent:-?} 已确认，状态 working"
                sync_task_board "$task_dir" "ack-detected"
                mark_notified "$ack_key"
            fi
        fi

        # 检测 result.json → 通知 PM
        if [ -f "$task_dir/result.json" ]; then
            result_key="${task_id}_result"
            if ! is_notified "$result_key" || is_file_newer_than_notified "$result_key" "$task_dir/result.json"; then
                agent=$(json_pick "$task_dir/result.json" agent agent_id)
                result_status=$(json_pick "$task_dir/result.json" status)
                summary=$(json_pick "$task_dir/result.json" summary)

                if [ "$result_status" = "done" ]; then
                    set_task_status "$task_dir" "ready_for_merge" "watcher observed result.json status=done"
                    notify_pm "[task-watcher] $task_id 已完成（agent: ${agent:-?}）。摘要：$(truncate_utf8 "$summary" 60)。请验收并决定是否推进下游任务。"
                    push_feishu "📋 $task_id 完成: $(truncate_utf8 "$summary" 60)"
                elif [ "$result_status" = "blocked" ]; then
                    set_task_status "$task_dir" "blocked" "watcher observed result.json status=blocked"
                    notify_pm "[task-watcher] $task_id 被 agent ${agent:-?} 标记为 blocked。摘要：$(truncate_utf8 "$summary" 60)。请处理。"
                    push_feishu "⚠️ $task_id 阻塞: $(truncate_utf8 "$summary" 60)"
                else
                    notify_pm "[task-watcher] $task_id 有 result.json（status=$result_status），请检查。"
                fi

                sync_task_board "$task_dir" "result-detected"
                mark_notified "$result_key"
            fi
        fi

        # 检测 review.md → 通知 PM 审查完成
        if [ -f "$task_dir/review.md" ]; then
            review_key="${task_id}_review"
            if ! is_notified "$review_key" || is_file_newer_than_notified "$review_key" "$task_dir/review.md"; then
                review_pass=$(grep -qi '通过\|approve' "$task_dir/review.md" && echo "pass" || echo "")
                review_fail=$(grep -qi '不通过\|未通过\|驳回\|reject\|block\|不接受\|request changes' "$task_dir/review.md" && echo "fail" || echo "")
                if [ "$review_pass" = "pass" ] && [ -z "$review_fail" ]; then
                    review_conclusion=$(grep -i '通过\|approve' "$task_dir/review.md" | head -1)
                    notify_pm "[task-watcher] $task_id 审查已完成（通过），请验收并决定是否推进下游任务。"
                    push_feishu "✅ $task_id 审查通过: $review_conclusion"
                else
                    review_conclusion=$(grep -i '不通过\|未通过\|驳回\|reject\|block\|不接受\|request changes' "$task_dir/review.md" | head -1)
                    notify_pm "[task-watcher] $task_id 审查未通过，需要修改。请安排修复。"
                    push_feishu "❌ $task_id 审查未通过: $review_conclusion"
                fi
                sync_task_board "$task_dir" "review-detected"
                mark_notified "$review_key"
            fi
        fi

        # 检测 verify.json → 通知 PM 审查结果
        if [ -f "$task_dir/verify.json" ]; then
            verify_key="${task_id}_verify"
            if ! is_notified "$verify_key"; then
                verify_pass=$(json_pick "$task_dir/verify.json" ok pass)
                if [ "$verify_pass" = "True" ] || [ "$verify_pass" = "true" ] || [ "$verify_pass" = "1" ]; then
                    notify_pm "[task-watcher] $task_id verify 通过，可以合并。"
                else
                    notify_pm "[task-watcher] $task_id verify 未通过，请检查 verify.json。"
                fi
                sync_task_board "$task_dir" "verify-detected"
                mark_notified "$verify_key"
            fi
        fi

        sync_if_changed "$task_dir" "$task_dir/task.json" "taskjson"
        sync_if_changed "$task_dir" "$task_dir/transitions.jsonl" "transitions"
        sync_if_changed "$task_dir" "$task_dir/ack.json" "ack"
        sync_if_changed "$task_dir" "$task_dir/result.json" "result"
        sync_if_changed "$task_dir" "$task_dir/review.md" "review"
        sync_if_changed "$task_dir" "$task_dir/verify.json" "verify"
    done

    sleep "$INTERVAL"
done
