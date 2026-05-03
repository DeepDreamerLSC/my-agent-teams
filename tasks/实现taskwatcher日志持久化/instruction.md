# 任务：实现 task-watcher 持久化日志与 7 天轮转

功能目录：`/Users/lin/Desktop/work/my-agent-teams/features/task-watcher可靠性优化/`
开始前必须先读：
- `/Users/lin/Desktop/work/my-agent-teams/features/task-watcher可靠性优化/BRIEF.md`
- `/Users/lin/Desktop/work/my-agent-teams/features/task-watcher可靠性优化/CONTEXT.md`
- `/Users/lin/Desktop/work/my-agent-teams/features/task-watcher可靠性优化/notes/dev.md`
- `/Users/lin/Desktop/work/my-agent-teams/features/task-watcher可靠性优化/notes/arch.md`
- `/Users/lin/Desktop/work/my-agent-teams/features/task-watcher可靠性优化/notes/qa.md`

## 背景
这是第二条 execution，依赖：`实现taskwatcher进程级可靠性`。

## 你的任务
实现 watcher 的重要事件文件日志：
1. 记录关键事件：
   - 状态流转
   - 自动派发
   - 超时重发
   - review / QA 路由
   - 自动收口
   - 外部脚本失败
   - watchdog 重启
2. 日志落点：`~/.openclaw/workspace/logs/task-watcher.log`
3. 实现 7 天轮转 / 保留
4. 日志写入失败不得阻塞主流转

## 约束
- 基于当前 shell watcher 做最小增强
- 不把日志文件纳入 board sync 触发链
- 不顺手做通知重试/去重改造

## 交付物
完成后写：
- `/Users/lin/Desktop/work/my-agent-teams/tasks/实现taskwatcher日志持久化/result.json`
