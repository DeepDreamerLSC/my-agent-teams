#!/bin/bash
# task_watcher_runtime.sh - task-watcher runtime, logging, migration, and singleton helpers.
#
# This module is sourced by scripts/task-watcher.sh and is not executable on its own.
# Required variables from the parent script include SCRIPT_DIR, WORKSPACE_ROOT,
# STATE_DIR, LOG_DIR, LOG_FILE, WATCHER_STDOUT_LOG, TASK_WATCHER_TEST_MODE,
# PID_FILE, HEARTBEAT_FILE, INTERVAL, LOG_RETENTION_DAYS,
# LEGACY_STATE_DIR, LEGACY_LOG_DIR, LEGACY_PROJECT_OMX_STATE_DIR,
# LEGACY_PROJECT_OMX_LOG_DIR, and MIGRATION_SENTINEL_FILE.

ensure_stdout_log_compat() {
    local compat_stdout_log="$STATE_DIR/task-watcher.stdout.log"
    [ "$WATCHER_STDOUT_LOG" = "$compat_stdout_log" ] && return 0
    mkdir -p "$(dirname "$compat_stdout_log")" "$(dirname "$WATCHER_STDOUT_LOG")"
    rm -f "$compat_stdout_log" 2>/dev/null || true
    ln -s "$WATCHER_STDOUT_LOG" "$compat_stdout_log" 2>/dev/null || printf 'redirected to %s\n' "$WATCHER_STDOUT_LOG" > "$compat_stdout_log"
}

redirect_stdout_log_if_needed() {
    [ "$TASK_WATCHER_TEST_MODE" = "1" ] && return 0
    [ "${TASK_WATCHER_STDOUT_REDIRECTED:-0}" = "1" ] && return 0
    export TASK_WATCHER_STDOUT_REDIRECTED=1
    exec >> "$WATCHER_STDOUT_LOG" 2>&1
}

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
    if [ "${TASK_WATCHER_STDOUT_REDIRECTED:-0}" != "1" ]; then
        echo "$line"
    fi
    rotate_watcher_log_if_needed
    printf '%s\n' "$line" >> "$LOG_FILE" 2>/dev/null || true
}

pid_command() {
    local pid="$1"
    ps -p "$pid" -o command= 2>/dev/null || true
}

is_task_watcher_pid() {
    local pid="$1" cmd=""
    [ -n "$pid" ] || return 1
    kill -0 "$pid" 2>/dev/null || return 1
    cmd="$(pid_command "$pid")"
    [ -n "$cmd" ] || return 0
    case "$cmd" in
        *"$SCRIPT_DIR/task-watcher.sh"*|*"task-watcher.sh"*) return 0 ;;
        *) return 1 ;;
    esac
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

ensure_single_instance() {
    local existing_pid=""
    existing_pid=$(cat "$PID_FILE" 2>/dev/null || true)
    if [ -n "$existing_pid" ] && [ "$existing_pid" != "$$" ]; then
        if is_task_watcher_pid "$existing_pid"; then
            log "task-watcher 已在运行（pid=$existing_pid），当前实例退出"
            exit 0
        fi
        log "清理失效 task-watcher pid 文件（pid=$existing_pid）"
        rm -f "$PID_FILE"
    fi

    local heartbeat_pid=""
    heartbeat_pid="$(read_heartbeat_pid 2>/dev/null || true)"
    if [ -n "$heartbeat_pid" ] && [ "$heartbeat_pid" != "$$" ] && is_task_watcher_pid "$heartbeat_pid"; then
        log "task-watcher 已在运行（heartbeat pid=$heartbeat_pid），修正 pid 文件并退出当前实例"
        printf '%s
' "$heartbeat_pid" > "$PID_FILE"
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
