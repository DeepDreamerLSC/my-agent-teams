# 任务：实现 task-watcher 超时检测优化

功能目录：`/Users/lin/Desktop/work/my-agent-teams/features/task-watcher可靠性优化/`
开始前必须先读：
- `/Users/lin/Desktop/work/my-agent-teams/features/task-watcher可靠性优化/BRIEF.md`
- `/Users/lin/Desktop/work/my-agent-teams/features/task-watcher可靠性优化/CONTEXT.md`
- `/Users/lin/Desktop/work/my-agent-teams/features/task-watcher可靠性优化/notes/dev.md`
- `/Users/lin/Desktop/work/my-agent-teams/features/task-watcher可靠性优化/notes/arch.md`
- `/Users/lin/Desktop/work/my-agent-teams/features/task-watcher可靠性优化/notes/qa.md`

## 背景
这是第三条 execution，依赖：
- `实现taskwatcher进程级可靠性`
- `实现taskwatcher日志持久化`

## 你的任务
优化当前超时检测策略，减少误报：
1. `dispatched` 无 ack 且无 Working：超过 **3 分钟** 才重发
2. `Working` 超过 **30 分钟**：通知 PM 介入，不重发
3. 保留重发冷却，避免短时间重复重发
4. 让超时判断优先依据任务工件和明确状态，而不是只看 tmux pane 文本

## 约束
- 不大改 `send-to-agent.sh` 协议
- 不做通知去重体系重构
- 不改变现有 review / QA / close 主链路

## 交付物
完成后写：
- `/Users/lin/Desktop/work/my-agent-teams/tasks/实现taskwatcher超时检测优化/result.json`
