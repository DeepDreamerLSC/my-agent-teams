#!/bin/bash
# publish-to-wiki.sh — 将设计文档发布到飞书知识库
#
# 用法:
#   ./scripts/publish-to-wiki.sh design/archive/review-xxx.md 审查记录
#   ./scripts/publish-to-wiki.sh design/collaboration/xxx.md 技术方案
#
# 配置:
#   FEISHU_WIKI_SPACE_ID
#   FEISHU_WIKI_NODE_REVIEW / FEISHU_WIKI_NODE_DESIGN / FEISHU_WIKI_NODE_PROJECT
#   或 config.local.json notifications.wiki.{space_id,nodes}

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
CONFIG_FILE="${FEISHU_CONFIG_PATH:-$WORKSPACE_ROOT/config.local.json}"

load_wiki_config() {
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
wiki = ((payload.get('notifications') or {}).get('wiki') or {})
nodes = wiki.get('nodes') or {}
print(str(wiki.get('space_id') or ''))
print(str(nodes.get('审查记录') or nodes.get('review') or ''))
print(str(nodes.get('技术方案') or nodes.get('design') or ''))
print(str(nodes.get('项目文档') or nodes.get('project') or ''))
PYCONFIG
}

CONFIG_VALUES="$(load_wiki_config 2>/dev/null || true)"
SPACE_ID="${FEISHU_WIKI_SPACE_ID:-$(printf '%s\n' "$CONFIG_VALUES" | sed -n '1p')}"

declare -A NODE_MAP
NODE_MAP["审查记录"]="${FEISHU_WIKI_NODE_REVIEW:-$(printf '%s\n' "$CONFIG_VALUES" | sed -n '2p')}"
NODE_MAP["技术方案"]="${FEISHU_WIKI_NODE_DESIGN:-$(printf '%s\n' "$CONFIG_VALUES" | sed -n '3p')}"
NODE_MAP["项目文档"]="${FEISHU_WIKI_NODE_PROJECT:-$(printf '%s\n' "$CONFIG_VALUES" | sed -n '4p')}"

if [ $# -lt 2 ]; then
  echo "Usage: $0 <markdown_file> <category: 审查记录|技术方案|项目文档>" >&2
  exit 1
fi

SRC_FILE="$1"
CATEGORY="$2"
PARENT_NODE="${NODE_MAP[$CATEGORY]:-}"

if [ -z "$SPACE_ID" ]; then
  echo "缺少 FEISHU_WIKI_SPACE_ID（或 config.local.json notifications.wiki.space_id）" >&2
  exit 1
fi
if [ -z "$PARENT_NODE" ]; then
  echo "未知分类或未配置节点: $CATEGORY (可选: 审查记录 技术方案 项目文档)" >&2
  exit 1
fi
if [ ! -f "$SRC_FILE" ]; then
  echo "文件不存在: $SRC_FILE" >&2
  exit 1
fi

TITLE=$(basename "$SRC_FILE" .md)
echo "[wiki] 发布: $SRC_FILE → $CATEGORY"

RESULT=$(lark-cli wiki +node-create \
  --space-id "$SPACE_ID" \
  --parent-node-token "$PARENT_NODE" \
  --title "$TITLE" \
  --obj-type docx 2>&1)

OBJ_TOKEN=$(echo "$RESULT" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('data',{}).get('obj_token',''))" 2>/dev/null)
URL=$(echo "$RESULT" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('data',{}).get('url',''))" 2>/dev/null)

if [ -z "$OBJ_TOKEN" ]; then
  echo "[wiki] 创建节点失败"
  exit 1
fi

lark-cli docs +update \
  --doc-token "$OBJ_TOKEN" \
  --api-version v2 \
  --content @"$SRC_FILE" 2>&1 | python3 -c "import json,sys; d=json.load(sys.stdin); print('OK' if d.get('ok') else d.get('error',{}).get('message','?'))" 2>/dev/null || true

echo "[wiki] 已发布: $URL"
