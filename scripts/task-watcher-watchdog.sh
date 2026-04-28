#!/bin/bash
# task-watcher-watchdog.sh - 监控 task-watcher 进程与 heartbeat，并在退出/卡死时自动重启。

STATE_DIR="${STATE_DIR:-/Users/lin/.openclaw/workspace/.task-watcher}"
TASK_WATCHER_SCRIPT="${TASK_WATCHER_SCRIPT:-/Users/lin/Desktop/work/my-agent-teams/scripts/task-watcher.sh}"
WATCHDOG_INTERVAL="${WATCHDOG_INTERVAL:-15}"
HEARTBEAT_TIMEOUT_SECONDS="${HEARTBEAT_TIMEOUT_SECONDS:-120}"
WATCHDOG_RUN_ONCE="${WATCHDOG_RUN_ONCE:-0}"
PID_FILE="${PID_FILE:-$STATE_DIR/task-watcher.pid}"
HEARTBEAT_FILE="${HEARTBEAT_FILE:-$STATE_DIR/task-watcher-heartbeat.json}"
RESTART_CAUSE_FILE="${RESTART_CAUSE_FILE:-$STATE_DIR/task-watcher-restart-cause.txt}"
WATCHER_STDOUT_LOG="${WATCHER_STDOUT_LOG:-$STATE_DIR/task-watcher.stdout.log}"
LOG_DIR="${LOG_DIR:-/Users/lin/.openclaw/workspace/logs}"
LOG_FILE="${LOG_FILE:-$LOG_DIR/task-watcher.log}"
LOG_RETENTION_DAYS="${LOG_RETENTION_DAYS:-7}"

LAST_LOG_ROTATE_DAY=""

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

is_pid_alive() {
    local pid="$1"
    [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null
}

read_pid() {
    cat "$PID_FILE" 2>/dev/null || true
}

read_heartbeat_ts() {
    python3 - "$HEARTBEAT_FILE" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
if not path.exists():
    raise SystemExit(1)
try:
    payload = json.loads(path.read_text(encoding='utf-8'))
except Exception:
    raise SystemExit(1)
value = payload.get('updated_ts')
if isinstance(value, int):
    print(value)
    raise SystemExit(0)
raise SystemExit(1)
PY
}

record_restart_cause() {
    local reason="$1"
    printf '%s %s\n' "$(date '+%Y-%m-%dT%H:%M:%S%z')" "$reason" > "$RESTART_CAUSE_FILE"
}

start_watcher() {
    local reason="$1"
    if [ ! -x "$TASK_WATCHER_SCRIPT" ]; then
        log "无法启动 task-watcher：脚本不存在或不可执行: $TASK_WATCHER_SCRIPT"
        return 1
    fi
    record_restart_cause "$reason"
    nohup "$TASK_WATCHER_SCRIPT" >> "$WATCHER_STDOUT_LOG" 2>&1 &
    local child_pid=$!
    sleep 1
    log "watchdog 已启动 task-watcher（child pid=$child_pid，reason=$reason）"
    return 0
}

stop_watcher() {
    local pid="$1"
    local reason="$2"
    if ! is_pid_alive "$pid"; then
        rm -f "$PID_FILE"
        return 0
    fi
    log "watchdog 检测到异常，准备停止 task-watcher（pid=$pid，reason=$reason）"
    kill "$pid" 2>/dev/null || true
    local waited=0
    while is_pid_alive "$pid" && [ "$waited" -lt 5 ]; do
        sleep 1
        waited=$((waited + 1))
    done
    if is_pid_alive "$pid"; then
        kill -9 "$pid" 2>/dev/null || true
    fi
    rm -f "$PID_FILE"
}

check_once() {
    local pid
    pid=$(read_pid)
    if [ -z "$pid" ] || ! is_pid_alive "$pid"; then
        log "watchdog 检测到 task-watcher 未运行"
        start_watcher "process_exit"
        return
    fi

    if [ ! -f "$HEARTBEAT_FILE" ]; then
        stop_watcher "$pid" "heartbeat_missing"
        start_watcher "heartbeat_missing"
        return
    fi

    local heartbeat_ts
    if ! heartbeat_ts=$(read_heartbeat_ts 2>/dev/null); then
        stop_watcher "$pid" "heartbeat_invalid"
        start_watcher "heartbeat_invalid"
        return
    fi

    local now age
    now=$(date +%s)
    age=$((now - heartbeat_ts))
    if [ "$age" -gt "$HEARTBEAT_TIMEOUT_SECONDS" ]; then
        stop_watcher "$pid" "heartbeat_timeout_${age}s"
        start_watcher "heartbeat_timeout_${age}s"
    fi
}

log "task-watcher-watchdog 启动，interval=${WATCHDOG_INTERVAL}s timeout=${HEARTBEAT_TIMEOUT_SECONDS}s"

while true; do
    check_once
    if [ "$WATCHDOG_RUN_ONCE" = "1" ]; then
        exit 0
    fi
    sleep "$WATCHDOG_INTERVAL"
done
