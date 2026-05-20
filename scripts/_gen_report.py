#!/usr/bin/env python3
"""Generate daily/weekly report from dashboard Gantt data."""
import json, sys
from datetime import datetime

mode = sys.argv[1]
type_label = sys.argv[2]
period_label = sys.argv[3]
today = sys.argv[4]
now = sys.argv[5]
outfile = sys.argv[6]
datafile = sys.argv[7]

with open(datafile) as f:
    gantt = json.load(f)

items = gantt.get("items", [])
core = {"pm-chief", "arch-1", "dev-1", "dev-2", "qa-1", "review-1"}
role_map = {"pm-chief": "PM", "arch-1": "架构师", "dev-1": "开发者",
            "dev-2": "开发者", "qa-1": "测试", "review-1": "审查"}

agents = {}
for i in items:
    a = i.get("assigned_agent", "")
    if a not in core:
        continue
    if a not in agents:
        agents[a] = {"total": 0, "done": 0, "blocked": 0, "ready_for_merge": 0}
    s = i.get("board_status", "")
    agents[a]["total"] += 1
    agents[a][s] = agents[a].get(s, 0) + 1

total_all = sum(a["total"] for a in agents.values())
done_all = sum(a["done"] for a in agents.values())
blocked_all = sum(a["blocked"] for a in agents.values())
merge_all = sum(a["ready_for_merge"] for a in agents.values())

done_tasks = sorted(
    [i for i in items if i.get("board_status") == "done" and i.get("assigned_agent") in core],
    key=lambda x: x.get("display_end_at", ""), reverse=True
)[:5]
blocked_tasks = [i for i in items if i.get("board_status") == "blocked" and i.get("assigned_agent") in core]

lines = []
lines.append(f"# agent 团队{type_label}（{period_label}）")
lines.append(f"生成时间：{now}")
lines.append("")
lines.append("## 概览")
lines.append("")
lines.append(f"- 总任务数：{total_all}")
pct = round(done_all / total_all * 100, 1) if total_all else 0
lines.append(f"- 已完成：{done_all}（{pct}%）")
lines.append(f"- 阻塞中：{blocked_all}")
lines.append(f"- 待合入：{merge_all}")
lines.append("")

lines.append("## 各角色负载")
lines.append("")
lines.append("| 角色 | 总 | 完成 | 阻塞 | 待合入 | 负载 |")
lines.append("|------|-----|------|------|--------|------|")
for a in ["pm-chief", "arch-1", "dev-1", "dev-2", "qa-1", "review-1"]:
    d = agents.get(a, {})
    t = d.get("total", 0)
    dn = d.get("done", 0)
    bl = d.get("blocked", 0)
    mg = d.get("ready_for_merge", 0)
    load = f"{round((bl + mg) / t * 100)}%" if t else "0%"
    lines.append(f"| {a}({role_map.get(a, a)}) | {t} | {dn} | {bl} | {mg} | {load} |")
lines.append("")

if done_tasks:
    lines.append("## 最近完成")
    lines.append("")
    for t in done_tasks:
        lines.append(f"- ✅ [{t.get('assigned_agent', '')}] {t.get('title', '?')[:50]}")
    lines.append("")

if blocked_tasks:
    lines.append("## 当前阻塞")
    lines.append("")
    for t in blocked_tasks[:10]:
        lines.append(f"- 🔴 [{t.get('assigned_agent', '')}] {t.get('title', '?')[:50]}")
    lines.append("")

lines.append("---")
lines.append("*本报告由 agent 团队自动生成*")

with open(outfile, "w") as f:
    f.write("\n".join(lines) + "\n")
