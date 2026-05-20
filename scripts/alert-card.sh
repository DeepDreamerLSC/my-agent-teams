#!/bin/bash
# alert-card.sh — 分级警报卡片推送到飞书
#
# 用法:
#   echo "【任务完成】\n任务：任务ID\n摘要：...\n下一步：..." | ./alert-card.sh
#   ./alert-card.sh <task_id> <level> <title> [details]
#
# 配置:
#   FEISHU_RECEIVE_ID / FEISHU_OPEN_ID  接收者 open_id（无内置默认值）
#   ALERT_CARD_FALLBACK_SCRIPT          lark-cli 不可用时的纯文本推送脚本

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
CONFIG_FILE="${FEISHU_CONFIG_PATH:-$WORKSPACE_ROOT/config.local.json}"
FEISHU_OPEN_ID="${FEISHU_OPEN_ID:-${FEISHU_RECEIVE_ID:-}}"
FALLBACK_SCRIPT="${ALERT_CARD_FALLBACK_SCRIPT:-$SCRIPT_DIR/feishu-push.sh}"

load_receive_id_from_config() {
  python3 - "$CONFIG_FILE" <<'PYCONFIG'
import json
import sys
from pathlib import Path
path = Path(sys.argv[1]).expanduser()
if not path.exists():
    raise SystemExit(0)
try:
    payload = json.loads(path.read_text(encoding='utf-8'))
except Exception:
    raise SystemExit(0)
notifications = payload.get('notifications') or {}
print(str(notifications.get('feishu_receive_id') or notifications.get('feishu_open_id') or ''))
PYCONFIG
}

if [ -z "$FEISHU_OPEN_ID" ]; then
  FEISHU_OPEN_ID="$(load_receive_id_from_config 2>/dev/null || true)"
fi

trim() {
  local value="$1"
  value="${value#${value%%[![:space:]]*}}"
  value="${value%${value##*[![:space:]]}}"
  printf '%s' "$value"
}

strip_label_value() {
  local value="$1"
  value="${value#*：}"
  value="${value#*:}"
  printf '%s' "$(trim "$value")"
}

infer_level() {
  local title="$1" detail="$2"
  case "$title $detail" in
    *生产故障*|*agent_offline*|*离线*) printf 'P0' ;;
    *失败*|*阻塞*|*blocked*|*timeout*|*超时*|*未通过*|*异常*) printf 'P1' ;;
    *完成*|*通过*|*done*|*review_ok*|*QA通过*) printf 'P2' ;;
    *) printf 'info' ;;
  esac
}

parse_stdin_payload() {
  local raw="$1"
  local first_line task_line summary_line next_line
  first_line="$(printf '%s\n' "$raw" | sed -n '1p')"
  task_line="$(printf '%s\n' "$raw" | sed -n '/^任务[:：]/ {p;q;}')"
  summary_line="$(printf '%s\n' "$raw" | sed -n '/^摘要[:：]/ {p;q;}')"
  next_line="$(printf '%s\n' "$raw" | sed -n '/^下一步[:：]/ {p;q;}')"

  if [ -n "$task_line" ] || [ -n "$summary_line" ] || [ -n "$next_line" ]; then
    TITLE="$(trim "$first_line")"
    TASK_ID="$(strip_label_value "$task_line")"
    [ -n "$TASK_ID" ] || TASK_ID="unknown"
    DETAIL=""
    if [ -n "$summary_line" ]; then
      DETAIL="摘要：$(strip_label_value "$summary_line")"
    fi
    if [ -n "$next_line" ]; then
      [ -n "$DETAIL" ] && DETAIL="$DETAIL\n"
      DETAIL="${DETAIL}下一步：$(strip_label_value "$next_line")"
    fi
    LEVEL="$(infer_level "$TITLE" "$DETAIL")"
    return 0
  fi

  # 兼容旧的 stdin: task_id level title details
  read -r TASK_ID LEVEL TITLE DETAIL <<< "$raw" || true
  TASK_ID="${TASK_ID:-unknown}"
  LEVEL="${LEVEL:-$(infer_level "${TITLE:-通知}" "${DETAIL:-}")}"
  TITLE="${TITLE:-通知}"
  DETAIL="${DETAIL:-}"
}

if [ $# -ge 3 ]; then
  TASK_ID="$1"
  LEVEL="$2"
  TITLE="$3"
  DETAIL="${4:-}"
else
  RAW_INPUT="$(cat || true)"
  parse_stdin_payload "$RAW_INPUT"
fi

case "${LEVEL}" in
  P0|agent_offline|offline)
    COLOR="red"
    LEVEL_LABEL="🔴 P0 生产故障"
    ;;
  P1|timeout|blocked|failed|failure)
    COLOR="orange"
    LEVEL_LABEL="🟠 P1 生产告警"
    ;;
  P2|done|review_pass|review_ok|success)
    COLOR="green"
    LEVEL_LABEL="🟢 P2 任务完成"
    ;;
  *)
    COLOR="blue"
    LEVEL_LABEL="ℹ️ 通知"
    ;;
esac

NOW=$(date '+%m-%d %H:%M')
CARD_JSON=$(TASK_ID="$TASK_ID" TITLE="$TITLE" DETAIL="${DETAIL:-}" LEVEL_LABEL="$LEVEL_LABEL" COLOR="$COLOR" NOW="$NOW" python3 - <<'PYCARD'
import json
import os

def text(name: str) -> str:
    return str(os.environ.get(name) or '')

card = {
    'config': {'wide_screen_mode': True},
    'header': {
        'title': {'tag': 'plain_text', 'content': text('LEVEL_LABEL')},
        'template': text('COLOR') or 'blue',
    },
    'elements': [
        {'tag': 'div', 'text': {'tag': 'lark_md', 'content': f"**任务：{text('TITLE')}**"}},
        {'tag': 'div', 'text': {'tag': 'lark_md', 'content': f"ID: {text('TASK_ID')}  |  {text('NOW')}"}},
    ],
}
detail = text('DETAIL')
if detail:
    card['elements'].append({'tag': 'div', 'text': {'tag': 'lark_md', 'content': detail[:500]}})
print(json.dumps(card, ensure_ascii=False))
PYCARD
)

if [ -n "$FEISHU_OPEN_ID" ] && command -v lark-cli >/dev/null 2>&1; then
  if lark-cli im +messages-send \
    --user-id "$FEISHU_OPEN_ID" \
    --msg-type interactive \
    --content "$CARD_JSON" 2>/dev/null; then
    exit 0
  fi
fi

FALLBACK_MSG="$LEVEL_LABEL: $TITLE (${TASK_ID})"
if [ -n "${DETAIL:-}" ]; then
  FALLBACK_MSG="$FALLBACK_MSG\n${DETAIL}"
fi

if [ -x "$FALLBACK_SCRIPT" ]; then
  printf '%b\n' "$FALLBACK_MSG" | FEISHU_RECEIVE_ID="$FEISHU_OPEN_ID" FEISHU_MESSAGE_UUID="" "$FALLBACK_SCRIPT"
else
  echo "ERROR: fallback push script not executable: $FALLBACK_SCRIPT" >&2
  exit 1
fi
