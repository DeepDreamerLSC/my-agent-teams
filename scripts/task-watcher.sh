#!/bin/bash
# task-watcher.sh - 监控 tasks/ 目录下的任务状态变更，执行事件驱动自动流转，并同步任务看板 SQLite 数据。
# 关键职责：
# - ack.json 新增 → 更新 task.json 状态为 working
# - result.json 新增 → 根据任务类型自动通知 PM / reviewer
# - review / QA 通过 → 推进 merge gate，并在全部必需 gate 满足后通知 PM 收口
# - review 驳回 / QA 失败 → 通知 PM 仲裁

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_ROOT="${WORKSPACE_ROOT:-$(cd "$SCRIPT_DIR/.." && pwd)}"
LEGACY_OPENCLAW_ROOT="${LEGACY_OPENCLAW_ROOT:-$HOME/.openclaw/workspace}"
LEGACY_STATE_DIR="${LEGACY_STATE_DIR:-$LEGACY_OPENCLAW_ROOT/.task-watcher}"
LEGACY_LOG_DIR="${LEGACY_LOG_DIR:-$LEGACY_OPENCLAW_ROOT/logs}"

TASKS_ROOT="${TASKS_ROOT:-$WORKSPACE_ROOT/tasks}"
CONFIG_PATH="${CONFIG_PATH:-$WORKSPACE_ROOT/config.json}"
AGENT_CONFIG_PY="${AGENT_CONFIG_PY:-$SCRIPT_DIR/lib/agent_config.py}"

agent_config_value() {
    local command="$1"
    shift || true
    [ -r "$AGENT_CONFIG_PY" ] || return 1
    python3 "$AGENT_CONFIG_PY" "$command" --config "$CONFIG_PATH" "$@" 2>/dev/null
}

PM_AGENT_ID="${PM_AGENT_ID:-${PM_SESSION:-}}"
if [ -z "$PM_AGENT_ID" ]; then
    PM_AGENT_ID="$(agent_config_value root-pm || true)"
fi
PM_AGENT_ID="${PM_AGENT_ID:-}"
INTEGRATION_OWNER_AGENT_ID="${INTEGRATION_OWNER_AGENT_ID:-}"
if [ -z "$INTEGRATION_OWNER_AGENT_ID" ]; then
    INTEGRATION_OWNER_AGENT_ID="$(agent_config_value integration-owner || true)"
fi
INTEGRATION_OWNER_AGENT_ID="${INTEGRATION_OWNER_AGENT_ID:-}"
PUSH_SCRIPT="${PUSH_SCRIPT:-}"
USER_ID="${USER_ID:-}"
LEGACY_PROJECT_OMX_STATE_DIR="${LEGACY_PROJECT_OMX_STATE_DIR:-$WORKSPACE_ROOT/.omx/state/task-watcher}"
LEGACY_PROJECT_OMX_LOG_DIR="${LEGACY_PROJECT_OMX_LOG_DIR:-$WORKSPACE_ROOT/.omx/logs}"
STATE_DIR="${STATE_DIR:-$WORKSPACE_ROOT/.runtime/state/task-watcher}"
BOARD_SYNC_SCRIPT="${BOARD_SYNC_SCRIPT:-$WORKSPACE_ROOT/scripts/task-board-sync.py}"
SEND_SCRIPT="${SEND_SCRIPT:-$WORKSPACE_ROOT/scripts/send-to-agent.sh}"
SEND_CHAT_SCRIPT="${SEND_CHAT_SCRIPT:-$WORKSPACE_ROOT/scripts/send-chat.sh}"
DISPATCH_TASK_SCRIPT="${DISPATCH_TASK_SCRIPT:-$WORKSPACE_ROOT/scripts/dispatch-task.sh}"
CLOSE_TASK_SCRIPT="${CLOSE_TASK_SCRIPT:-$WORKSPACE_ROOT/scripts/close-task.sh}"
ARTIFACTS_PY="${ARTIFACTS_PY:-$WORKSPACE_ROOT/scripts/lib/task_artifacts.py}"
STATE_INVARIANTS_PY="${STATE_INVARIANTS_PY:-$WORKSPACE_ROOT/scripts/lib/task_state_invariants.py}"
TASK_POOL_ROUTER="${TASK_POOL_ROUTER:-$WORKSPACE_ROOT/scripts/task-pool-router.py}"
TASK_QUEUE_ROUTER="${TASK_QUEUE_ROUTER:-$WORKSPACE_ROOT/scripts/task-queue-router.py}"
REASSIGN_TASK_SCRIPT="${REASSIGN_TASK_SCRIPT:-$WORKSPACE_ROOT/scripts/reassign-task.sh}"
ENSURE_TASK_WORKSPACE_PY="${ENSURE_TASK_WORKSPACE_PY:-$WORKSPACE_ROOT/scripts/ensure-task-workspace.py}"
AUTO_ASSIGN_MARKERS="${AUTO_ASSIGN_MARKERS:-auto,auto-dev,unassigned}"
ARCH_AUTO_DISPATCH="${ARCH_AUTO_DISPATCH:-1}"
DEV_AUTO_CLAIM="${DEV_AUTO_CLAIM:-1}"
INTERVAL="${INTERVAL:-5}"
HEARTBEAT_EVERY_TASKS="${HEARTBEAT_EVERY_TASKS:-10}"
TERMINAL_SWEEP_EVERY_LOOPS="${TERMINAL_SWEEP_EVERY_LOOPS:-12}"
PID_FILE="${PID_FILE:-$STATE_DIR/task-watcher.pid}"
HEARTBEAT_FILE="${HEARTBEAT_FILE:-$STATE_DIR/task-watcher-heartbeat.json}"
RESTART_CAUSE_FILE="${RESTART_CAUSE_FILE:-$STATE_DIR/task-watcher-restart-cause.txt}"
MIGRATION_SENTINEL_FILE="${MIGRATION_SENTINEL_FILE:-$STATE_DIR/migration-complete.json}"
LOG_DIR="${LOG_DIR:-$WORKSPACE_ROOT/.runtime/logs}"
LOG_FILE="${LOG_FILE:-$LOG_DIR/task-watcher.log}"
WATCHER_STDOUT_LOG="${WATCHER_STDOUT_LOG:-$LOG_FILE}"
LOG_RETENTION_DAYS="${LOG_RETENTION_DAYS:-7}"
DISPATCH_RESEND_AFTER_SECONDS="${DISPATCH_RESEND_AFTER_SECONDS:-300}"
RESEND_COOLDOWN_SECONDS="${RESEND_COOLDOWN_SECONDS:-300}"
DISPATCH_FAILURE_THRESHOLD="${DISPATCH_FAILURE_THRESHOLD:-3}"
WORKING_TIMEOUT_SECONDS="${WORKING_TIMEOUT_SECONDS:-1800}"
WORKING_REASSIGN_GRACE_SECONDS="${WORKING_REASSIGN_GRACE_SECONDS:-900}"
ACK_NO_PROGRESS_REMINDER_SECONDS="${ACK_NO_PROGRESS_REMINDER_SECONDS:-900}"
ACK_NO_PROGRESS_REPOOL_SECONDS="${ACK_NO_PROGRESS_REPOOL_SECONDS:-1800}"
ACK_NO_PROGRESS_REPOOL_COOLDOWN_SECONDS="${ACK_NO_PROGRESS_REPOOL_COOLDOWN_SECONDS:-1800}"
TASK_WATCHER_TEST_MODE="${TASK_WATCHER_TEST_MODE:-0}"
NOTIFY_RETRY_COOLDOWN_SECONDS="${NOTIFY_RETRY_COOLDOWN_SECONDS:-$RESEND_COOLDOWN_SECONDS}"

LAST_LOG_ROTATE_DAY=""
WATCHER_STARTED_AT_EPOCH="$(date +%s)"

mkdir -p "$STATE_DIR" "$LOG_DIR"

TASK_WATCHER_RUNTIME_SH="${TASK_WATCHER_RUNTIME_SH:-$SCRIPT_DIR/lib/task_watcher_runtime.sh}"
if [ -r "$TASK_WATCHER_RUNTIME_SH" ]; then
    # shellcheck source=lib/task_watcher_runtime.sh
    source "$TASK_WATCHER_RUNTIME_SH"
else
    printf 'task-watcher runtime module missing: %s
' "$TASK_WATCHER_RUNTIME_SH" >&2
    exit 1
fi

ensure_stdout_log_compat
redirect_stdout_log_if_needed

resolve_notifications_config() {
    python3 - "$CONFIG_PATH" <<'PY'
import json
import sys
from pathlib import Path

config_path = Path(sys.argv[1])
local_path = config_path.parent / 'config.local.json'

# 优先从 config.local.json 读取，其次从 config.json 读取
payload = {}
for p in [local_path, config_path]:
    if p.exists():
        try:
            payload = json.loads(p.read_text(encoding='utf-8'))
            break
        except Exception:
            continue

if not payload:
    raise SystemExit(0)

notifications = payload.get('notifications') or {}
push_script = str(notifications.get('push_script') or '').strip()
open_id = str(notifications.get('feishu_receive_id') or notifications.get('feishu_open_id') or '').strip()
print(f"{push_script}\n{open_id}")
PY
}

if [ -z "$PUSH_SCRIPT" ] || [ -z "$USER_ID" ]; then
    notifications_config="$(resolve_notifications_config 2>/dev/null || true)"
    if [ -n "$notifications_config" ]; then
        if [ -z "$PUSH_SCRIPT" ]; then
            PUSH_SCRIPT="$(printf '%s\n' "$notifications_config" | sed -n '1p')"
        fi
        if [ -z "$USER_ID" ]; then
            USER_ID="$(printf '%s\n' "$notifications_config" | sed -n '2p')"
        fi
    fi
fi
PUSH_SCRIPT="${PUSH_SCRIPT:-$WORKSPACE_ROOT/scripts/feishu-push.sh}"
USER_ID="${USER_ID:-}"

migrate_legacy_task_watcher_runtime


if [ "$TASK_WATCHER_TEST_MODE" != "1" ]; then
    trap cleanup_task_watcher_runtime EXIT
    trap stop_task_watcher INT TERM

    ensure_single_instance
    write_pid_file
fi

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

resolve_agent_session() {
    local target="$1"
    if [ -n "$target" ] && [ -r "$AGENT_CONFIG_PY" ]; then
        python3 "$AGENT_CONFIG_PY" resolve-session "$target" --config "$CONFIG_PATH" 2>/dev/null || printf '%s\n' "$target"
    else
        printf '%s\n' "$target"
    fi
}

resolve_agent_runtime() {
    local target="$1"
    if [ -n "$target" ] && [ -r "$AGENT_CONFIG_PY" ]; then
        python3 "$AGENT_CONFIG_PY" resolve-runtime "$target" --config "$CONFIG_PATH" 2>/dev/null || printf 'unknown\n'
    else
        printf 'unknown\n'
    fi
}

default_tester_agent() {
    local task_dir="${1:-}"
    local domain=""
    if [ -n "$task_dir" ]; then
        domain=$(task_json_pick "$task_dir" domain 2>/dev/null || true)
    fi
    agent_config_value default-tester --domain "$domain" || true
}

is_integration_owner_planning_task() {
    local assigned_agent="$1"
    local task_level="$2"
    local integration_owner="${INTEGRATION_OWNER_AGENT_ID:-}"
    [ -n "$integration_owner" ] || integration_owner="$(agent_config_value integration-owner || true)"
    [ -n "$integration_owner" ] || return 1
    [ "$assigned_agent" = "$integration_owner" ] || return 1
    case "$task_level" in
        domain|epic) return 0 ;;
        *) return 1 ;;
    esac
}

legacy_send_tmux() {
    local target="$1"
    local msg="$2"
    local session runtime
    session="$(resolve_agent_session "$target")"
    runtime="$(resolve_agent_runtime "$target")"

    if [ "$runtime" = "codex" ]; then
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

TASK_WATCHER_NOTIFICATIONS_SH="${TASK_WATCHER_NOTIFICATIONS_SH:-$SCRIPT_DIR/lib/task_watcher_notifications.sh}"
if [ -r "$TASK_WATCHER_NOTIFICATIONS_SH" ]; then
    # shellcheck source=lib/task_watcher_notifications.sh
    source "$TASK_WATCHER_NOTIFICATIONS_SH"
else
    log "task-watcher 通知模块缺失: $TASK_WATCHER_NOTIFICATIONS_SH"
    exit 1
fi

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
    [ -f "$task_dir/result.json" ] || [ -f "$task_dir/review.json" ] || [ -f "$task_dir/design-review.json" ] || [ -f "$task_dir/review.md" ] || [ -f "$task_dir/design-review.md" ] || [ -f "$task_dir/verify.json" ]
}

task_has_current_round_progress_artifact() {
    local task_dir="$1"
    local artifact
    local status
    local current_round

    artifact="result"
    status=$(artifact_pick "$artifact" "$task_dir" normalized_status 2>/dev/null || true)
    current_round=$(artifact_pick "$artifact" "$task_dir" is_current_round 2>/dev/null || true)
    if [ "$status" != "missing" ] && [ "$status" != "invalid" ] && [ "$current_round" != "false" ]; then
        return 0
    fi

    artifact="review"
    status=$(artifact_pick "$artifact" "$task_dir" normalized_status 2>/dev/null || true)
    current_round=$(artifact_pick "$artifact" "$task_dir" is_current_round 2>/dev/null || true)
    if [ "$status" != "missing" ] && [ "$status" != "invalid" ] && [ "$current_round" != "false" ]; then
        return 0
    fi

    artifact="verify"
    status=$(artifact_pick "$artifact" "$task_dir" normalized_status 2>/dev/null || true)
    current_round=$(artifact_pick "$artifact" "$task_dir" is_current_round 2>/dev/null || true)
    if [ "$status" != "missing" ] && [ "$status" != "invalid" ] && [ "$current_round" != "false" ]; then
        return 0
    fi

    return 1
}

task_workspace_has_changes() {
    local task_dir="$1"
    python3 - "$task_dir/task.json" <<'PY'
import json
import subprocess
import sys
from pathlib import Path

task = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
workspace = str(task.get('workspace_path') or task.get('worktree_path') or '').strip()
if not workspace:
    raise SystemExit(1)
workspace_path = Path(workspace)
if not workspace_path.exists():
    raise SystemExit(1)

completed = subprocess.run(
    ['git', '-C', str(workspace_path), 'status', '--porcelain', '--untracked-files=all'],
    capture_output=True,
    text=True,
    check=False,
)
if completed.returncode != 0:
    raise SystemExit(1)
if completed.stdout.strip():
    print('1')
    raise SystemExit(0)
raise SystemExit(1)
PY
}

task_has_effective_progress() {
    local task_dir="$1"
    local reference_epoch="${2:-0}"
    local artifact artifact_epoch
    for artifact in result.json review.json design-review.json review.md design-review.md verify.json; do
        if [ -f "$task_dir/$artifact" ]; then
            artifact_epoch=$(stat -f %m "$task_dir/$artifact" 2>/dev/null || echo 0)
            if [ "${artifact_epoch:-0}" -gt "${reference_epoch:-0}" ]; then
                return 0
            fi
        fi
    done
    task_workspace_has_changes "$task_dir" && return 0
    return 1
}

task_clear_working_timeout_state() {
    local task_id="$1"
    rm -f \
        "$STATE_DIR/${task_id}_working_timeout_notice" \
        "$STATE_DIR/${task_id}_working_timeout_push" \
        "$(notification_retry_flag "${task_id}_working_timeout_push")" \
        "$STATE_DIR/${task_id}_working_timeout_grace_started" \
        "$STATE_DIR/${task_id}_working_no_progress_reminder"
}

task_no_progress_repool_cooldown_active() {
    local task_dir="$1"
    local agent_id="$2"
    python3 - "$task_dir/task.json" "$agent_id" "$ACK_NO_PROGRESS_REPOOL_COOLDOWN_SECONDS" <<'PY'
import json
import sys
from datetime import datetime
from pathlib import Path

task = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
agent_id = sys.argv[2].strip()
cooldown_seconds = int(sys.argv[3] or 0)
if cooldown_seconds <= 0:
    raise SystemExit(1)
if str(task.get('status') or '') != 'pooled':
    raise SystemExit(1)
if str(task.get('last_no_progress_repool_agent') or '').strip() != agent_id:
    raise SystemExit(1)
until_raw = str(task.get('no_progress_repool_until') or '').strip()
if not until_raw:
    raise SystemExit(1)
try:
    until = datetime.fromisoformat(until_raw.replace('Z', '+00:00'))
except Exception:
    raise SystemExit(1)
now = datetime.now().astimezone()
if until.tzinfo is None:
    until = until.astimezone()
if now < until:
    print(until_raw)
    raise SystemExit(0)
raise SystemExit(1)
PY
}

notify_working_no_progress_if_needed() {
    local task_dir="$1"
    local task_id="$2"
    local assigned_agent="$3"
    local working_since="$4"
    local reminder_key="${task_id}_working_no_progress_reminder"
    local now elapsed

    [ -n "$assigned_agent" ] || return 1
    [ -n "$working_since" ] && [ "$working_since" -gt 0 ] || return 1
    now=$(date +%s)
    elapsed=$(( now - working_since ))
    [ "$elapsed" -ge "${ACK_NO_PROGRESS_REMINDER_SECONDS:-900}" ] || return 1
    if is_notified "$reminder_key" && ! is_file_newer_than_notified "$reminder_key" "$task_dir/ack.json"; then
        return 0
    fi

    notify_agent "$assigned_agent" "任务 ${task_id} 已 ack ${elapsed} 秒但仍未检测到实际进展（result/review/verify 工件或 workspace 变更）。请尽快开始执行，否则将自动回池。"
    emit_system_chat_event nudge "$task_id" "ack 后无实际进展，已发送推进提醒。" "$assigned_agent" info nudge
    mark_notified "$reminder_key"
    return 0
}

requeue_working_task_to_pool_if_no_progress() {
    local task_dir="$1"
    local task_id="$2"
    local working_since="$3"
    local reason="${4:-ack 后无实际进展}"
    local now

    [ -n "$working_since" ] && [ "$working_since" -gt 0 ] || return 1
    now=$(date +%s)
    [ $(( now - working_since )) -ge "${ACK_NO_PROGRESS_REPOOL_SECONDS:-1800}" ] || return 1

    python3 - "$task_dir" "$task_id" "$reason" "$ACK_NO_PROGRESS_REPOOL_COOLDOWN_SECONDS" <<'PY'
import json
import os
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

task_dir = Path(sys.argv[1])
task_id = sys.argv[2]
reason = sys.argv[3].strip()
cooldown_seconds = int(sys.argv[4] or 0)
task_path = task_dir / 'task.json'
task = json.loads(task_path.read_text(encoding='utf-8'))
if str(task.get('status') or '') != 'working':
    raise SystemExit(1)

now = datetime.now().astimezone()
now_iso = now.isoformat(timespec='seconds')
previous_agent = str(task.get('assigned_agent') or '')
cooldown_until = now + timedelta(seconds=max(0, cooldown_seconds))
cooldown_until_iso = cooldown_until.astimezone().isoformat(timespec='seconds')

task['last_no_progress_repool_agent'] = previous_agent or None
task['last_no_progress_repool_at'] = now_iso
task['last_no_progress_repool_reason'] = reason
task['no_progress_repool_until'] = cooldown_until_iso
task['assigned_agent'] = task.get('pre_claim_assigned_agent') or 'auto'
task['status'] = 'pooled'
task['pool_entered_at'] = now_iso
task['updated_at'] = now_iso
task['last_delivery_state'] = 'no_progress_requeue'
task['last_delivery_error'] = reason
task['last_delivery_attempt_at'] = now_iso
task['session_health'] = None
task['control_plane_state'] = 'no_progress_requeue'
task['control_plane_updated_at'] = now_iso
task['dispatch_delivery_attempt_count'] = 0
task['dispatch_delivery_retry_count'] = 0
task['dispatch_delivery_consecutive_failures'] = 0
for key in (
    'claimed_by',
    'claimed_at',
    'claim_reason',
    'reserved_by',
    'reserved_at',
    'reserved_reason',
    'delivery_deferred_until',
    'delivery_deferred_reason',
    'delivery_deferred_at',
    'delivery_deferred_by',
    'lease_owner',
    'lease_acquired_at',
    'lease_expires_at',
):
    task.pop(key, None)
with tempfile.NamedTemporaryFile('w', delete=False, dir=str(task_dir), encoding='utf-8') as tmp:
    json.dump(task, tmp, ensure_ascii=False, indent=2)
    tmp.write('\n')
os.replace(tmp.name, task_path)
ack_path = task_dir / 'ack.json'
if ack_path.exists():
    ack_path.rename(task_dir / f"ack.requeued.{now_iso.replace(':', '').replace('+', '_')}.json")
claim_path = task_dir / 'claim.json'
if claim_path.exists():
    claim_path.rename(task_dir / f"claim.requeued.{now_iso.replace(':', '').replace('+', '_')}.json")
with (task_dir / 'transitions.jsonl').open('a', encoding='utf-8') as fp:
    fp.write(json.dumps({
        'from': 'working',
        'to': 'pooled',
        'at': now_iso,
        'reason': reason,
        'previous_agent': previous_agent or None,
        'cooldown_until': cooldown_until_iso,
    }, ensure_ascii=False) + '\n')
print(previous_agent or '')
PY
}

agent_has_working_signal() {
    local agent_session="$1"
    local tmux_session
    tmux_session="$(resolve_agent_session "$agent_session")"
    local is_working=0
    if [ -n "$tmux_session" ] && tmux has-session -t "$tmux_session" 2>/dev/null; then
        is_working=$(tmux capture-pane -t "$tmux_session" -p 2>/dev/null | grep -c 'Working\|• Working' || true)
    fi
    printf '%s\n' "${is_working:-0}"
}

should_pause_working_timeout_escalation() {
    local task_dir="$1"
    local agent_session="$2"
    local grace_key="${3:-}"
    local now="${4:-$(date +%s)}"

    if [ -n "$grace_key" ]; then
        local grace_started
        grace_started=$(notified_epoch "$grace_key")
        if [ "${grace_started:-0}" -gt 0 ] && [ $(( now - grace_started )) -lt "$WORKING_REASSIGN_GRACE_SECONDS" ]; then
            return 0
        fi
    fi

    if task_has_current_round_progress_artifact "$task_dir"; then
        return 0
    fi

    if [ -n "$agent_session" ]; then
        local session_health
        session_health=$(session_health_state "$agent_session")
        if [ "$session_health" = "working_signal" ]; then
            return 0
        fi
    fi

    return 1
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

artifact_parse_json() {
    local artifact="$1"
    local task_dir="$2"
    python3 "$ARTIFACTS_PY" "$artifact" --task-dir "$task_dir" 2>/dev/null || echo '{}'
}

artifact_pick() {
    local artifact="$1"
    local task_dir="$2"
    shift 2
    local _ap_tmpfile
    _ap_tmpfile=$(mktemp "${STATE_DIR:-/tmp}/ap_pick.XXXXXX" 2>/dev/null || mktemp)
    artifact_parse_json "$artifact" "$task_dir" > "$_ap_tmpfile" 2>/dev/null
    _AP_JSON_FILE="$_ap_tmpfile" python3 - "$@" <<'PY'
import json
import os
import sys
from pathlib import Path

keys = sys.argv[1:]
json_file = os.environ.get("_AP_JSON_FILE", "")
try:
    payload = json.loads(Path(json_file).read_text(encoding="utf-8")) if json_file else {}
except Exception:
    payload = {}

for key in keys:
    value = payload
    missing = False
    for part in key.split("."):
        if isinstance(value, dict) and part in value:
            value = value[part]
        else:
            missing = True
            break
    if missing or value in (None, ""):
        continue
    if isinstance(value, bool):
        print("true" if value else "false")
    else:
        print(value)
    raise SystemExit(0)
PY
    local _ap_rc=$?
    rm -f "$_ap_tmpfile"
    return "$_ap_rc"
}

review_artifact_is_terminal() {
    local task_dir="$1"
    local existing_review_status
    existing_review_status=$(artifact_pick review "$task_dir" normalized_status 2>/dev/null || true)
    case "$existing_review_status" in
        approve|request_changes|blocked) return 0 ;;
        *) return 1 ;;
    esac
}

task_json_pick() {
    local task_dir="$1"
    shift
    json_pick "$task_dir/task.json" "$@"
}

task_reviewers() {
    local task_dir="$1"
    local explicit_reviewers review_level domain
    python3 - "$task_dir/task.json" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
payload = json.loads(path.read_text(encoding='utf-8'))
reviewers = payload.get('reviewers') if isinstance(payload.get('reviewers'), list) else []
reviewers = [str(item).strip() for item in reviewers if str(item).strip()]
if not reviewers:
    reviewer = str(payload.get('reviewer') or '').strip()
    if reviewer:
        reviewers = [reviewer]
for reviewer in reviewers:
    print(reviewer)
PY
    explicit_reviewers=$(python3 - "$task_dir/task.json" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
payload = json.loads(path.read_text(encoding='utf-8'))
reviewers = payload.get('reviewers') if isinstance(payload.get('reviewers'), list) else []
reviewers = [str(item).strip() for item in reviewers if str(item).strip()]
if not reviewers:
    reviewer = str(payload.get('reviewer') or '').strip()
    if reviewer:
        reviewers = [reviewer]
print("1" if reviewers else "")
PY
)
    [ -n "$explicit_reviewers" ] && return 0
    review_level=$(task_json_pick "$task_dir" review_level 2>/dev/null || true)
    review_level="${review_level:-standard}"
    [ "$review_level" = "skip" ] && return 0
    domain=$(task_json_pick "$task_dir" domain 2>/dev/null || true)
    agent_config_value default-reviewers --domain "$domain" --review-level "$review_level" || true
}

task_quality_gate_mode() {
    local task_dir="$1"
    local current
    current=$(task_json_pick "$task_dir" quality_gate_mode 2>/dev/null || true)
    if [ -n "$current" ]; then
        echo "$current"
        return 0
    fi
    python3 - "$task_dir/task.json" <<'PY'
import json
import sys
from pathlib import Path

task = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
review_required = str(task.get('review_required') or '').strip().lower() in {'1', 'true', 'yes', 'y'}
test_required = str(task.get('test_required') or '').strip().lower() in {'1', 'true', 'yes', 'y'}
task_type = str(task.get('task_type') or '').strip().lower()
execution_mode = str(task.get('execution_mode') or '').strip().lower()
target_environment = str(task.get('target_environment') or '').strip().lower()
task_level = str(task.get('task_level') or '').strip().lower()
if not (review_required and test_required):
    print('single')
elif target_environment == 'prod' or execution_mode == 'deploy' or task_type in {'deployment', 'integration'} or task_level == 'integration':
    print('serial')
else:
    print('parallel')
PY
}

parse_send_attempts() {
    local output="$1"
    python3 - "$output" <<'PY'
import re
import sys

text = sys.argv[1]
patterns = (
    re.compile(r'attempt=(\d+)'),
    re.compile(r'after\s+(\d+)\s+attempts'),
)
for pattern in patterns:
    match = pattern.search(text)
    if match:
        print(int(match.group(1)))
        raise SystemExit(0)
print(1)
PY
}

session_health_state() {
    local agent_session="$1"
    local tmux_session
    if [ -z "$agent_session" ]; then
        echo "unknown"
        return 0
    fi
    tmux_session="$(resolve_agent_session "$agent_session")"
    if ! tmux has-session -t "$tmux_session" 2>/dev/null; then
        echo "missing_session"
        return 0
    fi
    local is_working
    is_working=$(agent_has_working_signal "$agent_session")
    if [ "${is_working:-0}" -gt 0 ] 2>/dev/null; then
        echo "working_signal"
        return 0
    fi
    echo "idle_session"
}


mark_dispatch_delivery_deferred_until_idle() {
    local task_dir="$1"
    local reason="${2:-agent busy; defer delivery until idle}"
    local session_health="${3:-unknown}"
    python3 - "$task_dir" "$reason" "$session_health" <<'PY'
import json
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path

task_dir = Path(sys.argv[1])
reason = sys.argv[2].strip() or 'agent busy; defer delivery until idle'
session_health = sys.argv[3].strip() or 'unknown'
task_path = task_dir / 'task.json'
task = json.loads(task_path.read_text(encoding='utf-8'))
now = datetime.now().astimezone().isoformat(timespec='seconds')

task['last_delivery_state'] = 'deferred_agent_busy'
task['last_delivery_error'] = None
task['delivery_deferred_until'] = 'agent_idle'
task['delivery_deferred_reason'] = reason
task['delivery_deferred_at'] = now
task['delivery_deferred_by'] = 'task-watcher'
task['session_health'] = session_health
task['control_plane_state'] = 'delivery_deferred'
task['control_plane_updated_at'] = now
task['updated_at'] = now

with tempfile.NamedTemporaryFile('w', delete=False, dir=str(task_dir), encoding='utf-8') as tmp:
    json.dump(task, tmp, ensure_ascii=False, indent=2)
    tmp.write('\n')
os.replace(tmp.name, task_path)
PY
}

record_dispatch_delivery_attempt() {
    local task_dir="$1"
    local delivery_state="$2"
    local attempts="${3:-1}"
    local delivery_error="${4:-}"
    local session_health="${5:-unknown}"
    python3 - "$task_dir" "$delivery_state" "$attempts" "$delivery_error" "$session_health" <<'PY'
import json
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path

task_dir = Path(sys.argv[1])
delivery_state = sys.argv[2].strip()
attempts_raw = sys.argv[3].strip()
delivery_error = sys.argv[4].strip()
session_health = sys.argv[5].strip() or 'unknown'
task_path = task_dir / 'task.json'
task = json.loads(task_path.read_text(encoding='utf-8'))
now = datetime.now().astimezone().isoformat(timespec='seconds')

try:
    attempts = max(1, int(attempts_raw or '1'))
except Exception:
    attempts = 1

attempt_count = int(task.get('dispatch_delivery_attempt_count') or 0) + attempts
retry_count = int(task.get('dispatch_delivery_retry_count') or 0) + 1
failure_count = int(task.get('dispatch_delivery_consecutive_failures') or 0)
if delivery_state in {'delivery_failed', 'session_unhealthy'}:
    failure_count += 1
    task['control_plane_state'] = delivery_state
    task['control_plane_updated_at'] = now
else:
    failure_count = 0
    if str(task.get('control_plane_state') or '') in {'delivery_failed', 'session_unhealthy'}:
        task['control_plane_state'] = None
        task['control_plane_updated_at'] = now

# Any real delivery attempt consumes/ends a previous non-interrupt deferral.
for key in (
    'delivery_deferred_until',
    'delivery_deferred_reason',
    'delivery_deferred_at',
    'delivery_deferred_by',
):
    task.pop(key, None)
if str(task.get('control_plane_state') or '') == 'delivery_deferred':
    task['control_plane_state'] = None
    task['control_plane_updated_at'] = now

task['dispatch_delivery_attempt_count'] = attempt_count
task['dispatch_delivery_retry_count'] = retry_count
task['dispatch_delivery_consecutive_failures'] = failure_count
task['last_delivery_attempt_at'] = now
task['last_delivery_state'] = delivery_state or None
task['last_delivery_error'] = delivery_error or None
task['session_health'] = session_health
task['updated_at'] = now

with tempfile.NamedTemporaryFile('w', delete=False, dir=str(task_dir), encoding='utf-8') as tmp:
    json.dump(task, tmp, ensure_ascii=False, indent=2)
    tmp.write('\n')
os.replace(tmp.name, task_path)
PY
}

clear_dispatch_recovery_state() {
    local task_dir="$1"
    python3 - "$task_dir" <<'PY'
import json
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path

task_dir = Path(sys.argv[1])
task_path = task_dir / 'task.json'
task = json.loads(task_path.read_text(encoding='utf-8'))
now = datetime.now().astimezone().isoformat(timespec='seconds')
changed = False

defaults = {
    'dispatch_delivery_consecutive_failures': 0,
    'session_health': None,
}
for key, value in defaults.items():
    if task.get(key) != value:
        task[key] = value
        changed = True

if str(task.get('control_plane_state') or '') in {'delivery_failed', 'session_unhealthy'}:
    task['control_plane_state'] = None
    task['control_plane_updated_at'] = now
    changed = True

if changed:
    task['updated_at'] = now
    with tempfile.NamedTemporaryFile('w', delete=False, dir=str(task_dir), encoding='utf-8') as tmp:
        json.dump(task, tmp, ensure_ascii=False, indent=2)
        tmp.write('\n')
    os.replace(tmp.name, task_path)
PY
}

deliver_execution_instruction_and_record() {
    local task_dir="$1"
    local task_id="$2"
    local agent_session="$3"
    local message="$4"
    local session_health output rc attempts delivery_state delivery_error tmux_session

    session_health=$(session_health_state "$agent_session")
    tmux_session="$(resolve_agent_session "$agent_session")"
    output=""
    rc=0
    if [ -x "$SEND_SCRIPT" ]; then
        output=$(CONFIG_PATH="$CONFIG_PATH" "$SEND_SCRIPT" "$agent_session" "$message" 2>&1) || rc=$?
    else
        rc=127
        output="send script unavailable: $SEND_SCRIPT"
    fi

    attempts=$(parse_send_attempts "$output")
    if [ "$rc" -eq 0 ]; then
        delivery_state="delivered"
        delivery_error=""
        log "$task_id: 投递成功 -> ${agent_session}/${tmux_session} | $(truncate_utf8 "$output" 160)"
    else
        if [ "$session_health" = "missing_session" ]; then
            delivery_state="session_unhealthy"
        else
            delivery_state="delivery_failed"
        fi
        delivery_error=$(truncate_utf8 "$output" 240)
        if [ "$session_health" != "missing_session" ] && tmux has-session -t "$tmux_session" 2>/dev/null; then
            legacy_send_tmux "$agent_session" "$message" || true
        fi
        log "$task_id: 投递失败 -> ${agent_session}/${tmux_session} | state=${delivery_state} | $(truncate_utf8 "$output" 200)"
    fi

    record_dispatch_delivery_attempt "$task_dir" "$delivery_state" "$attempts" "$delivery_error" "$session_health"
    [ "$rc" -eq 0 ]
}

prepare_task_workspace_payload() {
    local task_dir="$1"
    [ -f "$ENSURE_TASK_WORKSPACE_PY" ] || {
        echo '{}'
        return 0
    }
    python3 "$ENSURE_TASK_WORKSPACE_PY" "$task_dir" --config "$CONFIG_PATH" 2>/dev/null || echo '{}'
}

workspace_hint_from_payload() {
    local payload="${1-}"
    [ -n "$payload" ] || payload='{}'
    python3 - "$payload" <<'PY' 2>/dev/null || true
import json
import sys

try:
    payload = json.loads(sys.argv[1] or '{}')
except Exception:
    payload = {}

print((payload.get("dispatch_hint") or "").strip())
PY
}

reconcile_task_state_invariants() {
    local task_dir="$1"
    local task_id="$2"
    local report
    report=$(python3 "$STATE_INVARIANTS_PY" --task-dir "$task_dir" --config "$CONFIG_PATH" 2>/dev/null || printf '{"parse_error": true, "violations": [], "signature": ""}')
    python3 - "$task_dir" "$report" <<'PY'
import json
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path

task_dir = Path(sys.argv[1])
raw_report = sys.argv[2] or '{}'
try:
    report = json.loads(raw_report)
except Exception:
    report = {'parse_error': True, 'violations': [], 'signature': ''}
task_path = task_dir / 'task.json'
task = json.loads(task_path.read_text(encoding='utf-8'))
now = datetime.now().astimezone().isoformat(timespec='seconds')
violations = report.get('violations') if isinstance(report.get('violations'), list) else []
signature = str(report.get('signature') or '')
parse_error = bool(report.get('parse_error'))
previous_signature = str(task.get('state_invariant_signature') or '')
current_state = str(task.get('control_plane_state') or '')
changed = False
notify = False

if parse_error:
    task['state_invariant_checked_at'] = now
    if task.get('state_invariant_parse_error_at') != now:
        task['state_invariant_parse_error_at'] = now
        changed = True
elif violations:
    if task.get('state_invariant_violations') != violations:
        task['state_invariant_violations'] = violations
        changed = True
    if previous_signature != signature:
        task['state_invariant_violation_count'] = int(task.get('state_invariant_violation_count') or 0) + 1
        task['state_invariant_signature'] = signature
        notify = True
        changed = True
    task['state_invariant_checked_at'] = now
    if current_state not in {'reassigned', 'auto_requeue'}:
        if task.get('control_plane_state') != 'state_invariant_violation':
            task['control_plane_state'] = 'state_invariant_violation'
            changed = True
        task['control_plane_updated_at'] = now
        changed = True
else:
    if task.get('state_invariant_parse_error_at'):
        task['state_invariant_parse_error_at'] = None
        changed = True
    if task.get('state_invariant_violations'):
        task['state_invariant_violations'] = []
        changed = True
    if previous_signature:
        task['state_invariant_signature'] = ''
        changed = True
    if current_state == 'state_invariant_violation':
        task['control_plane_state'] = None
        task['control_plane_updated_at'] = now
        changed = True
    # Clean tasks should not be rewritten on every watcher scan.  Rewriting
    # task.json refreshes its mtime and can make file-mtime based notification
    # gates think that a terminal event changed again.

if changed:
    task['updated_at'] = now
    with tempfile.NamedTemporaryFile('w', delete=False, dir=str(task_dir), encoding='utf-8') as tmp:
        json.dump(task, tmp, ensure_ascii=False, indent=2)
        tmp.write('\n')
    os.replace(tmp.name, task_path)

print(json.dumps({
    'notify': notify,
    'parse_error': parse_error,
    'count': len(violations),
    'messages': [str(item.get('message') or '') for item in violations if isinstance(item, dict)],
}, ensure_ascii=False))
PY
}

list_dev_agents() {
    python3 "$AGENT_CONFIG_PY" list-dev-agent-ids --config "$CONFIG_PATH"
}

is_development_agent() {
    local agent_id="$1"
    [ -n "$agent_id" ] || return 1
    list_dev_agents | grep -Fx -- "$agent_id" >/dev/null 2>&1
}

list_pool_agents() {
    python3 "$AGENT_CONFIG_PY" list-pool-agent-ids --config "$CONFIG_PATH"
}

task_pool_bool() {
    local key="$1"
    local default_value="${2:-false}"
    python3 - "$CONFIG_PATH" "$key" "$default_value" <<'PY'
import json
import sys
from pathlib import Path

config = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
key = sys.argv[2]
default = sys.argv[3].strip().lower() in {'1', 'true', 'yes', 'on'}
value = (config.get('task_pool') or {}).get(key, default)
if isinstance(value, str):
    value = value.strip().lower() in {'1', 'true', 'yes', 'on'}
print('1' if value else '0')
PY
}

task_pool_int() {
    local key="$1"
    local default_value="${2:-0}"
    python3 - "$CONFIG_PATH" "$key" "$default_value" <<'PY'
import json
import sys
from pathlib import Path

config = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
key = sys.argv[2]
default = int(sys.argv[3])
value = (config.get('task_pool') or {}).get(key, default)
try:
    print(int(value))
except Exception:
    print(default)
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

reserved_task_count_for_agent() {
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
    if str(task.get('assigned_agent') or '') == agent_id and str(task.get('status') or '') == 'dispatched':
        count += 1
print(count)
PY
}


agent_has_other_working_task() {
    local agent_id="$1"
    local current_task_id="${2:-}"
    python3 - "$TASKS_ROOT" "$agent_id" "$current_task_id" <<'PY'
import json
import sys
from pathlib import Path

tasks_root = Path(sys.argv[1])
agent_id = sys.argv[2]
current_task_id = sys.argv[3]
for task_path in tasks_root.glob('*/task.json'):
    try:
        task = json.loads(task_path.read_text(encoding='utf-8'))
    except Exception:
        continue
    task_id = str(task.get('id') or task_path.parent.name)
    if task_id == current_task_id:
        continue
    if str(task.get('assigned_agent') or '') == agent_id and str(task.get('status') or '') == 'working':
        print(task_id)
        raise SystemExit(0)
raise SystemExit(1)
PY
}

task_delivery_deferred_until_idle() {
    local task_dir="$1"
    local state until
    state=$(task_json_pick "$task_dir" last_delivery_state 2>/dev/null || true)
    until=$(task_json_pick "$task_dir" delivery_deferred_until 2>/dev/null || true)
    [ "$state" = "deferred_agent_busy" ] || [ "$until" = "agent_idle" ]
}

deliver_reserved_task_ready_notice() {
    local task_dir="$1"
    local task_id="$2"
    local agent_id="$3"
    local notice_key="${task_id}_reserved_ready_notice"
    local now last_notice workspace_payload workspace_hint

    now=$(date +%s)
    last_notice=$(cat "$STATE_DIR/$notice_key" 2>/dev/null || echo 0)
    if [ $(( now - ${last_notice:-0} )) -lt "$RESEND_COOLDOWN_SECONDS" ]; then
        return 0
    fi

    workspace_payload=$(prepare_task_workspace_payload "$task_dir")
    workspace_hint=$(workspace_hint_from_payload "$workspace_payload")
    deliver_execution_instruction_and_record "$task_dir" "$task_id" "$agent_id" "你已有预留任务可开始：${task_id}。请读取 ${TASKS_ROOT}/${task_id}/instruction.md，确认后写 ack.json 开始执行。${workspace_hint:+ ${workspace_hint}}" || true
    emit_system_chat_event nudge "$task_id" "预留任务已成为 ${agent_id} 的下一条可执行任务，已在空闲后提醒 ack。" "$agent_id" info nudge
    echo "$now" > "$STATE_DIR/$notice_key"
}

reserved_task_for_agent() {
    local agent_id="$1"
    python3 - "$TASKS_ROOT" "$agent_id" <<'PY'
import json
import sys
from pathlib import Path

tasks_root = Path(sys.argv[1])
agent_id = sys.argv[2]
rows = []
for task_path in tasks_root.glob('*/task.json'):
    task = json.loads(task_path.read_text(encoding='utf-8'))
    if str(task.get('assigned_agent') or '') != agent_id:
        continue
    if str(task.get('status') or '') != 'dispatched':
        continue
    claimed_at = str(task.get('claimed_at') or task.get('reserved_at') or task.get('lease_acquired_at') or task.get('updated_at') or '')
    rows.append((claimed_at, str(task.get('id') or task_path.parent.name)))
for _, task_id in sorted(rows):
    print(task_id)
    break
PY
}

agent_capacity_limits() {
    local agent_id="$1"
    python3 - "$CONFIG_PATH" "$agent_id" <<'PY'
import json
import sys
from pathlib import Path

config = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
agent_id = sys.argv[2]
pool = config.get('task_pool') or {}
agents = config.get('agents') or {}
wip_limits = config.get('wip_limits') or {}

def as_int(value, default):
    try:
        if value in (None, ''):
            return default
        return int(value)
    except Exception:
        return default

working_limit = max(1, as_int(pool.get('default_working_limit'), 1))
reserved_limit = max(1, as_int(pool.get('default_reserved_limit'), 1))
role = str((agents.get(agent_id) or {}).get('role') or '').strip().lower()
role_keys = {
    'fullstack_dev': 'dev',
    'reviewer': 'reviewer',
    'qa': 'qa',
    'architect': 'architect',
    'pm': 'pm',
}
role_key = role_keys.get(role)
role_limit = wip_limits.get(agent_id)
if role_limit in (None, '') and role_key:
    role_limit = wip_limits.get(role_key)
if role_limit in (None, '') and role == 'pm':
    root_pm = str((config.get('orchestration') or {}).get('root_pm') or '').strip()
    if root_pm:
        role_limit = wip_limits.get(root_pm)
if role_limit not in (None, ''):
    working_limit = max(1, min(working_limit, as_int(role_limit, working_limit)))
print(f'{working_limit} {reserved_limit} {working_limit + reserved_limit}')
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
    python3 - "$task_dir/task.json" "$CONFIG_PATH" "$AGENT_CONFIG_PY" <<'PY'
import json
import sys
from pathlib import Path

task = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
config = json.loads(Path(sys.argv[2]).read_text(encoding='utf-8'))
sys.path.insert(0, str(Path(sys.argv[3]).resolve().parent))
from agent_config import default_claim_scope  # type: ignore

for value in default_claim_scope(task, config):
    print(value)
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
    python3 - "$task_dir/task.json" "$TASKS_ROOT" "$agent_id" "$CONFIG_PATH" <<'PY'
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
config = json.loads(Path(sys.argv[4]).read_text(encoding='utf-8'))

def project_roots(payload):
    project = str(payload.get('project') or '').strip()
    project_cfg = (config.get('projects') or {}).get(project) or {}
    dev_root = project_cfg.get('dev_root')
    prod_root = project_cfg.get('prod_root')
    return (
        Path(dev_root).expanduser().resolve() if dev_root else None,
        Path(prod_root).expanduser().resolve() if prod_root else None,
    )

def resolve_scope_paths(payload):
    raw_scope = [str(item).strip() for item in (payload.get('write_scope') or []) if str(item).strip()]
    if not raw_scope:
        return []
    dev_root, prod_root = project_roots(payload)
    target_env = str(payload.get('target_environment') or 'dev').strip().lower()
    base_root = prod_root if target_env == 'prod' and prod_root is not None else dev_root
    output = []
    for item in raw_scope:
        path = Path(item).expanduser()
        if not path.is_absolute() and base_root is not None:
            path = base_root / path
        output.append(path.resolve())
    return output

target_scope = resolve_scope_paths(task)
if not target_scope:
    raise SystemExit(0)

for task_path in tasks_root.glob('*/task.json'):
    payload = json.loads(task_path.read_text(encoding='utf-8'))
    if str(payload.get('assigned_agent') or '') != agent_id:
        continue
    if str(payload.get('status') or '') not in {'dispatched', 'working'}:
        continue
    for other in resolve_scope_paths(payload):
        for target in target_scope:
            if scopes_overlap(target, other):
                print(f'conflict:{task_path.parent.name}:{other}')
                raise SystemExit(1)
raise SystemExit(0)
PY
}

claim_dependencies_ready() {
    local task_dir="$1"
    dependencies_ready "$task_dir" >/dev/null 2>&1
}

claim_pool_gate_ready() {
    local task_dir="$1"
    python3 - "$task_dir" "$WORKSPACE_ROOT" <<'PY'
import json
import sys
from pathlib import Path

task_dir = Path(sys.argv[1])
workspace_root = Path(sys.argv[2])
sys.path.insert(0, str(workspace_root / 'scripts' / 'lib'))
from task_pool_rules import pool_gate_blockers  # type: ignore

task = json.loads((task_dir / 'task.json').read_text(encoding='utf-8'))
blockers = pool_gate_blockers(task, task_dir)
if blockers:
    print(','.join(blockers))
    raise SystemExit(1)
raise SystemExit(0)
PY
}

claim_agent_can_accept_task() {
    local task_dir="$1"
    local agent_id="$2"

    claim_pool_gate_ready "$task_dir" >/dev/null 2>&1 || return 1
    is_agent_in_claim_scope "$task_dir" "$agent_id" || return 1
    claim_dependencies_ready "$task_dir" || return 1
    claim_scope_conflict_free "$task_dir" "$agent_id" >/dev/null 2>&1 || return 1
    task_no_progress_repool_cooldown_active "$task_dir" "$agent_id" && return 1

    local working_count active_count reserved_count limits working_limit reserved_limit active_limit
    working_count=$(working_task_count_for_agent "$agent_id" 2>/dev/null || echo 0)
    reserved_count=$(reserved_task_count_for_agent "$agent_id" 2>/dev/null || echo 0)
    active_count=$(active_task_count_for_agent "$agent_id" 2>/dev/null || echo 0)
    limits=$(agent_capacity_limits "$agent_id" 2>/dev/null || echo "1 1 2")
    working_limit=$(echo "$limits" | awk '{print $1}')
    reserved_limit=$(echo "$limits" | awk '{print $2}')
    active_limit=$(echo "$limits" | awk '{print $3}')
    [ "${working_count:-0}" -le "${working_limit:-1}" ] || return 1
    [ "${reserved_count:-0}" -lt "${reserved_limit:-1}" ] || return 1
    [ "${active_count:-0}" -lt "${active_limit:-2}" ]
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

select_reassign_candidate() {
    local task_dir="$1"
    local current_agent="$2"
    while IFS= read -r agent_id; do
        [ -n "$agent_id" ] || continue
        [ "$agent_id" = "$current_agent" ] && continue
        if is_idle_agent "$agent_id" && claim_agent_can_accept_task "$task_dir" "$agent_id"; then
            echo "$agent_id"
            return 0
        fi
    done <<< "$(task_claim_scope "$task_dir")"
    return 1
}

dispatch_failure_threshold_exceeded() {
    local task_dir="$1"
    local failures
    failures=$(task_json_pick "$task_dir" dispatch_delivery_consecutive_failures 2>/dev/null || echo 0)
    [ "${failures:-0}" -ge "${DISPATCH_FAILURE_THRESHOLD:-3}" ]
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

confirm_claim_request() {
    local task_dir="$1"
    local task_id="$2"
    local claim_path="$task_dir/claim.json"
    [ -f "$claim_path" ] || return 1

    local claim_agent claim_time claim_reason current_status
    claim_agent=$(json_pick "$claim_path" agent agent_id)
    claim_time=$(json_pick "$claim_path" claimed_at timestamp)
    claim_reason=$(json_pick "$claim_path" reason)
    [ -n "$claim_agent" ] || { claim_reject "$task_dir" "" "claim.json 缺少 agent"; return 2; }

    current_status=$(get_task_status "$task_dir")
    [ "$current_status" = "pooled" ] || return 1

    current_status=$(get_task_status "$task_dir")
    if [ "$current_status" != "pooled" ]; then
        return 1
    fi
    if ! claim_agent_can_accept_task "$task_dir" "$claim_agent"; then
        claim_reject "$task_dir" "$claim_agent" "不满足认领条件（Pool Gate/依赖/并发/能力/write_scope 冲突）"
        return 2
    fi

    dispatch_task_to_agent "$task_dir" "$claim_agent" "watcher confirmed claim.json" "$claim_agent" "$claim_time" "$claim_reason"
    local workspace_payload workspace_hint
    workspace_payload=$(prepare_task_workspace_payload "$task_dir")
    workspace_hint=$(workspace_hint_from_payload "$workspace_payload")

    python3 - "$task_id" "$claim_agent" "$claim_time" "$claim_reason" "$workspace_hint" <<'PY'
import json
import sys

print(json.dumps({
    "task_id": sys.argv[1],
    "agent": sys.argv[2],
    "claimed_at": sys.argv[3] or None,
    "claim_reason": sys.argv[4] or None,
    "dispatch_hint": sys.argv[5] or None,
}, ensure_ascii=False))
PY
}

auto_push_next_task_for_agent() {
    local agent_id="$1"
    local trigger_task_id="${2:-}"
    [ -n "$agent_id" ] || return 1
    [ "$(task_pool_bool auto_claim_idle_agents true 2>/dev/null || echo 1)" = "1" ] || return 1

    local active_count working_count reserved_task reserved_notice_key now last_notice
    active_count=$(active_task_count_for_agent "$agent_id" 2>/dev/null || echo 0)
    if [ "${active_count:-0}" -gt 0 ]; then
        working_count=$(working_task_count_for_agent "$agent_id" 2>/dev/null || echo 0)
        if [ "${working_count:-0}" -eq 0 ]; then
            reserved_task=$(reserved_task_for_agent "$agent_id" 2>/dev/null || true)
            if [ -n "$reserved_task" ]; then
                deliver_reserved_task_ready_notice "$TASKS_ROOT/$reserved_task" "$reserved_task" "$agent_id"
                return 0
            fi
        fi
        return 1
    fi

    local next_task=""
    next_task=$(python3 "$TASK_POOL_ROUTER" --tasks-root "$TASKS_ROOT" --config "$CONFIG_PATH" --agent "$agent_id" --next 2>/dev/null || true)

    [ -n "$next_task" ] || return 1

    local reason="watcher auto-continued after ${trigger_task_id:-previous task completion}"
    local task_dir="$TASKS_ROOT/$next_task"
    local claim_payload=""
    if CLAIM_AGENT_ID="$agent_id" TASKS_ROOT="$TASKS_ROOT" CONFIG_PATH="$CONFIG_PATH" "$WORKSPACE_ROOT/scripts/claim-task.sh" "$next_task" "$reason" >/dev/null 2>&1 \
        && claim_payload=$(confirm_claim_request "$task_dir" "$next_task" 2>/dev/null); then
        local workspace_hint=""
        workspace_hint=$(workspace_hint_from_payload "$claim_payload")
        deliver_execution_instruction_and_record "$task_dir" "$next_task" "$agent_id" "你当前主线已完成/进入待审。下一条可执行任务已自动续推：${next_task}。请读取 ${TASKS_ROOT}/${next_task}/instruction.md，并在确认后写 ack.json 开始执行。${workspace_hint:+ ${workspace_hint}}" || true
        emit_system_chat_event nudge "$next_task" "上一条主线完成后，已自动续推给 ${agent_id} 作为下一条可执行任务。" "$agent_id" info nudge
        sync_task_board "$task_dir" "auto-claim-dev"
        log "${next_task}: 已在 ${trigger_task_id:-unknown} 完成后自动续推给 ${agent_id}"
        return 0
    fi

    return 1
}

auto_reserve_next_task_for_agent() {
    local agent_id="$1"
    local trigger_task_id="${2:-}"
    [ -n "$agent_id" ] || return 1
    [ "$(task_pool_bool auto_reserve_while_working false 2>/dev/null || echo 0)" = "1" ] || return 1

    local working_count reserved_count limits working_limit reserved_limit
    working_count=$(working_task_count_for_agent "$agent_id" 2>/dev/null || echo 0)
    [ "${working_count:-0}" -gt 0 ] || return 1
    reserved_count=$(reserved_task_count_for_agent "$agent_id" 2>/dev/null || echo 0)
    limits=$(agent_capacity_limits "$agent_id" 2>/dev/null || echo "1 1 2")
    working_limit=$(echo "$limits" | awk '{print $1}')
    reserved_limit=$(echo "$limits" | awk '{print $2}')
    [ "${working_count:-0}" -le "${working_limit:-1}" ] || return 1
    [ "${reserved_count:-0}" -lt "${reserved_limit:-1}" ] || return 1

    local next_task=""
    next_task=$(python3 "$TASK_POOL_ROUTER" --tasks-root "$TASKS_ROOT" --config "$CONFIG_PATH" --agent "$agent_id" --next 2>/dev/null || true)
    [ -n "$next_task" ] || return 1

    local reason="watcher auto-reserved while ${agent_id} is working"
    local task_dir="$TASKS_ROOT/$next_task"
    local claim_payload=""
    if CLAIM_AGENT_ID="$agent_id" TASKS_ROOT="$TASKS_ROOT" CONFIG_PATH="$CONFIG_PATH" "$WORKSPACE_ROOT/scripts/claim-task.sh" "$next_task" "$reason" >/dev/null 2>&1 \
        && claim_payload=$(confirm_claim_request "$task_dir" "$next_task" 2>/dev/null); then
        mark_dispatch_delivery_deferred_until_idle "$task_dir" "watcher auto-reserved while ${agent_id} is working; tmux delivery deferred until agent idle" "$(session_health_state "$agent_id")"
        emit_system_chat_event nudge "$next_task" "watcher 已为 ${agent_id} 预留下一条任务；因 agent 当前 working，tmux 执行通知已延后到空闲后触达。" "$agent_id" info nudge
        sync_task_board "$task_dir" "auto-reserve-dev-deferred"
        log "${next_task}: 已为 ${agent_id} 非打断预留下一条任务，投递延后到空闲后（trigger=${trigger_task_id:-idle sweep}）"
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
    next_task=$(python3 "$TASK_QUEUE_ROUTER" --tasks-root "$TASKS_ROOT" --queue review --agent "$agent_id" --next 2>/dev/null || true)
    [ -n "$next_task" ] || return 1

    # 防止对已有审查结论的任务重复续推：如果 review 已有明确结论，等待主循环流转 gate。
    local next_task_dir="$TASKS_ROOT/$next_task"
    if review_artifact_is_terminal "$next_task_dir"; then
        log "${next_task}: 跳过续推，已有审查结论 ($(artifact_pick review "$next_task_dir" normalized_status 2>/dev/null || true))"
        return 1
    fi

    rm -f "$STATE_DIR/${next_task}_review_queue_waiting_notice" "$STATE_DIR/${next_task}_review_queue_waiting_notice.retry"
    queue_state_set "review" "$agent_id" "$next_task"
    notify_agent "$agent_id" "请读取 ${TASKS_ROOT}/${next_task}/instruction.md 与 result.json，并输出 review.json（必需）与 review.md（人读说明，可选但推荐）。"
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
    next_task=$(python3 "$TASK_QUEUE_ROUTER" --tasks-root "$TASKS_ROOT" --queue qa --agent "$agent_id" --next 2>/dev/null || true)
    [ -n "$next_task" ] || return 1

    rm -f "$STATE_DIR/${next_task}_qa_queue_waiting_notice" "$STATE_DIR/${next_task}_qa_queue_waiting_notice.retry"
    queue_state_set "qa" "$agent_id" "$next_task"
    notify_agent "$agent_id" "请读取 ${TASKS_ROOT}/${next_task}/instruction.md、result/review artifacts，并输出 verify.json。"
    emit_system_chat_event nudge "$next_task" "QA 队列已在 ${trigger_task_id:-idle sweep} 后自动续推给 ${agent_id}。" "$agent_id" info nudge
    log "${next_task}: 已自动续推 QA 任务给 ${agent_id}"
    return 0
}

reconcile_open_merge_gate() {
    local task_dir="$1"
    local task_id="$2"
    local current_status="$3"
    [ "$current_status" = "ready_for_merge" ] || return 1

    local gate review_level summary current_review_state current_qa_state
    gate=$(task_json_pick "$task_dir" merge_gate_state)
    review_level=$(task_json_pick "$task_dir" review_level)
    summary=$(json_pick "$task_dir/result.json" summary)
    current_review_state=$(review_state "$task_dir" "$review_level")
    current_qa_state=$(verify_state "$task_dir/verify.json")

    case "$gate" in
        review_pending)
            if [ "$current_review_state" = "pending" ]; then
                auto_dispatch_review "$task_dir" "$task_id" "$review_level" "$summary"
                return $?
            fi
            ;;
        qa_pending)
            if [ "$current_qa_state" = "missing" ] || [ "$current_qa_state" = "pending" ]; then
                auto_dispatch_qa "$task_id"
                return $?
            fi
            ;;
        quality_pending)
            if [ "$current_review_state" = "pending" ]; then
                auto_dispatch_review "$task_dir" "$task_id" "$review_level" "$summary" || true
            fi
            if [ "$current_qa_state" = "missing" ] || [ "$current_qa_state" = "pending" ]; then
                auto_dispatch_qa "$task_id" || true
            fi
            return 0
            ;;
    esac
    return 1
}

is_idle_agent() {
    local agent_id="$1"
    local tmux_session
    local active_count
    active_count=$(active_task_count_for_agent "$agent_id" 2>/dev/null || echo 0)
    if [ "${active_count:-0}" -gt 0 ]; then
        return 1
    fi
    tmux_session="$(resolve_agent_session "$agent_id")"
    if tmux has-session -t "$tmux_session" 2>/dev/null; then
        local is_working
        is_working=$(tmux capture-pane -t "$tmux_session" -p 2>/dev/null | grep -c 'Working\|• Working' || true)
        [ "${is_working:-0}" -eq 0 ]
        return $?
    fi
    return 1
}

normalize_legacy_task_status() {
    local task_dir="$1"
    local current_status="$2"
    case "$current_status" in
        in_review|reviewing) ;;
        *) return 1 ;;
    esac

    local inferred_gate_state now_iso new_status
    inferred_gate_state=$(resolve_merge_gate_state "$task_dir" 2>/dev/null || true)
    [ -n "$inferred_gate_state" ] || inferred_gate_state="review_pending"
    now_iso=$(now_iso)

    case "$inferred_gate_state" in
        review_rejected|qa_failed|blocked)
            set_task_gate_state "$task_dir" "blocked" "watcher normalized legacy review status" "$inferred_gate_state" "$( [ "$inferred_gate_state" = "review_rejected" ] && echo review || { [ "$inferred_gate_state" = "qa_failed" ] && echo qa || echo ""; } )" "watcher" "$now_iso"
            ;;
        review_pending|qa_pending|quality_pending|pm_acceptance_pending)
            set_task_gate_state "$task_dir" "ready_for_merge" "watcher normalized legacy review status" "$inferred_gate_state" "" "watcher" "$now_iso"
            ;;
        closed)
            set_task_gate_state "$task_dir" "done" "watcher normalized legacy closed status" "closed" "" "watcher" "$now_iso"
            ;;
        *)
            set_task_gate_state "$task_dir" "ready_for_merge" "watcher normalized legacy review status" "review_pending" "" "watcher" "$now_iso"
            ;;
    esac
    return 0
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
    local patch_json="${4-}"
    [ -n "$patch_json" ] || patch_json='{}'
    local patch_file=""
    local output=""
    patch_file=$(mktemp "${STATE_DIR}/patch.XXXXXX.json" 2>/dev/null || mktemp)
    printf '%s' "$patch_json" > "$patch_file"
    output=$(python3 - "$task_dir" "$new_status" "$reason" "$patch_file" <<'PY'
import json
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path

task_dir = Path(sys.argv[1])
new_status = sys.argv[2].strip()
reason = sys.argv[3]
patch_path = Path(sys.argv[4])
patch_json = patch_path.read_text(encoding='utf-8').strip() or '{}'
task_path = task_dir / 'task.json'
transitions_path = task_dir / 'transitions.jsonl'
task = json.loads(task_path.read_text(encoding='utf-8'))
old_status = task.get('status', '')
now = datetime.now().astimezone().isoformat(timespec='seconds')
try:
    patch = json.loads(patch_json)
except Exception:
    raise SystemExit(f'patch_json_invalid:{patch_path}')

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
with tempfile.NamedTemporaryFile('w', delete=False, dir=str(task_path.parent), encoding='utf-8') as tmp:
    json.dump(task, tmp, ensure_ascii=False, indent=2)
    tmp.write('\n')
tmp_path = Path(tmp.name)
os.replace(tmp_path, task_path)
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
    rm -f "$patch_file"
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
    local patch_json="${2-}"
    [ -n "$patch_json" ] || patch_json='{}'
    local reason="${3:-watcher metadata update}"
    update_task_record "$task_dir" "" "$reason" "$patch_json"
}

set_task_gate_state() {
    local task_dir="$1"
    local new_status="${2:-}"
    local reason="${3:-watcher gate update}"
    local merge_gate_state="${4:-}"
    local rework_reason="${5:-__KEEP__}"
    local last_gate_actor="${6:-}"
    local last_gate_decision_at="${7:-}"
    local review_gate_state="${8:-__KEEP__}"
    local qa_gate_state="${9:-__KEEP__}"
    local output=""
    local effective_last_gate_decision_at="$last_gate_decision_at"
    if [ "$effective_last_gate_decision_at" != "__KEEP__" ]; then
        local current_task_value
        current_task_value=$(task_json_pick "$task_dir" merge_gate_state)
        if [ "$merge_gate_state" != "__KEEP__" ] && [ "$current_task_value" = "$merge_gate_state" ]; then
            effective_last_gate_decision_at="__KEEP__"
        fi
    fi
    output=$(python3 - "$task_dir" "$new_status" "$reason" "$merge_gate_state" "$rework_reason" "$last_gate_actor" "$effective_last_gate_decision_at" "$review_gate_state" "$qa_gate_state" <<'PY'
import json
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path

task_dir = Path(sys.argv[1])
new_status = sys.argv[2].strip()
reason = sys.argv[3]
merge_gate_state = sys.argv[4]
rework_reason = sys.argv[5]
last_gate_actor = sys.argv[6]
last_gate_decision_at = sys.argv[7]
review_gate_state = sys.argv[8]
qa_gate_state = sys.argv[9]

task_path = task_dir / 'task.json'
transitions_path = task_dir / 'transitions.jsonl'
task = json.loads(task_path.read_text(encoding='utf-8'))
old_status = str(task.get('status') or '')
now = datetime.now().astimezone().isoformat(timespec='seconds')

status_changed = bool(new_status) and old_status != new_status
fields_changed = False

def artifact_round(payload):
    for key in ('round', 'execution_round', 'review_round', 'verify_round', 'resume_round'):
        value = payload.get(key)
        if value in (None, ''):
            continue
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            continue
        if parsed >= 0:
            return parsed
    return None


def next_execution_round():
    current = task.get('execution_round', task.get('resume_round', 0))
    try:
        current_round = int(current or 0)
    except (TypeError, ValueError):
        current_round = 0
    result_path = task_dir / 'result.json'
    if result_path.exists():
        try:
            result_payload = json.loads(result_path.read_text(encoding='utf-8'))
        except Exception:
            result_payload = {}
        result_round = artifact_round(result_payload)
        if result_round is not None:
            return max(current_round, result_round)
    return current_round


if new_status:
    task['status'] = new_status
if merge_gate_state != "__KEEP__" and task.get('merge_gate_state') != merge_gate_state:
    task['merge_gate_state'] = merge_gate_state
    fields_changed = True
    if merge_gate_state in {'review_pending', 'qa_pending', 'quality_pending', 'pm_acceptance_pending'}:
        execution_round = next_execution_round()
        if task.get('execution_round') != execution_round:
            task['execution_round'] = execution_round
            fields_changed = True
if review_gate_state != "__KEEP__":
    value = None if review_gate_state in {"", "null", "None"} else review_gate_state
    if task.get('review_gate_state') != value:
        task['review_gate_state'] = value
        fields_changed = True
if qa_gate_state != "__KEEP__":
    value = None if qa_gate_state in {"", "null", "None"} else qa_gate_state
    if task.get('qa_gate_state') != value:
        task['qa_gate_state'] = value
        fields_changed = True
if rework_reason != "__KEEP__":
    value = None if rework_reason in {"", "null", "None"} else rework_reason
    if task.get('rework_reason') != value:
        task['rework_reason'] = value
        fields_changed = True
if last_gate_actor != "__KEEP__" and task.get('last_gate_actor') != last_gate_actor:
    task['last_gate_actor'] = last_gate_actor
    fields_changed = True
if last_gate_decision_at != "__KEEP__" and task.get('last_gate_decision_at') != last_gate_decision_at:
    task['last_gate_decision_at'] = last_gate_decision_at
    fields_changed = True

if not status_changed and not fields_changed:
    print(f'unchanged: status={old_status}')
    raise SystemExit(0)

task['updated_at'] = now
with tempfile.NamedTemporaryFile('w', delete=False, dir=str(task_path.parent), encoding='utf-8') as tmp:
    json.dump(task, tmp, ensure_ascii=False, indent=2)
    tmp.write('\n')
tmp_path = Path(tmp.name)
os.replace(tmp_path, task_path)
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
    print('fields updated without status change: gate-related fields')
PY
)
    local status_rc=$?
    if [ -n "$output" ]; then
        log "$(basename "$task_dir"): $output | reason=$reason"
    fi
    return $status_rc
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

notified_epoch() {
    local key="$1"
    local flag="$STATE_DIR/$key"
    if [ ! -f "$flag" ]; then
        echo 0
        return 0
    fi
    cat "$flag" 2>/dev/null || echo 0
}

final_done_transition_epoch() {
    local task_dir="$1"
    python3 - "$task_dir/transitions.jsonl" <<'PY'
import json
import os
import sys
import tempfile
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

notification_retry_flag() {
    local key="$1"
    printf '%s/%s.retry\n' "$STATE_DIR" "$key"
}

mark_notification_retry_pending() {
    local key="$1"
    echo "$(date +%s)" > "$(notification_retry_flag "$key")"
}

clear_notification_retry_pending() {
    local key="$1"
    rm -f "$(notification_retry_flag "$key")"
}

notification_retry_due() {
    local key="$1"
    local cooldown="${2:-$NOTIFY_RETRY_COOLDOWN_SECONDS}"
    local retry_flag
    retry_flag="$(notification_retry_flag "$key")"
    [ -f "$retry_flag" ] || return 0
    local last_failed now
    last_failed=$(cat "$retry_flag" 2>/dev/null || echo 0)
    [ -n "$last_failed" ] || return 0
    now=$(date +%s)
    [ $(( now - last_failed )) -ge "$cooldown" ]
}

push_task_event_with_retry() {
    local push_key="$1"
    local artifact_path="$2"
    local title="$3"
    local task_id="$4"
    local summary="${5:-}"
    local next_action="${6:-}"

    if is_notified "$push_key" && { [ -z "$artifact_path" ] || ! is_file_newer_than_notified "$push_key" "$artifact_path"; }; then
        return 0
    fi

    if ! notification_retry_due "$push_key"; then
        return 1
    fi

    if push_task_event "$title" "$task_id" "$summary" "$next_action"; then
        mark_notified "$push_key"
        clear_notification_retry_pending "$push_key"
        return 0
    fi

    mark_notification_retry_pending "$push_key"
    return 1
}

push_task_event_with_signature_retry() {
    local push_key="$1"
    local signature="$2"
    local title="$3"
    local task_id="$4"
    local summary="${5:-}"
    local next_action="${6:-}"

    if is_notified "$push_key" && ! is_signature_newer_than_notified "$push_key" "$signature"; then
        return 0
    fi

    if ! notification_retry_due "$push_key"; then
        return 1
    fi

    if push_task_event "$title" "$task_id" "$summary" "$next_action"; then
        mark_signature_notified "$push_key" "$signature"
        clear_notification_retry_pending "$push_key"
        return 0
    fi

    mark_notification_retry_pending "$push_key"
    return 1
}

review_signature() {
    local task_dir="$1"
    local review_mtime="0"
    local design_review_mtime="0"
    local review_json_mtime="0"
    local design_review_json_mtime="0"
    [ -f "$task_dir/review.json" ] && review_json_mtime=$(stat -f %m "$task_dir/review.json" 2>/dev/null || echo 0)
    [ -f "$task_dir/design-review.json" ] && design_review_json_mtime=$(stat -f %m "$task_dir/design-review.json" 2>/dev/null || echo 0)
    [ -f "$task_dir/review.md" ] && review_mtime=$(stat -f %m "$task_dir/review.md" 2>/dev/null || echo 0)
    [ -f "$task_dir/design-review.md" ] && design_review_mtime=$(stat -f %m "$task_dir/design-review.md" 2>/dev/null || echo 0)
    echo "${review_json_mtime}:${design_review_json_mtime}:${review_mtime}:${design_review_mtime}"
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

    # 优先提取明确结论块：标题「结论/审查结论/最终意见」及紧随其后的几行。
    local conclusion_block
    conclusion_block=$(python3 - "$review_file" <<'PY'
from pathlib import Path
import re
import sys

path = Path(sys.argv[1])
text = path.read_text(encoding='utf-8', errors='ignore')
lines = text.splitlines()
label_re = re.compile(r'^\s*(?:#{1,6}\s*)?(?:审查结论|复审结论|最终结论|最终意见|结论|review conclusion|conclusion|verdict|decision)\s*(?:[:：\-—]\s*)?(.*)$', re.I)
blocks = []
for idx, line in enumerate(lines[:80]):
    m = label_re.match(line)
    if not m:
        continue
    snippets = []
    suffix = (m.group(1) or '').strip()
    if suffix:
        snippets.append(suffix)
    for follow in lines[idx + 1: idx + 8]:
        stripped = follow.strip()
        if not stripped:
            continue
        if stripped.startswith('#') and snippets:
            break
        snippets.append(stripped)
        if len(snippets) >= 5:
            break
    if snippets:
        blocks.append('\n'.join(snippets))
if blocks:
    print('\n---\n'.join(blocks))
PY
)

    local scan_text
    if [ -n "$conclusion_block" ]; then
        scan_text="$conclusion_block"
    else
        scan_text="$(grep -v '^[[:space:]]*$' "$review_file" | head -40)"
    fi

    # 先判驳回，再判通过；避免「通过项」误把 REQUEST CHANGES 覆盖掉。
    if printf '%s\n' "$scan_text" | grep -qiE 'request[[:space:]_-]*changes|changes[[:space:]_-]*requested|驳回|不通过|未通过|不接受|reject(ed)?'; then
        echo "fail"
        return 0
    fi
    if printf '%s\n' "$scan_text" | grep -qiE 'approve(d)?|lgtm|ship[[:space:]]+it|通过|同意合入|批准'; then
        echo "pass"
        return 0
    fi
    echo "pending"
}

review_state() {
    local task_dir="$1"
    local normalized
    normalized=$(artifact_pick review "$task_dir" normalized_status)
    case "$normalized" in
        approve) echo "pass" ;;
        request_changes|blocked) echo "fail" ;;
        invalid) echo "invalid" ;;
        pending|missing|"") echo "pending" ;;
        *) echo "pending" ;;
    esac
}

is_truthy() {
    local value="${1:-}"
    case "$(printf '%s' "$value" | tr '[:upper:]' '[:lower:]')" in
        1|true|yes|y|on) return 0 ;;
        *) return 1 ;;
    esac
}

review_gate_state() {
    local task_dir="$1"
    local normalized
    normalized=$(artifact_pick review "$task_dir" normalized_status)
    case "$normalized" in
        approve) echo "approved" ;;
        request_changes) echo "rejected" ;;
        blocked) echo "blocked" ;;
        invalid) echo "invalid" ;;
        pending|missing|"") echo "pending" ;;
        *) echo "pending" ;;
    esac
}

first_review_conclusion() {
    local task_dir="$1"
    local summary
    summary=$(artifact_pick review "$task_dir" sources.review_json.summary sources.design_review_json.summary)
    if [ -n "$summary" ]; then
        echo "$summary"
        return 0
    fi
    local line
    line=$(grep -i '不通过\|未通过\|驳回\|reject\|block\|不接受\|request changes\|通过\|approve' "$task_dir/review.md" "$task_dir/design-review.md" 2>/dev/null | head -1)
    echo "$line"
}

verify_state() {
    local task_dir="${1%/verify.json}"
    local normalized
    normalized=$(artifact_pick verify "$task_dir" normalized_status)
    case "$normalized" in
        pass) echo "pass" ;;
        fail|blocked) echo "fail" ;;
        invalid) echo "invalid" ;;
        missing|"") echo "missing" ;;
        *) echo "pending" ;;
    esac
}

qa_gate_state() {
    local task_dir="${1%/verify.json}"
    local normalized
    normalized=$(artifact_pick verify "$task_dir" normalized_status)
    case "$normalized" in
        pass) echo "passed" ;;
        fail) echo "failed" ;;
        blocked) echo "blocked" ;;
        invalid) echo "invalid" ;;
        missing|"") echo "pending" ;;
        *) echo "pending" ;;
    esac
}

verify_summary() {
    local verify_file="$1"
    local task_dir="${verify_file%/verify.json}"
    artifact_pick verify "$task_dir" summary
}

resolve_merge_gate_state() {
    local task_dir="$1"
    local status merge_gate_state review_required test_required review_level rstate vstate quality_gate_mode
    status=$(get_task_status "$task_dir")
    merge_gate_state=$(task_json_pick "$task_dir" merge_gate_state)
    review_required=$(task_json_pick "$task_dir" review_required)
    test_required=$(task_json_pick "$task_dir" test_required)
    review_level=$(task_json_pick "$task_dir" review_level)
    quality_gate_mode=$(task_quality_gate_mode "$task_dir")
    rstate=$(review_state "$task_dir" "$review_level")
    vstate=$(verify_state "$task_dir/verify.json")

    if [ "$status" = "done" ]; then
        echo "closed"
        return 0
    fi
    case "$status" in
        cancelled|failed|timeout|archived)
            echo "${merge_gate_state:-$status}"
            return 0
            ;;
    esac
    if [ "$status" = "blocked" ]; then
        if [ "$vstate" = "fail" ]; then
            echo "qa_failed"
        elif [ "$rstate" = "fail" ]; then
            echo "review_rejected"
        else
            echo "${merge_gate_state:-blocked}"
        fi
        return 0
    fi
    if [ "$status" != "ready_for_merge" ]; then
        echo "${merge_gate_state:-}"
        return 0
    fi

    if [ "$vstate" = "fail" ]; then
        echo "qa_failed"
    elif [ "$rstate" = "fail" ]; then
        echo "review_rejected"
    elif [ "$quality_gate_mode" = "parallel" ] && { [ "$review_required" = "True" ] || [ "$review_required" = "true" ] || [ "$review_required" = "1" ]; } && { [ "$test_required" = "True" ] || [ "$test_required" = "true" ] || [ "$test_required" = "1" ]; }; then
        if [ "$rstate" = "pass" ] && [ "$vstate" = "pass" ]; then
            echo "pm_acceptance_pending"
        else
            echo "quality_pending"
        fi
    elif { [ "$test_required" = "True" ] || [ "$test_required" = "true" ] || [ "$test_required" = "1" ]; } && { [ "$review_required" != "True" ] && [ "$review_required" != "true" ] && [ "$review_required" != "1" ] || [ "$rstate" = "pass" ]; }; then
        if [ "$vstate" = "pass" ]; then
            echo "pm_acceptance_pending"
        else
            echo "qa_pending"
        fi
    elif { [ "$review_required" = "True" ] || [ "$review_required" = "true" ] || [ "$review_required" = "1" ]; } && [ "$rstate" != "pass" ]; then
        echo "review_pending"
    elif { [ "$test_required" != "True" ] && [ "$test_required" != "true" ] && [ "$test_required" != "1" ]; } && { [ "$review_required" != "True" ] && [ "$review_required" != "true" ] && [ "$review_required" != "1" ] || [ "$rstate" = "pass" ]; }; then
        echo "pm_acceptance_pending"
    else
        echo "${merge_gate_state:-}"
    fi
}

list_review_agents() {
    agent_config_value list-review-agent-ids || true
}

list_qa_agents() {
    agent_config_value list-qa-agent-ids || true
}

queue_state_file() {
    local queue_kind="$1"
    local agent_id="$2"
    printf '%s/%s-queue-%s.json\n' "$STATE_DIR" "$queue_kind" "$agent_id"
}

queue_state_current_task() {
    local queue_kind="$1"
    local agent_id="$2"
    local task_id=""
    task_id=$(python3 - "$(queue_state_file "$queue_kind" "$agent_id")" "$TASKS_ROOT" "$queue_kind" <<'PY'
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
allowed_gates = {'review_pending'} if queue_kind == 'review' else {'qa_pending'}
quality_gate_mode = str(task.get('quality_gate_mode') or '').strip().lower()
if quality_gate_mode == 'parallel':
    allowed_gates.add('quality_pending')
if status != 'ready_for_merge' or gate not in allowed_gates:
    state_path.unlink(missing_ok=True)
    raise SystemExit(1)
print(task_id)
PY
) || return 1

    [ -n "$task_id" ] || return 1
    if [ "$queue_kind" = "review" ]; then
        local review_level state
        review_level=$(task_json_pick "$TASKS_ROOT/$task_id" review_level)
        state=$(review_state "$TASKS_ROOT/$task_id" "$review_level")
        case "$state" in
            invalid|pass|fail)
                queue_state_clear_for_task "review" "$agent_id" "$task_id"
                return 1
                ;;
        esac
    else
        local vstate
        vstate=$(verify_state "$TASKS_ROOT/$task_id/verify.json")
        case "$vstate" in
            invalid|pass|fail)
                queue_state_clear_for_task "qa" "$agent_id" "$task_id"
                return 1
                ;;
        esac
    fi
    echo "$task_id"
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

queue_state_clear_for_task() {
    local queue_kind="$1"
    local agent_id="$2"
    local task_id="$3"
    python3 - "$(queue_state_file "$queue_kind" "$agent_id")" "$task_id" <<'PY'
import json
import sys
from pathlib import Path

state_path = Path(sys.argv[1])
expected_task_id = sys.argv[2]
if not state_path.exists():
    raise SystemExit(0)
try:
    payload = json.loads(state_path.read_text(encoding='utf-8'))
except Exception:
    state_path.unlink(missing_ok=True)
    raise SystemExit(0)
if str(payload.get('task_id') or '').strip() == expected_task_id:
    state_path.unlink(missing_ok=True)
PY
}

clear_review_queue_state_for_task() {
    local task_dir="$1"
    local task_id
    task_id="$(basename "$task_dir")"
    while IFS= read -r reviewer; do
        [ -n "$reviewer" ] || continue
        queue_state_clear_for_task "review" "$reviewer" "$task_id"
    done <<< "$(task_reviewers "$task_dir")"
    rm -f "$STATE_DIR/${task_id}_review_queue_waiting_notice" "$STATE_DIR/${task_id}_review_queue_waiting_notice.retry"
}

clear_qa_queue_state() {
    while IFS= read -r qa_agent; do
        [ -n "$qa_agent" ] || continue
        queue_state_clear "qa" "$qa_agent"
    done <<< "$(list_qa_agents)"
}

clear_qa_queue_state_for_task() {
    local task_id="$1"
    while IFS= read -r qa_agent; do
        [ -n "$qa_agent" ] || continue
        queue_state_clear_for_task "qa" "$qa_agent" "$task_id"
    done <<< "$(list_qa_agents)"
    rm -f "$STATE_DIR/${task_id}_qa_queue_waiting_notice" "$STATE_DIR/${task_id}_qa_queue_waiting_notice.retry"
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
    gate = str(task.get('merge_gate_state') or '')
    quality_gate_mode = str(task.get('quality_gate_mode') or '').strip().lower()
    allowed_gates = {'review_pending'}
    if quality_gate_mode == 'parallel':
        allowed_gates.add('quality_pending')
    if gate not in allowed_gates:
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
    gate = str(task.get('merge_gate_state') or '')
    quality_gate_mode = str(task.get('quality_gate_mode') or '').strip().lower()
    allowed_gates = {'qa_pending'}
    if quality_gate_mode == 'parallel':
        allowed_gates.add('quality_pending')
    if gate not in allowed_gates:
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
import os
import sys
import tempfile
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

if old_status == 'pooled':
    task['pre_claim_assigned_agent'] = task.get('pre_claim_assigned_agent') or task.get('assigned_agent')
task['assigned_agent'] = assigned_agent
task['status'] = 'dispatched'
task['updated_at'] = now
task['lease_owner'] = task.get('owner_pm')
task['lease_acquired_at'] = now
task['lease_expires_at'] = now
if claimed_by:
    task['claimed_by'] = claimed_by
    task['reserved_by'] = claimed_by
if claimed_at:
    task['claimed_at'] = claimed_at
    task['reserved_at'] = claimed_at
if claim_reason:
    task['claim_reason'] = claim_reason
    task['reserved_reason'] = claim_reason
if task.get('depends_on') and not task.get('dependencies_ready_at'):
    task['dependencies_ready_at'] = now
task['pool_entered_at'] = task.get('pool_entered_at')
task['dispatch_delivery_attempt_count'] = 0
task['dispatch_delivery_retry_count'] = 0
task['dispatch_delivery_consecutive_failures'] = 0
task['last_delivery_attempt_at'] = None
task['last_delivery_error'] = None
task['last_delivery_state'] = None
task['session_health'] = None
if str(task.get('control_plane_state') or '') not in {'reassigned', 'auto_requeue'}:
    task['control_plane_state'] = None
task['control_plane_updated_at'] = now

with tempfile.NamedTemporaryFile('w', delete=False, dir=str(task_path.parent), encoding='utf-8') as tmp:
    json.dump(task, tmp, ensure_ascii=False, indent=2)
    tmp.write('\n')
tmp_path = Path(tmp.name)
os.replace(tmp_path, task_path)
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
    local integration_owner workspace_payload workspace_hint

    [ "$ARCH_AUTO_DISPATCH" = "1" ] || return 1
    integration_owner="${INTEGRATION_OWNER_AGENT_ID:-}"
    [ -n "$integration_owner" ] || integration_owner="$(agent_config_value integration-owner || true)"
    [ -n "$integration_owner" ] || return 1
    [ "$assigned_agent" = "$integration_owner" ] || return 1
    case "$task_level" in
        domain|epic) ;;
        *) return 1 ;;
    esac

    if ! dependencies_ready "$task_dir" >/dev/null 2>&1; then
        return 1
    fi

    dispatch_task_to_agent "$task_dir" "$integration_owner" "watcher auto dispatch domain/epic task to $integration_owner"
    workspace_payload=$(prepare_task_workspace_payload "$task_dir")
    workspace_hint=$(workspace_hint_from_payload "$workspace_payload")
    deliver_execution_instruction_and_record "$task_dir" "$task_id" "$integration_owner" "请读取 ${TASKS_ROOT}/${task_id}/instruction.md 并开始执行任务。该任务由 task-watcher 自动派发，用于支持多 domain/epic 并行处理。${workspace_hint:+ ${workspace_hint}} 完成后写 ack.json 和 result.json。" || true
    sync_task_board "$task_dir" "auto-dispatch-arch"
    log "$task_id: 自动派发给 $integration_owner（domain/epic 并行）"
    return 0
}

auto_claim_pending_dev() {
    local task_dir="$1"
    local task_id="$2"
    local assigned_agent="$3"
    local task_level="$4"
    local workspace_payload workspace_hint

    [ "$DEV_AUTO_CLAIM" = "1" ] || return 1
    [ "$task_level" = "execution" ] || return 1

    if ! dependencies_ready "$task_dir" >/dev/null 2>&1; then
        return 1
    fi

    local target_agent=""
    if matches_auto_assign_marker "$assigned_agent"; then
        target_agent=$(select_idle_dev_agent 2>/dev/null || true)
    elif is_development_agent "$assigned_agent" && is_idle_agent "$assigned_agent"; then
        target_agent="$assigned_agent"
    fi

    [ -n "$target_agent" ] || return 1

    dispatch_task_to_agent "$task_dir" "$target_agent" "watcher auto-claimed pending execution task"
    workspace_payload=$(prepare_task_workspace_payload "$task_dir")
    workspace_hint=$(workspace_hint_from_payload "$workspace_payload")
    deliver_execution_instruction_and_record "$task_dir" "$task_id" "$target_agent" "请读取 ${task_dir}/instruction.md 并开始执行任务。该任务由 task-watcher 在你空闲时自动认领/派发。${workspace_hint:+ ${workspace_hint}} 完成后写 ack.json 和 result.json。" || true
    sync_task_board "$task_dir" "auto-claim-dev"
    log "$task_id: 自动认领并派发给 $target_agent"
    return 0
}

auto_pool_pending_task_if_needed() {
    local task_dir="$1"
    local task_id="$2"
    [ "$(task_pool_bool enabled true 2>/dev/null || echo 1)" = "1" ] || return 1
    [ "$(get_task_status "$task_dir")" = "pending" ] || return 1

    local output rc
    output=$(python3 - "$task_dir" "$task_id" "$CONFIG_PATH" "$WORKSPACE_ROOT" "$AUTO_ASSIGN_MARKERS" <<'PY_POOL_PENDING' 2>&1
import json
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(sys.argv[4]).resolve() / 'scripts' / 'lib'))
from agent_config import default_claim_scope  # type: ignore
from task_pool_rules import pool_gate_blockers  # type: ignore


def int_value(value, default):
    try:
        if value in (None, ''):
            return default
        return int(value)
    except Exception:
        return default


task_dir = Path(sys.argv[1])
task_id = sys.argv[2]
config_path = Path(sys.argv[3])
workspace_root = Path(sys.argv[4])
auto_markers = {item.strip().lower() for item in sys.argv[5].split(',') if item.strip()}

task_path = task_dir / 'task.json'
task = json.loads(task_path.read_text(encoding='utf-8'))
config = json.loads(config_path.read_text(encoding='utf-8'))
if str(task.get('status') or '') != 'pending':
    raise SystemExit(1)
assigned_agent = str(task.get('assigned_agent') or '').strip()
claim_policy = str(task.get('claim_policy') or '').strip().lower()
if claim_policy != 'pull' and assigned_agent.lower() not in auto_markers:
    raise SystemExit(1)

pool_config = config.get('task_pool') or {}
now = datetime.now().astimezone().isoformat(timespec='seconds')
previous = str(task.get('status') or 'pending')
original_assigned = assigned_agent

if assigned_agent.lower() not in auto_markers:
    task['pre_pool_assigned_agent'] = task.get('pre_pool_assigned_agent') or assigned_agent
task['assigned_agent'] = 'auto'
claim_scope = task.get('claim_scope') if isinstance(task.get('claim_scope'), list) else []
claim_scope = [str(item).strip() for item in claim_scope if str(item).strip()]
if not claim_scope:
    claim_scope = default_claim_scope(task, config)
task['claim_scope'] = claim_scope
task['claim_policy'] = 'pull'
task['claim_max_concurrency'] = int_value(task.get('claim_max_concurrency'), int_value(pool_config.get('default_claim_max_concurrency'), 1))
task['dependency_policy'] = str(task.get('dependency_policy') or 'done_only')
task['pool_timeout_minutes'] = int_value(task.get('pool_timeout_minutes'), int_value(pool_config.get('default_pool_timeout_minutes'), 120))
blockers = pool_gate_blockers(task, task_dir)
if not claim_scope:
    blockers.append('claim_scope_missing')
if blockers:
    print(json.dumps({'task_id': task_id, 'pooled': False, 'blockers': sorted(set(blockers))}, ensure_ascii=False))
    raise SystemExit(2)

task['pool_entered_at'] = task.get('pool_entered_at') or now
task['claimed_by'] = None
task['claimed_at'] = None
task['claim_reason'] = None
task['status'] = 'pooled'
task['updated_at'] = now
with tempfile.NamedTemporaryFile('w', delete=False, dir=str(task_dir), encoding='utf-8') as tmp:
    json.dump(task, tmp, ensure_ascii=False, indent=2)
    tmp.write('\n')
tmp_path = Path(tmp.name)
os.replace(tmp_path, task_path)
with (task_dir / 'transitions.jsonl').open('a', encoding='utf-8') as fp:
    fp.write(json.dumps({
        'from': previous,
        'to': 'pooled',
        'at': now,
        'reason': 'watcher auto queued pending pull/auto task into claim pool',
        'original_assigned_agent': original_assigned or None,
    }, ensure_ascii=False) + '\n')
print(json.dumps({'task_id': task_id, 'pooled': True, 'claim_scope': claim_scope}, ensure_ascii=False))
PY_POOL_PENDING
)
    rc=$?
    if [ "$rc" -eq 0 ]; then
        log "$task_id: pending pull/auto 任务已自动入池"
        emit_system_chat_event watcher "$task_id" "pending pull/auto 任务已由 watcher 自动进入 pooled，等待认领/自动续推。" "$PM_AGENT_ID" info task-pool >/dev/null 2>&1 || true
        sync_task_board "$task_dir" "auto-pool-pending"
        return 0
    fi
    if [ "$rc" -eq 2 ]; then
        log "$task_id: pending pull/auto 自动入池被 Pool Gate 阻塞：$(truncate_utf8 "$output" 240)"
        return 1
    fi
    return 1
}

pending_push_candidate_for_agent() {
    local agent_id="$1"
    python3 - "$TASKS_ROOT" "$CONFIG_PATH" "$agent_id" "$AUTO_ASSIGN_MARKERS" <<'PY_PENDING_PUSH'
import json
import sys
from datetime import datetime
from pathlib import Path

tasks_root = Path(sys.argv[1])
agent_id = sys.argv[3]
auto_markers = {item.strip().lower() for item in sys.argv[4].split(',') if item.strip()}
priority_rank = {'critical': 4, 'urgent': 4, 'high': 3, 'medium': 2, 'low': 1}
allowed_done = {'done', 'cancelled'}

def deps_ready(task):
    policy = str(task.get('dependency_policy') or 'done_only').strip().lower()
    allowed = set(allowed_done)
    if policy == 'ready_for_merge_ok':
        allowed.add('ready_for_merge')
    for dep in task.get('depends_on') or []:
        dep_path = tasks_root / dep / 'task.json'
        if not dep_path.exists():
            return False
        try:
            dep_task = json.loads(dep_path.read_text(encoding='utf-8'))
        except Exception:
            return False
        if str(dep_task.get('status') or '') not in allowed:
            return False
    return True

rows = []
for task_path in tasks_root.glob('*/task.json'):
    try:
        task = json.loads(task_path.read_text(encoding='utf-8'))
    except Exception:
        continue
    if str(task.get('status') or '') != 'pending':
        continue
    assigned = str(task.get('assigned_agent') or '').strip()
    if assigned != agent_id:
        continue
    if assigned.lower() in auto_markers:
        continue
    if str(task.get('claim_policy') or '').strip().lower() == 'pull':
        continue
    if not deps_ready(task):
        continue
    queued_at = str(task.get('created_at') or task.get('updated_at') or '')
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
    break
PY_PENDING_PUSH
}

auto_dispatch_next_pending_push_for_agent() {
    local agent_id="$1"
    local trigger_task_id="${2:-}"
    [ -n "$agent_id" ] || return 1
    [ "$(task_pool_bool auto_dispatch_pending_push true 2>/dev/null || echo 1)" = "1" ] || return 1
    matches_auto_assign_marker "$agent_id" && return 1

    local active_count
    active_count=$(active_task_count_for_agent "$agent_id" 2>/dev/null || echo 0)
    [ "${active_count:-0}" -eq 0 ] || return 1

    local next_task task_dir output rc
    next_task=$(pending_push_candidate_for_agent "$agent_id" 2>/dev/null || true)
    [ -n "$next_task" ] || return 1
    task_dir="$TASKS_ROOT/$next_task"
    [ -x "$DISPATCH_TASK_SCRIPT" ] || return 1

    rc=0
    output=$(TASKS_ROOT="$TASKS_ROOT" CONFIG_PATH="$CONFIG_PATH" WORKSPACE_ROOT="$WORKSPACE_ROOT" SEND_SCRIPT="$SEND_SCRIPT" SEND_CHAT_SCRIPT="$SEND_CHAT_SCRIPT" ENSURE_TASK_WORKSPACE_SCRIPT="$ENSURE_TASK_WORKSPACE_PY" "$DISPATCH_TASK_SCRIPT" "$task_dir/task.json" 2>&1) || rc=$?
    if [ "${rc:-0}" -eq 0 ]; then
        sync_task_board "$task_dir" "auto-dispatch-pending-push"
        log "$next_task: pending push 任务已在 ${trigger_task_id:-idle sweep} 后自动派发给 $agent_id"
        return 0
    fi

    log "$next_task: pending push 自动派发失败（agent=$agent_id）：$(truncate_utf8 "$output" 240)"
    return 1
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
    local claim_payload workspace_hint claim_agent
    if ! claim_payload=$(confirm_claim_request "$task_dir" "$task_id" 2>/dev/null); then
        local rc=$?
        [ "$rc" -eq 2 ] && return 0
        return 1
    fi

    claim_agent=$(python3 -c 'import json,sys; print((json.load(sys.stdin).get("agent") or "").strip())' <<< "$claim_payload" 2>/dev/null || true)
    workspace_hint=$(workspace_hint_from_payload "$claim_payload")
    [ -n "$claim_agent" ] || return 1

    deliver_execution_instruction_and_record "$task_dir" "$task_id" "$claim_agent" "你认领的任务 ${task_id} 已进入 dispatched。请读取 ${task_dir}/instruction.md 并继续执行。${workspace_hint:+ ${workspace_hint}} 完成后写 ack.json 和 result.json。" || true
    emit_system_chat_event dispatch "$task_id" "任务已被 ${claim_agent} 认领并进入 dispatched。" "$claim_agent" info dispatch
    notify_pm "[task-watcher] $task_id 已被 ${claim_agent} 认领，进入 dispatched。"
    sync_task_board "$task_dir" "claim-confirmed"
    log "$task_id: 已确认 ${claim_agent} 的 claim.json，进入 dispatched"
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

notify_pooled_timeout_if_needed() {
    local task_dir="$1"
    local task_id="$2"
    local status="$3"
    [ "$status" = "pooled" ] || return 1
    local timeout_minutes entered_at entered_epoch now timeout_key
    timeout_minutes=$(task_json_pick "$task_dir" pool_timeout_minutes)
    entered_at=$(task_json_pick "$task_dir" pool_entered_at)
    [ -n "$timeout_minutes" ] || return 1
    [ -n "$entered_at" ] || return 1
    entered_epoch=$(python3 - <<'PY' "$entered_at"
import sys
from datetime import datetime
try:
    print(int(datetime.fromisoformat(sys.argv[1].replace('Z', '+00:00')).timestamp()))
except Exception:
    print(0)
PY
)
    [ "${entered_epoch:-0}" -gt 0 ] || return 1
    now=$(date +%s)
    [ $(( now - entered_epoch )) -gt $(( timeout_minutes * 60 )) ] || return 1
    timeout_key="${task_id}_pool_timeout_notice"
    timeout_push_key="${task_id}_pool_timeout_push"
    if ! is_notified "$timeout_key" || ! is_notified "$timeout_push_key"; then
        if ! is_notified "$timeout_key"; then
            notify_pm "[task-watcher] $task_id 在任务池中等待已超 ${timeout_minutes} 分钟，请判断转派、拆分或提优先级。"
            emit_system_chat_event watcher "$task_id" "pooled 超时，建议 PM 转派/拆小/提高优先级。" "$PM_AGENT_ID" degraded notify
            mark_notified "$timeout_key"
        fi
        push_task_event_with_retry "$timeout_push_key" "$task_dir/task.json" "【任务池超时】" "$task_id" "任务在 pooled 中等待超过 ${timeout_minutes} 分钟" "请 PM 判断转派、拆小或提高优先级" || true
    fi
    return 0
}

record_dependencies_ready_if_needed() {
    local task_dir="$1"
    local task_id="$2"
    [ "$(get_task_status "$task_dir")" = "pooled" ] || return 1
    dependencies_ready "$task_dir" >/dev/null 2>&1 || return 1
    python3 - "$task_dir" "$task_id" <<'PY'
import json
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path

task_dir = Path(sys.argv[1])
task_id = sys.argv[2]
task_path = task_dir / 'task.json'
task = json.loads(task_path.read_text(encoding='utf-8'))
if not task.get('depends_on') or task.get('dependencies_ready_at'):
    raise SystemExit(1)
now = datetime.now().astimezone().isoformat(timespec='seconds')
task['dependencies_ready_at'] = now
task['updated_at'] = now
with tempfile.NamedTemporaryFile('w', delete=False, dir=str(task_dir), encoding='utf-8') as tmp:
    json.dump(task, tmp, ensure_ascii=False, indent=2)
    tmp.write('\n')
os.replace(tmp.name, task_path)
with (task_dir / 'transitions.jsonl').open('a', encoding='utf-8') as fp:
    fp.write(json.dumps({
        'from': 'pooled',
        'to': 'pooled',
        'at': now,
        'event': 'dependencies_ready',
        'reason': 'watcher observed all dependencies ready',
    }, ensure_ascii=False) + '\n')
print(task_id)
PY
}

return_reserved_to_pool_if_timed_out() {
    local task_dir="$1"
    local task_id="$2"
    [ "$(task_pool_bool auto_return_reserved_on_ack_timeout true 2>/dev/null || echo 1)" = "1" ] || return 1
    [ "$(get_task_status "$task_dir")" = "dispatched" ] || return 1
    [ ! -f "$task_dir/ack.json" ] || return 1

    local timeout_seconds dispatch_time now
    timeout_seconds=$(task_pool_int reserved_ack_timeout_seconds "$DISPATCH_RESEND_AFTER_SECONDS" 2>/dev/null || echo "$DISPATCH_RESEND_AFTER_SECONDS")
    dispatch_time=$(task_dispatch_reference_epoch "$task_dir")
    [ -n "$dispatch_time" ] && [ "$dispatch_time" -gt 0 ] || return 1
    now=$(date +%s)
    [ $(( now - dispatch_time )) -gt "${timeout_seconds:-300}" ] || return 1

    python3 - "$task_dir" "$task_id" <<'PY'
import json
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path

task_dir = Path(sys.argv[1])
task_id = sys.argv[2]
task_path = task_dir / 'task.json'
task = json.loads(task_path.read_text(encoding='utf-8'))
if str(task.get('status') or '') != 'dispatched':
    raise SystemExit(1)
if not (task.get('reserved_by') or task.get('claimed_by')):
    raise SystemExit(1)
if not task.get('pool_entered_at'):
    raise SystemExit(1)

now = datetime.now().astimezone().isoformat(timespec='seconds')
previous_agent = task.get('assigned_agent')
task['last_reserved_by'] = task.get('reserved_by') or task.get('claimed_by')
task['last_reserved_at'] = task.get('reserved_at') or task.get('claimed_at')
task['last_reserved_timeout_at'] = now
task['assigned_agent'] = task.get('pre_claim_assigned_agent') or 'auto'
task['status'] = 'pooled'
task['updated_at'] = now
for key in (
    'claimed_by',
    'claimed_at',
    'claim_reason',
    'reserved_by',
    'reserved_at',
    'reserved_reason',
    'lease_acquired_at',
    'lease_expires_at',
):
    task.pop(key, None)
with tempfile.NamedTemporaryFile('w', delete=False, dir=str(task_dir), encoding='utf-8') as tmp:
    json.dump(task, tmp, ensure_ascii=False, indent=2)
    tmp.write('\n')
os.replace(tmp.name, task_path)
claim_path = task_dir / 'claim.json'
if claim_path.exists():
    claim_path.rename(task_dir / f'claim.expired.{now.replace(":", "").replace("+", "_")}.json')
with (task_dir / 'transitions.jsonl').open('a', encoding='utf-8') as fp:
    fp.write(json.dumps({
        'from': 'dispatched',
        'to': 'pooled',
        'at': now,
        'reason': f'reserved task timed out without ack; returned to pool from {previous_agent}',
    }, ensure_ascii=False) + '\n')
print(previous_agent or '')
PY
}

reassign_dispatched_task() {
    local task_dir="$1"
    local task_id="$2"
    local previous_agent="$3"
    local next_agent="$4"
    local reason="$5"
    local workspace_payload workspace_hint
    [ -x "$REASSIGN_TASK_SCRIPT" ] || return 1

    if "$REASSIGN_TASK_SCRIPT" --task-dir "$task_dir" --agent "$next_agent" --reason "$reason" >/dev/null 2>&1; then
        workspace_payload=$(prepare_task_workspace_payload "$task_dir")
        workspace_hint=$(workspace_hint_from_payload "$workspace_payload")
        deliver_execution_instruction_and_record "$task_dir" "$task_id" "$next_agent" "你已接手任务 ${task_id}。请读取 ${task_dir}/instruction.md，并在确认后写 ack.json 开始执行。${workspace_hint:+ ${workspace_hint}}" || true
        notify_pm "[task-watcher] $task_id 因连接/会话恢复已从 ${previous_agent} 转派给 ${next_agent}。"
        emit_system_chat_event watcher "$task_id" "控制面恢复：已从 ${previous_agent} 转派给 ${next_agent}。" "$PM_AGENT_ID" degraded notify
        sync_task_board "$task_dir" "control-plane-reassign"
        log "$task_id: 控制面恢复后已从 ${previous_agent} 转派给 ${next_agent}"
        return 0
    fi
    log "$task_id: reassign-task.sh 执行失败，无法从 ${previous_agent} 转派到 ${next_agent}"
    return 1
}

requeue_dispatched_task_to_pool() {
    local task_dir="$1"
    local task_id="$2"
    local reason="$3"
    python3 - "$task_dir" "$task_id" "$reason" <<'PY'
import json
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path

task_dir = Path(sys.argv[1])
task_id = sys.argv[2]
reason = sys.argv[3].strip()
task_path = task_dir / 'task.json'
task = json.loads(task_path.read_text(encoding='utf-8'))
if str(task.get('status') or '') != 'dispatched':
    raise SystemExit(1)

now = datetime.now().astimezone().isoformat(timespec='seconds')
previous_agent = str(task.get('assigned_agent') or '')
task['last_connection_failed_agent'] = previous_agent
task['last_auto_requeue_at'] = now
task['last_auto_requeue_reason'] = reason
task['auto_requeue_count'] = int(task.get('auto_requeue_count') or 0) + 1
task['assigned_agent'] = task.get('pre_claim_assigned_agent') or 'auto'
task['status'] = 'pooled'
task['updated_at'] = now
task['dispatch_delivery_attempt_count'] = 0
task['dispatch_delivery_retry_count'] = 0
task['dispatch_delivery_consecutive_failures'] = 0
task['last_delivery_state'] = 'auto_requeue'
task['last_delivery_error'] = reason or task.get('last_delivery_error')
task['last_delivery_attempt_at'] = now
task['session_health'] = None
task['control_plane_state'] = 'auto_requeue'
task['control_plane_updated_at'] = now
for key in (
    'claimed_by',
    'claimed_at',
    'claim_reason',
    'reserved_by',
    'reserved_at',
    'reserved_reason',
    'lease_acquired_at',
    'lease_expires_at',
):
    task.pop(key, None)

with tempfile.NamedTemporaryFile('w', delete=False, dir=str(task_dir), encoding='utf-8') as tmp:
    json.dump(task, tmp, ensure_ascii=False, indent=2)
    tmp.write('\n')
os.replace(tmp.name, task_path)

claim_path = task_dir / 'claim.json'
if claim_path.exists():
    claim_path.rename(task_dir / f'claim.requeued.{now.replace(":", "").replace("+", "_")}.json')

with (task_dir / 'transitions.jsonl').open('a', encoding='utf-8') as fp:
    fp.write(json.dumps({
        'from': 'dispatched',
        'to': 'pooled',
        'at': now,
        'reason': f'watcher auto requeue after control-plane recovery failure: {reason}',
    }, ensure_ascii=False) + '\n')

print(previous_agent)
PY
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
        emit_system_chat_event_once "${task_id}_review_queue_waiting_notice" watcher "$task_id" "任务已进入 review 队列，等待 reviewer 空闲后自动续推。" "$PM_AGENT_ID" info notify
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
        emit_system_chat_event_once "${task_id}_qa_queue_waiting_notice" watcher "$task_id" "任务已进入 QA 队列，等待 QA 空闲后自动续推。" "$PM_AGENT_ID" info notify
    fi
}

auto_close_review_only_task() {
    local task_dir="$1"
    local task_id="$2"
    local result_summary task_type result_status result_outcome
    task_type=$(task_json_pick "$task_dir" task_type)
    result_status=$(artifact_pick result "$task_dir" normalized_status 2>/dev/null || true)
    result_outcome=$(artifact_pick result "$task_dir" outcome_status 2>/dev/null || true)
    if [ "$task_type" = "verification" ] && { [ "$result_status" = "failed" ] || [ "$result_status" = "blocked" ] || [ "$result_outcome" = "fail" ] || [ "$result_outcome" = "blocked" ]; }; then
        log "$task_id: 复验结论为负，禁止自动收口"
        return 2
    fi
    result_summary=$(json_pick "$task_dir/result.json" summary)
    if [ -z "$result_summary" ]; then
        result_summary="${task_id} 审查已通过并自动收口。"
    else
        result_summary="${result_summary}（审查通过自动收口，无 QA）"
    fi
    if "$CLOSE_TASK_SCRIPT" --task-dir "$task_dir" --summary "$result_summary" --reason "task-watcher auto close after review pass without qa" >/dev/null 2>&1; then
        log "$task_id: 审查通过且无需 QA，已自动收口"
        notify_pm "[task-watcher] $task_id 审查已通过且无需 QA，已自动收口。"
        emit_system_chat_event watcher "$task_id" "审查通过且无需 QA，已自动收口。" "$PM_AGENT_ID" info notify
        return 0
    fi
    log "$task_id: 审查通过自动收口失败"
    return 1
}

notify_final_done_if_needed() {
    local task_dir="$1"
    local task_id="$2"
    local done_key="${task_id}_done_notice"
    local done_push_key="${task_id}_done_push"

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

    local result_summary task_type execution_mode target_environment downstream_action done_signature
    done_signature="${task_id}:done:${done_transition_epoch}"
    result_summary=$(task_json_pick "$task_dir" result_summary)
    [ -n "$result_summary" ] || result_summary=$(json_pick "$task_dir/result.json" summary)
    [ -n "$result_summary" ] || result_summary="${task_id} 已进入 done 终态。"
    task_type=$(task_json_pick "$task_dir" task_type)
    execution_mode=$(task_json_pick "$task_dir" execution_mode)
    target_environment=$(task_json_pick "$task_dir" target_environment)
    downstream_action=$(task_json_pick "$task_dir" downstream_action)

    if [ "$task_type" = "deployment" ] || [ "$execution_mode" = "deploy" ] || [ "$target_environment" = "prod" ]; then
        push_task_event_with_signature_retry "$done_push_key" "$done_signature" "【部署完成】" "$task_id" "$(truncate_utf8 "$result_summary" 300)" "请关注生产验证结果与后续用户反馈" || {
            log "$task_id: 最终完成飞书推送失败，等待 cooldown 后自动补推"
            return 1
        }
    else
        push_task_event_with_signature_retry "$done_push_key" "$done_signature" "【任务完成】" "$task_id" "$(truncate_utf8 "$result_summary" 300)" "${downstream_action:-生命周期已结束}" || {
            log "$task_id: 最终完成飞书推送失败，等待 cooldown 后自动补推"
            return 1
        }
    fi
    emit_system_chat_event watcher "$task_id" "任务已进入 done 终态，已发送最终完成通知。" "$PM_AGENT_ID" info notify
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
        emit_system_chat_event watcher "$task_id" "QA 已通过并自动收口。" "$PM_AGENT_ID" info notify
        return 0
    fi
    log "$task_id: close-task.sh 执行失败，未自动收口"
    return 1
}

run_task_watcher_loop() {
    local restart_cause
    restart_cause=$(cat "$RESTART_CAUSE_FILE" 2>/dev/null || true)
    if [ -n "$restart_cause" ]; then
        log "检测到 watchdog 重启原因: $restart_cause"
    fi

    write_heartbeat "startup"
    log "task-watcher 启动，间隔 ${INTERVAL}s"

    loop_count=0
    while true; do
    loop_count=$((loop_count + 1))
    write_heartbeat "running"
    [ -d "$TASKS_ROOT" ] || { sleep "$INTERVAL"; continue; }
    task_scan_count=0
    terminal_scan_enabled=0
    if [ $(( loop_count % TERMINAL_SWEEP_EVERY_LOOPS )) -eq 0 ]; then
        terminal_scan_enabled=1
    fi

    for task_dir in "$TASKS_ROOT"/*/; do
        [ -d "$task_dir" ] || continue
        task_id=$(basename "$task_dir")
        case "$task_id" in
            _* ) continue ;;
        esac
        [ -f "$task_dir/task.json" ] || continue
        task_scan_count=$((task_scan_count + 1))
        if [ $(( task_scan_count % HEARTBEAT_EVERY_TASKS )) -eq 0 ]; then
            write_heartbeat "running:${task_id}"
        fi

        current_status=$(get_task_status "$task_dir")
        if normalize_legacy_task_status "$task_dir" "$current_status" >/dev/null 2>&1; then
            current_status=$(get_task_status "$task_dir")
        fi
        invariant_report=$(reconcile_task_state_invariants "$task_dir" "$task_id" 2>/dev/null || echo '{}')
        invariant_parse_error=$(python3 -c 'import json,sys; print("1" if json.load(sys.stdin).get("parse_error") else "0")' <<< "$invariant_report" 2>/dev/null || echo 0)
        invariant_notify=$(python3 -c 'import json,sys; print("1" if json.load(sys.stdin).get("notify") else "0")' <<< "$invariant_report" 2>/dev/null || echo 0)
        invariant_count=$(python3 -c 'import json,sys; print(int(json.load(sys.stdin).get("count") or 0))' <<< "$invariant_report" 2>/dev/null || echo 0)
        if [ "${invariant_parse_error:-0}" = "1" ]; then
            log "$task_id: state invariant report parse failed; preserved prior invariant state"
        elif [ "${invariant_notify:-0}" = "1" ] && [ "${invariant_count:-0}" -gt 0 ]; then
            invariant_summary=$(python3 -c 'import json,sys; payload=json.load(sys.stdin); print("；".join([item for item in payload.get("messages") or [] if item][:2]))' <<< "$invariant_report" 2>/dev/null || echo "")
            notify_pm "[task-watcher] $task_id 检测到状态一致性异常：${invariant_summary:-请检查 state_invariant_violations。}"
            emit_system_chat_event watcher "$task_id" "状态一致性异常：${invariant_summary:-请检查 state_invariant_violations。}" "$PM_AGENT_ID" degraded notify
        fi

        # 已关闭任务不再触发自动流转，但仍需在文件变更后同步到任务看板 SQLite
        case "$current_status" in
            done|cancelled|archived)
                [ "$terminal_scan_enabled" = "1" ] || continue
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
                auto_pool_pending_task_if_needed "$task_dir" "$task_id" || true
            else
                auto_dispatch_pending_arch "$task_dir" "$task_id" "$assigned_agent" "$task_level" || true
            fi
            current_status=$(get_task_status "$task_dir")
        fi

        if [ "$current_status" = "pooled" ]; then
            process_claim_json "$task_dir" "$task_id" || true
            current_status=$(get_task_status "$task_dir")
            if [ "$current_status" = "pooled" ]; then
                record_dependencies_ready_if_needed "$task_dir" "$task_id" >/dev/null 2>&1 || true
                nudge_pooled_task "$task_dir" "$task_id" "$current_status" || true
                notify_pooled_timeout_if_needed "$task_dir" "$task_id" "$current_status" || true
            fi
        fi

        if [ "$current_status" = "ready_for_merge" ] || [ "$current_status" = "blocked" ]; then
            _gate_err_file=$(mktemp "${STATE_DIR}/gate_err.XXXXXX" 2>/dev/null || mktemp)
            inferred_gate_state=$(resolve_merge_gate_state "$task_dir" 2>"$_gate_err_file" || true)
            if [ -s "$_gate_err_file" ]; then
                log "$(basename "$task_dir"): gate 归一化异常 - $(head -c 500 "$_gate_err_file")"
            fi
            rm -f "$_gate_err_file"
            current_gate_state=$(task_json_pick "$task_dir" merge_gate_state)
            if [ -n "$inferred_gate_state" ] && [ "$inferred_gate_state" != "$current_gate_state" ]; then
                now_iso=$(now_iso)
                set_task_gate_state "$task_dir" "" "watcher normalized merge gate state" "$inferred_gate_state" "__KEEP__" "__KEEP__" "$now_iso"
                current_status=$(get_task_status "$task_dir")
            fi
        fi

        if [ "$current_status" = "ready_for_merge" ]; then
            reconcile_open_merge_gate "$task_dir" "$task_id" "$current_status" || true
        fi

        # 兜底：dispatched 状态超 3 分钟无 ack 且无明确进展工件/Working 信号 → 重新发送指令
        if [ "$current_status" = "dispatched" ] && [ ! -f "$task_dir/ack.json" ]; then
            if task_delivery_deferred_until_idle "$task_dir"; then
                agent_session=$(task_json_pick "$task_dir" assigned_agent)
                if agent_has_other_working_task "$agent_session" "$task_id" >/dev/null 2>&1; then
                    log "$task_id: 非打断预留投递等待 ${agent_session} 空闲，跳过 ack 超时回池/重发"
                    continue
                fi
                deliver_reserved_task_ready_notice "$task_dir" "$task_id" "$agent_session"
                current_status=$(get_task_status "$task_dir")
                continue
            fi
            if returned_agent=$(return_reserved_to_pool_if_timed_out "$task_dir" "$task_id" 2>/dev/null); then
                notify_pm "[task-watcher] $task_id 预留后超时未 ack，已回退到 pooled。"
                if [ -n "$returned_agent" ]; then
                    emit_system_chat_event watcher "$task_id" "预留任务超时未 ack，已从 ${returned_agent} 回退到 pooled。" "$PM_AGENT_ID" degraded notify
                else
                    emit_system_chat_event watcher "$task_id" "预留任务超时未 ack，已回退到 pooled。" "$PM_AGENT_ID" degraded notify
                fi
                sync_task_board "$task_dir" "reserved-timeout-returned"
                current_status="pooled"
                continue
            fi
            dispatch_time=$(task_dispatch_reference_epoch "$task_dir")
            now=$(date +%s)
            if [ -n "$dispatch_time" ] && [ "$dispatch_time" -gt 0 ] && [ $(( now - dispatch_time )) -gt "$DISPATCH_RESEND_AFTER_SECONDS" ]; then
                resend_key="${task_id}_resend"
                agent_session=$(task_json_pick "$task_dir" assigned_agent)
                if task_has_progress_artifact "$task_dir"; then
                    log "$task_id: dispatched 超时检查跳过，已发现后续工件，优先按显式工件继续流转"
                else
                    session_health=$(session_health_state "$agent_session")
                    if [ "$session_health" = "working_signal" ]; then
                        continue
                    fi
                    last_resend=$(cat "$STATE_DIR/$resend_key" 2>/dev/null)
                    if [ -z "$last_resend" ] || [ $(( now - last_resend )) -gt "$RESEND_COOLDOWN_SECONDS" ]; then
                        instruction="$task_dir/instruction.md"
                        if [ -f "$instruction" ]; then
                            deliver_execution_instruction_and_record "$task_dir" "$task_id" "$agent_session" "请重新读取 ${task_dir}/instruction.md 并继续执行，完成后写 ack.json / result.json。" || true
                            emit_system_chat_event nudge "$task_id" "任务超时未确认，已触发控制面重试。" "${agent_session:-$PM_AGENT_ID}" degraded nudge
                            log "$task_id: dispatched 超过 ${DISPATCH_RESEND_AFTER_SECONDS}s 且无 ack/无 Working，已执行控制面重试"
                            push_task_event "【任务重发】" "$task_id" "超过 ${DISPATCH_RESEND_AFTER_SECONDS}s 未确认，已对 ${agent_session:-unknown} 执行重试" "等待 agent 写入 ack.json"
                            echo "$now" > "$STATE_DIR/$resend_key"
                        fi
                        if dispatch_failure_threshold_exceeded "$task_dir"; then
                            failure_state=$(task_json_pick "$task_dir" last_delivery_state 2>/dev/null || echo "delivery_failed")
                            failure_reason=$(task_json_pick "$task_dir" last_delivery_error 2>/dev/null || echo "")
                            threshold_reason="control-plane recovery reached ${DISPATCH_FAILURE_THRESHOLD} consecutive ${failure_state:-delivery_failed} attempts"
                            [ -n "$failure_reason" ] && threshold_reason="${threshold_reason}: ${failure_reason}"
                            if next_agent=$(select_reassign_candidate "$task_dir" "$agent_session" 2>/dev/null || true) && [ -n "$next_agent" ]; then
                                if reassign_dispatched_task "$task_dir" "$task_id" "$agent_session" "$next_agent" "$threshold_reason"; then
                                    current_status=$(get_task_status "$task_dir")
                                    continue
                                fi
                            fi
                            if previous_agent=$(requeue_dispatched_task_to_pool "$task_dir" "$task_id" "$threshold_reason" 2>/dev/null); then
                                notify_pm "[task-watcher] $task_id 连续 ${DISPATCH_FAILURE_THRESHOLD} 次控制面恢复失败，已从 ${previous_agent:-unknown} 自动回收到 pooled。"
                                emit_system_chat_event watcher "$task_id" "控制面恢复失败，已自动回收到 pooled。" "$PM_AGENT_ID" degraded notify
                                sync_task_board "$task_dir" "control-plane-requeue"
                                current_status="pooled"
                                continue
                            fi
                        fi
                    fi
                fi
            fi
        fi

        # 检测 ack.json → 状态应为 working（恢复后旧 ack 需忽略）
        if [ -f "$task_dir/ack.json" ] && [ "$current_status" = "dispatched" ]; then
            ack_key="${task_id}_ack"
            ack_invalid_key="${task_id}_artifact_invalid_ack"
            ack_stale_key="${task_id}_reopen_with_stale_state_ack"
            ack_agent=$(artifact_pick ack "$task_dir" agent)
            ack_state=$(artifact_pick ack "$task_dir" normalized_status)
            ack_current_round=$(artifact_pick ack "$task_dir" is_current_round)
            ack_errors=$(artifact_pick ack "$task_dir" errors.0)
            if [ "$ack_state" = "invalid" ]; then
                if ! is_notified "$ack_invalid_key"; then
                    notify_pm "[task-watcher] $task_id 的 ack.json 非法，请修正后重试。"
                    emit_system_chat_event watcher "$task_id" "ack.json 非法：${ack_errors:-unknown}" "$PM_AGENT_ID" degraded notify
                    mark_notified "$ack_invalid_key"
                fi
            elif [ "$ack_current_round" = "false" ]; then
                if ! is_notified "$ack_stale_key"; then
                    notify_pm "[task-watcher] $task_id 恢复后仍存在旧 ack.json，请使用 resume-task 或让 agent 重新 ack。"
                    emit_system_chat_event watcher "$task_id" "恢复后检测到旧 ack.json，已忽略当前轮次前的 ack。" "$PM_AGENT_ID" degraded notify
                    mark_notified "$ack_stale_key"
                fi
            else
                assigned_agent_for_ack=$(task_json_pick "$task_dir" assigned_agent)
                [ -n "$assigned_agent_for_ack" ] || assigned_agent_for_ack="$ack_agent"
                _ack_limits=$(agent_capacity_limits "$assigned_agent_for_ack" 2>/dev/null || echo "1 1 2")
                _ack_working_limit=$(echo "$_ack_limits" | awk '{print $1}')
                _ack_working_count=$(working_task_count_for_agent "$assigned_agent_for_ack" 2>/dev/null || echo 0)
                if [ "${_ack_working_count:-0}" -ge "${_ack_working_limit:-1}" ]; then
                    _ack_capacity_key="${task_id}_ack_capacity_blocked"
                    if ! is_notified "$_ack_capacity_key"; then
                        notify_agent "$assigned_agent_for_ack" "任务 ${task_id} 已预留，但你已有 working 任务。请先完成当前主线，再重新确认本任务。"
                        notify_pm "[task-watcher] $task_id 收到 ack，但 ${assigned_agent_for_ack} 已达到 working_limit=${_ack_working_limit}，已暂缓进入 working。"
                        emit_system_chat_event watcher "$task_id" "ack 暂缓：${assigned_agent_for_ack} 已达到 working_limit=${_ack_working_limit}。" "$PM_AGENT_ID" degraded notify
                        mark_notified "$_ack_capacity_key"
                    fi
                    continue
                fi
                set_task_status "$task_dir" "working" "watcher observed ack.json"
                clear_dispatch_recovery_state "$task_dir"
                current_status="working"
                if ! is_notified "$ack_key"; then
                    log "$task_id: agent ${ack_agent:-?} 已确认，状态 working"
                    sync_task_board "$task_dir" "ack-detected"
                    mark_notified "$ack_key"
                fi
            fi
        fi

        # 检测 result.json → 自动流转到 PM / reviewer
        if [ -f "$task_dir/result.json" ]; then
            result_key="${task_id}_result_route"
            result_push_key="${task_id}_result_push"
            result_invalid_key="${task_id}_artifact_invalid_result"
            result_stale_key="${task_id}_reopen_with_stale_state_result"
            result_route_pending=0
            result_push_pending=0
            if ! is_notified "$result_key" || is_file_newer_than_notified "$result_key" "$task_dir/result.json" || { [ "$current_status" != "ready_for_merge" ] && [ "$current_status" != "blocked" ] && [ "$current_status" != "done" ] && [ "$current_status" != "cancelled" ] && [ "$current_status" != "archived" ]; }; then
                result_route_pending=1
            fi
            if ! is_notified "$result_push_key" || is_file_newer_than_notified "$result_push_key" "$task_dir/result.json"; then
                result_push_pending=1
            fi
            if [ "$result_route_pending" -eq 1 ] || [ "$result_push_pending" -eq 1 ]; then
                agent=$(artifact_pick result "$task_dir" agent)
                result_status=$(artifact_pick result "$task_dir" normalized_status)
                result_current_round=$(artifact_pick result "$task_dir" is_current_round)
                result_errors=$(artifact_pick result "$task_dir" errors.0)
                summary=$(artifact_pick result "$task_dir" summary)
                task_level=$(task_json_pick "$task_dir" task_level)
                assigned_agent=$(task_json_pick "$task_dir" assigned_agent)
                review_level=$(task_json_pick "$task_dir" review_level)
                review_required=$(task_json_pick "$task_dir" review_required)
                test_required=$(task_json_pick "$task_dir" test_required)
                quality_gate_mode=$(task_quality_gate_mode "$task_dir")

                if [ "$result_status" = "invalid" ]; then
                    if ! is_notified "$result_invalid_key"; then
                        notify_pm "[task-watcher] $task_id 的 result.json 非法，请修正后重试。"
                        emit_system_chat_event watcher "$task_id" "result.json 非法：${result_errors:-unknown}" "$PM_AGENT_ID" degraded notify
                        mark_notified "$result_invalid_key"
                    fi
                elif [ "$result_current_round" = "false" ]; then
                    if ! is_notified "$result_stale_key"; then
                        notify_pm "[task-watcher] $task_id 恢复后仍存在旧 result.json，当前已忽略，请使用 resume-task 规范恢复。"
                        emit_system_chat_event watcher "$task_id" "恢复后检测到旧 result.json，watcher 已忽略旧轮次产物。" "$PM_AGENT_ID" degraded notify
                        mark_notified "$result_stale_key"
                    fi
                elif [ "$result_status" = "success" ]; then
                    if [ "$result_route_pending" -eq 1 ]; then
                        gate_decision_at=$(now_iso)
                        gate_state="pm_acceptance_pending"
                        next_status="ready_for_merge"
                        review_subgate="skipped"
                        qa_subgate="skipped"
                        if is_truthy "$review_required" && is_truthy "$test_required" && [ "$quality_gate_mode" = "parallel" ]; then
                            gate_state="quality_pending"
                            review_subgate="pending"
                            qa_subgate="pending"
                        elif is_truthy "$review_required"; then
                            gate_state="review_pending"
                            review_subgate="pending"
                            if is_truthy "$test_required"; then
                                qa_subgate="pending"
                            fi
                        elif is_truthy "$test_required"; then
                            gate_state="qa_pending"
                            qa_subgate="pending"
                        fi
                        set_task_gate_state "$task_dir" "$next_status" "watcher observed result.json status=success" "$gate_state" "" "watcher" "$gate_decision_at" "$review_subgate" "$qa_subgate"
                        current_status="$next_status"
                        if is_integration_owner_planning_task "$assigned_agent" "$task_level"; then
                            notify_pm "[task-watcher] $task_id 技术方案已完成，请查看 result.json 并整理飞书确认。"
                            emit_system_chat_event watcher "$task_id" "技术方案已完成，等待 PM 汇总确认。" "$PM_AGENT_ID" info notify
                        elif [ "$gate_state" = "quality_pending" ]; then
                            auto_dispatch_review "$task_dir" "$task_id" "$review_level" "$summary"
                            auto_dispatch_qa "$task_id"
                            log "$task_id: 已进入并行质量闸门（review + QA）"
                            auto_push_next_task_for_agent "$assigned_agent" "$task_id" || true
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
                            emit_system_chat_event watcher "$task_id" "任务实现结果已提交，当前进入 PM 最终验收队列。" "$PM_AGENT_ID" info notify
                            auto_push_next_task_for_agent "$assigned_agent" "$task_id" || true
                        fi
                    fi

                    gate_state=$(task_json_pick "$task_dir" merge_gate_state)
                    result_push_title="【实现完成待验收】"
                    result_push_next="请 PM 决定是否最终收口"
                    if is_integration_owner_planning_task "$assigned_agent" "$task_level"; then
                        result_push_title="【技术方案完成】"
                        result_push_next="请 PM 汇总并确认后续动作"
                    elif [ "$gate_state" = "quality_pending" ]; then
                        result_push_title="【进入并行质控】"
                        result_push_next="已同时通知 review 与 QA 开始处理"
                    elif [ "$gate_state" = "review_pending" ]; then
                        result_push_title="【进入审查】"
                        result_push_next="已通知 reviewer 开始审查"
                    elif [ "$gate_state" = "qa_pending" ]; then
                        result_push_title="【进入QA】"
                        result_push_next="已通知 QA 开始验证"
                    fi
                    if [ "$result_push_pending" -eq 1 ]; then
                        push_task_event_with_retry "$result_push_key" "$task_dir/result.json" "$result_push_title" "$task_id" "$(truncate_utf8 "$summary" 300)" "$result_push_next" || log "$task_id: result 事件飞书补推待重试"
                    fi
                elif [ "$result_status" = "blocked" ]; then
                    if [ "$result_route_pending" -eq 1 ]; then
                        gate_decision_at=$(now_iso)
                        set_task_gate_state "$task_dir" "blocked" "watcher observed result.json status=blocked" "blocked" "execution" "${assigned_agent:-executor}" "$gate_decision_at"
                        current_status="blocked"
                        notify_pm "[task-watcher] $task_id 已被标记为 blocked，请查看 result.json 处理阻塞。"
                        emit_system_chat_event watcher "$task_id" "任务进入 blocked，需 PM 处理。" "$PM_AGENT_ID" degraded notify
                    fi
                    if [ "$result_push_pending" -eq 1 ]; then
                        push_task_event_with_retry "$result_push_key" "$task_dir/result.json" "【任务阻塞】" "$task_id" "$(truncate_utf8 "$summary" 300)" "请 PM 介入处理阻塞原因" || log "$task_id: blocked 事件飞书补推待重试"
                    fi
                elif [ "$result_status" = "failed" ]; then
                    if [ "$result_route_pending" -eq 1 ]; then
                        gate_decision_at=$(now_iso)
                        set_task_gate_state "$task_dir" "blocked" "watcher observed result.json status=failed" "blocked" "execution" "${assigned_agent:-executor}" "$gate_decision_at"
                        current_status="blocked"
                        notify_pm "[task-watcher] $task_id 执行失败，请查看 result.json 处理。"
                        emit_system_chat_event watcher "$task_id" "任务执行失败，需 PM 判断补修、重试或关闭。" "$PM_AGENT_ID" degraded notify
                    fi
                    if [ "$result_push_pending" -eq 1 ]; then
                        push_task_event_with_retry "$result_push_key" "$task_dir/result.json" "【任务失败】" "$task_id" "$(truncate_utf8 "$summary" 300)" "请 PM 判断补修、重试或关闭" || log "$task_id: failed 事件飞书补推待重试"
                    fi
                else
                    if [ "$result_route_pending" -eq 1 ]; then
                        notify_pm "[task-watcher] $task_id 产生了 result.json（status=$result_status），请查看任务目录。"
                        emit_system_chat_event watcher "$task_id" "任务产出 result.json，需 PM 查看。" "$PM_AGENT_ID" info notify
                    fi
                fi

                sync_task_board "$task_dir" "result-detected"
                if [ "$result_status" != "invalid" ] && [ "$result_current_round" != "false" ]; then
                    mark_notified "$result_key"
                fi
            fi
        fi

        if [ "$current_status" = "working" ] && [ ! -f "$task_dir/result.json" ]; then
            working_since=$(task_working_reference_epoch "$task_dir")
            assigned_agent=$(task_json_pick "$task_dir" assigned_agent)
            now=$(date +%s)
            if [ -n "$working_since" ] && [ "$working_since" -gt 0 ] && ! task_has_effective_progress "$task_dir" "$working_since"; then
                elapsed_since_ack=$(( now - working_since ))
                if [ "$elapsed_since_ack" -ge "${ACK_NO_PROGRESS_REMINDER_SECONDS:-900}" ]; then
                    no_progress_reminder_key="${task_id}_working_no_progress_reminder"
                    if ! is_notified "$no_progress_reminder_key" || ! is_file_newer_than_notified "$no_progress_reminder_key" "$task_dir/ack.json"; then
                        notify_working_no_progress_if_needed "$task_dir" "$task_id" "$assigned_agent" "$working_since" || true
                    fi
                fi
                if [ "$elapsed_since_ack" -ge "${ACK_NO_PROGRESS_REPOOL_SECONDS:-1800}" ]; then
                    if returned_agent=$(requeue_working_task_to_pool_if_no_progress "$task_dir" "$task_id" "$working_since" 2>/dev/null); then
                        if [ -n "$returned_agent" ]; then
                            notify_agent "$returned_agent" "任务 ${task_id} 已 ack 超过 ${ACK_NO_PROGRESS_REPOOL_SECONDS:-1800} 秒且未发现实际进展，现已自动回池。"
                        fi
                        notify_pm "[task-watcher] $task_id ack 后 ${ACK_NO_PROGRESS_REPOOL_SECONDS:-1800} 秒仍无实际进展，已回退到 pooled。"
                        if [ -n "$returned_agent" ]; then
                            emit_system_chat_event watcher "$task_id" "ack 后无实际进展，已从 ${returned_agent} 回退到 pooled。" "$PM_AGENT_ID" degraded notify
                        else
                            emit_system_chat_event watcher "$task_id" "ack 后无实际进展，已回退到 pooled。" "$PM_AGENT_ID" degraded notify
                        fi
                        task_clear_working_timeout_state "$task_id"
                        sync_task_board "$task_dir" "working-no-progress-requeued"
                        current_status="pooled"
                        continue
                    fi
                fi
            fi
            if [ -n "$working_since" ] && [ "$working_since" -gt 0 ] && [ $(( now - working_since )) -gt "$WORKING_TIMEOUT_SECONDS" ]; then
                working_timeout_key="${task_id}_working_timeout_notice"
                working_timeout_push_key="${task_id}_working_timeout_push"
                working_grace_key="${task_id}_working_timeout_grace_started"
                if ! is_notified "$working_timeout_key" || ! is_notified "$working_timeout_push_key"; then
                    if ! is_notified "$working_timeout_key"; then
                        notify_pm "[task-watcher] $task_id 持续 working 超时，请 PM 介入检查。"
                        emit_system_chat_event watcher "$task_id" "任务 working 超时，需 PM 介入。" "$PM_AGENT_ID" degraded notify
                        log "$task_id: working 超时已通知 PM 介入，等待飞书送达"
                        mark_notified "$working_timeout_key"
                        mark_notified "$working_grace_key"
                    fi
                    push_task_event_with_retry "$working_timeout_push_key" "" "【任务超时】" "$task_id" "持续 working 超过 $((WORKING_TIMEOUT_SECONDS / 60)) 分钟" "请 PM 介入检查" || true
                fi
                working_grace_started=$(notified_epoch "$working_grace_key")
                if should_pause_working_timeout_escalation "$task_dir" "$(task_json_pick "$task_dir" assigned_agent)" "$working_grace_key" "$now"; then
                    log "$task_id: working 超时已进入 PM 观察窗口（${WORKING_REASSIGN_GRACE_SECONDS}s），暂不建议转派"
                    continue
                fi
            fi
        fi

        # 检测 review 结果 → 自动通知 QA 或通知 PM 仲裁
        if [ -f "$task_dir/review.json" ] || [ -f "$task_dir/design-review.json" ] || [ -f "$task_dir/review.md" ] || [ -f "$task_dir/design-review.md" ]; then
            review_level=$(task_json_pick "$task_dir" review_level)
            review_sig=$(review_signature "$task_dir")
            review_key="${task_id}_review_route"
            review_push_key="${task_id}_review_push"
            review_route_pending=0
            review_push_pending=0
            if ! is_notified "$review_key" || is_signature_newer_than_notified "$review_key" "$review_sig"; then
                review_route_pending=1
            fi
            if ! is_notified "$review_push_key" || is_signature_newer_than_notified "$review_push_key" "$review_sig"; then
                review_push_pending=1
            fi
            if [ "$review_route_pending" -eq 1 ] || [ "$review_push_pending" -eq 1 ]; then
                state=$(review_state "$task_dir" "$review_level")
                if [ "$state" = "invalid" ]; then
                    clear_review_queue_state_for_task "$task_dir"
                    review_invalid_key="${task_id}_artifact_invalid_review"
                    if ! is_notified "$review_invalid_key"; then
                        notify_pm "[task-watcher] $task_id 的 review 机器产物非法，请修正 review.json 后重试。"
                        emit_system_chat_event watcher "$task_id" "review.json 非法或缺关键字段，已停止自动推进。" "$PM_AGENT_ID" degraded notify
                        mark_notified "$review_invalid_key"
                    fi
                elif [ "$state" = "pass" ]; then
                    clear_review_queue_state_for_task "$task_dir"
                    test_required=$(task_json_pick "$task_dir" test_required)
                    quality_gate_mode=$(task_quality_gate_mode "$task_dir")
                    current_qa_gate_state=$(qa_gate_state "$task_dir")
                    current_status_now=$(get_task_status "$task_dir")
                    if [ "$test_required" = "True" ] || [ "$test_required" = "true" ] || [ "$test_required" = "1" ]; then
                        if [ "$review_route_pending" -eq 1 ]; then
                            gate_decision_at=$(now_iso)
                            if [ "$current_status_now" != "ready_for_merge" ]; then
                                set_task_gate_state "$task_dir" "" "watcher observed review pass while task not ready_for_merge" "__KEEP__" "__KEEP__" "review" "$gate_decision_at" "approved" "__KEEP__"
                            elif [ "$quality_gate_mode" = "parallel" ]; then
                                if [ "$current_qa_gate_state" = "passed" ]; then
                                    set_task_gate_state "$task_dir" "ready_for_merge" "watcher observed parallel review pass with qa already passed" "pm_acceptance_pending" "" "review" "$gate_decision_at" "approved" "__KEEP__"
                                    current_status="ready_for_merge"
                                    notify_pm "[task-watcher] $task_id 审查与 QA 已通过，请查看任务目录并决定是否最终收口。"
                                    emit_system_chat_event watcher "$task_id" "审查与 QA 已全部通过，等待 PM 最终验收。" "$PM_AGENT_ID" info notify
                                    log "$task_id: 并行质量闸门已全部完成，进入 PM 收口"
                                else
                                    set_task_gate_state "$task_dir" "ready_for_merge" "watcher observed parallel review pass and waiting for qa" "quality_pending" "" "review" "$gate_decision_at" "approved" "__KEEP__"
                                    current_status="ready_for_merge"
                                    if [ "$current_qa_gate_state" = "pending" ] || [ "$current_qa_gate_state" = "missing" ]; then
                                        auto_dispatch_qa "$task_id"
                                    fi
                                    log "$task_id: review 通过，等待并行 QA 完成"
                                fi
                            else
                                set_task_gate_state "$task_dir" "ready_for_merge" "watcher observed review pass and queued qa" "qa_pending" "" "review" "$gate_decision_at" "approved" "pending"
                                current_status="ready_for_merge"
                                auto_dispatch_qa "$task_id"
                                log "$task_id: review 通过，已进入 QA 队列"
                            fi
                        fi
                        if [ "$review_push_pending" -eq 1 ]; then
                            if [ "$quality_gate_mode" = "parallel" ] && [ "$current_qa_gate_state" = "passed" ]; then
                                push_task_event_with_signature_retry "$review_push_key" "$review_sig" "【质控完成待收口】" "$task_id" "$(truncate_utf8 "$(first_review_conclusion "$task_dir")" 300)" "审查与 QA 已通过，等待 PM 最终验收" || log "$task_id: review pass 事件飞书补推待重试"
                            elif [ "$quality_gate_mode" = "parallel" ]; then
                                push_task_event_with_signature_retry "$review_push_key" "$review_sig" "【审查通过，等待QA】" "$task_id" "$(truncate_utf8 "$(first_review_conclusion "$task_dir")" 300)" "QA 完成后自动进入 PM 验收" || log "$task_id: review pass 事件飞书补推待重试"
                            else
                                push_task_event_with_signature_retry "$review_push_key" "$review_sig" "【审查通过】" "$task_id" "$(truncate_utf8 "$(first_review_conclusion "$task_dir")" 300)" "已通知 QA 开始验证" || log "$task_id: review pass 事件飞书补推待重试"
                            fi
                        fi
                    else
                        auto_close_policy=$(task_json_pick "$task_dir" auto_close_policy)
                        task_type=$(task_json_pick "$task_dir" task_type)
                        result_status=$(artifact_pick result "$task_dir" normalized_status 2>/dev/null || true)
                        result_outcome=$(artifact_pick result "$task_dir" outcome_status 2>/dev/null || true)
                        verification_negative=0
                        if [ "$task_type" = "verification" ] && { [ "$result_status" = "failed" ] || [ "$result_status" = "blocked" ] || [ "$result_outcome" = "fail" ] || [ "$result_outcome" = "blocked" ]; }; then
                            verification_negative=1
                        fi
                        if [ "$review_route_pending" -eq 1 ]; then
                            gate_decision_at=$(now_iso)
                            if [ "$verification_negative" -eq 1 ]; then
                                set_task_gate_state "$task_dir" "blocked" "watcher observed review pass confirming verification fail" "blocked" "verification" "review" "$gate_decision_at" "approved" "skipped"
                                current_status="blocked"
                                notify_pm "[task-watcher] $task_id 复验结论未通过且审查已确认，请回退开发补修，不会自动收口。"
                                emit_system_chat_event watcher "$task_id" "复验结论未通过且审查已确认，任务已回到 blocked，需继续开发补修。" "$PM_AGENT_ID" degraded notify
                            else
                                set_task_gate_state "$task_dir" "" "watcher observed review pass without qa" "pm_acceptance_pending" "" "review" "$gate_decision_at" "approved" "skipped"
                                if [ "$auto_close_policy" = "review_pass_only" ]; then
                                    if ! auto_close_review_only_task "$task_dir" "$task_id"; then
                                        notify_pm "[task-watcher] $task_id 审查已通过且配置为自动收口，但 close-task 失败，请检查任务目录。"
                                        emit_system_chat_event watcher "$task_id" "审查通过自动收口失败。" "$PM_AGENT_ID" degraded notify
                                    fi
                                else
                                    notify_pm "[task-watcher] $task_id 审查已通过且无需 QA，请查看任务目录并决定是否收口。"
                                    emit_system_chat_event watcher "$task_id" "审查通过且无需 QA，等待 PM 最终验收。" "$PM_AGENT_ID" info notify
                                fi
                            fi
                        fi
                        if [ "$verification_negative" -eq 1 ] && [ "$review_push_pending" -eq 1 ]; then
                            push_task_event_with_signature_retry "$review_push_key" "$review_sig" "【复验失败待补修】" "$task_id" "$(truncate_utf8 "$(first_review_conclusion "$task_dir")" 300)" "审查已确认失败结论，请回退开发继续修复" || log "$task_id: verification fail 事件飞书补推待重试"
                        elif [ "$auto_close_policy" != "review_pass_only" ] && [ "$review_push_pending" -eq 1 ]; then
                            push_task_event_with_signature_retry "$review_push_key" "$review_sig" "【审查通过待收口】" "$task_id" "$(truncate_utf8 "$(first_review_conclusion "$task_dir")" 300)" "无需 QA，等待 PM 最终验收" || log "$task_id: review close-wait 事件飞书补推待重试"
                        fi
                    fi
                elif [ "$state" = "fail" ]; then
                    clear_review_queue_state_for_task "$task_dir"
                    if [ "$review_route_pending" -eq 1 ]; then
                        gate_decision_at=$(now_iso)
                        set_task_gate_state "$task_dir" "blocked" "watcher observed review fail" "review_rejected" "review" "review" "$gate_decision_at" "rejected" "__KEEP__"
                        current_status="blocked"
                        notify_pm "[task-watcher] $task_id 审查未通过，请查看 review 产物并仲裁。"
                        emit_system_chat_event watcher "$task_id" "审查未通过，需 PM 仲裁。" "$PM_AGENT_ID" degraded notify
                    fi
                    if [ "$review_push_pending" -eq 1 ]; then
                        push_task_event_with_signature_retry "$review_push_key" "$review_sig" "【审查未通过】" "$task_id" "$(truncate_utf8 "$(first_review_conclusion "$task_dir")" 300)" "请 PM 仲裁并决定是否补修" || log "$task_id: review fail 事件飞书补推待重试"
                    fi
                fi
                sync_task_board "$task_dir" "review-detected"
                if [ "$state" != "invalid" ]; then
                    mark_signature_notified "$review_key" "$review_sig"
                fi
            fi
        fi

        # 检测 verify.json → QA 通过推进 merge gate；QA 失败通知 PM 仲裁
        if [ -f "$task_dir/verify.json" ]; then
            verify_key="${task_id}_verify_route"
            verify_push_key="${task_id}_verify_push"
            verify_route_pending=0
            verify_push_pending=0
            if ! is_notified "$verify_key" || is_file_newer_than_notified "$verify_key" "$task_dir/verify.json"; then
                verify_route_pending=1
            fi
            if ! is_notified "$verify_push_key" || is_file_newer_than_notified "$verify_push_key" "$task_dir/verify.json"; then
                verify_push_pending=1
            fi
            if [ "$verify_route_pending" -eq 1 ] || [ "$verify_push_pending" -eq 1 ]; then
                vstate=$(verify_state "$task_dir/verify.json")
                vsummary=$(verify_summary "$task_dir/verify.json")
                if [ "$vstate" = "invalid" ]; then
                    clear_qa_queue_state_for_task "$task_id"
                    verify_invalid_key="${task_id}_artifact_invalid_verify"
                    if ! is_notified "$verify_invalid_key"; then
                        notify_pm "[task-watcher] $task_id 的 verify.json 非法，请修正后重试。"
                        emit_system_chat_event watcher "$task_id" "verify.json 非法或缺关键字段，已停止自动推进。" "$PM_AGENT_ID" degraded notify
                        mark_notified "$verify_invalid_key"
                    fi
                elif [ "$vstate" = "pass" ]; then
                    clear_qa_queue_state_for_task "$task_id"
                    review_required=$(task_json_pick "$task_dir" review_required)
                    review_level=$(task_json_pick "$task_dir" review_level)
                    summary=$(json_pick "$task_dir/result.json" summary)
                    quality_gate_mode=$(task_quality_gate_mode "$task_dir")
                    current_review_gate_state=$(review_gate_state "$task_dir" "$review_level")
                    if [ "$verify_route_pending" -eq 1 ]; then
                        current_status=$(get_task_status "$task_dir")
                        gate_decision_at=$(now_iso)
                        if [ "$current_status" != "ready_for_merge" ]; then
                            set_task_gate_state "$task_dir" "" "watcher observed qa pass while task not ready_for_merge" "__KEEP__" "__KEEP__" "qa" "$gate_decision_at" "__KEEP__" "passed"
                        elif is_truthy "$review_required" && [ "$quality_gate_mode" = "parallel" ]; then
                            if [ "$current_review_gate_state" = "approved" ]; then
                                set_task_gate_state "$task_dir" "ready_for_merge" "watcher observed parallel qa pass with review already approved" "pm_acceptance_pending" "" "qa" "$gate_decision_at" "__KEEP__" "passed"
                                notify_pm "[task-watcher] $task_id 审查与 QA 已通过，请查看任务目录并决定是否最终收口。"
                                emit_system_chat_event watcher "$task_id" "审查与 QA 已全部通过，等待 PM 最终验收。" "$PM_AGENT_ID" info notify
                                log "$task_id: QA 通过，并行质量闸门已全部完成"
                            else
                                set_task_gate_state "$task_dir" "ready_for_merge" "watcher observed parallel qa pass and waiting for review" "quality_pending" "" "qa" "$gate_decision_at" "__KEEP__" "passed"
                                if [ "$current_review_gate_state" = "pending" ]; then
                                    auto_dispatch_review "$task_dir" "$task_id" "$review_level" "$summary"
                                fi
                                log "$task_id: QA 通过，等待并行审查完成"
                            fi
                        else
                            set_task_gate_state "$task_dir" "ready_for_merge" "watcher observed qa verify pass" "pm_acceptance_pending" "" "qa" "$gate_decision_at" "__KEEP__" "passed"
                            notify_pm "[task-watcher] $task_id QA 已通过，请查看任务目录并决定是否最终收口。"
                            emit_system_chat_event watcher "$task_id" "QA 已通过，等待 PM 最终验收。" "$PM_AGENT_ID" info notify
                            log "$task_id: QA 通过，进入 PM 收口"
                        fi
                    fi
                    if [ "$verify_push_pending" -eq 1 ]; then
                        if is_truthy "$review_required" && [ "$quality_gate_mode" = "parallel" ] && [ "$current_review_gate_state" = "approved" ]; then
                            push_task_event_with_retry "$verify_push_key" "$task_dir/verify.json" "【质控完成待收口】" "$task_id" "$(truncate_utf8 "$vsummary" 300)" "审查与 QA 已通过，等待 PM 最终验收" || log "$task_id: QA pass 事件飞书补推待重试"
                        elif is_truthy "$review_required" && [ "$quality_gate_mode" = "parallel" ]; then
                            push_task_event_with_retry "$verify_push_key" "$task_dir/verify.json" "【QA通过，等待审查】" "$task_id" "$(truncate_utf8 "$vsummary" 300)" "审查通过后自动进入 PM 验收" || log "$task_id: QA pass 事件飞书补推待重试"
                        else
                            push_task_event_with_retry "$verify_push_key" "$task_dir/verify.json" "【QA通过待收口】" "$task_id" "$(truncate_utf8 "$vsummary" 300)" "等待 PM 最终验收" || log "$task_id: QA pass 事件飞书补推待重试"
                        fi
                    fi
                elif [ "$vstate" = "fail" ]; then
                    clear_qa_queue_state_for_task "$task_id"
                    if [ "$verify_route_pending" -eq 1 ]; then
                        gate_decision_at=$(now_iso)
                        qa_actor=$(artifact_pick verify "$task_dir" agent 2>/dev/null || true)
                        qa_actor="${qa_actor:-$(default_tester_agent "$task_dir")}"
                        set_task_gate_state "$task_dir" "blocked" "watcher observed qa verify fail" "qa_failed" "qa" "${qa_actor:-qa}" "$gate_decision_at" "__KEEP__" "failed"
                        current_status="blocked"
                        notify_pm "[task-watcher] $task_id QA 未通过，请查看 verify.json 并仲裁。"
                        emit_system_chat_event watcher "$task_id" "QA 未通过，需 PM 仲裁。" "$PM_AGENT_ID" degraded notify
                    fi
                    if [ "$verify_push_pending" -eq 1 ]; then
                        push_task_event_with_retry "$verify_push_key" "$task_dir/verify.json" "【QA未通过】" "$task_id" "$(truncate_utf8 "$vsummary" 300)" "请 PM 仲裁并决定修复、回退或重新验证" || log "$task_id: QA fail 事件飞书补推待重试"
                    fi
                fi
                sync_task_board "$task_dir" "verify-detected"
                if [ "$vstate" != "invalid" ]; then
                    mark_notified "$verify_key"
                fi
            fi
        fi

        sync_if_changed "$task_dir" "$task_dir/task.json" "taskjson"
        sync_if_changed "$task_dir" "$task_dir/transitions.jsonl" "transitions"
        sync_if_changed "$task_dir" "$task_dir/ack.json" "ack"
        sync_if_changed "$task_dir" "$task_dir/result.json" "result"
        sync_if_changed "$task_dir" "$task_dir/review.json" "reviewjson"
        sync_if_changed "$task_dir" "$task_dir/design-review.json" "designreviewjson"
        sync_if_changed "$task_dir" "$task_dir/review.md" "review"
        sync_if_changed "$task_dir" "$task_dir/design-review.md" "designreview"
        sync_if_changed "$task_dir" "$task_dir/verify.json" "verify"
    done

    while IFS= read -r pool_agent; do
        [ -n "$pool_agent" ] || continue
        auto_push_next_task_for_agent "$pool_agent" "idle sweep" || true
        auto_reserve_next_task_for_agent "$pool_agent" "working sweep" || true
        auto_dispatch_next_pending_push_for_agent "$pool_agent" "idle sweep" || true
    done <<< "$(list_pool_agents)"

    while IFS= read -r reviewer_agent; do
        [ -n "$reviewer_agent" ] || continue
        auto_push_next_review_for_agent "$reviewer_agent" "idle sweep" || true
    done <<< "$(list_review_agents)"

    while IFS= read -r qa_agent; do
        [ -n "$qa_agent" ] || continue
        auto_push_next_qa_for_agent "$qa_agent" "idle sweep" || true
    done <<< "$(list_qa_agents)"

    write_heartbeat "sleeping"
    sleep "$INTERVAL"
    done
}

if [ "$TASK_WATCHER_TEST_MODE" != "1" ]; then
    run_task_watcher_loop
fi
