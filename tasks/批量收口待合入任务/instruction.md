# 任务：使用收口脚本批量收口符合条件的 ready_for_merge 任务

## 背景

此任务由 PM 执行。在 `scripts/close-task.sh` 完成后，批量收口当前所有“责任链已闭环”的 `ready_for_merge` 任务。

## 你的任务
- 使用 `scripts/close-task.sh` 对当前 `my-agent-teams/tasks/` 下符合条件的任务做批量收口
- 只关闭真正满足闭环条件的任务

## 关闭条件建议
- 已有 review/QA/integration/deploy 结论，且后续没有未完成依赖
- 被后续修复任务吸收且最终链路已通过的旧任务，也可收口
- 仍缺关键 gate 的任务不得关闭

## write_scope
- `/Users/lin/Desktop/work/my-agent-teams/tasks`

## 交付物
完成后写 `/Users/lin/Desktop/work/my-agent-teams/tasks/批量收口待合入任务/result.json`，包括：
- 关闭了哪些任务
- 每个任务的关闭理由
- 仍保留 ready_for_merge 的任务及原因
