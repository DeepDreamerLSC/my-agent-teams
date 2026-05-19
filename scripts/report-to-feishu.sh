#!/bin/bash
# report-to-feishu.sh — 日报/周报汇总，推送到飞书文档 + 消息

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
WORKSPACE_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
CONFIG_FILE="${FEISHU_CONFIG_PATH:-$WORKSPACE_ROOT/config.local.json}"
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

FEISHU_OPEN_ID="${REPORT_FEISHU_OPEN_ID:-${FEISHU_RECEIVE_ID:-}}"
if [ -z "$FEISHU_OPEN_ID" ]; then
  FEISHU_OPEN_ID="$(load_receive_id_from_config 2>/dev/null || true)"
fi

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

DONE_COUNT=$(python3 -c "import json,sys; d=json.load(open(sys.argv[1])); core={'pm-chief','arch-1','dev-1','dev-2','qa-1','review-1'}; items=[i for i in d.get('items',[]) if i.get('assigned_agent') in core]; print(sum(1 for i in items if i.get('board_status')=='done'))" "$DATA_FILE")
TOTAL_COUNT=$(python3 -c "import json,sys; d=json.load(open(sys.argv[1])); core={'pm-chief','arch-1','dev-1','dev-2','qa-1','review-1'}; print(sum(1 for i in d.get('items',[]) if i.get('assigned_agent') in core))" "$DATA_FILE")
BLOCKED=$(python3 -c "import json,sys; d=json.load(open(sys.argv[1])); core={'pm-chief','arch-1','dev-1','dev-2','qa-1','review-1'}; print(sum(1 for i in d.get('items',[]) if i.get('assigned_agent') in core and i.get('board_status')=='blocked'))" "$DATA_FILE")

if command -v lark-cli >/dev/null 2>&1; then
  DOC_URL=""
  if DOC_RESULT=$(lark-cli docs +create --title "agent团队${TYPE} ${LABEL}" --content @"$OUTFILE" 2>&1); then
    DOC_URL=$(echo "$DOC_RESULT" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('data',{}).get('url',''))" 2>/dev/null || echo "")
  fi

  MSG_LINE="📊 agent团队${TYPE}：${DONE_COUNT}/${TOTAL_COUNT}已完成"
  [ "${BLOCKED:-0}" -gt 0 ] && MSG_LINE="$MSG_LINE，${BLOCKED}个阻塞"
  [ -n "$DOC_URL" ] && MSG_LINE="$MSG_LINE\n📄 $DOC_URL" || MSG_LINE="$MSG_LINE\n📄 reports/${MODE}/${TODAY}.md"

  if [ -n "$FEISHU_OPEN_ID" ]; then
    lark-cli im +messages-send --user-id "$FEISHU_OPEN_ID" --content "$MSG_LINE" 2>/dev/null || true
    echo "[report] 飞书推送完成"
  else
    echo "[report] 未配置 REPORT_FEISHU_OPEN_ID/FEISHU_RECEIVE_ID，跳过飞书消息"
  fi
else
  echo "[report] lark-cli 未安装，跳过推送"
fi
