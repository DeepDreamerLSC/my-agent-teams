#!/bin/bash
# 日报推送脚本 - 由 OpenClaw cron 触发
# 扫描 task 目录，生成进展摘要并推送飞书

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
TASKS_ROOT="$WORKSPACE_ROOT/tasks"
PUSH_SCRIPT="$SCRIPT_DIR/feishu-push.sh"

REPORT=$(python3 << 'PYREPORT'
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

tasks_root = Path("/Users/linsuchang/Desktop/work/my-agent-teams/tasks")
tz = timezone(timedelta(hours=8))
now = datetime.now(tz)
today = now.strftime("%Y-%m-%d")
yesterday = (now - timedelta(days=1)).strftime("%Y-%m-%d")

# Agent 角色
AGENT_ORDER = ["pm-chief", "arch-1", "dev-1", "dev-2", "qa-1", "review-1"]
AGENT_ROLES = {
    "pm-chief": "🤵 PM",
    "arch-1": "🏗  架构",
    "dev-1": "💻 开发①",
    "dev-2": "💻 开发②",
    "qa-1": "🧪 测试",
    "review-1": "🔍 审查",
}

lines = []
lines.append(f"📋 小秘日报 | {today}")
lines.append("")

# 分类统计 — 按角色分组
active = {}       # agent -> [(title, status)]
today_done = {}   # agent -> [title]
recent_blocked = []

for d in sorted(tasks_root.iterdir()):
    if not d.is_dir() or d.name == "_templates":
        continue
    tj = d / "task.json"
    if not tj.exists():
        continue
    try:
        t = json.loads(tj.read_text())
    except:
        continue
    status = t.get("status", "unknown")
    agent = t.get("assigned_agent", "?")
    title = t.get("title", d.name)[:80]
    updated = str(t.get("updated_at", ""))

    # 在途任务：不限更新时间，只要状态还在跑就显示
    if status in ("dispatched", "working", "blocked"):
        active.setdefault(agent, []).append((title, status))
    # 今日完成：只看 updated_at 在今天内的 done 任务
    if today in updated and status == "done":
        today_done.setdefault(agent, []).append(title)

# 在途任务 — 按角色排列
if active:
    lines.append("━━━ 📌 在途任务 ━━━")
    for agent in AGENT_ORDER:
        if agent not in active:
            continue
        role = AGENT_ROLES.get(agent, agent)
        for title, st in active[agent]:
            icon = "🔴" if st == "blocked" else "🔄"
            lines.append(f"  {icon} [{role}] {title}")
    lines.append("")

# 今日完成 — 按角色排列
if today_done:
    lines.append("━━━ ✅ 今日已完成 ━━━")
    for agent in AGENT_ORDER:
        if agent not in today_done:
            continue
        role = AGENT_ROLES.get(agent, agent)
        for title in today_done[agent]:
            lines.append(f"  ✅ [{role}] {title}")
        lines.append("")

# 阻塞项
if recent_blocked:
    lines.append("━━━ 🚨 阻塞任务 ━━━")
    for agent, title, _ in recent_blocked:
        role = AGENT_ROLES.get(agent, agent)
        lines.append(f"  🔴 [{role}] {title}")
    lines.append("")

# Agent 在线状态
tmux_sessions = set()
try:
    import subprocess
    r = subprocess.run(["tmux", "list-sessions"], capture_output=True, text=True, timeout=3)
    for line in r.stdout.strip().split("\n"):
        sname = line.split(":")[0].strip()
        tmux_sessions.add(sname)
except:
    pass

lines.append("━━━ 🤖 Agent 状态 ━━━")
agent_session_map = {
    "pm-chief": "pm-chief",
    "arch-1": "arch-1",
    "dev-1": "dev-1-2",
    "dev-2": "dev-2",
    "qa-1": "qa-1",
    "review-1": "review-1",
}
for aid in AGENT_ORDER:
    sname = agent_session_map.get(aid, aid)
    alive = "🟢 在线" if sname in tmux_sessions else "⚫ 离线"
    role = AGENT_ROLES.get(aid, aid)
    lines.append(f"  {alive} [{role}]")

# 统计 — 仅今日
active_count = sum(len(items) for items in active.values())
done_count = sum(len(items) for items in today_done.values())
lines.append("")
lines.append("━━━ 📊 今日统计 ━━━")
lines.append(f"  完成: {done_count} | 在途: {active_count}")
lines.append(f"  在线 Agent: {sum(1 for _, s in agent_session_map.items() if s in tmux_sessions)}/6")

# 生成纯文本（飞书 text 消息用 \n）
print("\n".join(lines))
PYREPORT
)

# 推送到飞书
echo "$REPORT" | "$PUSH_SCRIPT"
