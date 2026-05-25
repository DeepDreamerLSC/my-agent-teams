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
TEAM_SIZE="${TEAM_SIZE:-}"
WATCHER_INTERVAL="${WATCHER_INTERVAL:-5}"
DASHBOARD_HOST="${TASK_BOARD_HOST:-127.0.0.1}"
DASHBOARD_PORT="${TASK_BOARD_PORT:-5001}"
CODEX_GATEWAY_CONFIG="${CODEX_GATEWAY_CONFIG:-$WORKSPACE_ROOT/config/codex-responses-gateway.json}"
CODEX_GATEWAY_HOST="${CODEX_GATEWAY_HOST:-127.0.0.1}"
CODEX_GATEWAY_PORT="${CODEX_GATEWAY_PORT:-8787}"
CODEX_GATEWAY_LOG="${CODEX_GATEWAY_LOG:-$LOG_DIR/codex-responses-gateway.log}"
CODEX_GATEWAY_PROFILE_BASE_URL="${CODEX_GATEWAY_PROFILE_BASE_URL:-http://$CODEX_GATEWAY_HOST:$CODEX_GATEWAY_PORT/v1}"
CODEX_GATEWAY_API_KEY_ENV="${CODEX_GATEWAY_API_KEY_ENV:-CODEX_GATEWAY_API_KEY}"

usage() {
  cat <<EOF_USAGE
usage: scripts/teamctl.sh <command> [options]

Commands:
  init            创建 .venv、安装看板依赖，并执行 bootstrap --render-config
  bootstrap       初始化本机目录、config.local、agent 文件、tasks symlink、看板库
  doctor          检查迁移就绪度和运行依赖
  up              启动 agents、watcher、dashboard
  sessions        列出 config 中声明的 agent tmux session
  attach [agent]  进入 agent 对应的 tmux session；不传默认进入第一个 agent
  start-agents    按 config 创建 tmux session 并进入 agent workdir 启动 CLI
  stop-agents     停止 config 中声明的 agent tmux session（危险操作：需要人工确认）
  restart-agents  重启所有 agent tmux session（危险操作：需要人工确认）
  start-watcher   后台启动 task-watcher
  stop-watcher    停止 task-watcher
  start-dashboard 后台启动任务看板
  stop-dashboard  停止任务看板
  restart-services 仅重启当前正在运行的 watcher / dashboard / codex-gateway，不触碰 agent tmux
  init-codex-gateway-config  从示例生成本机 Codex Responses Gateway 配置
  start-codex-gateway        后台启动 Codex Responses Gateway
  stop-codex-gateway         停止 Codex Responses Gateway
  install-codex-profile      写入/更新 ~/.codex/config.toml 托管 profile
  smoke           做轻量 smoke：脚本语法、Python 编译、agent 文件 dry-run
  status          输出关键运行状态

Options:
  --attach        start-agents 创建后自动 attach 第一个 session
  --force         restart-services 在服务当前未运行时也尝试重新拉起
  --team <size>   init/bootstrap --render-config 时选择团队规模：small（默认）/ medium / large
  --render-config bootstrap 时按当前 checkout 重写 config.json 本机路径
  -h, --help      显示帮助

Environment overrides:
  WORKSPACE_ROOT, CONFIG_PATH, CONFIG_LOCAL_PATH, TASKS_ROOT, AGENTS_ROOT,
  DEFAULT_WORK_PARENT, CODEX_CMD, CLAUDE_CMD, START_ATTACH=1, START_FORCE=1,
  TEAM_SIZE=small|medium|large,
  CODEX_GATEWAY_CONFIG, CODEX_GATEWAY_HOST, CODEX_GATEWAY_PORT, CODEX_GATEWAY_API_KEY_ENV
EOF_USAGE
}

log() { printf '[teamctl] %s\n' "$*"; }
warn() { printf '[teamctl][WARN] %s\n' "$*" >&2; }
err() { printf '[teamctl][ERROR] %s\n' "$*" >&2; }

need_cmd() {
  command -v "$1" >/dev/null 2>&1
}

validate_team_size() {
  case "${1:-}" in
    small|medium|large) return 0 ;;
    *) err "invalid team size: ${1:-}; expected small, medium, or large"; return 1 ;;
  esac
}

workspace_python() {
  local venv_python="$WORKSPACE_ROOT/.venv/bin/python"
  if [ -x "$venv_python" ]; then
    printf '%s' "$venv_python"
    return 0
  fi
  printf '%s' "python3"
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
    local python_bin
    python_bin="$(workspace_python)"
    PYTHONPYCACHEPREFIX="${PYTHONPYCACHEPREFIX:-/tmp/my-agent-teams-pycache}" \
      TASK_BOARD_DB_PATH="${TASK_BOARD_DB_PATH:-$WORKSPACE_ROOT/.omx/task-board/task-board.sqlite3}" \
      "$python_bin" "$SCRIPT_DIR/task-board-sync.py" backfill --tasks-root "$TASKS_ROOT" --source bootstrap >/dev/null 2>&1 || \
      warn "dashboard backfill failed; run doctor for details"
  fi
}

render_config_if_requested() {
  [ "$RENDER_CONFIG" = "1" ] || return 0
  if [ ! -x "$SCRIPT_DIR/render-local-config.py" ]; then
    warn "render-local-config.py not found; skip config render"
    return 0
  fi
  local team_args=()
  if [ -n "$TEAM_SIZE" ]; then
    validate_team_size "$TEAM_SIZE" || return 1
    team_args=(--team-size "$TEAM_SIZE")
  fi
  python3 "$SCRIPT_DIR/render-local-config.py" \
    --input "$CONFIG_PATH" \
    --output "$CONFIG_PATH" \
    --workspace-root "$WORKSPACE_ROOT" \
    --work-parent "$DEFAULT_WORK_PARENT" \
    "${team_args[@]}"
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

ensure_workspace_venv() {
  local venv_dir="$WORKSPACE_ROOT/.venv"
  if [ -x "$venv_dir/bin/python" ]; then
    log "venv exists: $venv_dir"
    return 0
  fi
  need_cmd python3 || {
    err "python3 not found"
    return 1
  }
  python3 -m venv "$venv_dir"
  log "created venv: $venv_dir"
}

install_dashboard_requirements() {
  local requirements_file="$WORKSPACE_ROOT/dashboard/requirements.txt"
  local python_bin="$WORKSPACE_ROOT/.venv/bin/python"
  if [ ! -f "$requirements_file" ]; then
    warn "dashboard requirements not found: $requirements_file"
    return 0
  fi
  if [ ! -x "$python_bin" ]; then
    err "venv python missing: $python_bin"
    return 1
  fi
  "$python_bin" -m pip install -r "$requirements_file"
}

init() {
  local previous_render_config="${RENDER_CONFIG:-0}"
  local previous_team_size="${TEAM_SIZE:-}"
  ensure_workspace_venv
  install_dashboard_requirements
  RENDER_CONFIG=1
  TEAM_SIZE="${TEAM_SIZE:-small}"
  bootstrap
  RENDER_CONFIG="$previous_render_config"
  TEAM_SIZE="$previous_team_size"
  log "init complete"
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
  check_file codex-gateway-example "$WORKSPACE_ROOT/config/codex-responses-gateway.example.json" || rc=1
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

TEAMCTL_SERVICES_SH="${TEAMCTL_SERVICES_SH:-$SCRIPT_DIR/lib/teamctl_services.sh}"
if [ -r "$TEAMCTL_SERVICES_SH" ]; then
  # shellcheck source=lib/teamctl_services.sh
  source "$TEAMCTL_SERVICES_SH"
else
  err "teamctl services module missing: $TEAMCTL_SERVICES_SH"
  exit 1
fi


smoke() {
  local rc=0
  for f in "$SCRIPT_DIR"/*.sh; do
    bash -n "$f" || rc=1
  done
  python3 "$SCRIPT_DIR/codex-responses-gateway.py" check-config --config "$WORKSPACE_ROOT/config/codex-responses-gateway.example.json" >/dev/null || rc=1
  python3 "$SCRIPT_DIR/install-codex-gateway-profile.py" --dry-run >/dev/null || rc=1
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
  echo "gateway:   http://$CODEX_GATEWAY_HOST:$CODEX_GATEWAY_PORT/v1 config=$CODEX_GATEWAY_CONFIG"
  echo "agents:"
  agent_rows | while IFS=$'\t' read -r agent_id session runtime workdir guidance; do
    [ -n "$agent_id" ] || continue
    if tmux has-session -t "$session" 2>/dev/null; then state=running; else state=stopped; fi
    printf '  - %-10s session=%-12s runtime=%-12s state=%-8s workdir=%s\n' "$agent_id" "$session" "$runtime" "$state" "$workdir"
  done
}

sessions_cmd() {
  echo "agent tmux sessions:"
  agent_rows | while IFS=$'\t' read -r agent_id session runtime workdir guidance; do
    [ -n "$agent_id" ] || continue
    if tmux has-session -t "$session" 2>/dev/null; then state=running; else state=stopped; fi
    printf '  - %-10s session=%-12s runtime=%-12s state=%s\n' "$agent_id" "$session" "$runtime" "$state"
  done
}

resolve_attach_session() {
  local target="${1:-}"
  python3 - "$CONFIG_PATH" "$target" <<'PY'
import json
import sys
from pathlib import Path

config = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
target = str(sys.argv[2] or "").strip()
agents = config.get("agents") or {}
if not agents:
    raise SystemExit(1)
if not target:
    first_id, first_payload = next(iter(agents.items()))
    print(str((first_payload or {}).get("tmux_session") or first_id))
    raise SystemExit(0)
if target in agents:
    print(str((agents[target] or {}).get("tmux_session") or target))
    raise SystemExit(0)
for agent_id, payload in agents.items():
    session = str((payload or {}).get("tmux_session") or agent_id)
    if target == session:
        print(session)
        raise SystemExit(0)
raise SystemExit(2)
PY
}

attach_session_cmd() {
  local target="${1:-}" session=""
  session="$(resolve_attach_session "$target" 2>/dev/null || true)"
  if [ -z "$session" ]; then
    err "unknown agent or session: ${target:-<default>}"
    sessions_cmd >&2 || true
    return 1
  fi
  if ! tmux has-session -t "$session" 2>/dev/null; then
    err "tmux session not running: $session"
    sessions_cmd >&2 || true
    return 1
  fi
  exec tmux attach -t "$session"
}

up() {
  start_agents
  start_watcher
  start_dashboard
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  COMMAND="${1:-}"
  if [ -z "$COMMAND" ]; then
    usage >&2
    exit 2
  fi
  shift || true
  POSITIONAL=()
  while [ $# -gt 0 ]; do
    case "$1" in
      --attach) START_ATTACH=1; shift ;;
      --force) START_FORCE=1; shift ;;
      --team)
        if [ $# -lt 2 ]; then
          err "--team requires one of: small, medium, large"
          usage >&2
          exit 2
        fi
        TEAM_SIZE="$2"
        shift 2
        ;;
      --team=*) TEAM_SIZE="${1#--team=}"; shift ;;
      --render-config) RENDER_CONFIG=1; shift ;;
      -h|--help) usage; exit 0 ;;
      --*) err "unknown option: $1"; usage >&2; exit 2 ;;
      *) POSITIONAL+=("$1"); shift ;;
    esac
  done

  case "$COMMAND" in
    init) init ;;
    bootstrap) bootstrap ;;
    doctor) doctor ;;
    up) up ;;
    sessions) sessions_cmd ;;
    attach) attach_session_cmd "${POSITIONAL[0]:-}" ;;
    start-agents) start_agents ;;
    stop-agents) stop_agents ;;
    restart-agents) restart_agents ;;
    start-watcher) start_watcher ;;
    stop-watcher) stop_watcher ;;
    start-dashboard) start_dashboard ;;
    stop-dashboard) stop_dashboard ;;
    restart-services) restart_services ;;
    init-codex-gateway-config) init_codex_gateway_config ;;
    start-codex-gateway) start_codex_gateway ;;
    stop-codex-gateway) stop_codex_gateway ;;
    install-codex-profile) install_codex_profile ;;
    smoke) smoke ;;
    status) status_cmd ;;
    -h|--help|help) usage ;;
    *) err "unknown command: $COMMAND"; usage >&2; exit 2 ;;
  esac
fi
