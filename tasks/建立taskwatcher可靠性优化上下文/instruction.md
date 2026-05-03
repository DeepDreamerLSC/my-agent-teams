# 任务：建立 task-watcher 可靠性优化共享上下文与拆分方案

功能目录：`/Users/lin/Desktop/work/my-agent-teams/features/task-watcher可靠性优化/`
开始前必须先读：
- `/Users/lin/Desktop/work/my-agent-teams/features/task-watcher可靠性优化/BRIEF.md`
- `/Users/lin/Desktop/work/my-agent-teams/features/task-watcher可靠性优化/CONTEXT.md`
- `/Users/lin/Desktop/work/my-agent-teams/features/task-watcher可靠性优化/notes/`

## 背景
林总工已确认 task-watcher 第一批优化范围：
1. 进程级可靠性（heartbeat + watchdog 自动重启）
2. 日志持久化（重要事件写文件，7天轮转）
3. 超时检测优化（区分无响应和工作中，减少误报）

本任务按新的功能级共享上下文协作规范执行：先建立 feature 级共享上下文，再由 PM 基于上下文拆 execution 子任务。

## 你的任务
请作为架构师完成：
1. 补全 `CONTEXT.md` 初版：
   - 涉及哪些模块/文件
   - 模块依赖关系
   - 敏感区域
   - 与现有自动流转、send-to-agent、close-task、日志/状态目录的耦合点
2. 在 `notes/arch.md` 中记录架构层补充约束
3. 在 `decisions.log` 中追加关键决策
4. 给出建议的任务拆分：
   - 哪些适合一个 execution 任务完成
   - 哪些需要拆成多个 execution 任务
   - 拆分顺序与依赖关系

## 方法论要求
- 先看现有实现，不要脱离当前 watcher/脚本结构空想重构
- 不要假设，直接基于当前 `scripts/task-watcher.sh`、`send-to-agent.sh`、`close-task.sh`、状态目录和日志现状给结论

## 交付物
完成后写：
- `/Users/lin/Desktop/work/my-agent-teams/tasks/建立taskwatcher可靠性优化上下文/result.json`

结果中请包含：
- CONTEXT.md 路径
- 建议拆分的 execution 任务清单
- 哪些点建议先做，哪些点后做
