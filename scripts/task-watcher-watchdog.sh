#!/bin/bash
# task-watcher-watchdog.sh - 监控 task-watcher 进程与 heartbeat，并在退出/卡死时自动重启。

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_ROOT="${WORKSPACE_ROOT:-$(cd "$SCRIPT_DIR/.." && pwd)}"
LEGACY_OPENCLAW_ROOT="${LEGACY_OPENCLAW_ROOT:-$HOME/.openclaw/workspace}"
LEGACY_STATE_DIR="${LEGACY_STATE_DIR:-$LEGACY_OPENCLAW_ROOT/.task-watcher}"
LEGACY_LOG_DIR="${LEGACY_LOG_DIR:-$LEGACY_OPENCLAW_ROOT/logs}"

LEGACY_PROJECT_OMX_STATE_DIR="${LEGACY_PROJECT_OMX_STATE_DIR:-$WORKSPACE_ROOT/.omx/state/task-watcher}"
LEGACY_PROJECT_OMX_LOG_DIR="${LEGACY_PROJECT_OMX_LOG_DIR:-$WORKSPACE_ROOT/.omx/logs}"
STATE_DIR="${STATE_DIR:-$WORKSPACE_ROOT/.runtime/state/task-watcher}"
TASK_WATCHER_SCRIPT="${TASK_WATCHER_SCRIPT:-$WORKSPACE_ROOT/scripts/task-watcher.sh}"
WATCHDOG_INTERVAL="${WATCHDOG_INTERVAL:-15}"
HEARTBEAT_TIMEOUT_SECONDS="${HEARTBEAT_TIMEOUT_SECONDS:-300}"
WATCHDOG_RUN_ONCE="${WATCHDOG_RUN_ONCE:-0}"
PID_FILE="${PID_FILE:-$STATE_DIR/task-watcher.pid}"
HEARTBEAT_FILE="${HEARTBEAT_FILE:-$STATE_DIR/task-watcher-heartbeat.json}"
WATCHDOG_PID_FILE="${WATCHDOG_PID_FILE:-$STATE_DIR/task-watcher-watchdog.pid}"
RESTART_CAUSE_FILE="${RESTART_CAUSE_FILE:-$STATE_DIR/task-watcher-restart-cause.txt}"
MIGRATION_SENTINEL_FILE="${MIGRATION_SENTINEL_FILE:-$STATE_DIR/migration-complete.json}"
LOG_DIR="${LOG_DIR:-$WORKSPACE_ROOT/.runtime/logs}"
LOG_FILE="${LOG_FILE:-$LOG_DIR/task-watcher.log}"
WATCHER_STDOUT_LOG="${WATCHER_STDOUT_LOG:-$LOG_FILE}"
LOG_RETENTION_DAYS="${LOG_RETENTION_DAYS:-7}"

LAST_LOG_ROTATE_DAY=""

mkdir -p "$STATE_DIR" "$LOG_DIR"

ensure_watchdog_single_instance() {
  local existing_pid=""
  existing_pid=$(cat "$WATCHDOG_PID_FILE" 2>/dev/null || true)
  if [ -n "$existing_pid" ] && [ "$existing_pid" != "$$" ] && kill -0 "$existing_pid" 2>/dev/null; then
    printf "%s\n" "$(date '+%Y-%m-%d %H:%M:%S') task-watcher-watchdog 已在运行（pid=$existing_pid），当前实例退出" >&2
    exit 0
  fi
}

write_watchdog_pid() {
  printf '%s\n' "$$" > "$WATCHDOG_PID_FILE"
}

cleanup_watchdog_runtime() {
  local existing_pid=""
  existing_pid=$(cat "$WATCHDOG_PID_FILE" 2>/dev/null || true)
  if [ "$existing_pid" = "$$" ]; then
    rm -f "$WATCHDOG_PID_FILE"
  fi
}

trap cleanup_watchdog_runtime EXIT INT TERM
ensure_watchdog_single_instance
write_watchdog_pid

ensure_stdout_log_compat() {
  local compat_stdout_log="$STATE_DIR/task-watcher.stdout.log"
  [ "$WATCHER_STDOUT_LOG" = "$compat_stdout_log" ] && return 0
  mkdir -p "$(dirname "$compat_stdout_log")" "$(dirname "$WATCHER_STDOUT_LOG")"
  rm -f "$compat_stdout_log" 2>/dev/null || true
  ln -s "$WATCHER_STDOUT_LOG" "$compat_stdout_log" 2>/dev/null || printf 'redirected to %s\n' "$WATCHER_STDOUT_LOG" > "$compat_stdout_log"
}

ensure_stdout_log_compat

migrate_legacy_task_watcher_runtime() {
    [ -f "$MIGRATION_SENTINEL_FILE" ] && return 0

    local migration_lock="$STATE_DIR/.runtime-migration.lockdir"
    if ! mkdir "$migration_lock" 2>/dev/null; then
        return 0
    fi

    LEGACY_STATE_DIR="$LEGACY_STATE_DIR" \
    LEGACY_LOG_DIR="$LEGACY_LOG_DIR" \
    LEGACY_PROJECT_OMX_STATE_DIR="$LEGACY_PROJECT_OMX_STATE_DIR" \
    LEGACY_PROJECT_OMX_LOG_DIR="$LEGACY_PROJECT_OMX_LOG_DIR" \
    STATE_DIR="$STATE_DIR" \
    LOG_DIR="$LOG_DIR" \
    MIGRATION_SENTINEL_FILE="$MIGRATION_SENTINEL_FILE" \
    python3 - <<'PY_MIGRATE_RUNTIME'
import json
import os
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path

legacy_state_dir = Path(os.environ["LEGACY_STATE_DIR"]).expanduser()
legacy_log_dir = Path(os.environ["LEGACY_LOG_DIR"]).expanduser()
legacy_project_omx_state_dir = Path(os.environ["LEGACY_PROJECT_OMX_STATE_DIR"]).expanduser()
legacy_project_omx_log_dir = Path(os.environ["LEGACY_PROJECT_OMX_LOG_DIR"]).expanduser()
state_dir = Path(os.environ["STATE_DIR"]).expanduser()
log_dir = Path(os.environ["LOG_DIR"]).expanduser()
sentinel_path = Path(os.environ["MIGRATION_SENTINEL_FILE"]).expanduser()

state_dir.mkdir(parents=True, exist_ok=True)
log_dir.mkdir(parents=True, exist_ok=True)

SKIP_STATE_NAMES = {
    'task-watcher.pid',
    'task-watcher-heartbeat.json',
    'task-watcher-restart-cause.txt',
    'task-watcher.stdout.log',
}
SKIP_SUFFIXES = ('.lock', '.tmp')
SKIP_PREFIXES = ('.', 'patch.', 'gate_err.')

def should_skip_state(source: Path) -> bool:
    name = source.name
    return name in SKIP_STATE_NAMES or name.endswith(SKIP_SUFFIXES) or any(name.startswith(prefix) for prefix in SKIP_PREFIXES)

def copy_files(source_dir: Path, target_dir: Path, patterns: list[str], *, state_files: bool = False):
    copied = []
    if not source_dir.exists():
        return copied
    for pattern in patterns:
        for source in sorted(source_dir.glob(pattern)):
            if not source.is_file():
                continue
            if state_files and should_skip_state(source):
                continue
            target = target_dir / source.name
            if target.exists() and target.stat().st_mtime >= source.stat().st_mtime:
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            try:
                shutil.copy2(str(source), str(target))
                copied.append({"from": str(source), "to": str(target)})
            except Exception:
                continue
    return copied

state_patterns = ["*"]
log_patterns = [
    "task-watcher.log",
    "task-watcher.*.log",
    "task-watcher.stdout.log",
]

copied_state = []
for source in [legacy_state_dir, legacy_project_omx_state_dir]:
    copied_state.extend(copy_files(source, state_dir, state_patterns, state_files=True))
copied_logs = []
for source in [legacy_log_dir, legacy_project_omx_log_dir]:
    copied_logs.extend(copy_files(source, log_dir, log_patterns))

payload = {
    "migrated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    "mode": "copy-once",
    "legacy_state_dir": str(legacy_state_dir),
    "legacy_log_dir": str(legacy_log_dir),
    "legacy_project_omx_state_dir": str(legacy_project_omx_state_dir),
    "legacy_project_omx_log_dir": str(legacy_project_omx_log_dir),
    "state_dir": str(state_dir),
    "log_dir": str(log_dir),
    "copied_state_files": copied_state,
    "copied_log_files": copied_logs,
}
sentinel_path.parent.mkdir(parents=True, exist_ok=True)
with tempfile.NamedTemporaryFile("w", delete=False, dir=str(sentinel_path.parent), encoding="utf-8") as tmp:
    json.dump(payload, tmp, ensure_ascii=False, indent=2)
    tmp.write("\n")
tmp_path = Path(tmp.name)
os.replace(tmp_path, sentinel_path)
PY_MIGRATE_RUNTIME
    local rc=$?
    rmdir "$migration_lock" 2>/dev/null || true
    return "$rc"
}

migrate_legacy_task_watcher_runtime

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
  TASK_WATCHER_STDOUT_REDIRECTED=1 WATCHER_STDOUT_LOG="$WATCHER_STDOUT_LOG" nohup "$TASK_WATCHER_SCRIPT" >> "$WATCHER_STDOUT_LOG" 2>&1 &
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
