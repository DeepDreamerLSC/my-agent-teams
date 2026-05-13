#!/bin/bash
# teamctl.sh - 顶层控制脚本：迁移初始化、健康检查、agent 启动、watcher/dashboard 启停。

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_ROOT="${WORKSPACE_ROOT:-$(cd "$SCRIPT_DIR/.." && pwd)}"
CONFIG_PATH="${CONFIG_PATH:-$WORKSPACE_ROOT/config.json}"
CONFIG_LOCAL_PATH="${CONFIG_LOCAL_PATH:-$WORKSPACE_ROOT/config.local.json}"
TASKS_ROOT="${TASKS_ROOT:-$WORKSPACE_ROOT/tasks}"
AGENTS_ROOT="${AGENTS_ROOT:-$WORKSPACE_ROOT/agents}"
RUNTIME_ROOT="${RUNTIME_ROOT:-$WORKSPACE_ROOT/.runtime}"
LOG_DIR="${LOG_DIR:-$RUNTIME_ROOT/logs}"
STATE_DIR="${STATE_DIR:-$RUNTIME_ROOT/state}"
DEFAULT_WORK_PARENT="${DEFAULT_WORK_PARENT:-$(cd "$WORKSPACE_ROOT/.." && pwd)}"
START_ATTACH="${START_ATTACH:-0}"
START_FORCE="${START_FORCE:-0}"
RENDER_CONFIG="${RENDER_CONFIG:-0}"
WATCHER_INTERVAL="${WATCHER_INTERVAL:-5}"
DASHBOARD_HOST="${TASK_BOARD_HOST:-127.0.0.1}"
DASHBOARD_PORT="${TASK_BOARD_PORT:-5001}"

usage() {
  cat <<EOF_USAGE
usage: scripts/teamctl.sh <command> [options]

Commands:
  bootstrap       初始化本机目录、config.local、agent 文件、tasks symlink、看板库
  doctor          检查迁移就绪度和运行依赖
  start-agents    按 config 创建 tmux session 并进入 agent workdir 启动 CLI
  stop-agents     停止 config 中声明的 agent tmux session
  start-watcher   后台启动 task-watcher
  stop-watcher    停止 task-watcher
  start-dashboard 后台启动任务看板
  stop-dashboard  停止任务看板
  smoke           做轻量 smoke：脚本语法、Python 编译、agent 文件 dry-run
  status          输出关键运行状态

Options:
  --attach        start-agents 创建后自动 attach 第一个 session
  --force         start-agents/stop-agents 跳过部分保护或重建已有 session
  --render-config bootstrap 时按当前 checkout 重写 config.json 本机路径
  -h, --help      显示帮助

Environment overrides:
  WORKSPACE_ROOT, CONFIG_PATH, CONFIG_LOCAL_PATH, TASKS_ROOT, AGENTS_ROOT,
  DEFAULT_WORK_PARENT, CODEX_CMD, CLAUDE_CMD, START_ATTACH=1, START_FORCE=1
EOF_USAGE
}

log() { printf '[teamctl] %s\n' "$*"; }
warn() { printf '[teamctl][WARN] %s\n' "$*" >&2; }
err() { printf '[teamctl][ERROR] %s\n' "$*" >&2; }

need_cmd() {
  command -v "$1" >/dev/null 2>&1
}

agent_rows() {
  python3 - "$CONFIG_PATH" "$WORKSPACE_ROOT" "$AGENTS_ROOT" <<'PY'
import json
import sys
from pathlib import Path

config_path = Path(sys.argv[1]).expanduser()
workspace = Path(sys.argv[2]).expanduser().resolve()
agents_root = Path(sys.argv[3]).expanduser().resolve()
if not config_path.exists():
    raise SystemExit(1)
config = json.loads(config_path.read_text(encoding='utf-8'))
for agent_id, payload in (config.get('agents') or {}).items():
    payload = payload or {}
    session = str(payload.get('tmux_session') or agent_id)
    runtime = str(payload.get('runtime') or 'codex')
    workdir_raw = str(payload.get('workdir') or agents_root / agent_id)
    workdir = Path(workdir_raw).expanduser()
    if not workdir.is_absolute():
        workdir = workspace / workdir
    # If config was generated on another machine but uses the conventional path,
    # prefer this checkout's agents/<id> when it exists or can be created.
    if '/my-agent-teams/agents/' in workdir_raw and not str(workdir).startswith(str(workspace)):
        workdir = agents_root / agent_id
    guidance = str(payload.get('guidance_file') or ('CLAUDE.md' if runtime == 'claude_code' else 'AGENT.md'))
    print('\t'.join([agent_id, session, runtime, str(workdir), guidance]))
PY
}

ensure_runtime_dirs() {
  mkdir -p "$TASKS_ROOT" "$AGENTS_ROOT" "$LOG_DIR" "$STATE_DIR" "$WORKSPACE_ROOT/.omx/task-board" "$WORKSPACE_ROOT/chat/general" "$WORKSPACE_ROOT/chat/tasks"
}

ensure_config_local() {
  if [ -f "$CONFIG_LOCAL_PATH" ]; then
    log "config.local exists: $CONFIG_LOCAL_PATH"
    return 0
  fi
  if [ -f "$WORKSPACE_ROOT/config.local.example.json" ]; then
    cp "$WORKSPACE_ROOT/config.local.example.json" "$CONFIG_LOCAL_PATH"
    chmod 600 "$CONFIG_LOCAL_PATH" 2>/dev/null || true
    log "created config.local from example: $CONFIG_LOCAL_PATH"
  else
    cat > "$CONFIG_LOCAL_PATH" <<'JSON'
{
  "notifications": {
    "feishu_receive_id": "ou_xxx",
    "feishu_app_id": "cli_xxx",
    "feishu_app_secret": "replace-with-local-secret"
  }
}
JSON
    chmod 600 "$CONFIG_LOCAL_PATH" 2>/dev/null || true
    log "created minimal config.local: $CONFIG_LOCAL_PATH"
  fi
}

ensure_agent_dirs_and_links() {
  agent_rows | while IFS=$'\t' read -r agent_id session runtime workdir guidance; do
    [ -n "$agent_id" ] || continue
    mkdir -p "$workdir"
    local_link="$workdir/tasks"
    if [ -L "$local_link" ] || [ -e "$local_link" ]; then
      if [ -L "$local_link" ]; then
        :
      else
        warn "$local_link exists and is not a symlink; left untouched"
        continue
      fi
    fi
    if [ ! -e "$local_link" ]; then
      ln -s ../../tasks "$local_link" 2>/dev/null || ln -s "$TASKS_ROOT" "$local_link" || true
    fi
  done
}

build_agent_files() {
  WORKSPACE_ROOT="$WORKSPACE_ROOT" CONFIG_PATH="$CONFIG_PATH" "$SCRIPT_DIR/build-agent-files.sh"
}

init_dashboard_db() {
  if [ -f "$SCRIPT_DIR/task-board-sync.py" ]; then
    PYTHONPYCACHEPREFIX="${PYTHONPYCACHEPREFIX:-/tmp/my-agent-teams-pycache}" \
      TASK_BOARD_DB_PATH="${TASK_BOARD_DB_PATH:-$WORKSPACE_ROOT/.omx/task-board/task-board.sqlite3}" \
      python3 "$SCRIPT_DIR/task-board-sync.py" backfill --tasks-root "$TASKS_ROOT" --source bootstrap >/dev/null 2>&1 || \
      warn "dashboard backfill failed; run doctor for details"
  fi
}

render_config_if_requested() {
  [ "$RENDER_CONFIG" = "1" ] || return 0
  if [ ! -x "$SCRIPT_DIR/render-local-config.py" ]; then
    warn "render-local-config.py not found; skip config render"
    return 0
  fi
  python3 "$SCRIPT_DIR/render-local-config.py" \
    --input "$CONFIG_PATH" \
    --output "$CONFIG_PATH" \
    --workspace-root "$WORKSPACE_ROOT" \
    --work-parent "$DEFAULT_WORK_PARENT"
}

bootstrap() {
  ensure_runtime_dirs
  render_config_if_requested
  ensure_config_local
  ensure_agent_dirs_and_links
  build_agent_files
  init_dashboard_db
  log "bootstrap complete: $WORKSPACE_ROOT"
}

check_file() {
  local label="$1" path="$2"
  if [ -e "$path" ]; then
    printf 'PASS %-24s %s\n' "$label" "$path"
    return 0
  fi
  printf 'FAIL %-24s %s\n' "$label" "$path"
  return 1
}

check_cmd() {
  local cmd="$1" required="${2:-required}"
  if need_cmd "$cmd"; then
    printf 'PASS cmd %-20s %s\n' "$cmd" "$(command -v "$cmd")"
    return 0
  fi
  if [ "$required" = "optional" ]; then
    printf 'WARN cmd %-20s missing optional\n' "$cmd"
    return 0
  fi
  printf 'FAIL cmd %-20s missing\n' "$cmd"
  return 1
}

check_config_paths() {
  python3 - "$CONFIG_PATH" "$WORKSPACE_ROOT" <<'PY'
import json
import sys
from pathlib import Path

config_path = Path(sys.argv[1]).expanduser()
workspace = Path(sys.argv[2]).expanduser().resolve()
if not config_path.exists():
    print(f'FAIL config missing {config_path}')
    raise SystemExit(1)
config = json.loads(config_path.read_text(encoding='utf-8'))
status = 0
for key in ['workspace_root', 'tasks_root', 'scripts_root', 'agents_root']:
    raw = str(config.get(key) or config.get('shared_paths', {}).get(key) or '')
    if not raw:
        print(f'WARN config {key} empty')
        continue
    if raw.startswith(str(workspace)) or raw == str(workspace) or '/my-agent-teams' in raw:
        print(f'INFO config {key}={raw}')
    else:
        print(f'WARN config {key} may be machine-specific: {raw}')
for project, payload in (config.get('projects') or {}).items():
    dev_root = Path(str((payload or {}).get('dev_root') or '')).expanduser()
    if dev_root and dev_root.exists():
        print(f'PASS project {project}.dev_root {dev_root}')
    else:
        print(f'WARN project {project}.dev_root missing {dev_root}')
print('PASS config parse')
PY
}

doctor() {
  local rc=0
  check_cmd python3 || rc=1
  check_cmd tmux || rc=1
  check_cmd jq optional || true
  check_cmd curl optional || true
  check_cmd node optional || true
  check_cmd codex optional || true
  check_cmd claude optional || true
  check_file repo "$WORKSPACE_ROOT/README.md" || rc=1
  check_file config "$CONFIG_PATH" || rc=1
  check_file config.local "$CONFIG_LOCAL_PATH" || true
  check_file scripts "$SCRIPT_DIR/create-task.sh" || rc=1
  check_file templates "$WORKSPACE_ROOT/design/agent-templates/base.md" || rc=1
  check_config_paths || rc=1
  agent_rows | while IFS=$'\t' read -r agent_id session runtime workdir guidance; do
    [ -n "$agent_id" ] || continue
    check_file "agent:$agent_id" "$workdir/$guidance" || true
    if tmux has-session -t "$session" 2>/dev/null; then
      printf 'PASS tmux %-21s running\n' "$session"
    else
      printf 'WARN tmux %-21s not running\n' "$session"
    fi
  done
  if [ -x "$SCRIPT_DIR/build-agent-files.sh" ]; then
    WORKSPACE_ROOT="$WORKSPACE_ROOT" CONFIG_PATH="$CONFIG_PATH" "$SCRIPT_DIR/build-agent-files.sh" --dry-run >/dev/null || rc=1
    [ "$rc" = 0 ] && printf 'PASS agent generation dry-run\n'
  fi
  return "$rc"
}

runtime_command() {
  local runtime="$1"
  case "$runtime" in
    claude_code) printf '%s' "${CLAUDE_CMD:-claude}" ;;
    codex) printf '%s' "${CODEX_CMD:-codex}" ;;
    *) printf '%s' "${AGENT_CMD:-$runtime}" ;;
  esac
}

start_agents() {
  agent_rows | while IFS=$'\t' read -r agent_id session runtime workdir guidance; do
    [ -n "$agent_id" ] || continue
    mkdir -p "$workdir"
    if tmux has-session -t "$session" 2>/dev/null; then
      if [ "$START_FORCE" = "1" ]; then
        tmux kill-session -t "$session"
      else
        log "session exists, skip: $session"
        continue
      fi
    fi
    cmd="$(runtime_command "$runtime")"
    if ! need_cmd "$cmd"; then
      warn "command not found for $agent_id runtime=$runtime: $cmd; creating shell session only"
      tmux new-session -d -s "$session" -c "$workdir"
    else
      tmux new-session -d -s "$session" -c "$workdir" "$cmd"
    fi
    log "started $agent_id session=$session runtime=$runtime workdir=$workdir"
  done
  if [ "$START_ATTACH" = "1" ]; then
    local attach_session
    attach_session="$(agent_rows | head -1 | cut -f2)"
    [ -n "$attach_session" ] && exec tmux attach -t "$attach_session"
  fi
}

stop_agents() {
  agent_rows | while IFS=$'\t' read -r agent_id session runtime workdir guidance; do
    [ -n "$agent_id" ] || continue
    if tmux has-session -t "$session" 2>/dev/null; then
      tmux kill-session -t "$session"
      log "stopped $session"
    fi
  done
}

start_watcher() {
  ensure_runtime_dirs
  if [ -f "$STATE_DIR/task-watcher/task-watcher.pid" ]; then
    pid="$(cat "$STATE_DIR/task-watcher/task-watcher.pid" 2>/dev/null || true)"
    if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
      log "task-watcher already running pid=$pid"
      return 0
    fi
  fi
  WORKSPACE_ROOT="$WORKSPACE_ROOT" CONFIG_PATH="$CONFIG_PATH" TASKS_ROOT="$TASKS_ROOT" INTERVAL="$WATCHER_INTERVAL" \
    nohup "$SCRIPT_DIR/task-watcher.sh" >> "$LOG_DIR/task-watcher.nohup.log" 2>&1 &
  log "task-watcher started pid=$! log=$LOG_DIR/task-watcher.nohup.log"
}

stop_pid_file() {
  local pid_file="$1" label="$2"
  local pid=""
  pid="$(cat "$pid_file" 2>/dev/null || true)"
  if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
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
  stop_pid_file "$STATE_DIR/task-watcher/task-watcher.pid" task-watcher
}

start_dashboard() {
  ensure_runtime_dirs
  local pid_file="$STATE_DIR/task-board.pid"
  local pid="$(cat "$pid_file" 2>/dev/null || true)"
  if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
    log "dashboard already running pid=$pid"
    return 0
  fi
  (cd "$WORKSPACE_ROOT" && \
    TASK_BOARD_HOST="$DASHBOARD_HOST" TASK_BOARD_PORT="$DASHBOARD_PORT" \
    TASK_BOARD_DB_PATH="${TASK_BOARD_DB_PATH:-$WORKSPACE_ROOT/.omx/task-board/task-board.sqlite3}" \
    nohup python3 -m dashboard.app >> "$LOG_DIR/task-board.log" 2>&1 & echo $! > "$pid_file")
  log "dashboard started pid=$(cat "$pid_file") url=http://$DASHBOARD_HOST:$DASHBOARD_PORT/"
}

stop_dashboard() {
  stop_pid_file "$STATE_DIR/task-board.pid" dashboard
}

smoke() {
  local rc=0
  for f in "$SCRIPT_DIR"/*.sh; do
    bash -n "$f" || rc=1
  done
  PYTHONPYCACHEPREFIX="${PYTHONPYCACHEPREFIX:-/tmp/my-agent-teams-pycache}" \
    python3 -m compileall -q "$SCRIPT_DIR" "$WORKSPACE_ROOT/dashboard" "$WORKSPACE_ROOT/tests" || rc=1
  WORKSPACE_ROOT="$WORKSPACE_ROOT" CONFIG_PATH="$CONFIG_PATH" "$SCRIPT_DIR/build-agent-files.sh" --dry-run >/dev/null || rc=1
  if [ "$rc" = 0 ]; then
    log "smoke passed"
  else
    err "smoke failed"
  fi
  return "$rc"
}

status_cmd() {
  echo "workspace: $WORKSPACE_ROOT"
  echo "config:    $CONFIG_PATH"
  echo "tasks:     $TASKS_ROOT"
  echo "runtime:   $RUNTIME_ROOT"
  echo "agents:"
  agent_rows | while IFS=$'\t' read -r agent_id session runtime workdir guidance; do
    [ -n "$agent_id" ] || continue
    if tmux has-session -t "$session" 2>/dev/null; then state=running; else state=stopped; fi
    printf '  - %-10s session=%-12s runtime=%-12s state=%-8s workdir=%s\n' "$agent_id" "$session" "$runtime" "$state" "$workdir"
  done
}

COMMAND="${1:-}"
if [ -z "$COMMAND" ]; then
  usage >&2
  exit 2
fi
shift || true
while [ $# -gt 0 ]; do
  case "$1" in
    --attach) START_ATTACH=1; shift ;;
    --force) START_FORCE=1; shift ;;
    --render-config) RENDER_CONFIG=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) err "unknown option: $1"; usage >&2; exit 2 ;;
  esac
done

case "$COMMAND" in
  bootstrap) bootstrap ;;
  doctor) doctor ;;
  start-agents) start_agents ;;
  stop-agents) stop_agents ;;
  start-watcher) start_watcher ;;
  stop-watcher) stop_watcher ;;
  start-dashboard) start_dashboard ;;
  stop-dashboard) stop_dashboard ;;
  smoke) smoke ;;
  status) status_cmd ;;
  -h|--help|help) usage ;;
  *) err "unknown command: $COMMAND"; usage >&2; exit 2 ;;
esac
