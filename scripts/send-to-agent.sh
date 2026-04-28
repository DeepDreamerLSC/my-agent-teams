#!/bin/bash
set -euo pipefail

SESSION="${1:-}"
shift || true
MESSAGE="$*"
CONFIG_PATH="${CONFIG_PATH:-$HOME/Desktop/work/my-agent-teams/config.json}"
INSERT_WAIT_SECONDS="${SEND_TO_AGENT_INSERT_WAIT_SECONDS:-0.5}"
POST_SEND_WAIT_SECONDS="${SEND_TO_AGENT_POST_SEND_WAIT_SECONDS:-0.1}"
ACK_WAIT_SECONDS="${SEND_TO_AGENT_ACK_WAIT_SECONDS:-10}"
TIMEOUT_SECONDS="${SEND_TO_AGENT_TIMEOUT_SECONDS:-15}"
RETRY_LIMIT="${SEND_TO_AGENT_RETRY_LIMIT:-1}"
RESPONSE_REGEX="${SEND_TO_AGENT_RESPONSE_REGEX:-Working|• Working|⏺|✻|thinking|Thinking|Esc to interrupt}"

if [ -z "$SESSION" ] || [ -z "$MESSAGE" ]; then
  echo "usage: send-to-agent.sh <session> <message>" >&2
  exit 2
fi

if ! tmux has-session -t "$SESSION" 2>/dev/null; then
  echo "tmux session not found: $SESSION" >&2
  exit 1
fi

RUNTIME=$(python3 - "$CONFIG_PATH" "$SESSION" <<'PY'
import json
import sys
from pathlib import Path

config_path = Path(sys.argv[1]).expanduser()
session = sys.argv[2]
if not config_path.exists():
    print('unknown')
    raise SystemExit(0)
try:
    config = json.loads(config_path.read_text(encoding='utf-8'))
except Exception:
    print('unknown')
    raise SystemExit(0)
agents = config.get('agents') or {}
agent = agents.get(session) or {}
if not agent:
    for payload in agents.values():
        if isinstance(payload, dict) and payload.get('tmux_session') == session:
            agent = payload
            break
print((agent or {}).get('runtime') or 'unknown')
PY
)

run_tmux_with_timeout() {
  tmux "$@" &
  local pid=$!
  (
    sleep "$TIMEOUT_SECONDS"
    kill "$pid" 2>/dev/null || true
  ) &
  local watchdog=$!
  local status=0
  wait "$pid" || status=$?
  kill "$watchdog" 2>/dev/null || true
  wait "$watchdog" 2>/dev/null || true
  return "$status"
}

pane_acknowledged() {
  local before="$1"
  local after="$2"
  local runtime="$3"
  if [ "$after" = "$before" ]; then
    return 1
  fi
  if printf '%s\n' "$after" | tail -40 | grep -Eq "$RESPONSE_REGEX"; then
    return 0
  fi
  case "$runtime" in
    codex|claude_code)
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}

attempt=0
while [ "$attempt" -le "$RETRY_LIMIT" ]; do
  before_pane=$(tmux capture-pane -t "$SESSION" -p -S -80 2>/dev/null || true)

  if [ "$RUNTIME" = "codex" ]; then
    run_tmux_with_timeout send-keys -t "$SESSION" i || true
    sleep "$INSERT_WAIT_SECONDS"
  fi

  run_tmux_with_timeout send-keys -t "$SESSION" -l -- "$MESSAGE"
  sleep "$POST_SEND_WAIT_SECONDS"
  run_tmux_with_timeout send-keys -t "$SESSION" Enter
  sleep "$ACK_WAIT_SECONDS"

  after_pane=$(tmux capture-pane -t "$SESSION" -p -S -80 2>/dev/null || true)
  if pane_acknowledged "$before_pane" "$after_pane" "$RUNTIME"; then
    echo "delivered to $SESSION (runtime=$RUNTIME, attempt=$((attempt + 1)))"
    exit 0
  fi

  attempt=$((attempt + 1))
  if [ "$attempt" -le "$RETRY_LIMIT" ]; then
    echo "no response detected from $SESSION, retrying ($attempt/$RETRY_LIMIT)" >&2
  fi
done

echo "failed to deliver message to $SESSION after $((RETRY_LIMIT + 1)) attempts" >&2
exit 1
