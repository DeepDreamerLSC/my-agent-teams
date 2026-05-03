# 任务：实现 task-watcher 进程级可靠性（heartbeat + watchdog）

功能目录：`/Users/lin/Desktop/work/my-agent-teams/features/task-watcher可靠性优化/`
开始前必须先读：
- `/Users/lin/Desktop/work/my-agent-teams/features/task-watcher可靠性优化/BRIEF.md`
- `/Users/lin/Desktop/work/my-agent-teams/features/task-watcher可靠性优化/CONTEXT.md`
- `/Users/lin/Desktop/work/my-agent-teams/features/task-watcher可靠性优化/notes/dev.md`
- `/Users/lin/Desktop/work/my-agent-teams/features/task-watcher可靠性优化/notes/arch.md`
- `/Users/lin/Desktop/work/my-agent-teams/features/task-watcher可靠性优化/notes/qa.md`

## 背景
林总工已确认直接进入实施。按 feature 上下文与 arch-1 建议，第一条 execution 先做进程级可靠性。

## 你的任务
在不重写 watcher 架构的前提下，完成：
1. `task-watcher.sh` 周期性写 heartbeat 文件
2. 增加 watchdog / 自动重启脚本（建议新增 `scripts/task-watcher-watchdog.sh`）
3. 能检测：
   - watcher 进程退出
   - watcher 存活但 heartbeat 超时
4. 在异常情况下自动拉起/重启 watcher

## 约束
- 继续基于现有 shell watcher 架构做最小增强
- 不改变现有 `ack -> working -> ready_for_merge -> review -> QA -> close` 主链路语义
- 不要把 heartbeat/pid/restart-cause 文件纳入任务看板同步链

## 验收标准
1. heartbeat 文件存在且周期更新
2. watchdog 脚本能在 watcher 退出或 heartbeat 超时后重启 watcher
3. 不破坏现有 watcher 主流程
4. 相关验证命令通过

## 交付物
完成后写：
- `/Users/lin/Desktop/work/my-agent-teams/tasks/实现taskwatcher进程级可靠性/result.json`
