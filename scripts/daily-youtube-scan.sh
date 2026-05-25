#!/bin/bash
# daily-youtube-scan.sh — 每天 6AM 扫 6 个 AI YouTube 频道 → 入库飞书
set -euo pipefail

SKILL_DIR="$HOME/.openclaw/skills/youtube-summarizer"
WORKSPACE_ROOT="${WORKSPACE_ROOT:-$HOME/Desktop/work/my-agent-teams}"
SCRIPT_DIR="$WORKSPACE_ROOT/scripts"
CONFIG_PATH="${CONFIG_PATH:-$WORKSPACE_ROOT/config.json}"
AGENT_CONFIG_PY="${AGENT_CONFIG_PY:-$SCRIPT_DIR/lib/agent_config.py}"
CONFIG="$WORKSPACE_ROOT/config/youtube-channels.json"
OUTPUT="/tmp/youtube_daily_$(date +%Y%m%d).json"
LOG="/tmp/youtube-daily.log"
YOUTUBE_API_KEY_AGENT="${YOUTUBE_API_KEY_AGENT:-}"

log() { echo "[$(date '+%H:%M:%S')] $*" | tee -a "$LOG"; }

log "=== 每日 YouTube 扫描 ==="

# 1. 获取 API key
if [ -z "$YOUTUBE_API_KEY_AGENT" ] && [ -r "$AGENT_CONFIG_PY" ]; then
  YOUTUBE_API_KEY_AGENT="$(python3 "$AGENT_CONFIG_PY" integration-owner --config "$CONFIG_PATH" 2>/dev/null || true)"
fi
YOUTUBE_API_KEY_AGENT="${YOUTUBE_API_KEY_AGENT:-integration-owner}"

API_KEY_SESSION="$YOUTUBE_API_KEY_AGENT"
if [ -r "$AGENT_CONFIG_PY" ]; then
  API_KEY_SESSION="$(python3 "$AGENT_CONFIG_PY" resolve-session "$YOUTUBE_API_KEY_AGENT" --config "$CONFIG_PATH" 2>/dev/null || printf '%s\n' "$YOUTUBE_API_KEY_AGENT")"
fi
KEY=$(tmux show-environment -t "$API_KEY_SESSION" 2>/dev/null | grep '^OPENAI_API_KEY=' | head -1 | cut -d= -f2-)
if [ -z "$KEY" ]; then
  KEY="${OPENAI_API_KEY:-}"
fi
if [ -z "$KEY" ]; then
  log "❌ 找不到 API key"
  exit 1
fi

# 2. 扫描频道
log "扫描频道..."
cd "$SKILL_DIR"
source venv/bin/activate
OPENAI_API_KEY="$KEY" python3 -u scripts/summarize.py \
  --config "$CONFIG" \
  --daily --output "$OUTPUT" 2>&1 | tee -a "$LOG"

if [ ! -f "$OUTPUT" ]; then
  log "❌ 没有输出文件"
  exit 1
fi

# 3. 入库飞书
log "入库飞书..."
OPENAI_API_KEY="$KEY" python3 -u "$SCRIPT_DIR/youtube-to-feishu.py" "$OUTPUT" 2>&1 | tee -a "$LOG"

log "✅ 完成"
