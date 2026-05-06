#!/bin/bash
# task-watcher.sh - 监控 tasks/ 目录下的任务状态变更，执行事件驱动自动流转，并同步任务看板 SQLite 数据。
# 关键职责：
# - ack.json 新增 → 更新 task.json 状态为 working
# - result.json 新增 → 根据任务类型自动通知 PM / reviewer
# - review 通过 → 自动通知 qa-1
# - verify 通过 → 自动执行 close-task.sh 收口
# - review 驳回 / QA 失败 → 通知 PM 仲裁

TASKS_ROOT="${TASKS_ROOT:-/Users/lin/Desktop/work/my-agent-teams/tasks}"
PM_SESSION="${PM_SESSION:-pm-chief}"
QA_SESSION="${QA_SESSION:-qa-1}"
PUSH_SCRIPT="${PUSH_SCRIPT:-/Users/lin/.openclaw/workspace/scripts/feishu-push.sh}"
USER_ID="${USER_ID:-ou_f95ee559a38a607c5f312e7b64304143}"
STATE_DIR="${STATE_DIR:-/Users/lin/.openclaw/workspace/.task-watcher}"
BOARD_SYNC_SCRIPT="${BOARD_SYNC_SCRIPT:-/Users/lin/Desktop/work/my-agent-teams/scripts/task-board-sync.py}"
SEND_SCRIPT="${SEND_SCRIPT:-/Users/lin/Desktop/work/my-agent-teams/scripts/send-to-agent.sh}"
SEND_CHAT_SCRIPT="${SEND_CHAT_SCRIPT:-/Users/lin/Desktop/work/my-agent-teams/scripts/send-chat.sh}"
CLOSE_TASK_SCRIPT="${CLOSE_TASK_SCRIPT:-/Users/lin/Desktop/work/my-agent-teams/scripts/close-task.sh}"
CONFIG_PATH="${CONFIG_PATH:-/Users/lin/Desktop/work/my-agent-teams/config.json}"
AUTO_ASSIGN_MARKERS="${AUTO_ASSIGN_MARKERS:-auto,auto-dev,unassigned}"
ARCH_AUTO_DISPATCH="${ARCH_AUTO_DISPATCH:-1}"
DEV_AUTO_CLAIM="${DEV_AUTO_CLAIM:-1}"
INTERVAL="${INTERVAL:-5}"
PID_FILE="${PID_FILE:-$STATE_DIR/task-watcher.pid}"
HEARTBEAT_FILE="${HEARTBEAT_FILE:-$STATE_DIR/task-watcher-heartbeat.json}"
RESTART_CAUSE_FILE="${RESTART_CAUSE_FILE:-$STATE_DIR/task-watcher-restart-cause.txt}"
LOG_DIR="${LOG_DIR:-/Users/lin/.openclaw/workspace/logs}"
LOG_FILE="${LOG_FILE:-$LOG_DIR/task-watcher.log}"
LOG_RETENTION_DAYS="${LOG_RETENTION_DAYS:-7}"
DISPATCH_RESEND_AFTER_SECONDS="${DISPATCH_RESEND_AFTER_SECONDS:-300}"
RESEND_COOLDOWN_SECONDS="${RESEND_COOLDOWN_SECONDS:-300}"
WORKING_TIMEOUT_SECONDS="${WORKING_TIMEOUT_SECONDS:-1800}"

LAST_LOG_ROTATE_DAY=""
WATCHER_STARTED_AT_EPOCH="$(date +%s)"

mkdir -p "$STATE_DIR"

rotate_watcher_log_if_needed() {
    local today file_day archive_file retention_days
    today=$(date '+%Y-%m-%d')
    [ "$LAST_LOG_ROTATE_DAY" = "$today" ] && return 0
    LAST_LOG_ROTATE_DAY="$today"

    mkdir -p "$LOG_DIR" 2>/dev/null || return 0

    if [ -f "$LOG_FILE" ]; then
        file_day=$(python3 - "$LOG_FILE" <<'PY'
import os
import sys
from datetime import datetime

try:
    ts = os.path.getmtime(sys.argv[1])
except Exception:
    raise SystemExit(1)
print(datetime.fromtimestamp(ts).strftime('%Y-%m-%d'))
PY
)
        if [ -n "$file_day" ] && [ "$file_day" != "$today" ]; then
            archive_file="$LOG_DIR/task-watcher.${file_day}.log"
            if [ -f "$archive_file" ]; then
                cat "$LOG_FILE" >> "$archive_file" 2>/dev/null || true
                : > "$LOG_FILE"
            else
                mv "$LOG_FILE" "$archive_file" 2>/dev/null || true
            fi
        fi
    fi

    retention_days="$LOG_RETENTION_DAYS"
    [ -n "$retention_days" ] || retention_days=7
    if [ "$retention_days" -gt 0 ] 2>/dev/null; then
        find "$LOG_DIR" -maxdepth 1 -type f -name 'task-watcher.*.log' -mtime "+$((retention_days - 1))" -delete 2>/dev/null || true
    fi
}

log() {
    local line
    line="$(date '+%Y-%m-%d %H:%M:%S') $*"
    echo "$line"
    rotate_watcher_log_if_needed
    printf '%s\n' "$line" >> "$LOG_FILE" 2>/dev/null || true
}

ensure_single_instance() {
    local existing_pid=""
    existing_pid=$(cat "$PID_FILE" 2>/dev/null || true)
    if [ -n "$existing_pid" ] && [ "$existing_pid" != "$$" ] && kill -0 "$existing_pid" 2>/dev/null; then
        log "task-watcher 已在运行（pid=$existing_pid），当前实例退出"
        exit 0
    fi
}

write_pid_file() {
    printf '%s\n' "$$" > "$PID_FILE"
}

write_heartbeat() {
    local phase="${1:-running}"
    python3 - "$HEARTBEAT_FILE" "$$" "$phase" "$INTERVAL" <<'PY'
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

heartbeat_path = Path(sys.argv[1])
payload = {
    "pid": int(sys.argv[2]),
    "phase": sys.argv[3],
    "interval_seconds": int(sys.argv[4]),
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

cleanup_task_watcher_runtime() {
    local existing_pid=""
    existing_pid=$(cat "$PID_FILE" 2>/dev/null || true)
    if [ "$existing_pid" = "$$" ]; then
        rm -f "$PID_FILE"
    fi
}

stop_task_watcher() {
    cleanup_task_watcher_runtime
    exit 0
}

trap cleanup_task_watcher_runtime EXIT
trap stop_task_watcher INT TERM

ensure_single_instance
write_pid_file

# 安全截断 UTF-8 字符串（按字符数，避免截断多字节字符）
truncate_utf8() {
    local str="$1"
    local max_len="${2:-60}"
    python3 -c "import sys; s=sys.stdin.read(); print(s[:$max_len] if len(s)>$max_len else s)" <<< "$str" 2>/dev/null
}

now_iso() {
    python3 - <<'PY'
from datetime import datetime
print(datetime.now().astimezone().isoformat(timespec='seconds'))
PY
}

legacy_send_tmux() {
    local session="$1"
    local msg="$2"
    local is_codex=0
    case "$session" in
        arch-1|dev-1|dev-2|review-1|pm-chief) is_codex=1 ;;
    esac

    if [ "$is_codex" = "1" ]; then
        tmux send-keys -t "$session" i 2>/dev/null &
        local pid=$!
        sleep 0.3
        kill "$pid" 2>/dev/null; wait "$pid" 2>/dev/null
    fi

    tmux send-keys -t "$session" -l -- "$msg" 2>/dev/null &
    local pid=$!
    sleep 2
    kill "$pid" 2>/dev/null; wait "$pid" 2>/dev/null

    tmux send-keys -t "$session" Enter 2>/dev/null &
    pid=$!
    sleep 0.5
    kill "$pid" 2>/dev/null; wait "$pid" 2>/dev/null
}

send_session_message() {
    local session="$1"
    local msg="$2"

    if [ -x "$SEND_SCRIPT" ]; then
        if "$SEND_SCRIPT" "$session" "$msg" >/dev/null 2>&1; then
            log "通知 $session: $msg"
            return 0
        fi
        log "send-to-agent.sh 发送失败，回退 legacy tmux: $session"
    fi

    legacy_send_tmux "$session" "$msg"
    log "通知 $session: $msg"
}

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
    if [ -x "$PUSH_SCRIPT" ]; then
        local tmpfile
        tmpfile=$(mktemp)
        echo "$msg" > "$tmpfile"
        FEISHU_RECEIVE_ID="$USER_ID" "$PUSH_SCRIPT" < "$tmpfile" 2>/dev/null &
        disown
        rm -f "$tmpfile"
    fi
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
    push_feishu "$message"
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
        --source-name "$source_name" >/dev/null 2>&1 || true
}

# 检查 task.json 中的 status
get_task_status() {
    local task_dir="$1"
    python3 -c "import json; print(json.load(open('$task_dir/task.json')).get('status','unknown'))" 2>/dev/null
}

task_timestamp_epoch() {
    local task_dir="$1"
    shift
    python3 - "$task_dir/task.json" "$@" <<'PY'
import json
import sys
from datetime import datetime
from pathlib import Path

path = Path(sys.argv[1])
keys = sys.argv[2:]
payload = json.loads(path.read_text(encoding='utf-8'))
for key in keys:
    value = payload.get(key)
    if not value:
        continue
    try:
        print(int(datetime.fromisoformat(str(value)).timestamp()))
        raise SystemExit(0)
    except Exception:
        continue
print(0)
PY
}

task_dispatch_reference_epoch() {
    local task_dir="$1"
    task_timestamp_epoch "$task_dir" lease_acquired_at updated_at
}

task_working_reference_epoch() {
    local task_dir="$1"
    if [ -f "$task_dir/ack.json" ]; then
        stat -f %m "$task_dir/ack.json" 2>/dev/null && return 0
    fi
    task_timestamp_epoch "$task_dir" updated_at
}

task_has_progress_artifact() {
    local task_dir="$1"
    [ -f "$task_dir/result.json" ] || [ -f "$task_dir/review.md" ] || [ -f "$task_dir/design-review.md" ] || [ -f "$task_dir/verify.json" ]
}

agent_has_working_signal() {
    local agent_session="$1"
    local is_working=0
    if [ -n "$agent_session" ] && tmux has-session -t "$agent_session" 2>/dev/null; then
        is_working=$(tmux capture-pane -t "$agent_session" -p 2>/dev/null | grep -c 'Working\|• Working' || true)
    fi
    printf '%s\n' "${is_working:-0}"
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

task_json_pick() {
    local task_dir="$1"
    shift
    json_pick "$task_dir/task.json" "$@"
}

task_reviewers() {
    local task_dir="$1"
    python3 - "$task_dir/task.json" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
payload = json.loads(path.read_text(encoding='utf-8'))
review_level = str(payload.get('review_level') or '').strip().lower()
reviewers = payload.get('reviewers') if isinstance(payload.get('reviewers'), list) else []
reviewers = [str(item).strip() for item in reviewers if str(item).strip()]
if not reviewers:
    reviewer = str(payload.get('reviewer') or '').strip()
    if reviewer:
        reviewers = [reviewer]
if not reviewers:
    if review_level == 'complex':
        reviewers = ['review-1', 'arch-1']
    elif review_level == 'standard':
        reviewers = ['review-1']
for reviewer in reviewers:
    print(reviewer)
PY
}

list_dev_agents() {
    python3 - "$CONFIG_PATH" <<'PY'
import json
import sys
from pathlib import Path

config = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
agents = config.get('agents') or {}

for agent_id, payload in agents.items():
    role = str((payload or {}).get('role') or '').strip().lower()
    if role == 'fullstack_dev' or agent_id.startswith('dev-'):
        print(agent_id)
PY
}

matches_auto_assign_marker() {
    local value="$1"
    [ -z "$value" ] && return 0
    python3 - "$value" "$AUTO_ASSIGN_MARKERS" <<'PY'
import sys

value = sys.argv[1].strip().lower()
markers = {item.strip().lower() for item in sys.argv[2].split(',') if item.strip()}
raise SystemExit(0 if value in markers else 1)
PY
}

dependencies_ready() {
    local task_dir="$1"
    python3 - "$task_dir" "$TASKS_ROOT" <<'PY'
import json
import sys
from pathlib import Path

task_dir = Path(sys.argv[1])
tasks_root = Path(sys.argv[2])
task = json.loads((task_dir / 'task.json').read_text(encoding='utf-8'))
depends_on = task.get('depends_on') or []
policy = str(task.get('dependency_policy') or 'done_only').strip().lower()
allowed = {'done', 'cancelled'}
if policy == 'ready_for_merge_ok':
    allowed.add('ready_for_merge')

for dep in depends_on:
    dep_path = tasks_root / dep / 'task.json'
    if not dep_path.exists():
        print(f'missing:{dep}')
        raise SystemExit(1)
    dep_task = json.loads(dep_path.read_text(encoding='utf-8'))
    if str(dep_task.get('status') or '') not in allowed:
        print(f'blocked:{dep}:{dep_task.get("status")}')
        raise SystemExit(1)

print('ready')
PY
}

active_task_count_for_agent() {
    local agent_id="$1"
    python3 - "$TASKS_ROOT" "$agent_id" <<'PY'
import json
import sys
from pathlib import Path

tasks_root = Path(sys.argv[1])
agent_id = sys.argv[2]
active = {'dispatched', 'working'}
count = 0

for task_path in tasks_root.glob('*/task.json'):
    task = json.loads(task_path.read_text(encoding='utf-8'))
    if str(task.get('assigned_agent') or '') == agent_id and str(task.get('status') or '') in active:
        count += 1

print(count)
PY
}

working_task_count_for_agent() {
    local agent_id="$1"
    python3 - "$TASKS_ROOT" "$agent_id" <<'PY'
import json
import sys
from pathlib import Path

tasks_root = Path(sys.argv[1])
agent_id = sys.argv[2]
count = 0
for task_path in tasks_root.glob('*/task.json'):
    task = json.loads(task_path.read_text(encoding='utf-8'))
    if str(task.get('assigned_agent') or '') == agent_id and str(task.get('status') or '') == 'working':
        count += 1
print(count)
PY
}

priority_rank() {
    local value="${1:-}"
    case "$value" in
        critical) echo 4 ;;
        high) echo 3 ;;
        medium) echo 2 ;;
        low) echo 1 ;;
        *) echo 0 ;;
    esac
}

task_claim_max_concurrency() {
    local task_dir="$1"
    python3 - "$task_dir/task.json" "$CONFIG_PATH" <<'PY'
import json
import sys
from pathlib import Path

task = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
config = json.loads(Path(sys.argv[2]).read_text(encoding='utf-8'))
value = task.get('claim_max_concurrency')
if value in (None, ''):
    value = config.get('task_pool', {}).get('default_claim_max_concurrency', 1)
print(int(value))
PY
}

task_claim_scope() {
    local task_dir="$1"
    python3 - "$task_dir/task.json" "$CONFIG_PATH" <<'PY'
import json
import sys
from pathlib import Path

task = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
config = json.loads(Path(sys.argv[2]).read_text(encoding='utf-8'))
scope = task.get('claim_scope')
if isinstance(scope, list) and scope:
    for item in scope:
        value = str(item).strip()
        if value:
            print(value)
    raise SystemExit(0)

task_type = str(task.get('task_type') or '').strip().lower()
domain = str(task.get('domain') or '').strip().lower()
agents = config.get('agents') or {}
for agent_id, payload in agents.items():
    role = str((payload or {}).get('role') or '').strip().lower()
    if task_type in {'development', 'investigation'}:
        if role == 'fullstack_dev' or agent_id.startswith('dev-'):
            print(agent_id)
    elif task_type == 'verification' or domain == 'quality':
        if role == 'qa' or agent_id.startswith('qa-'):
            print(agent_id)
    elif task_type == 'design':
        if role == 'architect' or agent_id == 'arch-1':
            print(agent_id)
PY
}

is_agent_in_claim_scope() {
    local task_dir="$1"
    local agent_id="$2"
    task_claim_scope "$task_dir" | grep -qx "$agent_id"
}

claim_scope_conflict_free() {
    local task_dir="$1"
    local agent_id="$2"
    python3 - "$task_dir/task.json" "$TASKS_ROOT" "$agent_id" <<'PY'
import json
import sys
from pathlib import Path

def is_relative_to(path: Path, other: Path) -> bool:
    try:
        path.relative_to(other)
        return True
    except ValueError:
        return False

def scopes_overlap(a: Path, b: Path) -> bool:
    return a == b or is_relative_to(a, b) or is_relative_to(b, a)

task = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
tasks_root = Path(sys.argv[2])
agent_id = sys.argv[3]
target_scope = [str(item).strip() for item in (task.get('write_scope') or []) if str(item).strip()]
if not target_scope:
    raise SystemExit(0)
target_scope = [Path(item).expanduser().resolve() for item in target_scope]

for task_path in tasks_root.glob('*/task.json'):
    payload = json.loads(task_path.read_text(encoding='utf-8'))
    if str(payload.get('assigned_agent') or '') != agent_id:
        continue
    if str(payload.get('status') or '') not in {'dispatched', 'working'}:
        continue
    other_scope = [str(item).strip() for item in (payload.get('write_scope') or []) if str(item).strip()]
    for raw in other_scope:
        other = Path(raw).expanduser().resolve()
        for target in target_scope:
            if scopes_overlap(target, other):
                print(f'conflict:{task_path.parent.name}:{raw}')
                raise SystemExit(1)
raise SystemExit(0)
PY
}

claim_dependencies_ready() {
    local task_dir="$1"
    dependencies_ready "$task_dir" >/dev/null 2>&1
}

claim_agent_can_accept_task() {
    local task_dir="$1"
    local agent_id="$2"

    is_agent_in_claim_scope "$task_dir" "$agent_id" || return 1
    claim_dependencies_ready "$task_dir" || return 1
    claim_scope_conflict_free "$task_dir" "$agent_id" >/dev/null 2>&1 || return 1

    local working_count active_count max_concurrency
    working_count=$(working_task_count_for_agent "$agent_id" 2>/dev/null || echo 0)
    [ "${working_count:-0}" -le 0 ] || return 1
    active_count=$(active_task_count_for_agent "$agent_id" 2>/dev/null || echo 0)
    max_concurrency=$(task_claim_max_concurrency "$task_dir" 2>/dev/null || echo 1)
    [ "${active_count:-0}" -lt "${max_concurrency:-1}" ]
}

claim_scope_idle_candidates() {
    local task_dir="$1"
    while IFS= read -r agent_id; do
        [ -n "$agent_id" ] || continue
        if is_idle_agent "$agent_id" && claim_agent_can_accept_task "$task_dir" "$agent_id"; then
            echo "$agent_id"
        fi
    done <<< "$(task_claim_scope "$task_dir")"
}

list_pooled_candidates_for_agent() {
    local agent_id="$1"
    python3 - "$TASKS_ROOT" "$agent_id" <<'PY'
import json
import sys
from datetime import datetime
from pathlib import Path

tasks_root = Path(sys.argv[1])
agent_id = sys.argv[2]
priority_rank = {'critical': 4, 'high': 3, 'medium': 2, 'low': 1}
rows = []
for task_path in tasks_root.glob('*/task.json'):
    try:
        task = json.loads(task_path.read_text(encoding='utf-8'))
    except Exception:
        continue
    if str(task.get('status') or '') != 'pooled':
        continue
    scope = [str(item).strip() for item in (task.get('claim_scope') or []) if str(item).strip()]
    if scope and agent_id not in scope:
        continue
    pool_entered_at = str(task.get('pool_entered_at') or task.get('created_at') or '')
    rows.append({
        'task_id': str(task.get('id') or task_path.parent.name),
        'priority_rank': priority_rank.get(str(task.get('priority') or '').strip().lower(), 0),
        'pool_entered_at': pool_entered_at,
    })

def sort_key(item):
    try:
        ts = datetime.fromisoformat(item['pool_entered_at'].replace('Z', '+00:00'))
    except Exception:
        ts = datetime.max
    return (-item['priority_rank'], ts, item['task_id'])

for item in sorted(rows, key=sort_key):
    print(item['task_id'])
PY
}

auto_push_next_task_for_agent() {
    local agent_id="$1"
    local trigger_task_id="${2:-}"
    [ -n "$agent_id" ] || return 1

    local active_count
    active_count=$(active_task_count_for_agent "$agent_id" 2>/dev/null || echo 0)
    [ "${active_count:-0}" -eq 0 ] || return 1

    local next_task=""
    while IFS= read -r candidate; do
        [ -n "$candidate" ] || continue
        local candidate_dir="$TASKS_ROOT/$candidate"
        [ -f "$candidate_dir/task.json" ] || continue
        if claim_agent_can_accept_task "$candidate_dir" "$agent_id"; then
            next_task="$candidate"
            break
        fi
    done <<< "$(list_pooled_candidates_for_agent "$agent_id")"

    [ -n "$next_task" ] || return 1

    local reason="watcher auto-continued after ${trigger_task_id:-previous task completion}"
    if CLAIM_AGENT_ID="$agent_id" TASKS_ROOT="$TASKS_ROOT" CONFIG_PATH="$CONFIG_PATH" /Users/lin/Desktop/work/my-agent-teams/scripts/claim-task.sh "$next_task" "$reason" >/dev/null 2>&1; then
        notify_agent "$agent_id" "你当前主线已完成/进入待审。下一条可执行任务已自动续推：${next_task}。请读取 ${TASKS_ROOT}/${next_task}/instruction.md，并在确认后写 ack.json 开始执行。"
        emit_system_chat_event nudge "$next_task" "上一条主线完成后，已自动续推给 ${agent_id} 作为下一条可执行任务。" "$agent_id" info nudge
        log "${next_task}: 已在 ${trigger_task_id:-unknown} 完成后自动续推给 ${agent_id}"
        return 0
    fi

    return 1
}

auto_push_next_review_for_agent() {
    local agent_id="$1"
    local trigger_task_id="${2:-}"
    [ -n "$agent_id" ] || return 1

    queue_state_current_task "review" "$agent_id" >/dev/null 2>&1 && return 1
    is_idle_agent "$agent_id" || return 1

    local next_task=""
    while IFS= read -r candidate; do
        [ -n "$candidate" ] || continue
        next_task="$candidate"
        break
    done <<< "$(list_review_candidates_for_agent "$agent_id")"
    [ -n "$next_task" ] || return 1

    queue_state_set "review" "$agent_id" "$next_task"
    notify_agent "$agent_id" "请读取 ${TASKS_ROOT}/${next_task}/instruction.md 与 result.json，并输出 review.md。"
    emit_system_chat_event nudge "$next_task" "review 队列已在 ${trigger_task_id:-idle sweep} 后自动续推给 ${agent_id}。" "$agent_id" info nudge
    log "${next_task}: 已自动续推 review 任务给 ${agent_id}"
    return 0
}

auto_push_next_qa_for_agent() {
    local agent_id="$1"
    local trigger_task_id="${2:-}"
    [ -n "$agent_id" ] || return 1

    queue_state_current_task "qa" "$agent_id" >/dev/null 2>&1 && return 1
    is_idle_agent "$agent_id" || return 1

    local next_task=""
    while IFS= read -r candidate; do
        [ -n "$candidate" ] || continue
        next_task="$candidate"
        break
    done <<< "$(list_qa_candidates_for_agent "$agent_id")"
    [ -n "$next_task" ] || return 1

    queue_state_set "qa" "$agent_id" "$next_task"
    notify_agent "$agent_id" "请读取 ${TASKS_ROOT}/${next_task}/instruction.md、result/review artifacts，并输出 verify.json。"
    emit_system_chat_event nudge "$next_task" "QA 队列已在 ${trigger_task_id:-idle sweep} 后自动续推给 ${agent_id}。" "$agent_id" info nudge
    log "${next_task}: 已自动续推 QA 任务给 ${agent_id}"
    return 0
}

is_idle_agent() {
    local agent_id="$1"
    local active_count
    active_count=$(active_task_count_for_agent "$agent_id" 2>/dev/null || echo 0)
    if [ "${active_count:-0}" -gt 0 ]; then
        return 1
    fi
    if tmux has-session -t "$agent_id" 2>/dev/null; then
        local is_working
        is_working=$(tmux capture-pane -t "$agent_id" -p 2>/dev/null | grep -c 'Working\|• Working' || true)
        [ "${is_working:-0}" -eq 0 ]
        return $?
    fi
    return 1
}

select_idle_dev_agent() {
    local dev_file="$STATE_DIR/.dev-candidates.tmp"
    local order_file="$STATE_DIR/.dev-order.tmp"
    list_dev_agents > "$dev_file"
    [ -s "$dev_file" ] || { rm -f "$dev_file" "$order_file"; return 1; }

    local state_file="$STATE_DIR/auto_claim_last_dev"
    local last_dev
    last_dev=$(cat "$state_file" 2>/dev/null || true)

    python3 - "$last_dev" "$dev_file" <<'PY' > "$order_file"
import sys
from pathlib import Path

last_dev = sys.argv[1].strip()
devs = [line.strip() for line in Path(sys.argv[2]).read_text(encoding='utf-8').splitlines() if line.strip()]
if last_dev in devs:
    idx = devs.index(last_dev)
    devs = devs[idx + 1:] + devs[:idx + 1]
for dev in devs:
    print(dev)
PY

    local dev
    while IFS= read -r dev; do
        [ -n "$dev" ] || continue
        if is_idle_agent "$dev"; then
            echo "$dev" > "$state_file"
            rm -f "$dev_file" "$order_file"
            echo "$dev"
            return 0
        fi
    done < "$order_file"

    rm -f "$dev_file" "$order_file"
    return 1
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

# 更新 task.json status / gate 字段，并在状态变化时追加 transitions.jsonl 记录
update_task_record() {
    local task_dir="$1"
    local new_status="${2:-}"
    local reason="${3:-watcher status update}"
    local patch_json="${4:-{}}"
    local output=""
    output=$(python3 - "$task_dir" "$new_status" "$reason" "$patch_json" <<'PY'
import json
import sys
from datetime import datetime
from pathlib import Path

task_dir = Path(sys.argv[1])
new_status = sys.argv[2].strip()
reason = sys.argv[3]
patch_json = sys.argv[4].strip() or '{}'
task_path = task_dir / 'task.json'
transitions_path = task_dir / 'transitions.jsonl'
task = json.loads(task_path.read_text(encoding='utf-8'))
old_status = task.get('status', '')
now = datetime.now().astimezone().isoformat(timespec='seconds')
patch = json.loads(patch_json)

status_changed = bool(new_status) and old_status != new_status
fields_changed = False

if new_status:
    task['status'] = new_status

for key, value in patch.items():
    if task.get(key) != value:
        task[key] = value
        fields_changed = True

if not status_changed and not fields_changed:
    print(f'unchanged: status={old_status}')
    raise SystemExit(0)

task['updated_at'] = now
task_path.write_text(json.dumps(task, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
if status_changed:
    with transitions_path.open('a', encoding='utf-8') as fp:
        fp.write(json.dumps({
            'from': old_status,
            'to': new_status,
            'at': now,
            'reason': reason,
        }, ensure_ascii=False) + '\n')
    print(f'status: {old_status} -> {new_status}')
else:
    print(f'fields updated without status change: {",".join(sorted(patch.keys()))}')
PY
)
    local status_rc=$?
    if [ -n "$output" ]; then
        log "$(basename "$task_dir"): $output | reason=$reason"
    fi
    return $status_rc
}

set_task_status() {
    local task_dir="$1"
    local new_status="$2"
    local reason="${3:-watcher status update}"
    update_task_record "$task_dir" "$new_status" "$reason" '{}'
}

set_task_fields() {
    local task_dir="$1"
    local patch_json="${2:-{}}"
    local reason="${3:-watcher metadata update}"
    update_task_record "$task_dir" "" "$reason" "$patch_json"
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

final_done_transition_epoch() {
    local task_dir="$1"
    python3 - "$task_dir/transitions.jsonl" <<'PY'
import json
import sys
from datetime import datetime
from pathlib import Path

transitions_path = Path(sys.argv[1])
latest_epoch = 0

if transitions_path.exists():
    for line in transitions_path.read_text(encoding='utf-8', errors='ignore').splitlines():
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except Exception:
            continue
        if str(event.get('from') or '') != 'ready_for_merge' or str(event.get('to') or '') != 'done':
            continue
        raw_at = str(event.get('at') or '').strip()
        if not raw_at:
            continue
        try:
            epoch = int(datetime.fromisoformat(raw_at.replace('Z', '+00:00')).timestamp())
        except Exception:
            continue
        latest_epoch = max(latest_epoch, epoch)

print(latest_epoch)
PY
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

review_signature() {
    local task_dir="$1"
    local review_mtime="0"
    local design_review_mtime="0"
    [ -f "$task_dir/review.md" ] && review_mtime=$(stat -f %m "$task_dir/review.md" 2>/dev/null || echo 0)
    [ -f "$task_dir/design-review.md" ] && design_review_mtime=$(stat -f %m "$task_dir/design-review.md" 2>/dev/null || echo 0)
    echo "${review_mtime}:${design_review_mtime}"
}

is_signature_newer_than_notified() {
    local key="$1"
    local signature="$2"
    local flag="$STATE_DIR/$key"
    [ -f "$flag" ] || return 0
    local last_sig
    last_sig=$(cat "$flag" 2>/dev/null)
    [ "$last_sig" != "$signature" ]
}

mark_signature_notified() {
    local key="$1"
    local signature="$2"
    echo "$signature" > "$STATE_DIR/$key"
}

review_file_state() {
    local review_file="$1"
    [ -f "$review_file" ] || { echo "missing"; return 0; }

    # 优先提取明确的结论行（## 结论 / ## 最终意见 / 结论： 等标题下的内容）
    local conclusion_block
    conclusion_block=$(awk '/^(#{1,4}\s*(结论|最终意见|审查结论|Conclusion|Summary|Verdict))/,/^#{1,3}\s/ {print}' "$review_file" 2>/dev/null)
    local scan_text
    scan_text="${conclusion_block:-$(cat "$review_file")}"

    # 在结论块（或全文）中检测通过/驳回信号
    local pass=""
    local fail=""
    # 通过信号
    echo "$scan_text" | grep -qi '通过\|approve\|approved\|lgtm\|ship it' && pass="pass" || true
    # 驳回信号 — 使用更精确的模式，避免「review blocker」等上下文词误触发
    #   - 不通过 / 未通过：完整词组
    #   - 驳回 / reject / block：后面紧跟标点或空白（即独立词），
    #     或以 blocked / blocking 形式出现但不在「review blocker」上下文中
    #   - 不接受 / request changes：完整词组
    echo "$scan_text" | grep -qiwE '不通过|未通过|驳回|reject|不接受|request.changes' && fail="fail" || true
    if [ -z "$fail" ]; then
        # block 独立词检测（非 blocker/blocking 等衍生词，排除 review blocker 上下文）
        echo "$scan_text" | grep -qiwE '\<block\>' && fail="fail" || true
    fi
    if [ -n "$fail" ] && [ -n "$pass" ]; then
        # 两者同时出现时：看谁出现在结论块更靠后的位置（结论块优先）
        if [ -n "$conclusion_block" ]; then
            local last_pass_line last_fail_line
            last_pass_line=$(echo "$conclusion_block" | grep -ni '通过\|approve\|approved' | tail -1 | cut -d: -f1)
            last_fail_line=$(echo "$conclusion_block" | grep -niE '不通过|未通过|驳回|reject|\\<block\\>|不接受|request.changes' | tail -1 | cut -d: -f1)
            if [ -n "$last_pass_line" ] && [ -n "$last_fail_line" ]; then
                if [ "$last_pass_line" -ge "$last_fail_line" ] 2>/dev/null; then
                    echo "pass"
                    return 0
                fi
            fi
        fi
        # 无法区分优先级时，默认通过（宁可多走 QA 也不误报驳回）
        echo "pass"
        return 0
    elif [ -n "$fail" ]; then
        echo "fail"
    elif [ -n "$pass" ]; then
        echo "pass"
    else
        echo "pending"
    fi
}

review_state() {
    local task_dir="$1"
    local review_level="$2"

    local review_main_state
    review_main_state=$(review_file_state "$task_dir/review.md")

    if [ "$review_level" = "complex" ]; then
        local design_state
        design_state=$(review_file_state "$task_dir/design-review.md")
        if [ "$review_main_state" = "fail" ] || [ "$design_state" = "fail" ]; then
            echo "fail"
        elif [ "$review_main_state" = "pass" ] && [ "$design_state" = "pass" ]; then
            echo "pass"
        else
            echo "pending"
        fi
    else
        if [ "$review_main_state" = "fail" ]; then
            echo "fail"
        elif [ "$review_main_state" = "pass" ]; then
            echo "pass"
        else
            echo "pending"
        fi
    fi
}

first_review_conclusion() {
    local task_dir="$1"
    local line
    line=$(grep -i '不通过\|未通过\|驳回\|reject\|block\|不接受\|request changes\|通过\|approve' "$task_dir/review.md" "$task_dir/design-review.md" 2>/dev/null | head -1)
    echo "$line"
}

verify_state() {
    local verify_file="$1"
    python3 - "$verify_file" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
if not path.exists():
    print('missing')
    raise SystemExit(0)

payload = json.loads(path.read_text(encoding='utf-8'))
values = [
    payload.get('pass'),
    payload.get('ok'),
    payload.get('result'),
    payload.get('status'),
    payload.get('verdict'),
    payload.get('conclusion'),
]

for value in values:
    if isinstance(value, bool):
        print('pass' if value else 'fail')
        raise SystemExit(0)
    if value is None:
        continue
    normalized = str(value).strip().lower()
    if normalized in {'pass', 'passed', 'approve', 'approved', 'ok', 'true', '1', 'success', 'done'}:
        print('pass')
        raise SystemExit(0)
    if normalized in {'fail', 'failed', 'false', '0', 'reject', 'rejected', 'error', 'blocked'}:
        print('fail')
        raise SystemExit(0)

print('pending')
PY
}

verify_summary() {
    local verify_file="$1"
    json_pick "$verify_file" summary notes message conclusion
}

resolve_merge_gate_state() {
    local task_dir="$1"
    python3 - "$task_dir" <<'PY'
import json
import sys
from pathlib import Path

task_dir = Path(sys.argv[1])
task = json.loads((task_dir / 'task.json').read_text(encoding='utf-8'))
status = str(task.get('status') or 'pending').strip()
merge_gate_state = task.get('merge_gate_state')
review_required = bool(task.get('review_required'))
test_required = bool(task.get('test_required'))
review_level = str(task.get('review_level') or '').strip().lower()

def parse_review_file(path: Path) -> str:
    if not path.exists():
        return 'missing'
    text = path.read_text(encoding='utf-8', errors='ignore')
    lowered = text.lower()
    has_reject = any(token in lowered for token in ('request changes', 'reject', '不通过', '未通过', '驳回', '不接受'))
    has_approve = any(token in lowered for token in ('approve', 'approved', '通过', 'lgtm', 'ship it'))
    if has_reject:
        return 'fail'
    if has_approve:
        return 'pass'
    return 'pending'

def parse_review_state() -> str:
    review_main_state = parse_review_file(task_dir / 'review.md')
    if review_level == 'complex':
        design_state = parse_review_file(task_dir / 'design-review.md')
        if review_main_state == 'fail' or design_state == 'fail':
            return 'fail'
        if review_main_state == 'pass' and design_state == 'pass':
            return 'pass'
        return 'pending'
    if review_main_state == 'fail':
        return 'fail'
    if review_main_state == 'pass':
        return 'pass'
    return 'pending'

def parse_verify_state() -> str:
    path = task_dir / 'verify.json'
    if not path.exists():
        return 'missing'
    payload = json.loads(path.read_text(encoding='utf-8'))
    values = [
        payload.get('pass'),
        payload.get('ok'),
        payload.get('result'),
        payload.get('status'),
        payload.get('verdict'),
        payload.get('conclusion'),
    ]
    for value in values:
        if isinstance(value, bool):
            return 'pass' if value else 'fail'
        if value is None:
            continue
        normalized = str(value).strip().lower()
        if normalized in {'pass', 'passed', 'approve', 'approved', 'ok', 'true', '1', 'success', 'done'}:
            return 'pass'
        if normalized in {'fail', 'failed', 'false', '0', 'reject', 'rejected', 'error', 'blocked'}:
            return 'fail'
    return 'pending'

review_state = parse_review_state()
verify_state = parse_verify_state()

if status == 'done':
    print('closed')
    raise SystemExit(0)
if status in {'cancelled', 'failed', 'timeout', 'archived'}:
    print(str(merge_gate_state or status))
    raise SystemExit(0)
if status == 'blocked':
    if verify_state == 'fail':
        print('qa_failed')
    elif review_state == 'fail':
        print('review_rejected')
    else:
        print(str(merge_gate_state or 'blocked'))
    raise SystemExit(0)
if status != 'ready_for_merge':
    print(str(merge_gate_state or ''))
    raise SystemExit(0)

if verify_state == 'fail':
    print('qa_failed')
elif review_state == 'fail':
    print('review_rejected')
elif test_required and (not review_required or review_state == 'pass'):
    print('qa_pending')
elif review_required and review_state != 'pass':
    print('review_pending')
elif not test_required and (not review_required or review_state == 'pass'):
    print('pm_acceptance_pending')
else:
    print(str(merge_gate_state or ''))
PY
}

list_review_agents() {
    python3 - "$CONFIG_PATH" <<'PY'
import json
import sys
from pathlib import Path

config = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
for agent_id, payload in (config.get('agents') or {}).items():
    role = str((payload or {}).get('role') or '').strip().lower()
    if role in {'reviewer', 'architect'}:
        print(agent_id)
PY
}

list_qa_agents() {
    python3 - "$CONFIG_PATH" <<'PY'
import json
import sys
from pathlib import Path

config = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
for agent_id, payload in (config.get('agents') or {}).items():
    role = str((payload or {}).get('role') or '').strip().lower()
    if role == 'qa':
        print(agent_id)
PY
}

queue_state_file() {
    local queue_kind="$1"
    local agent_id="$2"
    printf '%s/%s-queue-%s.json\n' "$STATE_DIR" "$queue_kind" "$agent_id"
}

queue_state_current_task() {
    local queue_kind="$1"
    local agent_id="$2"
    python3 - "$(queue_state_file "$queue_kind" "$agent_id")" "$TASKS_ROOT" "$queue_kind" <<'PY'
import json
import sys
from pathlib import Path

state_path = Path(sys.argv[1])
tasks_root = Path(sys.argv[2])
queue_kind = sys.argv[3]
if not state_path.exists():
    raise SystemExit(1)
try:
    payload = json.loads(state_path.read_text(encoding='utf-8'))
except Exception:
    state_path.unlink(missing_ok=True)
    raise SystemExit(1)
task_id = str(payload.get('task_id') or '').strip()
if not task_id:
    state_path.unlink(missing_ok=True)
    raise SystemExit(1)
task_path = tasks_root / task_id / 'task.json'
if not task_path.exists():
    state_path.unlink(missing_ok=True)
    raise SystemExit(1)
task = json.loads(task_path.read_text(encoding='utf-8'))
status = str(task.get('status') or '')
gate = str(task.get('merge_gate_state') or '')
allowed_gate = 'review_pending' if queue_kind == 'review' else 'qa_pending'
if status != 'ready_for_merge' or gate != allowed_gate:
    state_path.unlink(missing_ok=True)
    raise SystemExit(1)
print(task_id)
PY
}

queue_state_set() {
    local queue_kind="$1"
    local agent_id="$2"
    local task_id="$3"
    python3 - "$(queue_state_file "$queue_kind" "$agent_id")" "$task_id" <<'PY'
import json
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path

state_path = Path(sys.argv[1])
task_id = sys.argv[2]
payload = {
    'task_id': task_id,
    'assigned_at': datetime.now().astimezone().isoformat(timespec='seconds'),
}
state_path.parent.mkdir(parents=True, exist_ok=True)
with tempfile.NamedTemporaryFile('w', delete=False, dir=str(state_path.parent), encoding='utf-8') as tmp:
    json.dump(payload, tmp, ensure_ascii=False, indent=2)
    tmp.write('\n')
tmp_path = Path(tmp.name)
os.replace(tmp_path, state_path)
PY
}

queue_state_clear() {
    local queue_kind="$1"
    local agent_id="$2"
    rm -f "$(queue_state_file "$queue_kind" "$agent_id")"
}

clear_review_queue_state_for_task() {
    local task_dir="$1"
    while IFS= read -r reviewer; do
        [ -n "$reviewer" ] || continue
        queue_state_clear "review" "$reviewer"
    done <<< "$(task_reviewers "$task_dir")"
}

clear_qa_queue_state() {
    while IFS= read -r qa_agent; do
        [ -n "$qa_agent" ] || continue
        queue_state_clear "qa" "$qa_agent"
    done <<< "$(list_qa_agents)"
}

list_review_candidates_for_agent() {
    local agent_id="$1"
    python3 - "$TASKS_ROOT" "$agent_id" <<'PY'
import json
import sys
from datetime import datetime
from pathlib import Path

tasks_root = Path(sys.argv[1])
agent_id = sys.argv[2]
priority_rank = {'critical': 4, 'urgent': 4, 'high': 3, 'medium': 2, 'low': 1}
rows = []
for task_path in tasks_root.glob('*/task.json'):
    try:
        task = json.loads(task_path.read_text(encoding='utf-8'))
    except Exception:
        continue
    if str(task.get('status') or '') != 'ready_for_merge':
        continue
    if str(task.get('merge_gate_state') or '') != 'review_pending':
        continue
    reviewers = task.get('reviewers') if isinstance(task.get('reviewers'), list) else []
    reviewers = [str(item).strip() for item in reviewers if str(item).strip()]
    if not reviewers:
        reviewer = str(task.get('reviewer') or '').strip()
        if reviewer:
            reviewers = [reviewer]
    if agent_id not in reviewers:
        continue
    queued_at = str(task.get('updated_at') or task.get('created_at') or '')
    rows.append({
        'task_id': str(task.get('id') or task_path.parent.name),
        'priority_rank': priority_rank.get(str(task.get('priority') or '').strip().lower(), 0),
        'queued_at': queued_at,
    })

def sort_key(item):
    try:
        ts = datetime.fromisoformat(item['queued_at'].replace('Z', '+00:00'))
    except Exception:
        ts = datetime.max
    return (-item['priority_rank'], ts, item['task_id'])

for item in sorted(rows, key=sort_key):
    print(item['task_id'])
PY
}

list_qa_candidates_for_agent() {
    local agent_id="$1"
    python3 - "$TASKS_ROOT" "$agent_id" <<'PY'
import json
import sys
from datetime import datetime
from pathlib import Path

tasks_root = Path(sys.argv[1])
agent_id = sys.argv[2]
priority_rank = {'critical': 4, 'urgent': 4, 'high': 3, 'medium': 2, 'low': 1}
rows = []
for task_path in tasks_root.glob('*/task.json'):
    try:
        task = json.loads(task_path.read_text(encoding='utf-8'))
    except Exception:
        continue
    if str(task.get('status') or '') != 'ready_for_merge':
        continue
    if str(task.get('merge_gate_state') or '') != 'qa_pending':
        continue
    claim_scope = task.get('claim_scope') if isinstance(task.get('claim_scope'), list) else []
    scope = [str(item).strip() for item in claim_scope if str(item).strip()]
    if scope and agent_id not in scope:
        continue
    queued_at = str(task.get('last_gate_decision_at') or task.get('updated_at') or task.get('created_at') or '')
    rows.append({
        'task_id': str(task.get('id') or task_path.parent.name),
        'priority_rank': priority_rank.get(str(task.get('priority') or '').strip().lower(), 0),
        'queued_at': queued_at,
    })

def sort_key(item):
    try:
        ts = datetime.fromisoformat(item['queued_at'].replace('Z', '+00:00'))
    except Exception:
        ts = datetime.max
    return (-item['priority_rank'], ts, item['task_id'])

for item in sorted(rows, key=sort_key):
    print(item['task_id'])
PY
}

dispatch_task_to_agent() {
    local task_dir="$1"
    local assigned_agent="$2"
    local reason="$3"
    local claimed_by="${4:-}"
    local claimed_at="${5:-}"
    local claim_reason="${6:-}"
    python3 - "$task_dir" "$assigned_agent" "$reason" "$claimed_by" "$claimed_at" "$claim_reason" <<'PY'
import json
import sys
from datetime import datetime
from pathlib import Path

task_dir = Path(sys.argv[1])
assigned_agent = sys.argv[2]
reason = sys.argv[3]
claimed_by = sys.argv[4].strip()
claimed_at = sys.argv[5].strip()
claim_reason = sys.argv[6].strip()
task_path = task_dir / 'task.json'
transitions_path = task_dir / 'transitions.jsonl'
task = json.loads(task_path.read_text(encoding='utf-8'))
old_status = str(task.get('status') or '')
now = datetime.now().astimezone().isoformat(timespec='seconds')

task['assigned_agent'] = assigned_agent
task['status'] = 'dispatched'
task['updated_at'] = now
task['lease_owner'] = task.get('owner_pm')
task['lease_acquired_at'] = now
task['lease_expires_at'] = now
if claimed_by:
    task['claimed_by'] = claimed_by
if claimed_at:
    task['claimed_at'] = claimed_at
if claim_reason:
    task['claim_reason'] = claim_reason
task['pool_entered_at'] = task.get('pool_entered_at')

task_path.write_text(json.dumps(task, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
with transitions_path.open('a', encoding='utf-8') as fp:
    fp.write(json.dumps({
        'from': old_status,
        'to': 'dispatched',
        'at': now,
        'reason': reason,
    }, ensure_ascii=False) + '\n')
PY
}

auto_dispatch_pending_arch() {
    local task_dir="$1"
    local task_id="$2"
    local assigned_agent="$3"
    local task_level="$4"

    [ "$ARCH_AUTO_DISPATCH" = "1" ] || return 1
    [ "$assigned_agent" = "arch-1" ] || return 1
    case "$task_level" in
        domain|epic) ;;
        *) return 1 ;;
    esac

    if ! dependencies_ready "$task_dir" >/dev/null 2>&1; then
        return 1
    fi

    dispatch_task_to_agent "$task_dir" "arch-1" "watcher auto dispatch domain/epic task to arch-1"
    notify_agent "arch-1" "请读取 /Users/lin/Desktop/work/my-agent-teams/tasks/${task_id}/instruction.md 并开始执行任务。该任务由 task-watcher 自动派发，用于支持多 domain/epic 并行处理。完成后写 ack.json 和 result.json。"
    sync_task_board "$task_dir" "auto-dispatch-arch"
    log "$task_id: 自动派发给 arch-1（domain/epic 并行）"
    return 0
}

auto_claim_pending_dev() {
    local task_dir="$1"
    local task_id="$2"
    local assigned_agent="$3"
    local task_level="$4"

    [ "$DEV_AUTO_CLAIM" = "1" ] || return 1
    [ "$task_level" = "execution" ] || return 1

    if ! dependencies_ready "$task_dir" >/dev/null 2>&1; then
        return 1
    fi

    local target_agent=""
    if matches_auto_assign_marker "$assigned_agent"; then
        target_agent=$(select_idle_dev_agent 2>/dev/null || true)
    elif [[ "$assigned_agent" == dev-* ]] && is_idle_agent "$assigned_agent"; then
        target_agent="$assigned_agent"
    fi

    [ -n "$target_agent" ] || return 1

    dispatch_task_to_agent "$task_dir" "$target_agent" "watcher auto-claimed pending execution task"
    notify_agent "$target_agent" "请读取 /Users/lin/Desktop/work/my-agent-teams/tasks/${task_id}/instruction.md 并开始执行任务。该任务由 task-watcher 在你空闲时自动认领/派发。完成后写 ack.json 和 result.json。"
    sync_task_board "$task_dir" "auto-claim-dev"
    log "$task_id: 自动认领并派发给 $target_agent"
    return 0
}

claim_reject() {
    local task_dir="$1"
    local agent_id="$2"
    local reason="$3"
    local claim_path="$task_dir/claim.json"
    [ -f "$claim_path" ] || return 0
    local stamp
    stamp=$(date '+%Y%m%dT%H%M%S')
    mv "$claim_path" "$task_dir/claim.rejected.${stamp}.json" 2>/dev/null || rm -f "$claim_path"
    [ -n "$agent_id" ] && notify_agent "$agent_id" "任务认领失败：$(basename "$task_dir")。原因：$reason"
    emit_system_chat_event watcher "$(basename "$task_dir")" "任务认领失败：$reason" "${agent_id:-all}" degraded notify
    log "$(basename "$task_dir"): claim rejected for ${agent_id:-unknown} | $reason"
}

process_claim_json() {
    local task_dir="$1"
    local task_id="$2"
    local claim_path="$task_dir/claim.json"
    [ -f "$claim_path" ] || return 1

    local claim_agent claim_time claim_reason current_status lock_file
    claim_agent=$(json_pick "$claim_path" agent agent_id)
    claim_time=$(json_pick "$claim_path" claimed_at timestamp)
    claim_reason=$(json_pick "$claim_path" reason)
    current_status=$(get_task_status "$task_dir")
    [ "$current_status" = "pooled" ] || return 1
    [ -n "$claim_agent" ] || { claim_reject "$task_dir" "" "claim.json 缺少 agent"; return 0; }

    lock_file="$task_dir/.claim.lock"
    exec 9>"$lock_file"
    flock -n 9 || return 0

    current_status=$(get_task_status "$task_dir")
    if [ "$current_status" != "pooled" ]; then
        flock -u 9
        return 1
    fi
    if ! claim_agent_can_accept_task "$task_dir" "$claim_agent"; then
        claim_reject "$task_dir" "$claim_agent" "不满足认领条件（依赖/并发/能力/write_scope 冲突）"
        flock -u 9
        return 0
    fi

    dispatch_task_to_agent "$task_dir" "$claim_agent" "watcher confirmed claim.json" "$claim_agent" "$claim_time" "$claim_reason"
    emit_system_chat_event dispatch "$task_id" "任务已被 ${claim_agent} 认领并进入 dispatched。" "$claim_agent" info dispatch
    notify_pm "[task-watcher] $task_id 已被 ${claim_agent} 认领，进入 dispatched。"
    sync_task_board "$task_dir" "claim-confirmed"
    log "$task_id: 已确认 ${claim_agent} 的 claim.json，进入 dispatched"
    flock -u 9
    return 0
}

nudge_pooled_task() {
    local task_dir="$1"
    local task_id="$2"
    local status="$3"
    [ "$status" = "pooled" ] || return 1
    [ -f "$task_dir/claim.json" ] && return 1

    local nudge_key="${task_id}_pooled_nudge"
    local now last_nudge priority
    now=$(date +%s)
    last_nudge=$(cat "$STATE_DIR/$nudge_key" 2>/dev/null || echo 0)
    if [ $(( now - last_nudge )) -lt "$(python3 -c "import json;print(json.load(open('$CONFIG_PATH', encoding='utf-8')).get('task_pool',{}).get('nudge_cooldown_seconds',900))" 2>/dev/null || echo 900)" ]; then
        return 1
    fi

    local candidates=""
    candidates=$(claim_scope_idle_candidates "$task_dir" || true)
    [ -n "$candidates" ] || return 1
    priority=$(task_json_pick "$task_dir" priority)
    while IFS= read -r agent_id; do
        [ -n "$agent_id" ] || continue
        notify_agent "$agent_id" "任务池有可认领任务：${task_id}。请检查 ${task_dir}/instruction.md，确认依赖与 write_scope 后，如可执行请写 claim.json（可用 scripts/claim-task.sh）。"
        emit_system_chat_event nudge "$task_id" "任务池有可认领任务，已提醒 ${agent_id} 检查并认领。" "$agent_id" "$([ "$priority" = "critical" ] && echo critical || echo info)" nudge
    done <<< "$candidates"
    echo "$now" > "$STATE_DIR/$nudge_key"
    log "$task_id: 已提醒候选 agent 检查 pooled 任务"
    return 0
}

auto_dispatch_review() {
    local task_dir="$1"
    local task_id="$2"
    local review_level="$3"
    local summary="$4"
    local pushed=0

    while IFS= read -r reviewer; do
        [ -n "$reviewer" ] || continue
        if auto_push_next_review_for_agent "$reviewer" "$task_id"; then
            pushed=1
        fi
    done <<< "$(task_reviewers "$task_dir")"

    if [ "$pushed" -eq 0 ]; then
        emit_system_chat_event watcher "$task_id" "任务已进入 review 队列，等待 reviewer 空闲后自动续推。" "$PM_SESSION" info notify
    fi
}

auto_dispatch_qa() {
    local task_id="$1"
    local pushed=0
    while IFS= read -r qa_agent; do
        [ -n "$qa_agent" ] || continue
        if auto_push_next_qa_for_agent "$qa_agent" "$task_id"; then
            pushed=1
        fi
    done <<< "$(list_qa_agents)"
    if [ "$pushed" -eq 0 ]; then
        emit_system_chat_event watcher "$task_id" "任务已进入 QA 队列，等待 QA 空闲后自动续推。" "$PM_SESSION" info notify
    fi
}

auto_close_review_only_task() {
    local task_dir="$1"
    local task_id="$2"
    local result_summary
    result_summary=$(json_pick "$task_dir/result.json" summary)
    if [ -z "$result_summary" ]; then
        result_summary="${task_id} 审查已通过并自动收口。"
    else
        result_summary="${result_summary}（审查通过自动收口，无 QA）"
    fi
    if "$CLOSE_TASK_SCRIPT" --task-dir "$task_dir" --summary "$result_summary" --reason "task-watcher auto close after review pass without qa" >/dev/null 2>&1; then
        log "$task_id: 审查通过且无需 QA，已自动收口"
        notify_pm "[task-watcher] $task_id 审查已通过且无需 QA，已自动收口。"
        emit_system_chat_event watcher "$task_id" "审查通过且无需 QA，已自动收口。" "$PM_SESSION" info notify
        return 0
    fi
    log "$task_id: 审查通过自动收口失败"
    return 1
}

notify_final_done_if_needed() {
    local task_dir="$1"
    local task_id="$2"
    local done_key="${task_id}_done_notice"
    if is_notified "$done_key"; then
        return 0
    fi

    local done_transition_epoch
    done_transition_epoch=$(final_done_transition_epoch "$task_dir" 2>/dev/null || echo 0)
    if [ -z "$done_transition_epoch" ] || [ "$done_transition_epoch" -le 0 ] 2>/dev/null; then
        mark_notified "$done_key"
        log "$task_id: done 终态缺少 ready_for_merge->done 迁移记录，已补种最终通知 sentinel 并跳过历史通知"
        return 0
    fi
    if [ "$done_transition_epoch" -lt "$WATCHER_STARTED_AT_EPOCH" ] 2>/dev/null; then
        mark_notified "$done_key"
        log "$task_id: done 终态早于本轮 watcher 启动，已补种最终通知 sentinel 并跳过历史通知"
        return 0
    fi

    local result_summary task_type execution_mode target_environment downstream_action
    result_summary=$(task_json_pick "$task_dir" result_summary)
    [ -n "$result_summary" ] || result_summary=$(json_pick "$task_dir/result.json" summary)
    [ -n "$result_summary" ] || result_summary="${task_id} 已进入 done 终态。"
    task_type=$(task_json_pick "$task_dir" task_type)
    execution_mode=$(task_json_pick "$task_dir" execution_mode)
    target_environment=$(task_json_pick "$task_dir" target_environment)
    downstream_action=$(task_json_pick "$task_dir" downstream_action)

    if [ "$task_type" = "deployment" ] || [ "$execution_mode" = "deploy" ] || [ "$target_environment" = "prod" ]; then
        push_task_event "【部署完成】" "$task_id" "$(truncate_utf8 "$result_summary" 300)" "请关注生产验证结果与后续用户反馈"
    else
        push_task_event "【任务完成】" "$task_id" "$(truncate_utf8 "$result_summary" 300)" "${downstream_action:-生命周期已结束}"
    fi
    emit_system_chat_event watcher "$task_id" "任务已进入 done 终态，已发送最终完成通知。" "$PM_SESSION" info notify
    mark_notified "$done_key"
}

auto_close_task() {
    local task_dir="$1"
    local task_id="$2"
    local verify_msg="$3"
    local result_summary
    result_summary=$(json_pick "$task_dir/result.json" summary)
    if [ -z "$result_summary" ]; then
        result_summary="${task_id} QA 已通过并自动收口。"
    else
        result_summary="${result_summary}（QA 已通过自动收口）"
    fi
    if [ -n "$verify_msg" ]; then
        result_summary="${result_summary} QA 结论：$(truncate_utf8 "$verify_msg" 300)"
    fi
    if "$CLOSE_TASK_SCRIPT" --task-dir "$task_dir" --summary "$result_summary" --reason "task-watcher auto close after qa verify pass" >/dev/null 2>&1; then
        log "$task_id: QA 通过，已自动收口"
        notify_pm "[task-watcher] $task_id QA 已通过并自动收口，请查看任务目录与 verify.json。" 
        emit_system_chat_event watcher "$task_id" "QA 已通过并自动收口。" "$PM_SESSION" info notify
        return 0
    fi
    log "$task_id: close-task.sh 执行失败，未自动收口"
    return 1
}

restart_cause=$(cat "$RESTART_CAUSE_FILE" 2>/dev/null || true)
if [ -n "$restart_cause" ]; then
    log "检测到 watchdog 重启原因: $restart_cause"
fi

write_heartbeat "startup"
log "task-watcher 启动，间隔 ${INTERVAL}s"

while true; do
    write_heartbeat "running"
    [ -d "$TASKS_ROOT" ] || { sleep "$INTERVAL"; continue; }

    for task_dir in "$TASKS_ROOT"/*/; do
        [ -d "$task_dir" ] || continue
        task_id=$(basename "$task_dir")
        [ -f "$task_dir/task.json" ] || continue

        current_status=$(get_task_status "$task_dir")

        # 已关闭任务不再触发自动流转，但仍需在文件变更后同步到任务看板 SQLite
        case "$current_status" in
            done|cancelled|archived)
                if [ "$current_status" = "done" ]; then
                    notify_final_done_if_needed "$task_dir" "$task_id" || true
                    assigned_agent=$(task_json_pick "$task_dir" assigned_agent)
                    auto_push_next_task_for_agent "$assigned_agent" "$task_id" || true
                fi
                sync_if_changed "$task_dir" "$task_dir/task.json" "taskjson"
                sync_if_changed "$task_dir" "$task_dir/transitions.jsonl" "transitions"
                sync_if_changed "$task_dir" "$task_dir/result.json" "result"
                sync_if_changed "$task_dir" "$task_dir/review.md" "review"
                sync_if_changed "$task_dir" "$task_dir/design-review.md" "designreview"
                sync_if_changed "$task_dir" "$task_dir/verify.json" "verify"
                continue
                ;;
        esac

        if [ "$current_status" = "pending" ]; then
            task_level=$(task_json_pick "$task_dir" task_level)
            assigned_agent=$(task_json_pick "$task_dir" assigned_agent)
            claim_policy=$(task_json_pick "$task_dir" claim_policy)
            if [ "$claim_policy" = "pull" ] || matches_auto_assign_marker "$assigned_agent"; then
                :
            else
                auto_dispatch_pending_arch "$task_dir" "$task_id" "$assigned_agent" "$task_level" || true
            fi
            current_status=$(get_task_status "$task_dir")
        fi

        if [ "$current_status" = "pooled" ]; then
            process_claim_json "$task_dir" "$task_id" || true
            current_status=$(get_task_status "$task_dir")
            if [ "$current_status" = "pooled" ]; then
                nudge_pooled_task "$task_dir" "$task_id" "$current_status" || true
            fi
        fi

        if [ "$current_status" = "ready_for_merge" ] || [ "$current_status" = "blocked" ]; then
            inferred_gate_state=$(resolve_merge_gate_state "$task_dir" 2>/dev/null || true)
            current_gate_state=$(task_json_pick "$task_dir" merge_gate_state)
            if [ -n "$inferred_gate_state" ] && [ "$inferred_gate_state" != "$current_gate_state" ]; then
                now_iso=$(now_iso)
                set_task_fields "$task_dir" "{\"merge_gate_state\": \"${inferred_gate_state}\", \"last_gate_decision_at\": \"${now_iso}\"}" "watcher normalized merge gate state"
            fi
        fi

        # 兜底：dispatched 状态超 3 分钟无 ack 且无明确进展工件/Working 信号 → 重新发送指令
        if [ "$current_status" = "dispatched" ] && [ ! -f "$task_dir/ack.json" ]; then
            dispatch_time=$(task_dispatch_reference_epoch "$task_dir")
            now=$(date +%s)
            if [ -n "$dispatch_time" ] && [ "$dispatch_time" -gt 0 ] && [ $(( now - dispatch_time )) -gt "$DISPATCH_RESEND_AFTER_SECONDS" ]; then
                resend_key="${task_id}_resend"
                agent_session=$(task_json_pick "$task_dir" assigned_agent)
                if task_has_progress_artifact "$task_dir"; then
                    log "$task_id: dispatched 超时检查跳过，已发现后续工件，优先按显式工件继续流转"
                else
                    is_working=$(agent_has_working_signal "$agent_session")
                    [ "$is_working" -gt 0 ] && continue
                    last_resend=$(cat "$STATE_DIR/$resend_key" 2>/dev/null)
                    if [ -z "$last_resend" ] || [ $(( now - last_resend )) -gt "$RESEND_COOLDOWN_SECONDS" ]; then
                        if [ -n "$agent_session" ]; then
                            instruction="$task_dir/instruction.md"
                            if [ -f "$instruction" ]; then
                                notify_agent "$agent_session" "请重新读取 ${task_dir}/instruction.md 并继续执行，完成后写 ack.json / result.json。"
                                emit_system_chat_event nudge "$task_id" "任务超时未确认，已触发重新唤醒。" "$agent_session" degraded nudge
                                log "$task_id: dispatched 超过 ${DISPATCH_RESEND_AFTER_SECONDS}s 且无 ack/无 Working，兜底重发指令给 $agent_session"
                                push_task_event "【任务重发】" "$task_id" "超过 ${DISPATCH_RESEND_AFTER_SECONDS}s 未确认，已重新发送给 ${agent_session}" "等待 agent 写入 ack.json"
                            fi
                            echo "$now" > "$STATE_DIR/$resend_key"
                        fi
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
                current_status="working"
            fi
        fi

        # 检测 result.json → 自动流转到 PM / reviewer
        if [ -f "$task_dir/result.json" ]; then
            result_key="${task_id}_result_route"
            if ! is_notified "$result_key" || is_file_newer_than_notified "$result_key" "$task_dir/result.json"; then
                agent=$(json_pick "$task_dir/result.json" agent agent_id)
                result_status=$(json_pick "$task_dir/result.json" status)
                summary=$(json_pick "$task_dir/result.json" summary)
                task_level=$(task_json_pick "$task_dir" task_level)
                assigned_agent=$(task_json_pick "$task_dir" assigned_agent)
                review_level=$(task_json_pick "$task_dir" review_level)
                review_required=$(task_json_pick "$task_dir" review_required)
                test_required=$(task_json_pick "$task_dir" test_required)
                task_type=$(task_json_pick "$task_dir" task_type)
                execution_mode=$(task_json_pick "$task_dir" execution_mode)
                target_environment=$(task_json_pick "$task_dir" target_environment)
                downstream_action=$(task_json_pick "$task_dir" downstream_action)

                if [ "$result_status" = "done" ]; then
                    gate_decision_at=$(now_iso)
                    gate_state="pm_acceptance_pending"
                    if [ "$review_required" = "True" ] || [ "$review_required" = "true" ] || [ "$review_required" = "1" ]; then
                        gate_state="review_pending"
                    elif [ "$test_required" = "True" ] || [ "$test_required" = "true" ] || [ "$test_required" = "1" ]; then
                        gate_state="qa_pending"
                    fi
                    update_task_record "$task_dir" "ready_for_merge" "watcher observed result.json status=done" "{\"merge_gate_state\":\"${gate_state}\",\"rework_reason\":null,\"last_gate_actor\":\"watcher\",\"last_gate_decision_at\":\"${gate_decision_at}\"}"
                    current_status="ready_for_merge"
                    if [ "$assigned_agent" = "arch-1" ] && { [ "$task_level" = "domain" ] || [ "$task_level" = "epic" ]; }; then
                        notify_pm "[task-watcher] $task_id 技术方案已完成，请查看 result.json 并整理飞书确认。"
                        emit_system_chat_event watcher "$task_id" "技术方案已完成，等待 PM 汇总确认。" "$PM_SESSION" info notify
                    elif [ "$gate_state" = "review_pending" ]; then
                        auto_dispatch_review "$task_dir" "$task_id" "$review_level" "$summary"
                        log "$task_id: 已进入 review 队列，review_level=$review_level"
                        auto_push_next_task_for_agent "$assigned_agent" "$task_id" || true
                    elif [ "$gate_state" = "qa_pending" ]; then
                        auto_dispatch_qa "$task_id"
                        log "$task_id: 已进入 QA 队列"
                        auto_push_next_task_for_agent "$assigned_agent" "$task_id" || true
                    else
                        notify_pm "[task-watcher] $task_id 已提交实现结果，请查看任务目录并决定是否最终收口。"
                        emit_system_chat_event watcher "$task_id" "任务实现结果已提交，当前进入 PM 最终验收队列。" "$PM_SESSION" info notify
                    fi
                elif [ "$result_status" = "blocked" ]; then
                    gate_decision_at=$(now_iso)
                    update_task_record "$task_dir" "blocked" "watcher observed result.json status=blocked" "{\"merge_gate_state\":\"blocked\",\"rework_reason\":\"execution\",\"last_gate_actor\":\"${assigned_agent:-executor}\",\"last_gate_decision_at\":\"${gate_decision_at}\"}"
                    current_status="blocked"
                    notify_pm "[task-watcher] $task_id 已被标记为 blocked，请查看 result.json 处理阻塞。"
                    emit_system_chat_event watcher "$task_id" "任务进入 blocked，需 PM 处理。" "$PM_SESSION" degraded notify
                    push_task_event "【任务阻塞】" "$task_id" "$(truncate_utf8 "$summary" 300)" "请 PM 介入处理阻塞原因"
                else
                    notify_pm "[task-watcher] $task_id 产生了 result.json（status=$result_status），请查看任务目录。"
                    emit_system_chat_event watcher "$task_id" "任务产出 result.json，需 PM 查看。" "$PM_SESSION" info notify
                fi

                sync_task_board "$task_dir" "result-detected"
                mark_notified "$result_key"
            fi
        fi

        if [ "$current_status" = "working" ] && [ ! -f "$task_dir/result.json" ]; then
            working_since=$(task_working_reference_epoch "$task_dir")
            now=$(date +%s)
            if [ -n "$working_since" ] && [ "$working_since" -gt 0 ] && [ $(( now - working_since )) -gt "$WORKING_TIMEOUT_SECONDS" ]; then
                working_timeout_key="${task_id}_working_timeout_notice"
                if ! is_notified "$working_timeout_key" || is_file_newer_than_notified "$working_timeout_key" "$task_dir/task.json"; then
                    agent_session=$(task_json_pick "$task_dir" assigned_agent)
                    notify_pm "[task-watcher] $task_id 持续 working 超时，请 PM 介入检查。"
                    emit_system_chat_event watcher "$task_id" "任务 working 超时，需 PM 介入。" "$PM_SESSION" degraded notify
                    push_task_event "【任务超时】" "$task_id" "持续 working 超过 $((WORKING_TIMEOUT_SECONDS / 60)) 分钟" "请 PM 介入检查"
                    log "$task_id: working 超时已通知 PM 介入，未触发重发"
                    mark_notified "$working_timeout_key"
                fi
            fi
        fi

        # 检测 review 结果 → 自动通知 QA 或通知 PM 仲裁
        if [ -f "$task_dir/review.md" ] || [ -f "$task_dir/design-review.md" ]; then
            review_level=$(task_json_pick "$task_dir" review_level)
            review_sig=$(review_signature "$task_dir")
            review_key="${task_id}_review_route"
            if ! is_notified "$review_key" || is_signature_newer_than_notified "$review_key" "$review_sig"; then
                state=$(review_state "$task_dir" "$review_level")
                clear_review_queue_state_for_task "$task_dir"
                if [ "$state" = "pass" ]; then
                    test_required=$(task_json_pick "$task_dir" test_required)
                    if [ "$test_required" = "True" ] || [ "$test_required" = "true" ] || [ "$test_required" = "1" ]; then
                        gate_decision_at=$(now_iso)
                        set_task_fields "$task_dir" "{\"merge_gate_state\":\"qa_pending\",\"rework_reason\":null,\"last_gate_actor\":\"review\",\"last_gate_decision_at\":\"${gate_decision_at}\"}" "watcher observed review pass and queued qa"
                        auto_dispatch_qa "$task_id"
                        log "$task_id: review 通过，已进入 QA 队列"
                    else
                        auto_close_policy=$(task_json_pick "$task_dir" auto_close_policy)
                        gate_decision_at=$(now_iso)
                        set_task_fields "$task_dir" "{\"merge_gate_state\":\"pm_acceptance_pending\",\"rework_reason\":null,\"last_gate_actor\":\"review\",\"last_gate_decision_at\":\"${gate_decision_at}\"}" "watcher observed review pass without qa"
                        if [ "$auto_close_policy" = "review_pass_only" ]; then
                            if ! auto_close_review_only_task "$task_dir" "$task_id"; then
                                notify_pm "[task-watcher] $task_id 审查已通过且配置为自动收口，但 close-task 失败，请检查任务目录。"
                                emit_system_chat_event watcher "$task_id" "审查通过自动收口失败。" "$PM_SESSION" degraded notify
                            fi
                        else
                            notify_pm "[task-watcher] $task_id 审查已通过且无需 QA，请查看任务目录并决定是否收口。"
                            emit_system_chat_event watcher "$task_id" "审查通过且无需 QA，等待 PM 最终验收。" "$PM_SESSION" info notify
                        fi
                    fi
                elif [ "$state" = "fail" ]; then
                    gate_decision_at=$(now_iso)
                    update_task_record "$task_dir" "blocked" "watcher observed review fail" "{\"merge_gate_state\":\"review_rejected\",\"rework_reason\":\"review\",\"last_gate_actor\":\"review\",\"last_gate_decision_at\":\"${gate_decision_at}\"}"
                    current_status="blocked"
                    notify_pm "[task-watcher] $task_id 审查未通过，请查看 review.md 并仲裁。"
                    emit_system_chat_event watcher "$task_id" "审查未通过，需 PM 仲裁。" "$PM_SESSION" degraded notify
                    push_task_event "【审查未通过】" "$task_id" "$(truncate_utf8 "$(first_review_conclusion "$task_dir")" 300)" "请 PM 仲裁并决定是否补修"
                fi
                sync_task_board "$task_dir" "review-detected"
                mark_signature_notified "$review_key" "$review_sig"
            fi
        fi

        # 检测 verify.json → QA 通过自动收口；QA 失败通知 PM 仲裁
        if [ -f "$task_dir/verify.json" ]; then
            verify_key="${task_id}_verify_route"
            if ! is_notified "$verify_key" || is_file_newer_than_notified "$verify_key" "$task_dir/verify.json"; then
                vstate=$(verify_state "$task_dir/verify.json")
                vsummary=$(verify_summary "$task_dir/verify.json")
                clear_qa_queue_state
                if [ "$vstate" = "pass" ]; then
                    current_status=$(get_task_status "$task_dir")
                    if [ "$current_status" = "ready_for_merge" ]; then
                        if ! auto_close_task "$task_dir" "$task_id" "$vsummary"; then
                            notify_pm "[task-watcher] $task_id QA 已通过，但自动收口失败，请检查 close-task.sh 与任务状态。"
                            emit_system_chat_event watcher "$task_id" "QA 已通过但自动收口失败。" "$PM_SESSION" degraded notify
                            continue
                        fi
                    else
                        notify_pm "[task-watcher] $task_id QA 已通过但未自动收口，请检查任务状态。"
                        emit_system_chat_event watcher "$task_id" "QA 已通过但未自动收口。" "$PM_SESSION" degraded notify
                        continue
                    fi
                elif [ "$vstate" = "fail" ]; then
                    gate_decision_at=$(now_iso)
                    update_task_record "$task_dir" "blocked" "watcher observed qa verify fail" "{\"merge_gate_state\":\"qa_failed\",\"rework_reason\":\"qa\",\"last_gate_actor\":\"qa-1\",\"last_gate_decision_at\":\"${gate_decision_at}\"}"
                    current_status="blocked"
                    notify_pm "[task-watcher] $task_id QA 未通过，请查看 verify.json 并仲裁。"
                    emit_system_chat_event watcher "$task_id" "QA 未通过，需 PM 仲裁。" "$PM_SESSION" degraded notify
                    push_task_event "【QA未通过】" "$task_id" "$(truncate_utf8 "$vsummary" 300)" "请 PM 仲裁并决定修复、回退或重新验证"
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
        sync_if_changed "$task_dir" "$task_dir/design-review.md" "designreview"
        sync_if_changed "$task_dir" "$task_dir/verify.json" "verify"
    done

    while IFS= read -r reviewer_agent; do
        [ -n "$reviewer_agent" ] || continue
        auto_push_next_review_for_agent "$reviewer_agent" "idle sweep" || true
    done <<< "$(list_review_agents)"

    while IFS= read -r qa_agent; do
        [ -n "$qa_agent" ] || continue
        auto_push_next_qa_for_agent "$qa_agent" "idle sweep" || true
    done <<< "$(list_qa_agents)"

    sleep "$INTERVAL"
done
