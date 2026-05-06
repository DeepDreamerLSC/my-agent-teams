# Code Review - 补修taskwatcher历史Done通知去重

## 结论
- **审查结论：通过（APPROVE）**
- **Architectural Status：CLEAR**
- **代码问题数：0（CRITICAL/HIGH/MEDIUM/LOW 均无）**
- 依据：`instruction.md`、`result.json`、原任务 `修正taskwatcher仅在任务最终完成后发飞书通知` 的 `review.md` / `verify.json`、当前 `scripts/task-watcher.sh` 与 `design/OpenClaw-tmux协作方案优化.md` diff。
- 说明：本任务目录当前 **无 `verify.json`**；本结论是代码/文档审查结论。`task.json.test_required=true`，后续仍应由 QA 产出 `verify.json` 后再最终收口。

## 审查范围
- `/Users/lin/Desktop/work/my-agent-teams/scripts/task-watcher.sh`
- `/Users/lin/Desktop/work/my-agent-teams/design/OpenClaw-tmux协作方案优化.md`
- `/Users/lin/Desktop/work/my-agent-teams/tasks/补修taskwatcher历史Done通知去重/result.json`

## 通过项

### 1. 已修复原 HIGH 阻塞：历史 done 任务不会在 watcher 重启后批量补发最终完成通知
- watcher 启动时记录本轮实例边界：
  - `scripts/task-watcher.sh:35-36`：`WATCHER_STARTED_AT_EPOCH="$(date +%s)"`
- 新增 `final_done_transition_epoch()`，只识别 `transitions.jsonl` 中最新的 `ready_for_merge -> done` 迁移时间：
  - `scripts/task-watcher.sh:912-944`
- `notify_final_done_if_needed()` 在发送前校验：
  - 没有合法 `ready_for_merge -> done` 迁移：只补种 `${task_id}_done_notice` sentinel，跳过通知；
  - 迁移早于本轮 watcher 启动：只补种 sentinel，跳过通知；
  - 仅本轮启动后产生的合法 done 迁移才发送“任务完成/部署完成”通知。
  - 对应实现：`scripts/task-watcher.sh:1668-1705`

这符合本任务“宁可少发历史通知，也不能批量补发误报”的约束。

### 2. 新近合法收口任务仍能触发一次最终完成通知
- done 观察分支仍对 `task.json.status=done` 调用 `notify_final_done_if_needed()`：
  - `scripts/task-watcher.sh:1750-1758`
- `close-task.sh` 的合法收口会写入 `from=ready_for_merge, to=done` 的 transition；当前 watcher 只要在运行中观察到该本轮启动后的迁移，就会发送一次最终完成通知，并随后写 sentinel 去重。
- 原有 `${task_id}_done_notice` 去重仍保留：`scripts/task-watcher.sh:1671-1674,1704`。

### 3. 已修复原 MEDIUM 文档不一致
- 文档已明确：`verify.json` 通过只负责自动收口到 `done`，不在 verify 分支发送最终完成类飞书：
  - `design/OpenClaw-tmux协作方案优化.md:930`
- 文档新增 done 观察分支描述：只有本轮 watcher 启动后出现 `ready_for_merge -> done` 迁移才统一发送一次“任务完成/部署完成”：
  - `design/OpenClaw-tmux协作方案优化.md:932`
- 通知机制段落也补充了 sentinel + transition 时间判定，说明历史 done 只补种 sentinel 不补发飞书：
  - `design/OpenClaw-tmux协作方案优化.md:939`

### 4. result.json 符合当前规范
- `result.json.status` 使用 `done`，符合当前 `AGENT.md` 规范（只允许 `done/failed/blocked`）。
- `result.json` 已包含实现策略、验证命令与剩余风险。

## 验证证据
- `bash -n /Users/lin/Desktop/work/my-agent-teams/scripts/task-watcher.sh`：通过。
- 只读历史 done 扫描（以当前时间模拟 watcher 新启动边界）：
  - `done_tasks_scanned=95`
  - `historical_done_that_would_notify_if_started_now=0`
  - `done_without_ready_for_merge_transition=2`
  - `done_with_transition_before_start=93`

该扫描与 dev-2 的 `result.json` 结论一致：历史 done 任务不会在当前补修逻辑下被批量补发最终完成通知。

## 严重级别 findings

### CRITICAL
无。

### HIGH
无。

### MEDIUM
无。

### LOW
无。

## 非阻塞备注
- 该方案会跳过 watcher 停止期间已经收口到 `done` 的任务最终通知；这是任务指令明确允许的取舍（“宁可少发历史通知，也不能批量补发误报”），且 `result.json.risks` 已如实记录。
- 本审查未实际重启常驻 watcher，也未发送飞书；这类端到端行为应由后续 QA 在受控环境验证。

## 最终意见
当前补修已解决原 review/QA 指出的两个阻塞点：历史 `done` 不再因 watcher 重启批量补发最终通知，文档也已从“verify 分支发送最终通知”修正为“done 观察分支统一发送”。代码审查 **APPROVE**。
