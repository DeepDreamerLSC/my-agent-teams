#!/bin/bash
# report-to-feishu.sh — 日报/周报汇总，推送到飞书文档 + 消息

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
WORKSPACE_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
CONFIG_FILE="${FEISHU_CONFIG_PATH:-$WORKSPACE_ROOT/config.local.json}"
CONFIG_PATH="${CONFIG_PATH:-$WORKSPACE_ROOT/config.json}"
AGENT_CONFIG_PY="${AGENT_CONFIG_PY:-$SCRIPT_DIR/lib/agent_config.py}"
REPORTS_DIR="$WORKSPACE_ROOT/reports"
DASHBOARD_URL="${REPORT_DASHBOARD_URL:-http://127.0.0.1:5001/api/gantt}"

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
print(str(notifications.get('report_feishu_open_id') or notifications.get('feishu_receive_id') or notifications.get('feishu_open_id') or ''))
PYCONFIG
}

load_push_script_from_config() {
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
print(str(notifications.get('push_script') or ''))
PYCONFIG
}

FEISHU_OPEN_ID="${REPORT_FEISHU_OPEN_ID:-${FEISHU_RECEIVE_ID:-}}"
if [ -z "$FEISHU_OPEN_ID" ]; then
  FEISHU_OPEN_ID="$(load_receive_id_from_config 2>/dev/null || true)"
fi
PUSH_SCRIPT="${PUSH_SCRIPT:-}"
if [ -z "$PUSH_SCRIPT" ]; then
  PUSH_SCRIPT="$(load_push_script_from_config 2>/dev/null || true)"
fi
PUSH_SCRIPT="${PUSH_SCRIPT:-$SCRIPT_DIR/alert-card.sh}"

MODE="${1:-daily}"
TODAY=$(date +%F)
NOW=$(date '+%Y-%m-%d %H:%M:%S %Z')

case "$MODE" in
  daily)   SUBDIR="$REPORTS_DIR/daily"; TYPE="日报"; LABEL="$TODAY" ;;
  weekly)  SUBDIR="$REPORTS_DIR/weekly"; TYPE="周报"; LABEL="$(date -v-6d +%F) ~ $TODAY" ;;
  *) echo "Usage: $0 daily|weekly" >&2; exit 1 ;;
esac

mkdir -p "$SUBDIR"
OUTFILE="$SUBDIR/${TODAY}.md"
DATA_FILE=$(mktemp "${TMPDIR:-/tmp}/gantt_data.XXXXXX.json")
trap 'rm -f "$DATA_FILE"' EXIT

curl -s --max-time 10 "$DASHBOARD_URL" > "$DATA_FILE" 2>/dev/null || echo '{"items":[]}' > "$DATA_FILE"
python3 "$SCRIPT_DIR/_gen_report.py" "$MODE" "$TYPE" "$LABEL" "$TODAY" "$NOW" "$OUTFILE" "$DATA_FILE"

echo "[report] 已生成: $OUTFILE"

SUMMARY_COUNTS=$(python3 - "$DATA_FILE" "$CONFIG_PATH" "$AGENT_CONFIG_PY" <<'PYSUMMARY_COUNTS'
import importlib.util
import json
import sys
from pathlib import Path

data_path = Path(sys.argv[1])
config_path = Path(sys.argv[2])
agent_config_path = Path(sys.argv[3])
spec = importlib.util.spec_from_file_location("agent_config", agent_config_path)
agent_config = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(agent_config)
config = agent_config.load_config(config_path)
core = set(agent_config.agent_metadata(config))
data = json.loads(data_path.read_text(encoding="utf-8"))
items = [item for item in data.get("items", []) if item.get("assigned_agent") in core]
done = sum(1 for item in items if item.get("board_status") == "done")
blocked = sum(1 for item in items if item.get("board_status") == "blocked")
print(f"{done}\t{len(items)}\t{blocked}")
PYSUMMARY_COUNTS
)
IFS=$'\t' read -r DONE_COUNT TOTAL_COUNT BLOCKED <<< "$SUMMARY_COUNTS"

DOC_URL=""
if command -v lark-cli >/dev/null 2>&1; then
  if DOC_RESULT=$(lark-cli docs +create --title "agent团队${TYPE} ${LABEL}" --content @"$OUTFILE" 2>&1); then
    DOC_URL=$(echo "$DOC_RESULT" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('data',{}).get('url',''))" 2>/dev/null || echo "")
  fi
else
  echo "[report] lark-cli 未安装，跳过飞书文档创建"
fi

REPORT_LOCATION="$DOC_URL"
if [ -z "$REPORT_LOCATION" ]; then
  REPORT_LOCATION="reports/${MODE}/${TODAY}.md"
fi

SUMMARY="agent团队${TYPE}：${DONE_COUNT}/${TOTAL_COUNT}已完成"
[ "${BLOCKED:-0}" -gt 0 ] && SUMMARY="$SUMMARY，${BLOCKED}个阻塞"

if [ -n "$FEISHU_OPEN_ID" ]; then
  NOTIFY_PAYLOAD=$(cat <<EOF
【agent团队${TYPE}已生成】
任务：report-${MODE}-${TODAY}
摘要：${SUMMARY}；报告位置：${REPORT_LOCATION}
下一步：打开报告复盘并优先处理阻塞项
EOF
)
  printf '%s\n' "$NOTIFY_PAYLOAD" | FEISHU_RECEIVE_ID="$FEISHU_OPEN_ID" "$PUSH_SCRIPT"
  echo "[report] 飞书消息推送完成"
else
  echo "[report] 未配置 REPORT_FEISHU_OPEN_ID/FEISHU_RECEIVE_ID，跳过飞书消息"
fi
