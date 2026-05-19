#!/bin/bash
# refresh-deps-whiteboard.sh — 依赖链拓扑图刷新到飞书画板
#
# 配置:
#   FEISHU_DEPS_DOC_TOKEN  目标飞书文档 token（必填）
#   FEISHU_DEPS_DOC_URL    成功日志展示 URL（可选）

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
WORKSPACE_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
DOC_TOKEN="${FEISHU_DEPS_DOC_TOKEN:-}"
DOC_URL="${FEISHU_DEPS_DOC_URL:-}"

if [ -z "$DOC_TOKEN" ]; then
  echo "[deps-board] 缺少 FEISHU_DEPS_DOC_TOKEN" >&2
  exit 1
fi

TMP_DIR=$(mktemp -d "${TMPDIR:-/tmp}/deps-whiteboard.XXXXXX")
trap 'rm -rf "$TMP_DIR"' EXIT

python3 "$SCRIPT_DIR/analyze-deps.py" > "$TMP_DIR/analysis.txt" 2>/dev/null
python3 "$SCRIPT_DIR/analyze-deps.py" mermaid > "$TMP_DIR/deps.mmd" 2>/dev/null || true

if [ ! -s "$TMP_DIR/deps.mmd" ]; then
  cat > "$TMP_DIR/deps.mmd" << 'MMDEOF'
flowchart TD
    subgraph Legend[图例]
        L1[🔴 blocked]
        L2[🟡 working/dispatched]
        L3[🟢 done]
    end
    T0["尚无依赖关系数据"]
    T0 ~~~ T1["等待任务间添加 depends_on 字段"]
    classDef blocked fill:#ff4444,color:white
    classDef working fill:#ff9900,color:white
    classDef done fill:#44bb44,color:white
    class L1 blocked
    class L2 working
    class L3 done
    class T0,T1 working
MMDEOF
fi

if cat "$TMP_DIR/deps.mmd" | npx -y @larksuite/whiteboard-cli@^0.2.11 -f mermaid -t openapi > "$TMP_DIR/openapi.json" 2>/dev/null; then
  echo "[deps-board] 渲染完成"
else
  echo "[deps-board] 渲染失败" >&2
  exit 1
fi

if lark-cli api PATCH "/open-apis/docx/v2/documents/$DOC_TOKEN/blocks" \
  --data @"$TMP_DIR/openapi.json" 2>/dev/null | python3 -c "import json,sys; d=json.load(sys.stdin); print('OK' if d.get('code')==0 else d.get('msg','?'))" 2>/dev/null; then
  if [ -n "$DOC_URL" ]; then
    echo "[deps-board] 画板已刷新: $DOC_URL"
  else
    echo "[deps-board] 画板已刷新"
  fi
else
  echo "[deps-board] 上传失败（此版本 API 可能需调整）" >&2
fi
