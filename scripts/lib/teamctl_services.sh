#!/bin/bash
# teamctl_services.sh - runtime command, PID, watcher/dashboard/gateway service helpers for teamctl.
#
# Sourced by scripts/teamctl.sh. Depends on parent variables SCRIPT_DIR,
# WORKSPACE_ROOT, CONFIG_PATH, TASKS_ROOT, STATE_DIR, LOG_DIR,
# WATCHER_INTERVAL, DASHBOARD_HOST, DASHBOARD_PORT, CODEX_GATEWAY_* and
# parent helper functions log, warn, err, need_cmd, workspace_python,
# ensure_runtime_dirs.

runtime_command() {
  local runtime="$1"
  case "$runtime" in
    claude_code) printf '%s' "${CLAUDE_CMD:-claude}" ;;
    codex) printf '%s' "${CODEX_CMD:-codex}" ;;
    *) printf '%s' "${AGENT_CMD:-$runtime}" ;;
  esac
}

runtime_command_executable() {
  local command_line="$1"
  python3 - "$command_line" <<'PY'
import shlex
import sys

try:
    parts = shlex.split(sys.argv[1])
except ValueError:
    parts = []
print(parts[0] if parts else "")
PY
}

pid_command() {
  local pid="$1"
  ps -p "$pid" -o command= 2>/dev/null || true
}

pid_matches_label() {
  local pid="$1" label="$2" cmd=""
  [ -n "$pid" ] || return 1
  kill -0 "$pid" 2>/dev/null || return 1
  cmd="$(pid_command "$pid")"
  [ -n "$cmd" ] || return 0
  case "$label:$cmd" in
    task-watcher-watchdog:*task-watcher-watchdog.sh*) return 0 ;;
    task-watcher:*task-watcher.sh*) return 0 ;;
    dashboard:*dashboard.app*) return 0 ;;
    codex-responses-gateway:*codex-responses-gateway.py*) return 0 ;;
    *:*) return 1 ;;
  esac
}

pid_file_running() {
  local pid_file="$1" label="${2:-}" pid=""
  pid="$(cat "$pid_file" 2>/dev/null || true)"
  [ -n "$pid" ] || return 1
  if [ -n "$label" ]; then
    pid_matches_label "$pid" "$label"
  else
    kill -0 "$pid" 2>/dev/null
  fi
}

read_task_watcher_heartbeat_pid() {
  python3 - "$STATE_DIR/task-watcher/task-watcher-heartbeat.json" <<'PY_HEARTBEAT_PID'
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

watcher_running() {
  local heartbeat_pid=""
  heartbeat_pid="$(read_task_watcher_heartbeat_pid 2>/dev/null || true)"
  pid_file_running "$STATE_DIR/task-watcher/task-watcher-watchdog.pid" task-watcher-watchdog ||     pid_file_running "$STATE_DIR/task-watcher/task-watcher.pid" task-watcher ||     { [ -n "$heartbeat_pid" ] && pid_matches_label "$heartbeat_pid" task-watcher; }
}

dashboard_running() {
  pid_file_running "$STATE_DIR/task-board.pid"
}

codex_gateway_running() {
  pid_file_running "$STATE_DIR/codex-responses-gateway.pid"
}

confirm_agent_tmux_action() {
  local action_label="$1" phrase="$2"
  if [ ! -t 0 ] || [ ! -t 1 ]; then
    err "$action_label 只能在交互式终端中执行，并需要人工输入确认短语：$phrase"
    return 1
  fi
  printf '%s\n' "危险操作：即将对 config 中声明的全部 agent tmux session 执行：$action_label"
  printf '%s\n' "当前会受影响的 session："
  agent_rows | while IFS=$'\t' read -r agent_id session runtime workdir guidance; do
    [ -n "$agent_id" ] || continue
    printf '  - %-10s session=%s runtime=%s\n' "$agent_id" "$session" "$runtime"
  done
  printf '%s ' "这会中断所有 agent 当前会话。输入 $phrase 后回车继续："
  local answer=""
  read -r answer
  if [ "$answer" != "$phrase" ]; then
    err "确认短语不匹配，已取消操作"
    return 1
  fi
}

confirm_stop_agents() {
  confirm_agent_tmux_action "stop-agents" "STOP-ALL-TMUX-AGENTS"
}

confirm_restart_agents() {
  confirm_agent_tmux_action "restart-agents" "RESTART-ALL-TMUX-AGENTS"
}

start_agents() {
  local cmd=""
  local cmd_exec=""
  if [ "$START_FORCE" = "1" ]; then
    err "start-agents --force 会重建全部 tmux agent session；请改用 scripts/teamctl.sh restart-agents，并在交互式终端完成人工确认"
    return 1
  fi
  agent_rows | while IFS=$'\t' read -r agent_id session runtime workdir guidance; do
    [ -n "$agent_id" ] || continue
    mkdir -p "$workdir"
    if tmux has-session -t "$session" 2>/dev/null; then
      log "session exists, skip: $session"
      continue
    fi
    cmd="$(runtime_command "$runtime")"
    cmd_exec="$(runtime_command_executable "$cmd")"
    if [ -z "$cmd_exec" ] || ! need_cmd "$cmd_exec"; then
      warn "command not found for $agent_id runtime=$runtime: $cmd; creating shell session only"
      tmux new-session -d -s "$session" -c "$workdir"
    else
      tmux new-session -d -s "$session" -c "$workdir" "exec $cmd"
    fi
    log "started $agent_id session=$session runtime=$runtime workdir=$workdir"
  done
  if [ "$START_ATTACH" = "1" ]; then
    local attach_session
    attach_session="$(agent_rows | head -1 | cut -f2)"
    [ -n "$attach_session" ] && exec tmux attach -t "$attach_session"
  fi
}

stop_agents_internal() {
  agent_rows | while IFS=$'\t' read -r agent_id session runtime workdir guidance; do
    [ -n "$agent_id" ] || continue
    if tmux has-session -t "$session" 2>/dev/null; then
      tmux kill-session -t "$session"
      log "stopped $session"
    fi
  done
}

stop_agents() {
  confirm_stop_agents || return 1
  stop_agents_internal
}

restart_agents() {
  confirm_restart_agents || return 1
  stop_agents_internal
  start_agents
}

start_watcher() {
  ensure_runtime_dirs
  local watcher_pid_file="$STATE_DIR/task-watcher/task-watcher.pid"
  local watchdog_pid_file="$STATE_DIR/task-watcher/task-watcher-watchdog.pid"
  local standalone_pid=""
  if [ -f "$watchdog_pid_file" ]; then
    pid="$(cat "$watchdog_pid_file" 2>/dev/null || true)"
    if [ -n "$pid" ] && pid_matches_label "$pid" task-watcher-watchdog; then
      log "task-watcher watchdog already running pid=$pid"
      return 0
    elif [ -n "$pid" ]; then
      rm -f "$watchdog_pid_file"
    fi
  fi
  if [ -f "$watcher_pid_file" ]; then
    pid="$(cat "$watcher_pid_file" 2>/dev/null || true)"
    if [ -n "$pid" ] && pid_matches_label "$pid" task-watcher; then
      standalone_pid="$pid"
      log "detected standalone task-watcher pid=$pid; starting watchdog to take over supervision"
    elif [ -n "$pid" ]; then
      rm -f "$watcher_pid_file"
    fi
  fi
  WORKSPACE_ROOT="$WORKSPACE_ROOT" CONFIG_PATH="$CONFIG_PATH" TASKS_ROOT="$TASKS_ROOT" INTERVAL="$WATCHER_INTERVAL" \
    nohup "$SCRIPT_DIR/task-watcher-watchdog.sh" >> "$LOG_DIR/task-watcher.nohup.log" 2>&1 &
  if [ -n "$standalone_pid" ]; then
    log "task-watcher watchdog started pid=$! and will supervise existing watcher pid=$standalone_pid log=$LOG_DIR/task-watcher.nohup.log"
  else
    log "task-watcher watchdog started pid=$! log=$LOG_DIR/task-watcher.nohup.log"
  fi
}

stop_pid_file() {
  local pid_file="$1" label="$2"
  local pid=""
  pid="$(cat "$pid_file" 2>/dev/null || true)"
  if [ -n "$pid" ] && pid_matches_label "$pid" "$label"; then
    kill "$pid" 2>/dev/null || true
    for _ in {1..20}; do
      kill -0 "$pid" 2>/dev/null || break
      sleep 0.25
    done
    if kill -0 "$pid" 2>/dev/null; then
      warn "$label still running after TERM pid=$pid"
      return 1
    fi
    if [ "$(cat "$pid_file" 2>/dev/null || true)" = "$pid" ]; then
      rm -f "$pid_file"
    fi
    log "stopped $label pid=$pid"
  else
    warn "$label not running"
    if [ -f "$pid_file" ] && [ -n "$pid" ]; then
      rm -f "$pid_file"
    fi
  fi
}

stop_watcher() {
  local rc=0 heartbeat_pid=""
  stop_pid_file "$STATE_DIR/task-watcher/task-watcher-watchdog.pid" task-watcher-watchdog || rc=1
  stop_pid_file "$STATE_DIR/task-watcher/task-watcher.pid" task-watcher || rc=1
  heartbeat_pid="$(read_task_watcher_heartbeat_pid 2>/dev/null || true)"
  if [ -n "$heartbeat_pid" ] && pid_matches_label "$heartbeat_pid" task-watcher; then
    kill "$heartbeat_pid" 2>/dev/null || true
    log "stopped task-watcher heartbeat pid=$heartbeat_pid"
  fi
  return "$rc"
}

restart_managed_service() {
  local label="$1" running_fn="$2" stop_fn="$3" start_fn="$4"
  if "$running_fn"; then
    log "restarting $label"
    "$stop_fn" || warn "$label stop returned non-zero; will still attempt start"
    "$start_fn"
    return $?
  fi
  if [ "$START_FORCE" = "1" ]; then
    log "$label not running; starting because --force was provided"
    "$start_fn"
    return $?
  fi
  log "$label not running; skip（如需拉起未运行服务，请单独执行 start-* 或加 --force）"
  return 0
}

start_dashboard() {
  ensure_runtime_dirs
  local pid_file="$STATE_DIR/task-board.pid"
  local pid="$(cat "$pid_file" 2>/dev/null || true)"
  local python_bin
  python_bin="$(workspace_python)"
  if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
    log "dashboard already running pid=$pid"
    return 0
  fi
  pid="$(
    WORKSPACE_ROOT="$WORKSPACE_ROOT" \
    LOG_DIR="$LOG_DIR" \
    DASHBOARD_PYTHON="$python_bin" \
    TASK_BOARD_HOST="$DASHBOARD_HOST" \
    TASK_BOARD_PORT="$DASHBOARD_PORT" \
    TASK_BOARD_DB_PATH="${TASK_BOARD_DB_PATH:-$WORKSPACE_ROOT/.omx/task-board/task-board.sqlite3}" \
    python3 - <<'PY'
import os
import subprocess
import sys

workspace_root = os.environ['WORKSPACE_ROOT']
log_dir = os.environ['LOG_DIR']
python_bin = os.environ['DASHBOARD_PYTHON']
env = os.environ.copy()
log_path = os.path.join(log_dir, 'task-board.log')

with open(log_path, 'ab', buffering=0) as log_fp:
    proc = subprocess.Popen(
        [python_bin, '-m', 'dashboard.app'],
        cwd=workspace_root,
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=log_fp,
        stderr=subprocess.STDOUT,
        start_new_session=True,
        close_fds=True,
    )

print(proc.pid)
PY
  )"
  printf '%s\n' "$pid" > "$pid_file"
  sleep 1
  if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
    log "dashboard started pid=$pid python=$python_bin url=http://$DASHBOARD_HOST:$DASHBOARD_PORT/"
    return 0
  fi
  rm -f "$pid_file"
  err "dashboard failed to start; see $LOG_DIR/task-board.log"
  tail -n 40 "$LOG_DIR/task-board.log" >&2 || true
  return 1
}

stop_dashboard() {
  stop_pid_file "$STATE_DIR/task-board.pid" dashboard
}

init_codex_gateway_config() {
  local example="$WORKSPACE_ROOT/config/codex-responses-gateway.example.json"
  if [ -f "$CODEX_GATEWAY_CONFIG" ]; then
    log "Codex gateway config exists: $CODEX_GATEWAY_CONFIG"
    return 0
  fi
  if [ ! -f "$example" ]; then
    err "missing example config: $example"
    return 1
  fi
  mkdir -p "$(dirname "$CODEX_GATEWAY_CONFIG")"
  cp "$example" "$CODEX_GATEWAY_CONFIG"
  chmod 600 "$CODEX_GATEWAY_CONFIG" 2>/dev/null || true
  log "created Codex gateway config: $CODEX_GATEWAY_CONFIG"
  warn "set OPENAI_API_KEY and CODEX_GATEWAY_API_KEY before starting the gateway"
}

start_codex_gateway() {
  ensure_runtime_dirs
  if [ ! -f "$CODEX_GATEWAY_CONFIG" ]; then
    init_codex_gateway_config
  fi
  python3 "$SCRIPT_DIR/codex-responses-gateway.py" check-config --config "$CODEX_GATEWAY_CONFIG" >/dev/null
  local pid_file="$STATE_DIR/codex-responses-gateway.pid"
  local pid="$(cat "$pid_file" 2>/dev/null || true)"
  if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
    log "Codex Responses Gateway already running pid=$pid"
    return 0
  fi
  nohup python3 "$SCRIPT_DIR/codex-responses-gateway.py" serve \
    --config "$CODEX_GATEWAY_CONFIG" \
    --host "$CODEX_GATEWAY_HOST" \
    --port "$CODEX_GATEWAY_PORT" \
    >> "$CODEX_GATEWAY_LOG" 2>&1 &
  echo $! > "$pid_file"
  log "Codex Responses Gateway started pid=$(cat "$pid_file") url=http://$CODEX_GATEWAY_HOST:$CODEX_GATEWAY_PORT/v1"
}

stop_codex_gateway() {
  stop_pid_file "$STATE_DIR/codex-responses-gateway.pid" codex-responses-gateway
}

restart_services() {
  ensure_runtime_dirs
  restart_managed_service task-watcher watcher_running stop_watcher start_watcher
  restart_managed_service dashboard dashboard_running stop_dashboard start_dashboard
  restart_managed_service codex-responses-gateway codex_gateway_running stop_codex_gateway start_codex_gateway
}

install_codex_profile() {
  python3 "$SCRIPT_DIR/install-codex-gateway-profile.py" \
    --gateway-base-url "$CODEX_GATEWAY_PROFILE_BASE_URL" \
    --api-key-env "$CODEX_GATEWAY_API_KEY_ENV"
}
