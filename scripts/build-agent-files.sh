#!/bin/bash
# build-agent-files.sh - 从 design/agent-templates/ 构建各 agent 的 AGENT.md / CLAUDE.md
# 用法: ./scripts/build-agent-files.sh [--dry-run] [--agent <agent-id>]

set -eo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE="${WORKSPACE_ROOT:-$(cd "$SCRIPT_DIR/.." && pwd)}"
CONFIG_PATH="${CONFIG_PATH:-$WORKSPACE/config.json}"
TEMPLATES="${AGENT_TEMPLATES_DIR:-$WORKSPACE/design/agent-templates}"
BASE_MD="$TEMPLATES/base.md"
AGENTS_DIR="${AGENTS_DIR:-$WORKSPACE/agents}"

DRY_RUN=""
AGENT_FILTER="${AGENT_FILTER:-}"
while [ $# -gt 0 ]; do
  case "$1" in
    --dry-run) DRY_RUN="1"; shift ;;
    --agent) AGENT_FILTER="${2:-}"; shift 2 ;;
    --help|-h)
      echo "usage: build-agent-files.sh [--dry-run] [--agent <agent-id>]" >&2
      exit 0
      ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
done

if [[ ! -f "$BASE_MD" ]]; then
  echo "❌ base.md not found: $BASE_MD"
  exit 1
fi

count=0

build_agent() {
  local agent_id="$1"
  local role_template="$2"
  local agent_file="$3"

  local template_file="$TEMPLATES/$role_template.md"
  local target_dir="$AGENTS_DIR/$agent_id"
  local target_file="$target_dir/$agent_file"

  if [[ ! -f "$template_file" ]]; then
    echo "⚠️  Template not found for $agent_id: $template_file (skipped)"
    return
  fi

  if [[ -n "$DRY_RUN" ]]; then
    echo "📝 [DRY-RUN] Would generate: $target_file"
    count=$((count + 1))
    return
  fi

  mkdir -p "$target_dir"
  {
    echo "# ${agent_id} - ${agent_file}"
    echo "> ⚠️ 本文件由 build-agent-files.sh 自动生成，请勿手动编辑。"
    echo "> 通用规则来自 design/agent-templates/base.md"
    echo "> 角色规则来自 design/agent-templates/${role_template}.md"
    echo "> 如需修改，请编辑模板文件后重新运行构建脚本。"
    echo "> 同一 agent 同时生成 AGENT.md 与 CLAUDE.md，林总工可按运行时规划选择 Codex 或 Claude Code。"
    echo ""
    echo "你是 \`${agent_id}\`（${role_template} 角色）。你的角色身份由本文件确定，不依赖 tmux session 名，也不从 instruction.md 推断。"
    echo ""
    echo "## 启动后立即执行"
    echo "1. 读取并遵守根共享规则：\`${WORKSPACE}/AGENTS.md\` 与 \`${WORKSPACE}/CLAUDE.md\`（按当前运行时读取对应文件）"
    echo "2. 当前工作目录固定为：\`${target_dir}\`"
    echo "3. 所有共享资源都用绝对路径访问"
    echo ""
    echo "---"
    echo "## 通用行为准则"
    echo ""
    cat "$BASE_MD"
    echo ""
    echo "---"
    echo "## ${role_template} 角色规则"
    echo ""
    cat "$template_file"
  } > "$target_file"

  echo "✅ Generated: $target_file"
  count=$((count + 1))
}

build_agent_pair() {
  local agent_id="$1"
  local role_template="$2"
  if [ -n "$AGENT_FILTER" ] && [ "$AGENT_FILTER" != "$agent_id" ]; then
    return
  fi
  build_agent "$agent_id" "$role_template" "AGENT.md"
  build_agent "$agent_id" "$role_template" "CLAUDE.md"
}

load_agents_from_config() {
  python3 - "$CONFIG_PATH" <<'PY'
import json
import sys
from pathlib import Path

role_map = {
    "pm": "pm",
    "architect": "architect",
    "fullstack_dev": "developer",
    "developer": "developer",
    "qa": "qa",
    "reviewer": "reviewer",
}
config_path = Path(sys.argv[1]).expanduser()
if not config_path.exists():
    raise SystemExit(1)
config = json.loads(config_path.read_text(encoding="utf-8"))
for agent_id, payload in (config.get("agents") or {}).items():
    role = str((payload or {}).get("role") or "").strip()
    template = role_map.get(role)
    if template:
        print(f"{agent_id}\t{template}")
PY
}

AGENT_LINES="$(load_agents_from_config || true)"
if [ -n "$AGENT_LINES" ]; then
  while IFS=$'\t' read -r agent_id role_template; do
    [ -n "$agent_id" ] || continue
    build_agent_pair "$agent_id" "$role_template"
  done <<< "$AGENT_LINES"
else
  echo "⚠️  Could not load agents from $CONFIG_PATH; using built-in fallback" >&2
  build_agent_pair "pm-chief" "pm"
  build_agent_pair "arch-1" "architect"
  build_agent_pair "dev-1" "developer"
  build_agent_pair "dev-2" "developer"
  build_agent_pair "qa-1" "qa"
  build_agent_pair "review-1" "reviewer"
fi

echo ""
echo "Done. $count agent file(s) generated."
