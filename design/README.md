# my-agent-teams 文档索引

> 更新时间：2026-08-14
> 范围：跨项目 Codex 交付控制面、任务管理、Chat Hub、任务看板、agent 配置。
> 规则：`tasks/` 是任务事实记录，`.omx/` 是运行态，二者不纳入正式设计文档整理。

## 当前优先阅读

### 项目入口
- `../README.md` — 项目总览、启动方式、当前作业流。
- `../AGENTS.md` — Codex 全局规则。
- `../CLAUDE.md` — Claude Code 全局规则。

### Agent 配置与模板
- `agent-templates/base.md` — 所有 agent 通用行为准则，模板唯一真相源。
- `agent-templates/pm.md` — PM 角色模板。
- `agent-templates/architect.md` — 架构边界、依赖方向、状态所有权与 ADR 模板。
- `agent-templates/critic.md` — 独立对抗审查角色模板。
- `agent-templates/developer.md` — 开发角色模板。
- `agent-templates/qa.md` — QA 通用流程模板。
- `agent-templates/software-qa.md` — 软件质量 QA 特化模板。
- `agent-templates/education-qa.md` — 教育质量 QA 特化模板。
- `agent-templates/reviewer.md` — 审查角色模板。
- `agent-templates/overlays/tmux.md` — tmux 运行时交付约定。
- `agent-templates/overlays/codex_app.md` — Codex App 运行时交付约定。
- `代码质量治理闭环.md` — quality report、自动门禁、返工、Owner 升级与交付摘要契约。

> `agents/<agent-id>/AGENT.md` 与 `agents/<agent-id>/CLAUDE.md` 由这些模板生成；不要把旧 `prompts/` 当作当前角色源。

### 协作架构与任务池
- `control-plane/architecture.md` — 控制面/执行面分离、统一 backend、会话事件和阶段门禁。
- `control-plane/gap-analysis.md` — 现状审计与已有/部分/缺失/废弃差距表。
- `control-plane/migration.md` — 控制面 schema 迁移、旧项目导入和回滚。
- `control-plane/integration-guide.md` — 外部项目注册、bootstrap/check/uninstall 和会话绑定。
- `control-plane/operations.md` — 日常检查、失联/阻塞/乱序事件和恢复规则。
- `collaboration/control-plane-and-task-pool.md` — 当前最新综合方案：任务事实层、编排执行层、通信时间线层、只读视图层，以及任务池优化。
- `collaboration/task-pool-claiming.md` — 任务池认领机制专项方案。
- `collaboration/parallelism-task-pool-and-gantt-optimization.md` — 并行度、任务池默认使用、watcher 续推与 Gantt 真实性优化方案。
- `collaboration/feature-shared-context.md` — 功能级共享上下文协作规范。

### Chat Hub
- `../chat/README.md` — Chat Hub A-Lite 当前运行说明。
- `chat-hub/protocol.md` — Chat Hub 协议、system 事件、priority/severity、看板桥接契约。
- `chat-hub/a-lite-usage.md` — A-Lite 验证期使用说明。
- `chat-hub/implementation-checklist.md` — A-Lite → 验证期 → B/C 的落地清单。
- `chat-hub/validation-record-template.md` — 每日验证记录模板。
- `chat-hub/validation-retro-template.md` — 验证期复盘模板。

### 任务看板
- `task-board/system-design.md` — 看板系统与 SQLite 数据模型基础方案。
- `task-board/optimization-plan.md` — 任务进展可视化、沟通串联、分析能力优化方案。
- `task-board/migration-strategy.md` — schema version、migrate、backfill、rebuild-all 策略。
- `task-board/deployment.md` — 看板独立部署方案。

### 专题上下文
- `../features/task-watcher可靠性优化/BRIEF.md` — task-watcher 可靠性优化专题简报。
- `../features/task-watcher可靠性优化/CONTEXT.md` — task-watcher 可靠性优化上下文。

## 已归档 / 历史参考

### 协作流程历史方案
- `archive/collaboration/openclaw-tmux-optimization-v15.md` — OpenClaw + tmux 超大历史总方案；当前入口已收敛到 `collaboration/control-plane-and-task-pool.md`。
- `archive/collaboration/multi-agent-workflow-optimization-v2.md` — 早期协作流程优化方案。
- `archive/collaboration/layered-pm-evolution.md` — 分层 PM 组织演进草案。

### 任务看板历史材料
- `archive/task-board/task-breakdown-2026-05-03.md` — 看板实施任务拆解。
- `archive/task-board/architecture-review-2026-05-03.md` — 看板架构审查记录。

### Chat Hub 历史审查
- `archive/chat-hub/architecture-review-2026-05-03.md` — Chat Hub 架构审查记录。

### 旧角色 Prompt
- `archive/prompts/*.md` — 旧 `prompts/` 角色 prompt 基底。当前角色配置以 `agent-templates/` 及生成的 `agents/*/AGENT.md` / `CLAUDE.md` 为准。

## 不纳入整理的文档

- `tasks/**/instruction.md`、`tasks/**/review.md`：任务事实记录，保留原位。
- `.omx/**`、`.pytest_cache/**`：运行态/缓存。
- `tests/fixtures/**`：测试夹具。
