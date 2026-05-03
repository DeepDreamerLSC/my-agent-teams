# notes/arch.md

> 架构补充说明、约束变更、敏感区提醒

## 架构约束
1. 第一批优化继续以 `scripts/task-watcher.sh` 为主入口，不引入大规模技术栈迁移。
2. heartbeat / watchdog / 日志文件属于 watcher 自身运行时工件，**不得进入任务看板同步触发链**。
3. 任何日志写入失败都不能阻塞 `ack -> working -> ready_for_merge -> review -> QA -> close` 主链路。
4. 超时检测优先基于任务工件与明确状态，不要过度依赖 tmux pane 文本匹配。
5. 自动重启只能恢复 watcher 进程，不得重复执行 close-task 或重复推进已经完成的状态。

## 敏感区提醒
- `set_task_status()`
- `transitions.jsonl`
- `auto_dispatch_review()` / `auto_dispatch_qa()`
- `auto_close_task()`
- `send-to-agent.sh` 的投递确认逻辑

## 推荐实施顺序
- 先 heartbeat + watchdog
- 再持久化日志
- 最后超时策略优化

## 不建议本轮做的事
- watcher 改写为 Python 服务
- 引入文件系统事件监听替代轮询
- 全面重构消息投递协议
- 通知失败重试 / 去重体系重做
