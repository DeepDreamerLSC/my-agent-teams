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
HEARTBEAT_PID_MISMATCH_GRACE_SECONDS="${HEARTBEAT_PID_MISMATCH_GRACE_SECONDS:-60}"
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

pid_command() {
  local pid="$1"
  ps -p "$pid" -o command= 2>/dev/null || true
}

is_pid_for_script() {
  local pid="$1" script_name="$2" cmd=""
  [ -n "$pid" ] || return 1
  kill -0 "$pid" 2>/dev/null || return 1
  cmd="$(pid_command "$pid")"
  [ -n "$cmd" ] || return 0
  case "$cmd" in
    *"$script_name"*) return 0 ;;
    *) return 1 ;;
  esac
}

is_watchdog_pid() {
  is_pid_for_script "$1" "task-watcher-watchdog.sh"
}

is_watcher_pid() {
  is_pid_for_script "$1" "task-watcher.sh"
}

ensure_watchdog_single_instance() {
  local existing_pid=""
  existing_pid=$(cat "$WATCHDOG_PID_FILE" 2>/dev/null || true)
  if [ -n "$existing_pid" ] && [ "$existing_pid" != "$$" ]; then
    if is_watchdog_pid "$existing_pid"; then
      printf "%s\n" "$(date '+%Y-%m-%d %H:%M:%S') task-watcher-watchdog 已在运行（pid=$existing_pid），当前实例退出" >&2
      exit 0
    fi
    rm -f "$WATCHDOG_PID_FILE"
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

shutdown_watchdog() {
  cleanup_watchdog_runtime
  exit 0
}

trap cleanup_watchdog_runtime EXIT
trap shutdown_watchdog INT TERM
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

heartbeat_pid_matches() {
    local expected_pid="$1"
    python3 - "$HEARTBEAT_FILE" "$expected_pid" <<'PYHEARTBEAT'
import json
import sys
from pathlib import Path
path = Path(sys.argv[1])
expected = str(sys.argv[2])
if not path.exists():
    raise SystemExit(0)
try:
    payload = json.loads(path.read_text(encoding='utf-8'))
except Exception:
    raise SystemExit(0)
actual = payload.get('pid')
if actual is None or str(actual) == expected:
    raise SystemExit(0)
raise SystemExit(1)
PYHEARTBEAT
}

read_pid() {
    cat "$PID_FILE" 2>/dev/null || true
}

read_heartbeat_pid() {
    python3 - "$HEARTBEAT_FILE" <<'PY_HEARTBEAT_PID'
import json
import sys
from pathlib import Path
path = Path(sys.argv[1])
if not path.exists():
    raise SystemExit(0)
try:
    payload = json.loads(path.read_text(encoding='utf-8'))
except Exception:
    raise SystemExit(0)
pid = payload.get('pid')
if pid:
    print(pid)
PY_HEARTBEAT_PID
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

task_watcher_grace_file() {
    local reason="$1"
    printf '%s\n' "$STATE_DIR/task-watcher-watchdog-grace-${reason}.json"
}

task_watcher_grace_active() {
    local reason="$1"
    local grace_file now started_at
    grace_file="$(task_watcher_grace_file "$reason")"
    [ -f "$grace_file" ] || return 1
    started_at=$(python3 - "$grace_file" <<'PY'
import json
import sys
from pathlib import Path
path = Path(sys.argv[1])
try:
    payload = json.loads(path.read_text(encoding='utf-8'))
except Exception:
    raise SystemExit(0)
print(int(payload.get('started_at') or 0))
PY
)
    [ -n "$started_at" ] || return 1
    now=$(date +%s)
    [ $(( now - started_at )) -lt "$HEARTBEAT_PID_MISMATCH_GRACE_SECONDS" ]
}

mark_task_watcher_grace() {
    local reason="$1"
    local grace_file
    grace_file="$(task_watcher_grace_file "$reason")"
    python3 - "$grace_file" "$reason" <<'PY'
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
path = Path(sys.argv[1]).expanduser()
reason = sys.argv[2]
payload = {
    "reason": reason,
    "started_at": int(datetime.now(timezone.utc).timestamp()),
    "started_at_iso": datetime.now(timezone.utc).isoformat(timespec="seconds"),
}
with tempfile.NamedTemporaryFile("w", delete=False, dir=str(path.parent), encoding="utf-8") as tmp:
    json.dump(payload, tmp, ensure_ascii=False, indent=2)
    tmp.write("\n")
tmp_path = Path(tmp.name)
os.replace(tmp_path, path)
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
    if [ -z "$pid" ] || ! is_watcher_pid "$pid"; then
        [ -n "$pid" ] && rm -f "$PID_FILE"
        local heartbeat_pid=""
        heartbeat_pid="$(read_heartbeat_pid 2>/dev/null || true)"
        if [ -n "$heartbeat_pid" ] && is_watcher_pid "$heartbeat_pid"; then
            printf '%s
' "$heartbeat_pid" > "$PID_FILE"
            pid="$heartbeat_pid"
            log "watchdog 已采用 heartbeat 中的 task-watcher pid=$pid"
        else
            log "watchdog 检测到 task-watcher 未运行或 pid 失效"
            start_watcher "process_exit"
            return
        fi
    fi

    if ! heartbeat_pid_matches "$pid"; then
        if task_watcher_grace_active "heartbeat_pid_mismatch"; then
            log "watchdog 检测到 heartbeat pid 与 pid 文件不一致，但仍在宽限期内，暂不重启"
            return
        fi
        log "watchdog 检测到 heartbeat pid 与 pid 文件不一致"
        mark_task_watcher_grace "heartbeat_pid_mismatch"
        stop_watcher "$pid" "heartbeat_pid_mismatch"
        start_watcher "heartbeat_pid_mismatch"
        return
    fi

    if [ ! -f "$HEARTBEAT_FILE" ]; then
        if task_watcher_grace_active "heartbeat_missing"; then
            log "watchdog 检测到 heartbeat 暂时缺失，但仍在宽限期内，暂不重启"
            return
        fi
        mark_task_watcher_grace "heartbeat_missing"
        stop_watcher "$pid" "heartbeat_missing"
        start_watcher "heartbeat_missing"
        return
    fi

    local heartbeat_ts
    if ! heartbeat_ts=$(read_heartbeat_ts 2>/dev/null); then
        if task_watcher_grace_active "heartbeat_invalid"; then
            log "watchdog 检测到 heartbeat 暂时无效，但仍在宽限期内，暂不重启"
            return
        fi
        mark_task_watcher_grace "heartbeat_invalid"
        stop_watcher "$pid" "heartbeat_invalid"
        start_watcher "heartbeat_invalid"
        return
    fi

    local now age
    now=$(date +%s)
    age=$((now - heartbeat_ts))
    if [ "$age" -gt "$HEARTBEAT_TIMEOUT_SECONDS" ]; then
        if task_watcher_grace_active "heartbeat_timeout"; then
            log "watchdog 检测到 heartbeat 超时，但仍在宽限期内，暂不重启"
            return
        fi
        mark_task_watcher_grace "heartbeat_timeout"
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
