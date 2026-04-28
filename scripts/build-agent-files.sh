#!/bin/bash
# build-agent-files.sh - 从 design/agent-templates/ 构建各 agent 的 AGENT.md / CLAUDE.md
# 用法: ./scripts/build-agent-files.sh [--dry-run]

set -eo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
WORKSPACE="/Users/lin/Desktop/work/my-agent-teams"
TEMPLATES="$WORKSPACE/design/agent-templates"
BASE_MD="$TEMPLATES/base.md"
AGENTS_DIR="$WORKSPACE/agents"

DRY_RUN=""
[[ "${1:-}" == "--dry-run" ]] && DRY_RUN="1"

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

  # 生成文件内容
  {
    echo "# ${agent_id} - ${agent_file}"
    echo "> ⚠️ 本文件由 build-agent-files.sh 自动生成，请勿手动编辑。"
    echo "> 通用规则来自 design/agent-templates/base.md"
    echo "> 角色规则来自 design/agent-templates/${role_template}.md"
    echo "> 如需修改，请编辑模板文件后重新运行构建脚本。"
    echo ""
    echo "你是 \`${agent_id}\`（${role_template} 角色）。你的角色身份由本文件确定，不依赖 tmux session 名，也不从 instruction.md 推断。"
    echo ""
    echo "## 启动后立即执行"
    echo "1. 读取并遵守共享规则：\`${WORKSPACE}/CLAUDE.md\`"
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

# agent_id, role_template, agent_file
build_agent "pm-chief" "pm" "AGENT.md"
build_agent "arch-1" "architect" "AGENT.md"
build_agent "dev-1" "developer" "AGENT.md"
build_agent "dev-2" "developer" "AGENT.md"
build_agent "qa-1" "qa" "CLAUDE.md"
build_agent "review-1" "reviewer" "AGENT.md"

echo ""
echo "Done. $count agent file(s) generated."
