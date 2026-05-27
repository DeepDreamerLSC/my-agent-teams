#!/bin/bash
# sync-gantt-to-feishu.sh — 从 task-board dashboard 同步 agent 任务数据到飞书甘特图
#
# 前置条件:
#   1. dashboard 在运行（teamctl start-dashboard）
#   2. lark-cli 已认证（lark-cli auth login）
#   3. 飞书 Base / table / record id 已通过环境变量或 config.local.json 配置
#
# 配置优先级: 环境变量 > config.local.json:notifications.gantt > 无默认值
#   GANTT_FEISHU_BASE_TOKEN       飞书 Base Token（必填）
#   GANTT_FEISHU_TABLE_ID         人力总览表 ID（必填）
#   GANTT_FEISHU_TREND_TABLE_ID   完成趋势表 ID（可选，空则跳过趋势同步）
#   GANTT_FEISHU_TASK_TABLE_ID    任务详情表 ID（必填；旧变量 GANTT_FEISHU_TASK_TABLE 仍兼容）
#   GANTT_FEISHU_AGENTS           逗号分隔 agent 列表
#   GANTT_FEISHU_RECORD_IDS       与 agent 一一对应的 record_id 逗号列表（必填）
#   GANTT_DASHBOARD_URL           dashboard Gantt API URL
#   GANTT_DRY_RUN=1               只计算并打印，不写入或删除飞书记录

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
CONFIG_FILE="${FEISHU_CONFIG_PATH:-$WORKSPACE_ROOT/config.local.json}"
CONFIG_PATH="${CONFIG_PATH:-$WORKSPACE_ROOT/config.json}"
AGENT_CONFIG_PY="${AGENT_CONFIG_PY:-$SCRIPT_DIR/lib/agent_config.py}"
DASHBOARD_URL="${GANTT_DASHBOARD_URL:-http://127.0.0.1:5001/api/gantt}"
DRY_RUN="${GANTT_DRY_RUN:-0}"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m'

log()  { echo "[sync-gantt] $*"; }
warn() { echo -e "${YELLOW}[sync-gantt][WARN]${NC} $*" >&2; }
err()  { echo -e "${RED}[sync-gantt][ERROR]${NC} $*" >&2; }

while [ $# -gt 0 ]; do
  case "$1" in
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    -h|--help)
      cat <<'EOF_USAGE'
usage: scripts/sync-gantt-to-feishu.sh [--dry-run]

Required config:
  GANTT_FEISHU_BASE_TOKEN / notifications.gantt.base_token
  GANTT_FEISHU_TABLE_ID / notifications.gantt.table_id
  GANTT_FEISHU_TASK_TABLE_ID / notifications.gantt.task_table_id
  GANTT_FEISHU_RECORD_IDS / notifications.gantt.record_ids

Optional:
  GANTT_FEISHU_TREND_TABLE_ID, GANTT_FEISHU_AGENTS, GANTT_DASHBOARD_URL
EOF_USAGE
      exit 0
      ;;
    *)
      err "unknown option: $1"
      exit 2
      ;;
  esac
done

load_config_value() {
  local key="$1"
  python3 - "$CONFIG_FILE" "$key" <<'PYCONFIG'
import json
import sys
from pathlib import Path
path = Path(sys.argv[1]).expanduser()
key = sys.argv[2]
if not path.exists():
    raise SystemExit(0)
try:
    payload = json.loads(path.read_text(encoding='utf-8'))
except Exception:
    raise SystemExit(0)
node = ((payload.get('notifications') or {}).get('gantt') or {})
print(str(node.get(key) or ''))
PYCONFIG
}

config_default() {
  local env_name="$1"
  local config_key="$2"
  local current="${!env_name:-}"
  if [ -n "$current" ]; then
    printf '%s' "$current"
    return
  fi
  load_config_value "$config_key" 2>/dev/null || true
}

load_agent_ids_from_config() {
  if [ -r "$AGENT_CONFIG_PY" ]; then
    python3 "$AGENT_CONFIG_PY" list-agent-ids --config "$CONFIG_PATH" 2>/dev/null || true
  fi
}

BASE_TOKEN="$(config_default GANTT_FEISHU_BASE_TOKEN base_token)"
AGGREGATE_TABLE="$(config_default GANTT_FEISHU_TABLE_ID table_id)"
TREND_TABLE="$(config_default GANTT_FEISHU_TREND_TABLE_ID trend_table_id)"
TASK_DETAIL_TABLE="$(config_default GANTT_FEISHU_TASK_TABLE_ID task_table_id)"
if [ -z "$TASK_DETAIL_TABLE" ]; then
  TASK_DETAIL_TABLE="$(config_default GANTT_FEISHU_TASK_TABLE task_table)"
fi
AGENTS_CSV="$(config_default GANTT_FEISHU_AGENTS agents)"
RECORD_IDS_CSV="$(config_default GANTT_FEISHU_RECORD_IDS record_ids)"
if [ -z "$AGENTS_CSV" ]; then
  AGENTS_CSV="$(load_agent_ids_from_config)"
fi

require_value() {
  local value="$1"
  local label="$2"
  if [ -z "$value" ]; then
    err "缺少配置：${label}。请设置环境变量或写入 config.local.json notifications.gantt。"
    exit 1
  fi
}

require_value "$BASE_TOKEN" "GANTT_FEISHU_BASE_TOKEN"
require_value "$AGGREGATE_TABLE" "GANTT_FEISHU_TABLE_ID"
require_value "$TASK_DETAIL_TABLE" "GANTT_FEISHU_TASK_TABLE_ID"
require_value "$AGENTS_CSV" "GANTT_FEISHU_AGENTS 或 config.json agents"
require_value "$RECORD_IDS_CSV" "GANTT_FEISHU_RECORD_IDS"

if [ "$DRY_RUN" != "1" ] && ! command -v lark-cli >/dev/null 2>&1; then
  err "lark-cli 未安装，请先执行: npm install -g @larksuite/cli"
  exit 1
fi
if ! command -v bc >/dev/null 2>&1; then
  err "bc 未安装，无法计算平均耗时"
  exit 1
fi

JSON=$(curl -s --max-time 10 "$DASHBOARD_URL" 2>/dev/null)
if [ -z "$JSON" ]; then
  err "无法获取 dashboard 数据 ($DASHBOARD_URL)"
  exit 1
fi

IFS=',' read -r -a AGENTS <<< "$AGENTS_CSV"
IFS=',' read -r -a RECORD_IDS <<< "$RECORD_IDS_CSV"
if [ "${#AGENTS[@]}" -ne "${#RECORD_IDS[@]}" ]; then
  err "GANTT_FEISHU_AGENTS 与 GANTT_FEISHU_RECORD_IDS 数量不一致"
  exit 1
fi

for i in "${!AGENTS[@]}"; do
  AGENTS[$i]="$(echo "${AGENTS[$i]}" | xargs)"
  RECORD_IDS[$i]="$(echo "${RECORD_IDS[$i]}" | xargs)"
  AGENT_TOTAL[$i]=0; AGENT_DONE[$i]=0; AGENT_BLOCKED[$i]=0; AGENT_MERGE[$i]=0; AGENT_HOURS[$i]=0
done

while IFS=$'\t' read -r agent status duration_sec; do
  for i in "${!AGENTS[@]}"; do
    if [ "${AGENTS[$i]}" = "$agent" ]; then
      AGENT_TOTAL[$i]=$((AGENT_TOTAL[$i] + 1))
      AGENT_HOURS[$i]=$(echo "${AGENT_HOURS[$i]} + $duration_sec" | bc)
      case "$status" in
        done) AGENT_DONE[$i]=$((AGENT_DONE[$i] + 1)) ;;
        blocked) AGENT_BLOCKED[$i]=$((AGENT_BLOCKED[$i] + 1)) ;;
        ready_for_merge) AGENT_MERGE[$i]=$((AGENT_MERGE[$i] + 1)) ;;
      esac
      break
    fi
  done
done < <(echo "$JSON" | python3 -c '
import json, sys
data = json.load(sys.stdin)
for item in data.get("items", []):
    print("%s\t%s\t%s" % (item.get("assigned_agent", ""), item.get("board_status", ""), item.get("duration_seconds", 0)))
')

UPDATED=0
ERRORS=0
for i in "${!AGENTS[@]}"; do
  agent="${AGENTS[$i]}"
  rid="${RECORD_IDS[$i]}"
  total=${AGENT_TOTAL[$i]}
  done_count=${AGENT_DONE[$i]}
  blocked=${AGENT_BLOCKED[$i]}
  merge=${AGENT_MERGE[$i]}
  hours=${AGENT_HOURS[$i]}

  if [ "$total" -gt 0 ]; then
    load=$(( (blocked + merge) * 100 / total ))
    avg_h=$(echo "scale=1; $hours / $total / 3600" | bc | sed "s/^\./0./")
  else
    load=0
    avg_h=0
  fi

  payload=$(AGENT="$agent" TOTAL="$total" DONE="$done_count" BLOCKED="$blocked" MERGE="$merge" LOAD="$load" AVG_H="$avg_h" python3 - <<'PYJSON'
import json
import os
print(json.dumps({
    "人员": os.environ["AGENT"],
    "当前任务数": int(os.environ["TOTAL"]),
    "已完成": int(os.environ["DONE"]),
    "阻塞中": int(os.environ["BLOCKED"]),
    "待合入": int(os.environ["MERGE"]),
    "负载率%": int(os.environ["LOAD"]),
    "平均耗时h": float(os.environ["AVG_H"]),
}, ensure_ascii=False))
PYJSON
)

  if [ "$DRY_RUN" = "1" ]; then
    log "[dry-run] 将更新人力总览 $agent record=$rid payload=$payload"
    UPDATED=$((UPDATED + 1))
  elif result=$(lark-cli base +record-upsert \
      --base-token "$BASE_TOKEN" \
      --table-id "$AGGREGATE_TABLE" \
      --record-id "$rid" \
      --json "$payload" 2>&1); then
    UPDATED=$((UPDATED + 1))
  else
    err "更新 $agent 失败: $(echo "$result" | head -3)"
    ERRORS=$((ERRORS + 1))
  fi
done

if [ "$DRY_RUN" = "1" ]; then
  echo -e "${GREEN}dry-run 完成${NC}: $UPDATED/${#AGENTS[@]} 个角色已计算，未写入飞书"
else
  echo -e "${GREEN}同步完成${NC}: $UPDATED/${#AGENTS[@]} 个角色更新"
fi
for i in "${!AGENTS[@]}"; do
  agent="${AGENTS[$i]}"
  total=${AGENT_TOTAL[$i]}
  done_count=${AGENT_DONE[$i]}
  blocked=${AGENT_BLOCKED[$i]}
  merge=${AGENT_MERGE[$i]}
  [ "$total" -gt 0 ] && load=$(( (blocked + merge) * 100 / total )) || load=0
  printf "  %-12s 总%3d  完成%3d  阻塞%2d  待合入%2d  负载%2d%%\n" \
    "$agent" "$total" "$done_count" "$blocked" "$merge" "$load"
done

TMP_DIR=$(mktemp -d "${TMPDIR:-/tmp}/gantt-sync.XXXXXX")
trap 'rm -rf "$TMP_DIR"' EXIT

if [ -z "$TREND_TABLE" ]; then
  warn "未配置 GANTT_FEISHU_TREND_TABLE_ID，跳过任务完成趋势同步"
else

  echo ""
  log "同步任务完成趋势..."
  export BASE_TOKEN TREND_TABLE DASHBOARD_URL TMP_DIR DRY_RUN

  python3 << 'PYEOF'
import json, urllib.request, subprocess, os, sys
from datetime import datetime, timedelta
from collections import defaultdict
from pathlib import Path

BASE_TOKEN = os.environ["BASE_TOKEN"]
TREND_TABLE = os.environ["TREND_TABLE"]
DASHBOARD_URL = os.environ["DASHBOARD_URL"]
TMP_DIR = Path(os.environ["TMP_DIR"])
DRY_RUN = os.environ.get("DRY_RUN") == "1"

def run_lark(cmd_list, input_data=None, cwd=None):
    if DRY_RUN:
        print(f"[trend][dry-run] skip lark-cli: {' '.join(cmd_list[:4])}", file=sys.stderr)
        return None
    try:
        r = subprocess.run(cmd_list, capture_output=True, text=True, timeout=15, input=input_data, cwd=cwd)
        if r.returncode != 0:
            print(f"[WARN] lark-cli failed: {r.stderr[:200]}", file=sys.stderr)
            return None
        return json.loads(r.stdout)
    except Exception as e:
        print(f"[WARN] lark-cli error: {e}", file=sys.stderr)
        return None

date_to_rid = {}
if not DRY_RUN:
    existing = run_lark([
        "lark-cli", "base", "+record-list",
        "--base-token", BASE_TOKEN,
        "--table-id", TREND_TABLE,
        "--as", "user",
        "--limit", "200",
        "--format", "json",
    ])
    if existing and existing.get("ok"):
        data = existing.get("data", {})
        record_ids = data.get("record_id_list", [])
        records = data.get("data", [])
        for i, rid in enumerate(record_ids):
            if i < len(records) and len(records[i]) >= 3:
                date_to_rid[records[i][2]] = rid
        print(f"[trend] 已有 {len(date_to_rid)} 条趋势记录", file=sys.stderr)
    else:
        print("[ERROR] 无法读取趋势表现有记录，停止趋势同步以避免重复写入", file=sys.stderr)
        raise SystemExit(1)

resp = urllib.request.urlopen(DASHBOARD_URL, timeout=10)
dashboard_data = json.loads(resp.read())
daily = defaultdict(int)

for item in dashboard_data.get("items", []):
    if item.get("board_status", "") != "done":
        continue
    cd = (item.get("milestones", {}).get("completed", "") or "")[:10]
    if not cd:
        start = (item.get("display_start_at", "") or "")[:10]
        duration = item.get("duration_seconds", 0)
        if start and duration > 0:
            try:
                sd = datetime.strptime(start, "%Y-%m-%d")
                cd = (sd + timedelta(seconds=duration)).strftime("%Y-%m-%d")
            except Exception:
                cd = (item.get("display_end_at", "") or "")[:10]
        else:
            cd = (item.get("display_end_at", "") or "")[:10]
    if cd:
        daily[cd] += 1

sorted_dates = sorted(daily.items(), key=lambda x: x[0])
print(f"[trend] Dashboard 计算: {len(sorted_dates)} 天", file=sys.stderr)

if DRY_RUN:
    print(f"[trend][dry-run] 将同步 {len(sorted_dates)} 天趋势数据", file=sys.stderr)
    raise SystemExit(0)

new_dates = []
for date_str, count in sorted_dates:
    if date_str in date_to_rid:
        rid = date_to_rid[date_str]
        result = run_lark([
            "lark-cli", "base", "+record-upsert",
            "--base-token", BASE_TOKEN,
            "--table-id", TREND_TABLE,
            "--record-id", rid,
            "--as", "user",
            "--json", json.dumps({"日期": date_str, "完成数": count}, ensure_ascii=False),
        ])
        if not (result and result.get("ok")):
            print(f"[WARN] upsert {date_str} 失败", file=sys.stderr)
    else:
        new_dates.append([date_str, count])

if new_dates:
    payload = {"fields": ["日期", "完成数"], "rows": new_dates}
    payload_path = TMP_DIR / "trend_sync_payload.json"
    payload_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    result = run_lark([
        "lark-cli", "base", "+record-batch-create",
        "--base-token", BASE_TOKEN,
        "--table-id", TREND_TABLE,
        "--as", "user",
        "--json", f"@{payload_path.name}",
    ], cwd=str(TMP_DIR))
    if result and result.get("ok"):
        new_ids = result.get("data", {}).get("record_id_list", [])
        print(f"[trend] 新增 {len(new_ids)} 天数据", file=sys.stderr)
    else:
        print("[WARN] 新增趋势数据失败", file=sys.stderr)
else:
    print("[trend] 无需新增", file=sys.stderr)

print(f"[trend] 同步完成: {len(sorted_dates)} 天", file=sys.stderr)
PYEOF

  log "趋势同步完成"
fi


# --------------- 任务详情同步（甘特图数据）---------------
echo ""
log "同步任务详情（甘特图）..."

export BASE_TOKEN TASK_DETAIL_TABLE DASHBOARD_URL TMP_DIR CONFIG_PATH AGENT_CONFIG_PY DRY_RUN
python3 << 'TDEOF'
import importlib.util
import json, urllib.request, subprocess, sys, os
from datetime import datetime, timedelta, timezone
from pathlib import Path

BASE_TOKEN = os.environ["BASE_TOKEN"]
TASK_TABLE = os.environ["TASK_DETAIL_TABLE"]
DASHBOARD_URL = os.environ["DASHBOARD_URL"]
TMP_DIR = Path(os.environ["TMP_DIR"])
CONFIG_PATH = Path(os.environ.get("CONFIG_PATH", "config.json")).expanduser()
AGENT_CONFIG_PY = Path(os.environ.get("AGENT_CONFIG_PY", "scripts/lib/agent_config.py")).expanduser()
DRY_RUN = os.environ.get("DRY_RUN") == "1"

def run_lark(cmd_list, cwd=None):
    if DRY_RUN:
        print(f"[task-detail][dry-run] skip lark-cli: {' '.join(cmd_list[:4])}", file=sys.stderr)
        return None
    try:
        r = subprocess.run(cmd_list, capture_output=True, text=True, timeout=30, cwd=cwd)
        if r.returncode != 0:
            print(f"[ERROR] lark-cli failed: {r.stderr[:200]}", file=sys.stderr)
            return None
        idx = r.stdout.find("{")
        return json.loads(r.stdout[idx:]) if idx >= 0 else None
    except Exception as exc:
        print(f"[ERROR] lark-cli error: {exc}", file=sys.stderr)
        return None

# Step 1: Delete all existing records in task detail table (with full pagination)
TMP_DIR.mkdir(parents=True, exist_ok=True)
offset = 0
all_rids = []
if DRY_RUN:
    print("[task-detail][dry-run] 跳过旧记录删除", file=sys.stderr)
else:
    while True:
        result = run_lark(["lark-cli", "base", "+record-list",
            "--base-token", BASE_TOKEN, "--table-id", TASK_TABLE,
            "--as", "user", "--limit", "200", "--offset", str(offset), "--format", "json"])
        if not (result and result.get("ok")):
            print("[ERROR] 无法读取任务详情表现有记录，停止同步以避免重复写入", file=sys.stderr)
            raise SystemExit(1)
        rids = result["data"].get("record_id_list", [])
        if not rids:
            break
        all_rids.extend(rids)
        if not result["data"].get("has_more", False):
            break
        offset += 200

if all_rids:
    for i in range(0, len(all_rids), 200):
        batch = all_rids[i:i+200]
        payload = {"record_id_list": batch}
        tmp = TMP_DIR / f"task_del_{i}.json"
        tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        run_lark(["lark-cli", "base", "+record-delete",
            "--base-token", BASE_TOKEN, "--table-id", TASK_TABLE,
            "--as", "user", "--yes", "--json", f"@{tmp.name}"], cwd=str(TMP_DIR))
        tmp.unlink()
    print(f"[task-detail] 已清除 {len(all_rids)} 条旧记录", file=sys.stderr)

# Step 2: Get fresh Dashboard data
resp = urllib.request.urlopen(DASHBOARD_URL)
data = json.loads(resp.read())
items = data.get("items", [])

def load_agent_metadata():
    spec = importlib.util.spec_from_file_location("agent_config", AGENT_CONFIG_PY)
    if not spec or not spec.loader:
        raise RuntimeError(f"cannot load agent config helper: {AGENT_CONFIG_PY}")
    agent_config = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(agent_config)
    config = agent_config.load_config(CONFIG_PATH)
    metadata = agent_config.agent_metadata(config)
    return set(metadata), agent_config.role_labels(config)

CORE_AGENTS, AGENT_ROLES = load_agent_metadata()

rows = []
for item in items:
    agent = item.get("assigned_agent", "") or ""
    if agent not in CORE_AGENTS:
        continue
    status = item.get("board_status", "")
    start_raw = (item.get("display_start_at", "") or "")
    end_raw = (item.get("display_end_at", "") or "")
    duration_sec = item.get("duration_seconds", 0)
    title = (item.get("title", "?") or "?")[:80]
    start_dt = start_raw[:16].replace("T", " ") if start_raw else ""
    end_dt = end_raw[:16].replace("T", " ") if end_raw else ""
    if status == "done":
        completed_raw = (item.get("milestones", {}).get("completed", "") or "")
        if completed_raw:
            end_dt = completed_raw[:16].replace("T", " ")
    duration_h = round(duration_sec / 3600, 1)
    role = AGENT_ROLES.get(agent, agent)
    rows.append([title, role, status, start_dt, end_dt, str(duration_h)])

if DRY_RUN:
    print(f"[task-detail][dry-run] 将同步 {len(rows)} 条任务详情", file=sys.stderr)
elif rows:
    FIELDS = ["任务名称", "负责人", "状态", "开始时间", "结束时间", "持续时长h"]
    BATCH_SIZE = 200
    total_synced = 0
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    for i in range(0, len(rows), BATCH_SIZE):
        batch = rows[i:i+BATCH_SIZE]
        payload = {"fields": FIELDS, "rows": batch}
        tmp = TMP_DIR / f"task_sync_{i}.json"
        tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        result = run_lark(["lark-cli", "base", "+record-batch-create",
            "--base-token", BASE_TOKEN, "--table-id", TASK_TABLE,
            "--as", "user", "--json", f"@{tmp.name}"], cwd=str(TMP_DIR))
        tmp.unlink()
        if result and result.get("ok"):
            count = len(result.get("data", {}).get("record_id_list", []))
            total_synced += count
            print(f"[task-detail] 批次 {i//BATCH_SIZE+1} 已同步 {count} 条", file=sys.stderr)
        else:
            print(f"[task-detail] 批次 {i//BATCH_SIZE+1} 同步失败", file=sys.stderr)
    print(f"[task-detail] 全部完成: {total_synced}/{len(rows)} 条", file=sys.stderr)
else:
    print("[task-detail] 无任务数据", file=sys.stderr)
TDEOF
exit "$ERRORS"
