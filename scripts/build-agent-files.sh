#!/bin/bash
# build-agent-files.sh - 从 design/agent-templates/ 构建各 agent 的 AGENT.md / CLAUDE.md
# 用法: ./scripts/build-agent-files.sh [--dry-run] [--agent <agent-id>]

set -eo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE="${WORKSPACE_ROOT:-$(cd "$SCRIPT_DIR/.." && pwd)}"
CONFIG_PATH="${CONFIG_PATH:-$WORKSPACE/config.json}"
TEMPLATES="${AGENT_TEMPLATES_DIR:-$WORKSPACE/design/agent-templates}"
BASE_MD="$TEMPLATES/base.md"
OVERLAYS_DIR="$TEMPLATES/overlays"
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

for required in "$BASE_MD" "$OVERLAYS_DIR/tmux.md" "$OVERLAYS_DIR/codex_app.md"; do
  if [[ ! -f "$required" ]]; then
    echo "missing required template: $required" >&2
    exit 1
  fi
done

count=0

render_agent_file() {
  local agent_id="$1"
  local role_templates="$2"
  local overlay_name="$3"
  local project_id="${4:-}"
  local overlay_file="$OVERLAYS_DIR/$overlay_name.md"
  local template_label="${role_templates//,/ + }"
  local -a template_names=()
  local role_template=""

  IFS=',' read -r -a template_names <<< "$role_templates"
  for role_template in "${template_names[@]}"; do
    if [[ ! -f "$TEMPLATES/$role_template.md" ]]; then
      echo "template not found for $agent_id: $TEMPLATES/$role_template.md" >&2
      exit 1
    fi
  done
  if [[ ! -f "$overlay_file" ]]; then
    echo "overlay not found for $agent_id: $overlay_file" >&2
    exit 1
  fi

  {
    echo "# ${agent_id} - Role Contract"
    echo "> ⚠️ 本文件由 build-agent-files.sh 自动生成，请勿手动编辑。"
    echo "> Core 来源: design/agent-templates/base.md"
    for role_template in "${template_names[@]}"; do
      echo "> 角色来源: design/agent-templates/${role_template}.md"
    done
    echo "> Overlay 来源: design/agent-templates/overlays/${overlay_name}.md"
    echo "> 同一 agent 的 AGENT.md 与 CLAUDE.md 内容保持一致；运行时差异只来自 overlay。"
    echo ""
    echo "你是 \`${agent_id}\`（${template_label} 角色）。角色身份以本文件为准，不从任务描述、会话名称或历史习惯推断。"
    if [[ -n "$project_id" ]]; then
      echo "长期项目绑定：\`${project_id}\`。当前任务边界、授权和优先级仍以任务工件为准。"
    fi
    echo ""
    echo "---"
    echo "## 共享核心契约"
    echo ""
    cat "$BASE_MD"
    echo ""
    echo "---"
    for role_template in "${template_names[@]}"; do
      echo "## ${role_template} 角色契约"
      echo ""
      cat "$TEMPLATES/$role_template.md"
      echo ""
      echo "---"
    done
    echo "## 运行时 Overlay"
    echo ""
    cat "$overlay_file"
  }
}

build_agent_pair() {
  local agent_id="$1"
  local role_templates="$2"
  local overlay_name="$3"
  local project_id="${4:-}"
  local target_dir="$AGENTS_DIR/$agent_id"
  local target_content=""

  if [[ -n "$AGENT_FILTER" && "$AGENT_FILTER" != "$agent_id" ]]; then
    return
  fi

  if [[ -n "$DRY_RUN" ]]; then
    echo "📝 [DRY-RUN] Would generate: $target_dir/AGENT.md"
    echo "📝 [DRY-RUN] Would generate: $target_dir/CLAUDE.md"
    count=$((count + 2))
    return
  fi

  mkdir -p "$target_dir"
  target_content="$(render_agent_file "$agent_id" "$role_templates" "$overlay_name" "$project_id")"
  printf '%s\n' "$target_content" > "$target_dir/AGENT.md"
  printf '%s\n' "$target_content" > "$target_dir/CLAUDE.md"
  echo "✅ Generated: $target_dir/AGENT.md"
  echo "✅ Generated: $target_dir/CLAUDE.md"
  count=$((count + 2))
}

load_agents_from_config() {
  python3 - "$CONFIG_PATH" <<'PY'
import json
import sys
from pathlib import Path

role_map = {
    "pm": ("pm",),
    "architect": ("architect",),
    "critic": ("critic",),
    "fullstack_dev": ("developer",),
    "developer": ("developer",),
    "qa": ("qa",),
    "software_qa": ("qa", "software-qa"),
    "education_qa": ("qa", "education-qa"),
    "reviewer": ("reviewer",),
}


def resolve_overlay(payload: dict, source: str, agent_id: str) -> str:
    surface = str((payload or {}).get("execution_surface") or "").strip()
    runtime = str((payload or {}).get("runtime") or "").strip()
    if surface:
        if surface in {"tmux", "codex_app"}:
            return surface
        raise SystemExit(
            f"Unsupported execution_surface '{surface}' for {source}:{agent_id}"
        )
    if runtime in {"codex", "claude_code"}:
        return "tmux"
    raise SystemExit(
        f"Unable to resolve execution surface for {source}:{agent_id}; "
        "set execution_surface or a supported runtime"
    )


config_path = Path(sys.argv[1]).expanduser()
if not config_path.exists():
    raise SystemExit(1)
config = json.loads(config_path.read_text(encoding="utf-8"))
seen = set()


def emit(agent_id: str, payload: dict, source: str, project_id: str = "") -> None:
    role = str((payload or {}).get("role") or "").strip()
    templates = role_map.get(role)
    if not templates or agent_id in seen:
        return
    overlay = resolve_overlay(payload or {}, source, agent_id)
    seen.add(agent_id)
    print(f"{agent_id}\t{','.join(templates)}\t{overlay}\t{project_id}")


for agent_id, payload in (config.get("agents") or {}).items():
    emit(agent_id, payload, "agents")
for project_id, project_agents in (config.get("project_agents") or {}).items():
    for agent_id, payload in (project_agents or {}).items():
        emit(agent_id, payload, f"project_agents.{project_id}", str(project_id))
PY
}

AGENT_LINES="$(load_agents_from_config)"
while IFS=$'\t' read -r agent_id role_templates overlay_name project_id; do
  [[ -n "$agent_id" ]] || continue
  build_agent_pair "$agent_id" "$role_templates" "$overlay_name" "$project_id"
done <<< "$AGENT_LINES"

echo ""
echo "Done. $count agent file(s) generated."
