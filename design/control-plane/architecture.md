# 跨项目 Codex 交付控制面架构

## 边界

`my-agent-teams` 是控制面，业务项目是执行面。控制面只保存项目、需求、任务引用、会话元数据、阶段状态、事件摘要和交付物 URI/校验值；业务源代码、完整聊天记录和用户凭据留在业务项目或执行后端。

```text
Owner -> PM -> Architect -> Critic -> PM task plan
                                      |
              external Git worktree <- Developer
                                      |
                         independent Reviewer -> QA -> PM summary
                                      |
                          release-ready / Owner exception

control_plane SQLite
  projects / requirements / sessions / session_events
  gates / artifacts / owner_decisions / state_changes
             ^                 ^
        Codex backend       tmux compatibility backend
```

## 统一执行后端

`control_plane.backends.ExecutionBackend` 是管理层唯一依赖的契约：`create`、`register`、`health`、`disconnect`、`capabilities`。tmux 适配器只做兼容健康探测；Codex 适配器只接受官方线程/App Server/SDK bridge，默认未配置时返回 `unsupported`。`fake` 仅用于契约测试和临时演示，控制面会保留明确的 `execution_backend=fake` 标识，不能把 fake 结果写成真实会话结果。

本机 `codex app-server generate-json-schema --experimental` 已验证公开协议包含 `ThreadStart`、`ThreadList`、`ThreadRead` 等类型。控制面只定义可替换 bridge 边界，不绑定实验性 wire protocol 的私有实现；bridge 不可用时能力明确为 `unsupported`。

## 会话事件

每个事件同时拥有 `event_id` 和 `idempotency_key`。重复事件直接返回已有结果；序列号或时间戳倒退的事件仍保留在 `control_plane_session_events`，但 `applied=0`，不回退会话快照。没有心跳、心跳过期、后端探测异常分别显示 `unknown`、`offline` 或 `unsupported`。

## 工作流门禁

阶段定义在 `control_plane/workflow.py`。PM 可自动推进澄清、分解和汇总，但 Architecture、独立 Critic、Reviewer、QA 必须有对应角色会话、必需 artifact，并提交结构化 `verdict=pass`。驳回进入 `rework_required`；同一阶段连续三次驳回自动进入 Owner 收件箱。release-ready 只表示控制面已满足交付条件，不会触发生产部署。

## 兼容原则

- `tasks/`、`transitions.jsonl`、task watcher、tmux 和旧 dashboard 表继续可用。
- 现有 `config.json.projects` 启动时只做保守导入；失效根目录不会伪造在线状态。
- dashboard 是读视图，写操作统一走 `ControlPlaneService`。
- `overview.delivery` 只投影旧任务读模型中的任务池、依赖边、并行质量门禁和甘特数据；旧任务文件仍是这些事实的来源。
- 旧任务表和新控制面表共用 SQLite，但各自有 schema version，迁移只追加表和索引。
