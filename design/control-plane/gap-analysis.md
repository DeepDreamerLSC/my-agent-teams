# 跨项目 Codex 交付控制面差距表

> 审计日期：2026-08-13
> 审计范围：项目注册、任务生命周期、依赖/任务池/甘特、角色规则、watcher/派发/tmux、后台/API/测试、既有阶段一至阶段四与 3.5 设计。

## 现状结论

仓库已经具备可运行的任务协作控制面，但控制面仍以 `tasks/` 文件、shell watcher 和 tmux 约定为中心。`config.json` 中已有跨项目根目录注册，任务状态机、依赖、池化、独立 worktree、Review/QA/PM 门禁和 dashboard 读模型也已存在。缺少的是面向外部业务项目的持久化纳管层：项目、需求、Codex 会话、可替换执行后端、幂等事件、阶段门禁、交付证据和 Owner 例外需要从脚本约定提升为统一服务契约。

## 差距表

| 能力域 | 已有能力 | 部分实现 | 缺失能力 | 应废弃或收敛 | 证据 |
| --- | --- | --- | --- | --- | --- |
| 项目组合 | `config.json.projects` 已登记 `chiralium`、`my-agent-teams`、`edu-agent`，含 dev/prod 根目录和目标分支 | 注册主要是配置读取，缺少可审计注册记录和项目健康状态 | 外部项目注册、根目录校验、项目状态/能力 | 各脚本重复解析 project 和路径的逻辑应收敛到项目服务 | `config.json`, `scripts/lib/task_workspace.py` |
| 任务生命周期 | `task-state-reducer.py`、`task-watcher.sh`、`transitions.jsonl`、ACK/result/review/verify 产物 | reducer 与 watcher 仍有重复判断，部分状态语义在脚本中分叉 | 需求级工作流、阶段入口/输出/通过/驳回契约 | 保留文件事实源；逐步让统一服务负责外部纳管，不直接替换兼容脚本 | `scripts/task-state-reducer.py`, `scripts/task-watcher.sh` |
| 依赖与并行池 | `depends_on/blocks`、pool/router/queue、WIP 和 write_scope 冲突校验 | 多个命令入口各自实现过滤和排序 | 跨项目并行度和依赖的统一管理 API | 重复的命令式路由判定应由服务层提供只读投影 | `scripts/task-pool-view.py`, `scripts/task-pool-router.py`, `scripts/task-queue-router.py` |
| 甘特与指标 | SQLite 派生表、甘特阶段、项目筛选、历史事件和统计 | 主要展示任务，缺少会话健康和需求阶段 | 跨项目交付状态、会话活动、门禁和证据时间线 | 不把 dashboard SQLite 当业务代码事实源；保留其任务读模型 | `dashboard/db.py`, `dashboard/query.py`, `dashboard/static/js/dashboard.js` |
| 角色与行为 | PM/Architect/Developer/Reviewer/QA 模板、生成链路、独立 workdir | 角色规则主要约束本地 task/tmux 流程 | 外部 Codex 会话角色、独立 Critic、高风险审查最小上下文 | `prompts/` 仅保留兼容归档，不再新增 live 角色规则 | `design/agent-templates/*.md`, `scripts/build-agent-files.sh` |
| 派发与 watcher | dispatch gate、send-to-agent、watcher、tmux watcher/watchdog | tmux 送达和控制面状态分散，失联判定不统一 | 后端无关的执行会话注册、心跳、事件接收、失联检测 | tmux 保留为兼容 backend，不再作为管理层的唯一抽象 | `scripts/dispatch-task.sh`, `scripts/task-watcher.sh`, `scripts/send-to-agent.sh` |
| Codex 集成 | 仓库已有 Codex gateway 配置和 agent runtime 字段 | 没有外部 Codex thread/session 持久化模型 | 官方线程/App Server 可替换适配器；能力不可用时 unknown/unsupported | 禁止读取 Desktop 私有 DB 或 transcript 文件作为事实源 | `config.json`, `scripts/install-codex-gateway-profile.py` |
| Owner 管理 | PM Inbox 已聚合 blocked/timeout/验收待处理 | 仍以 task 问题为主，选项/影响/推荐/截止时间不成结构 | 独立 Owner decision inbox，只收范围/资源/不可逆/生产/安全/多次失败 | 过程噪声不得直接进入 Owner inbox | `scripts/task-inbox.py`, `dashboard/app.py` |
| 接入与迁移 | 有 task workspace 和配置示例，dashboard schema 可初始化 | schema version 只是 metadata，缺少控制面迁移 runner | bootstrap/check/uninstall、预览/冲突/回滚、外部项目清单迁移 | 不覆盖已有 AGENTS.md、未提交修改或业务代码 | `dashboard/db.py`, `design/task-board/migration-strategy.md` |
| 测试与证据 | 任务、看板、池、worktree、gateway 回归测试 | 没有会话/事件/后端契约/工作流集成测试 | fake Codex backend、幂等/乱序/重试/注册绑定/全流程 demo | 沙箱网络限制下的 gateway 测试需单独标记环境缺口 | `tests/`, `dashboard/tests/` |

## 实施边界

1. 控制面只保存项目、需求、任务、会话元数据、状态事件、摘要和交付物引用，不复制完整聊天记录。
2. 现有 `tasks/`、`transitions.jsonl`、watcher、tmux 和 dashboard 继续可用；新增控制面表采用同一 SQLite 连接并通过幂等迁移追加。
3. Codex backend 使用可替换协议适配器。没有官方线程能力或配置时返回 `unsupported`/`unknown`，不猜测在线状态。
4. 外部项目接入默认只生成 `.my-agent-teams/` 管理文件和可选的 AGENTS 引用；已有规则冲突必须先报告，不能覆盖。
5. 生产发布、凭据、付费外部操作和不可逆迁移不由控制面自动执行。

## 分阶段完成标准

| 阶段 | 交付物 | 验证 | 提交门槛 |
| --- | --- | --- | --- |
| A | 控制面 SQLite 迁移、项目/需求/会话/事件/证据/Owner 表 | 迁移幂等、旧库兼容、约束测试 | Lore commit |
| B | tmux/Codex/fake 统一 backend、注册绑定、事件/心跳/失联 | backend 契约、幂等/乱序/重试测试 | Lore commit |
| C | PM 阶段状态机、门禁和 Owner inbox | 全流程状态机测试 | Lore commit |
| D | dashboard API 与关键视图 | API/前端契约、空/失败/失联状态测试 | Lore commit |
| E | 外部项目 bootstrap/check/uninstall 与 demo | 临时 Git 项目端到端演示 | Lore commit |
| F | README、架构、接入、运维/恢复、迁移文档 | 文档命令 smoke + 全量回归 | Lore commit |

## 完成审计

截至 2026-08-13，A-F 均已实现并完成独立验证：控制面 schema 与旧任务兼容、tmux/Codex/fake backend、会话注册绑定和幂等事件、PM 阶段门禁与独立审查、dashboard API/视图、外部项目 bootstrap/check/uninstall、临时 Git 项目全流程演示及接入/迁移/运维文档均已落地。Codex Desktop 的真实 App Server bridge 仍是可选部署项，未配置时按设计显示 `unsupported`。
