# scripts 目录结构与维护边界

本目录保留历史兼容的顶层入口脚本：外部 tmux/watcher/PM 指令可继续调用
`scripts/<name>`，新增共享逻辑优先沉淀到 `scripts/lib/`，避免继续膨胀单个入口脚本。

## 功能分组

### 任务生命周期入口

- `create-task.sh`：创建任务目录、`task.json`、`instruction.md` 与初始流转日志。
- `dispatch-task.sh`：将任务派发到指定 agent，并注入执行提示。
- `claim-task.sh` / `pool-task.sh` / `queue-task.sh` / `resume-task.sh`：任务池、预留、认领与恢复。
- `close-task.sh` / `archive-task.sh` / `reassign-task.sh`：收口、归档、改派。
- `write-ack.sh` / `write-result.sh` / `write-review.sh` / `write-verify.sh`：标准任务产物写入封装。

### Watcher 与运行时控制面

- `task-watcher.sh`：任务状态机主循环，保留为兼容入口。
- `task-watcher-watchdog.sh` / `tmux-watcher.sh`：常驻进程与 tmux 会话守护。
- `task-state-reducer.py` / `task-board-sync.py` / `task-board-governance.py`：状态归约与看板同步。
- `task-pool-router.py` / `task-queue-router.py` / `task-pool-view.py` / `task-inbox.py`：任务池、队列与收件箱视图。

### 通知与沟通

- `feishu-push.sh` / `report-to-feishu.sh` / `sync-gantt-to-feishu.sh`：飞书消息、日报与甘特图同步。
- `send-to-agent.sh`：面向 agent tmux 会话的可靠发送入口。
- `send-chat.sh` / `read-chat.sh` / `pm-chat-check.sh` / `lint-chat.sh` / `chat-metrics.py`：公开 chat hub 写入、读取、巡检与统计。

### 配置、模板与工作区

- `render-local-config.py`：生成本地配置视图。
- `build-agent-files.sh`：根据模板生成 agent 角色文件。
- `ensure-task-workspace.py`：确保任务 worktree/工作区存在。
- `install-codex-gateway-profile.py` / `codex-responses-gateway.py`：Codex gateway 相关工具。

### 报告、诊断与外部资料

- `daily-report.sh` / `_gen_report.py` / `dashboard-metrics.py` / `task-aggregate.py`：日报、仪表盘和聚合统计。
- `analyze-deps.py` / `refresh-deps-whiteboard.sh`：任务依赖分析与白板刷新。
- `daily-youtube-scan.sh` / `youtube-to-feishu.py`：YouTube 扫描与推送。
- `publish-to-wiki.sh` / `alert-card.sh` / `verify.sh`：发布、告警卡片与通用验证。

## 共享模块约定

- Python 共享逻辑放在 `scripts/lib/*.py`。
- Bash 共享逻辑放在 `scripts/lib/*.sh`，由顶层入口脚本 `source`。
- 顶层脚本应尽量保持“参数解析 + 编排”，业务规则和可复用函数逐步下沉到 `scripts/lib/`。
- 已有外部调用较多的顶层脚本暂不移动路径；若未来确需移动，必须先保留同名兼容 wrapper。

## 超大脚本拆分现状

当前超过 500 行的脚本及处理策略：

| 脚本 | 当前策略 |
| --- | --- |
| `task-watcher.sh` | 已先抽出通知/系统 chat 事件到 `scripts/lib/task_watcher_notifications.sh`；后续可继续按 runtime、routing、gate、queue 四个模块拆分。 |
| `teamctl.sh` | 仍作为团队控制入口；建议下一步拆出 agent/session 管理库。 |
| `scripts/lib/task_artifacts.py` | 已是共享库；建议下一步按 schema 读写、摘要提取、原子写入拆分。 |
| `create-task.sh` | 接近边界；建议后续拆出 task.json schema 构造与 worktree 初始化。 |

## 变更准则

1. 先新增共享模块，再让顶层入口 source/import，避免一次性大搬迁。
2. 保持 `bash -n scripts/*.sh scripts/lib/*.sh` 与 Python 编译检查通过。
3. 任何 watcher 拆分都必须验证通知去重、任务池派发、ready_for_merge 收口三条主链路。
