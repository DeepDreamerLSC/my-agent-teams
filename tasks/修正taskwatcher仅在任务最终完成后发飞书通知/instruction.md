# 任务：修正 task-watcher 仅在任务最终完成后发飞书通知

## 任务类型
开发

## 目标
修正 `task-watcher` 的通知时机：**不要在 review 未完成、QA 未完成时就通过飞书/完成类提示说“任务已完成”**。必须等整个生命周期结束（review 通过、QA 通过、最终 `done`）后，才发“任务完成”通知。

## 任务边界
- 重点修改 task-watcher 的通知逻辑与文案时机。
- 不改任务事实源结构。
- 不改 Chat Hub 基础协议。
- 可以同步修 README / 主方案文档中的流程说明，使其与实现一致。

## 输入事实
- 当前 watcher 在 `result.json` 进入 `ready_for_merge` 时会发 `【任务完成】` 类 push_task_event，语义上容易误导为“任务已经最终完成”。
- 林总工明确要求：**必须等 review/QA/最终 done 后才能说任务完成。**
- 当前关键脚本：
  - `/Users/lin/Desktop/work/my-agent-teams/scripts/task-watcher.sh`
- 相关文档：
  - `/Users/lin/Desktop/work/my-agent-teams/README.md`
  - `/Users/lin/Desktop/work/my-agent-teams/design/OpenClaw-tmux协作方案优化.md`

## 约束
- write_scope:
  - `/Users/lin/Desktop/work/my-agent-teams/scripts/task-watcher.sh`
  - `/Users/lin/Desktop/work/my-agent-teams/README.md`
  - `/Users/lin/Desktop/work/my-agent-teams/design/OpenClaw-tmux协作方案优化.md`
- read_only: false
- target_environment: dev
- execution_mode: dev
- owner_approval_required: false
- 允许保留 PM 内部提醒“任务实现已完成、待审/待验”，但不能对外/对飞书表述成最终完成。
- 最终 `done` 的飞书通知必须保留。

## 交付物
- task-watcher 通知逻辑修正
- 文档同步
- `result.json`

## 验收标准
1. `result.json -> ready_for_merge` 阶段不再发送“任务已完成”类飞书通知。
2. review fail / QA fail 时不会误报“任务完成”。
3. 只有进入 `done` 终态后，才发送最终完成类通知。
4. 文档说明与代码行为一致。

## 下游动作
review
