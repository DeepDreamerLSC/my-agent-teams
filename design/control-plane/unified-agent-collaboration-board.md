# 统一 Agent 协作看板 MVP

## 目标与边界

本实现把现有 SQLite control plane 作为唯一任务事实源，提供中文优先的统一协作看板。它不读取任务 transcript，不把 JSON 文件、OpenClaw heartbeat 或前端内存提升为权威状态，也不新增 React 构建链。

第一阶段除“分层授权决定/策略启停”外均为只读：看板不能执行合并、部署、删除、重试、任务状态修改或门禁豁免。正式合入仍由现有独立审查、Local CI 和 merge-gate 约束。

## 事实源与最小迁移

数据库仍由 `TASK_BOARD_DB_PATH` 指向，通常是 `.omx/task-board/task-board.sqlite3`。

- 复用 `tasks`、`control_plane_projects`、`control_plane_requirements`、`control_plane_sessions`、`control_plane_session_events`、`control_plane_gates`、`control_plane_artifacts` 和 `control_plane_state_changes`。
- 若数据库已有 `control_plane_deliveries`，读模型优先使用它的 ACK、deadline 和完成事实；旧 schema 则从规范消息事件投影相同语义。
- `agent_event/v1` 直接写入 `control_plane_session_events.payload_json`；Inbox 只保存同一事件的路由状态与安全信封，不复制业务 payload，也不是第二个消息队列。
- 授权复用 `control_plane_authorizations` 与 `control_plane_authorization_policy_overrides`；Inbox/focus 使用 `control_plane_event_inbox`、`control_plane_event_routing_transitions`、`control_plane_focus_leases`。
- 迁移使用独立的 `collaboration_schema_version=4`，不占用核心 control-plane schema 的版本号。v3 只追加授权种类、digest、来源任务和平台 capability 字段；v4 为 deferred Inbox 事件补充专注任务绑定，避免跨项目或错误 checkpoint 排空，兼容 v1/v2/v3 数据库。
- 初始化显式提交事务，旧数据库可原地补表且不改写已有事实。

## `agent_event/v1` 合同

每个外部事件必须包含：

- `contract=agent_event/v1`
- 稳定的 `event_id`
- `project_id`、`task_id`、`session_id`
- `actor.id` 与角色、来源、带时区的 `created_at`
- `entity_type/entity_id`、`source_task_id`、可选 `destination_task_id`
- `priority`、`requires_human`、可选 `supersedes_event_id`、`sequence`
- 带时区的 `occurred_at`，以及服务端基于安全投影校验的 `payload_digest`
- 与事件相关的 `revision`、`delivery`、`review`、`local_ci`、`merge_gate`、`artifact` 或 `authorization` 安全投影

支持的业务事件：

| 阶段 | 事件 |
| --- | --- |
| 任务 | `TASK_CREATED`、`TASK_STARTED`、`TASK_PROGRESS`、`TASK_BLOCKED`、`TASK_COMPLETED` |
| 消息 | `MESSAGE_SENT`、`MESSAGE_DELIVERED`、`CALLBACK_RECEIVED` |
| 审查 | `READY_FOR_REVIEW`、`CHANGES_REQUESTED`、`FIX_READY`、`APPROVED` |
| 合入 | `MERGE_GATE_RUNNING`、`MERGE_READY`、`GATE_BLOCKED`、`MERGED` |
| 证据 | `ARTIFACT_CREATED`、`LOCAL_CI_COMPLETED` |
| 授权 | `AUTHORIZATION_REQUESTED`；系统生成 `AUTHORIZATION_ROUTED`、`AUTHORIZATION_GRANTED`、`AUTHORIZATION_DENIED`、`AUTHORIZATION_EXPIRED`、`AUTHORIZATION_PLATFORM_MANUAL_REQUIRED`、`AUTHORIZATION_CONSUMED` |

### 幂等、乱序和旧 HEAD

- `event_id` 同时是稳定身份和恢复游标。同一内容重复提交只返回 `duplicate=true`，不会重复推进状态。
- 同一 `event_id` 被复用为不同内容时返回冲突。
- session 内低于已接受 `sequence` 的事件保留，但标记 `applied=false/out_of_order_sequence`。
- 当前 HEAD 来自该任务最后一个已接受、带 `revision.head_sha` 的规范事件。
- 审查、CI 和 merge-gate 等 HEAD 绑定事件若指向旧 HEAD，会保留并标记 `applied=false/stale_head`，不能覆盖新 HEAD。
- `FIX_READY`、`READY_FOR_REVIEW` 或新的开发起点只有携带 `supersedes_head_sha` 指向当前 HEAD 时，才能明确推进到新 HEAD。
- 授权事件的幂等指纹不包含动态策略路由结果，因此策略调整后重放原事件仍是重复事件，而不是身份冲突。
- 新 HEAD 的 `FIX_READY/CHANGES_REQUESTED` 会把同一实体旧 HEAD 的 `APPROVED`、阻塞和等待合入 Inbox 项标为 superseded，并使旧 HEAD 未消费授权过期；审计事实仍保留。

### 消息与 ACK

同一项目内的 `delivery_id` 只允许按 `MESSAGE_SENT → MESSAGE_DELIVERED → CALLBACK_RECEIVED` 前进，并校验来源/目标任务不漂移；发送、送达和回调允许来自不同 session。`sent` 仅说明消息已发出；`delivered/ack_id` 表示送达；`callback_id` 才表示回调完成。已有 delivery ledger 的 deadline 超时会成为 stuck 事实。

## 只读投影与门禁

看板以 `(project_id, task_id)` 为卡片身份，把任务读模型、需求、多个 session 和规范事件合并。主要投影包括：

- 项目、需求、父子任务、依赖、developer/reviewer 路由；
- 当前阶段、运行/空闲/阻塞、开始/完成/最后活动和耗时；
- PR 编号、URL、源分支、HEAD/base/merge-base、open/mergeable；
- 当前 HEAD 的审查结论与 P0/P1/P2；
- Local CI `run_id`、状态、证据引用和 24 小时新鲜度；
- merge-gate 状态、阻断检查和只读 `allowed` 结论；
- 消息送达/ACK/回调、产物、报告和截图引用；
- 待授权请求及路由依据。

`merge_gate.allowed=true` 必须同时满足：

1. 当前 HEAD 最后一次审查结果为 `APPROVED`；
2. 当前 HEAD 存在 24 小时内通过的 Local CI；
3. 当前 HEAD 最后一次门禁事件为 `MERGE_READY`；
4. PR 为 open 且 `mergeable=true`；
5. 没有 `blocking_checks`。

该字段只是事实判断，不能触发合入。

## Stuck 与瓶颈规则

规则和事实依据同时返回给前端：

- development/fix/rereview/merge-gate/review 阶段 30 分钟无新活动；
- blocked/merge-blocked 阶段 15 分钟无新活动；
- delivery 已超过明确 ACK deadline 且未完成。

每条命中结果包含最后活动时间、已等待秒数和阈值。瓶颈区还展示阶段任务分布及尚未完成的依赖边数量。没有事件或 deadline 证据时不会凭猜测标记卡住。

## 实时数据流

```text
Agent / bridge
  -> POST /api/control-plane/agent-events
  -> validate + redact + idempotent write
  -> control_plane_session_events (SQLite/WAL)
  -> control_plane_event_inbox + routing transitions
  -> classify: immediate/escalate | route/deferred | dashboard_only
  -> focus critical section: wait for commit/test/push/pr_created checkpoint
  -> route target ACK or human decision
  -> GET /api/collaboration/events (SSE, id=event_id)
  -> browser applies unseen event_id and refreshes read model
  -> SSE disconnect: GET /api/collaboration/event-log?after_event_id=...
```

- SSE 接受 `Last-Event-ID` 或 `after_event_id`。
- 浏览器按 `event_id` 去重；游标失效时服务端发送 `cursor_reset`，客户端重新获取当前读模型。
- SSE 失败自动降级为 4 秒增量 polling，并周期性重连 SSE。
- 过滤后的查询也推进扫描游标，避免被其他任务的大量事件永久挡住。

## 通用 Inbox、不中断路由与 focus lease

Router 只能验证、去重、持久化、分类、路由与升级，不拥有 merge、deploy、凭据、生产或策略覆盖权限。每个事件都有 `RECEIVED → VALIDATED → DEDUPED → ROUTED → ACKED`，或 `ESCALATED` 的可恢复审计轨迹。

- `immediate_escalate`：用户指令、P0/安全、生产/凭据/原生平台授权、`manual_only`、当前 focus 的 HEAD/门禁失效、无法确定接收者。
- `route_deferred`：其他 PR 的 `CHANGES_REQUESTED/FIX_READY/APPROVED`、任务完成和 L1 文本授权，发往明确的 developer/reviewer/coordinator。
- `dashboard_only`：普通进展、未改变状态和陈旧/乱序审计事实，写入看板后由 dashboard ACK，不打断协调者。
- 活跃 focus lease 表达当前项目、任务、操作、HEAD、是否 critical section、下一安全检查点和过期时间。同一项目的非 immediate 事件在活跃 focus 下保持 `VALIDATED`，并绑定当时的 focus task；只有匹配的 `commit/test/push/pr_created/idle/manual` 检查点才能排空。其他项目不受该 lease 阻塞，无活跃 focus 时可立即路由。
- Inbox、focus、目标与 ACK 均持久化在 SQLite，进程重启后可继续处理。看板只显示摘要、数量、最高优先级、最老等待时间、目标和轨迹，不返回事件 payload 正文。

## 分层授权 MVP

策略版本为 `delegated_authorization/v1`，第一版只支持启停内置显式规则，不实现通用规则 DSL、自动审批学习或多级策略系统。

### L0 AUTO

仅当 `action + action_type + environment + target_scope + reversible` 完整命中启用的白名单规则时自动授权。当前动作包括只读检查、运行测试、临时制品、本地 CI 重试和任务工作区内本地服务重启。

### L1 REVIEWER/COORDINATOR

测试环境服务重启、验证快照恢复、受控故障注入可由 Reviewer、Coordinator 或 Owner 批准。`MERGE_PR` 还会实时检查当前 HEAD 的独立审查、CI、merge-gate 和 PR open/mergeable，不能借授权绕过既有门禁。

### L2 OWNER

生产、不可逆删除/覆盖、凭据/密钥/权限、真实数据迁移或批量修复、公网访问扩大、门禁豁免，以及任何未知、不完整或未命中规则的请求都路由到 Owner。

共同约束：

- 默认 fail-closed；信息不完整的请求虽然显示为 L2，但不能直接批准，必须补齐后重新申请。
- `exact_targets` 在分类前即绑定已注册项目根、session 工作区或明确的测试逻辑目标；超出当前项目/任务 scope 的伪装目标直接降为不可授予的 L2，消费时使用同一规则复验。
- 请求只允许 `secret_refs`，出现 `secret_value`、password、token、private key 等正文字段会直接拒绝且不落库。
- 每个决定保留 requester、approver、policy version、reason、request id、精确目标、环境、HEAD、过期时间和结果。
- grant 只能由原 requester 按完全相同的环境、精确目标和 HEAD 消费一次；目标、环境或 HEAD 改变必须重新申请。
- 决定必须有明确 approver identity 和理由；L1 不能处理 L2。
- 授权请求是一等事件，额外绑定 `requester_role`、`action_class`、`risk_tier`、`human_required`、`command_or_action_digest`、`scope`、`decision_actor/decision_time` 与 capability 状态。
- `command_or_action_digest` 由授权种类、动作、环境、target scope、精确目标、HEAD、可逆性和平台引用计算。请求、消费或平台点击记录时 digest 漂移均失败关闭。
- 完整命令、stdout/stderr、prompt、工具输入输出、学生正文、token、密码和凭据正文不能进入授权事件；只能保留 digest 与 `secret_refs`。

协作扩展只开放事件写入、Inbox ACK/focus checkpoint 与授权决定这些受限入口；它们不能执行合并、部署或平台原生授权。未配置 token 时仅接受 localhost；配置 `MY_AGENT_TEAMS_CONTROL_PLANE_TOKEN` 后要求 Bearer token。

### 文本授权与 Codex 原生 approval 的真实边界

| 能力 | 当前状态 | 实际行为 |
| --- | --- | --- |
| A. 协作事件路由 | 已真正可用 | 事件进入 SQLite Inbox，按 focus/checkpoint 路由或升级，目标任务 ACK 后闭环。 |
| B. 文本授权转发 | 已真正可用 | L0 精确策略可自动决定；L1/L2 由具备权限的 Reviewer/Coordinator/Owner 记录决定，结果回到原 `source_task_id` 并等待 ACK。 |
| C. Codex 原生 sandbox/tool approval | 平台仍需人工点击 | 控制面只检测并展示 `platform_manual_required`，用户完成平台点击后可记录结果；消息或文本决定不能冒充原生 approve。 |

平台能力实证检查覆盖了当前 `CodexThreadClient`/JSON command backend 与工作区 App Server bridge：前者只声明 health/register/create/disconnect；当前 bridge 虽有 list/read/message/turn 等动作，但没有跨任务读取 pending sandbox/tool approval 并 approve/deny 的动作。因而 `codex_platform` 请求始终 fail-closed 到 L2 Owner，普通 `/decision` 被拒绝，只允许 `/platform-decision` 在核对原 digest 后记录用户已经完成的最终平台点击；控制面不执行该点击，也不消费原生权限。

## 社区方案启发与排除

本实现借鉴 [Agent Board](https://github.com/quentintou/agent-board) 的 DAG、事件审计、只读视图与 stuck 思路，以及 [AgentPeek](https://github.com/TranHuuHoang/agentpeek) 的拓扑、时间线、SSE/polling fallback 和瓶颈表达。

没有复制上游代码，因此不需要 THIRD_PARTY_NOTICES。明确排除：

- 不采用 JSON 文件替代 SQLite；
- 不把 heartbeat 当作权威任务状态；
- 不对失败自动重试；
- 不用通用 review/done 取代独立审查与 merge-gate；
- 不展示完整 prompt、工具输入输出、日志、凭据、密钥正文或学生数据；
- 不引入 React Flow 或第二套构建链。

## 后续写能力门禁

若未来要从看板执行重试、合并或部署，必须另行满足：操作专用 API、独立鉴权、CSRF/重放防护、签名 webhook、冻结 HEAD、策略版本、一次性授权消费、完整审计、dry-run/回滚以及相应业务验收。在这些条件完成前，主体看板保持只读。

本 MVP 的 localhost/Bearer 边界只验证调用入口；`actor/approver` 身份仍由调用端声明，尚未绑定到平台登录主体。因此当前授权能力适合受信本地控制面，不能当作生产级身份认证。

本 MVP 暂缓：通用 Authorization Broker、自动审批规则引擎、授权攒批、多级策略 DSL、跨任务原生 Codex approval API、平台身份绑定、完整 prompt/tool trace、文件触碰内容视图、自动合并/部署/删除/失败重试。
