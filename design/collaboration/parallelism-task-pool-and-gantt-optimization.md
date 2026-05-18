# 并行度、任务池与甘特图真实性优化方案

> 创建日期：2026-05-16  
> 状态：增量实施中（Phase 1/2/3 主路径已落地，Phase 3.5 控制面 hardening 与 Phase 4 待实现）  
> 适用范围：`my-agent-teams` 的 PM 拆分、任务池认领、watcher 续推、dashboard/Gantt 数据口径  
> 相关文档：`control-plane-and-task-pool.md`、`task-pool-claiming.md`、`task-board/optimization-plan.md`
>
> 文档定位：本文是对现有 control-plane / task-pool 设计的**增量修订稿**，用于补强并行度、任务池和 Gantt 真实性，不另起一套平行事实源。系统事实源仍是 `task.json`、标准 artifact、脚本状态流转与 dashboard/query 聚合。

## 0. 一句话结论

本轮优化启动前，并行度不足的主要原因不是 agent 数量绝对不够，而是：

```text
PM 虽然拆了任务，但仍以直接派发和手动接续为主
        ↓
任务池没有形成稳定、可认领的库存
        ↓
watcher 虽已具备 pooled nudge / timeout / 局部续推能力，但尚未形成完整、可审计、面向 idle agent 的持续喂给闭环
        ↓
看板/Gantt 仍主要读取 task.json 状态与粗粒度时间点，不能稳定反映真实执行负载
```

目标不是简单把 WIP 调大，而是把协作模式改成：

```text
PM 批量拆 DAG
  -> 默认入池 pooled
  -> watcher 按依赖/write_scope/角色能力自动续推
  -> agent ack 后才进入真实 working
  -> dashboard 展示 pool depth、idle、queue wait、真实执行段
```

如果任务池水位为 0，增加 watcher 逻辑或增加 CLI 会话都不会提升吞吐；所有 agent 只会一起等待 PM 手动派下一条。

但这个结论有一个前提：**任务定义必须先正确**。如果根因未明、接口契约未稳、owner 决策未完成，就不应为了并行度而提前铺开修复 DAG；此时正确做法是先创建 diagnosis / investigation / design 任务，把根因和边界收敛后再进入 pool-first。

## 1. 当前问题判断

以下判断主要用于回放本轮优化前的典型症状与设计动因；其中 artifact 标准化、idle-agent 自动续推、reserved 预留、pool health 与 Gantt 主干分段等能力现已在 Phase 1/2 中落地。

### 1.0 任务定义不成熟时，过早并行会放大返工

并行度优化只适用于“边界清楚”的任务，不适用于“问题还没定义清楚”的任务。实际运行中经常出现的更深层问题不是 agent 不够，而是：

```text
根因未确认
  -> PM 过早拆出多个修复子任务
  -> agent 分头在错误假设上推进
  -> review / rework 集中爆发
  -> 看起来很忙，实际 lead time 更长
```

因此在并行度方案里需要补一条 PM 前置原则：

- 根因未明时，先开 diagnosis / investigation；
- 接口契约未稳时，先开 design / contract；
- 只有当 write_scope、depends_on、验收标准和输入事实已稳定后，才默认批量入池。

### 1.1 任务池没有成为默认工作入口

已有设计已经定义了 `pooled + claim_scope + claim_policy=pull` 的任务池机制，也已有脚本：

- `pool-task.sh`
- `claim-task.sh`
- `task-pool-view.py`
- `task-pool-router.py`
- watcher 中的 pooled nudge 与 auto push

但实际运行中容易回到旧模式：

```text
PM 创建任务
  -> 直接 dispatch 给 dev/review/qa
  -> PM 人肉观察前置完成
  -> PM 再派后续任务
```

这种模式的问题是：

- agent 空闲时任务池没有库存；
- 后续任务虽然已知，但没有提前入池；
- PM 成为所有接续动作的串行瓶颈；
- 任务状态只反映“是否被喊去做”，不反映“是否真正可开工”。

这里的问题不是“watcher 完全不处理 pooled”，而是：现状中的 pooled nudge、timeout 提醒和局部 auto-push 还不足以稳定替代 PM 持续调度；因此优化重点应是把“已有零散能力”收束成可观测、可审计、可解释的闭环，而不是误判为系统从零开始。

### 1.2 后置依赖任务没有提前排队

很多需求天然是 DAG：

```text
方案/接口契约
  ├─ backend 实现
  ├─ frontend 接线
  ├─ 单测/回归
  └─ 文档/配置/部署检查
```

现在常见做法是等上游完成后再创建或派发下游。这样虽然避免了错误开工，但牺牲了并行准备：

- 下游任务不能提前出现在池中；
- watcher 无法在依赖满足的一瞬间自动续推；
- PM 需要反复切上下文判断“现在该派谁”。

正确做法应是：下游任务可以提前创建并入池，但由 `depends_on` 和 `dependency_policy` 控制是否可认领。

### 1.3 WIP 限制保护了正确性，但也暴露了库存不足

当前 `wip_limits.dev=1`、`task_pool.default_claim_max_concurrency=1` 是合理的，因为一个 CLI agent 多数时候只能认真执行一条主线。并行度不足不能靠简单把 dev WIP 改成 3 解决。

应该区分：

| 概念 | 建议口径 |
|---|---|
| `working` | agent 已 ack，真实开工，同一 agent 默认最多 1 条 |
| `dispatched` + reserved 元数据 | 已预分配给 agent，等待 ack，可作为下一条预加载 |
| `pooled` | 通过 Pool Gate，等待依赖满足或空闲 agent |

也就是说，可以允许 `1 working + 1 reserved`，但不应允许 `3 working`。

### 1.4 看板/Gantt 失真

如果看板只根据 `task.json.status`、artifact mtime、transitions 重建状态段，就容易把以下时间混在一起：

- PM 创建但未补全任务的等待时间；
- 任务在池中等待可认领的时间；
- 任务已派发但 agent 未 ack 的等待时间；
- agent 真实 working 时间；
- review/QA/PM acceptance 等待时间；
- blocked 或 artifact_invalid 的停滞时间。

结果是甘特图看起来像“任务一直在跑”，但真实情况可能是：

- 任务其实还没过 Pool Gate；
- 任务在 pooled 等依赖；
- 任务被 direct dispatch 后挂在 dispatched；
- agent 已空闲但没有下一条 pooled 可接；
- review/QA 队列卡住；
- JSON artifact 非法导致 watcher 不敢流转。

甘特图如果不拆这些阶段，就会对 PM 调度产生误导。

### 1.5 控制面故障会直接吞掉并行收益

近期实践表明，吞吐损失不只来自“池里没活”，也来自控制面自身断链：

```text
任务已具备可执行性
  -> watcher/PM 成功把任务推到 dispatched
  -> 消息投递失败 / 角色会话 502 / tmux 无响应 / ack 丢失
  -> 任务停在 dispatched 或 ready_for_merge
  -> auto-close / gate / 状态归约继续失真
  -> PM 只能人工排查“到底是连接问题、状态脏了，还是任务本身失败”
```

近期暴露过的典型故障包括：

- QA 已通过，但 auto-close 因 gate 状态不自洽而失败；
- agent 会话挂起后，任务长期停在 `dispatched` 且没有 `ack.json`；
- `resume/转派` 后 `assigned_agent` 已变更，但 `claimed_by / claim_scope / reserved_by` 仍残留旧值；
- `ack.json / review.json / verify.json` 非法，watcher 停止推进；
- 角色连接或消息投递失败被误看成执行阻塞，导致 Gantt / dashboard 继续失真。

因此，本文后续优化目标应从“提高并行度”扩展为“提高并行调度 + 控制面稳定性”。

## 2. 优化目标

### 2.1 并行度目标

短期目标：

- dev agent 空闲时，任务池中总有可接任务；
- PM 不需要手动等待前置任务完成再派后置任务；
- watcher 可以根据依赖满足自动续推下一条；
- 看板能看出“没有任务库存”还是“任务被 review/QA 卡住”。

中期目标：

- 每个需求都有任务 DAG；
- 下游任务提前创建并入池；
- `ready_for_merge` 后 review/QA 可并行排队；
- 复杂任务支持 review-1 + arch-1 双审并行；
- 甘特图能展示真实阶段耗时和瓶颈。

补充前置目标：

- PM 能区分“值得提前入池的后置任务”和“根因未明、只能先 pending 的候选任务”；
- 系统优先减少“错误并行”而不是单纯增加 `working` 数；
- 控制面能区分 delivery/session 故障、执行阻塞与业务失败，不把连接层问题误算成执行效率问题；
- 三次重试失败且无实际进展的任务，能够被系统化地回收或转派，而不是长期卡死在 `dispatched`；
- 复杂需求的第一步是确认是否应先产出 diagnosis/design 任务，而不是默认直接拆修复任务。

### 2.2 非目标

本方案不建议马上做：

- 把所有 agent 的 `working` 并发提高到多条；
- 让 Chat Hub 成为任务状态事实源；
- 让 dashboard 直接写 `task.json` 绕过脚本；
- 在任务池不稳定前引入复杂分布式队列。
- 把消息投递失败、角色连接失败直接记成业务 blocked/failed。
- 在根因未确认前，为了“提高并行度”提前铺满修复 DAG。

## 3. 新默认流程

### 3.1 PM 复杂需求流程

复杂需求默认流程应改为：

```text
0. PM 判断：根因是否已确认；若未确认，先创建 diagnosis / investigation / design 任务
1. PM 建 root_request_id
2. PM 或 arch-1 在根因/契约明确后产出任务 DAG
3. PM 批量 create-task
4. PM 补全每个子任务：
   - write_scope
   - depends_on
   - claim_scope
   - priority
   - review_level / test_required
   - dependency_policy
5. 通过 Pool Gate 的任务默认 pool-task.sh 入池
6. watcher 自动续推可执行任务
7. agent ack 后进入 working
```

补充限制：

- 若根因未明、验收边界未稳定、owner 决策仍未完成，修复类任务保持 `pending`，不要为了“库存好看”提前入自由池；
- diagnosis/design 任务可以作为真正的 DAG 前置，而不是把“待确认事项”塞进开发任务说明里。

只有这些任务继续允许直接 dispatch：

- deployment / prod；
- integration gate；
- owner 明确点名；
- critical 紧急任务；
- 高风险跨域协调任务；
- PM 判断任务池会引入明显风险并写明原因。

### 3.2 后置任务提前入池

后置任务不应等前置完成才创建，但前提是**上游输入契约、范围与验收目标已经稳定**。推荐：

```json
{
  "status": "pooled",
  "claim_policy": "pull",
  "depends_on": ["补齐接口契约"],
  "dependency_policy": "done_only",
  "claim_scope": ["dev-1", "dev-2"]
}
```

如果前置进入 `ready_for_merge` 后下游即可并行准备，则显式使用：

```json
{
  "dependency_policy": "ready_for_merge_ok"
}
```

这样 PM 可以一次性把 DAG 放进池里，watcher 负责在依赖满足时自动释放。

但默认策略应更保守：

- **默认 `dependency_policy = done_only`**；
- `ready_for_merge_ok` 只适用于：
  - 文档/说明同步；
  - 只读分析；
  - 低耦合测试准备；
  - 不写同一 `write_scope` 的后置动作。

对于真正依赖上游代码结果的开发任务，不应把 `ready_for_merge_ok` 当作默认值。

### 3.3 Pool Gate

目标态下，任务入池前应满足：

- `instruction.md` 无占位；
- development / integration / deployment 等写任务的 `write_scope` 非空且足够窄；
- read_only 的 design / 审计 / 评审任务允许 `write_scope=[]`；
- review / QA 这类 artifact-only 任务也允许 `write_scope=[]`，但必须在 `task_type`、`instruction.md` 与验收标准中明确其唯一写入产物是 `review.json` / `verify.json` 等任务工件，避免被通用写任务 gate 误伤；
- `depends_on` 明确；
- `claim_scope` 明确或可由 `task_type/domain` 推导；
- `priority` 明确；
- `review_level` 明确；
- `test_required` 明确；
- 非 prod/deploy/integration 自由池任务。

说明：以上是目标态 Pool Gate。当前系统已落地的主要是 `instruction.md` 结构/占位校验、特殊任务排除与基础 requeue 保护；development 空 `write_scope`、owner 决策未完成、根因未确认等强 gate 仍需继续 hardening。

目标态下，Pool Gate 不通过时，任务保持 `pending`，看板应显示为“定义未完成”，而不是进入执行队列。

还应补充以下 gate：

- 根因已确认，或已明确当前任务是 diagnosis / design 而非直接修复；
- 验收标准是单义的，不存在“做完后再看算不算完成”的模糊表述；
- 不存在尚未解决的 owner 决策项；
- 输入样例 / 契约来源明确，避免 agent 在不同事实集上各自推进；
- 只读任务的 read_only / write_scope 例外必须在 instruction 与 task.json 中显式体现，避免被通用写任务 gate 误伤。

### 3.4 任务类型与质量闸门模板

最近的收口实践说明：不能为了模板统一，把所有任务都机械设置为 `review_required=true + test_required=true + quality_gate_mode=parallel`。不同 `task_type` 应有更保守的默认 gate 模板：

| task_type | 默认 gate 模板 | 说明 |
|---|---|---|
| development | review + QA | 默认开发任务，允许按风险级别选择 serial / parallel，但必须显式声明 |
| verification | review-only 或 QA-only | 需在建任务时明确；验证类任务不应默认并行 review + QA |
| design | review-only | 以审查结论为主，不默认要求测试 |
| integration | review + QA + PM acceptance | 需要更严格收口，必要时加 arch gate |
| deployment / prod | owner / arch gate 优先 | 不进入自由池默认路径 |

规则上应明确：

- verification 任务若本质是“产出 `verify.json` 或 `review.json` 的收口动作”，必须在创建时选定唯一主 gate；
- complex/高风险任务可以保留并行 gate，但要在任务定义里显式说明为什么需要并行；
- `ready_for_merge`、`pm_acceptance_pending`、`done` 的 gate 状态必须与该模板自洽，避免出现 QA 已过但 auto-close 无法收敛的异常链路。

### 3.5 异常接管、回收与转派流程

任务池、reserved 与 auto-push 稳定后，异常接管必须成为一等流程，而不是 PM 的临时手工动作。建议把以下链路写成标准流程：

```text
dispatched / reserved
  -> 超时无 ack 或角色会话异常
  -> 先做消息重试 + 会话健康探测
  -> 连续 3 次失败且无实际进展
  -> 在 claim_scope 内尝试转派给空闲候选
  -> 若无安全候选，则回收到 pooled
```

需要补充两条明确语义：

- `resume` 只表示原执行者继续；
- `reassign` 表示换人接手，建议单独提供 `reassign-task.sh`，不要长期把“转派”混进 `resume-task.sh` 的语义里。

回收或转派时必须同时处理：

- 归档旧的 `claim.json / ack.json / result.json / review.json / verify.json`（按当前轮需要归档的工件处理）；
- 重置当前轮 sentinels、merge gate 与 auto-close retry 计数；
- 一次性改写 `assigned_agent / claimed_by / claimed_at / claim_scope / reserved_by / reserved_at / claim_reason / reserved_reason` 等一致性字段；
- 写入 `transitions.jsonl` 与 PM Inbox，明确这是“连接/会话恢复动作”，而不是业务失败。

这样才能把“agent 挂了、消息没送到、任务没人 ack”这类问题从人工排障变成标准化控制面流程。

## 4. 调度策略优化

### 4.1 池水位线

引入按角色的最低任务库存：

| 池 | 最低水位 | 说明 |
|---|---:|---|
| dev | `2 * dev_agent_count` | 例如 dev-1/dev-2 至少 4 个可认领或依赖等待任务 |
| review | `review_agent_count` | 至少能看到待审队列 |
| qa | `qa_agent_count` | 至少能看到待验队列 |
| arch | `1` | 方案/集成任务通常少但关键 |

水位统计分两类：

- `ready_now`：当前可认领；
- `waiting_dependency`：已入池但等依赖。

如果 `ready_now=0` 且所有 agent 空闲，PM Inbox 应出现 L2 告警：`pool_starvation`。

但 `pool_starvation` 不能简单等同于“大家都没活”。建议触发前提为：

- 存在 active `root_request_id`；
- 或存在 mature pending 任务，即任务定义已接近完成但尚未入池；
- 或存在 `waiting_dependency` backlog，且依赖已接近满足；
- 或 PM 显式标记当前工作流处于推进中。

如果没有 active root request，也没有成熟待入池任务，则应显示为“团队空闲/无待办”，不应作为饥饿告警。

说明：`pool_starvation` 已作为 PM Inbox / dashboard 的调度健康信号落地；后续要继续优化的是触发解释、治理阈值与 UI 呈现，而不是是否存在该指标本身。

### 4.2 自动续推优先级

目标态下，watcher 为 idle agent 选择下一条任务时，排序应为：

1. `status=pooled`；
2. `claim_scope` 命中；
3. 依赖满足；
4. 无 write_scope 冲突；
5. priority 高；
6. pool_wait_minutes 长；
7. root_request_id 上当前阻塞最少；
8. created_at 早。

选中后直接调用 `claim-task.sh`，使任务进入 `dispatched`，并用 reserved 元数据表达“下一条预留任务”语义，再通知 agent ack。

说明：当前仓库已经具备 `task-pool-router.py`、`task-pool-view.py`、watcher 局部 auto-push、idle-agent 扫描、reserved 预留与超时回退等基础能力；本节描述的是继续收敛排序规则、可观测解释和边界行为，而不是从零开始的新设计。

### 4.3 1 working + 1 reserved

在自动续推和池健康监控稳定后，应把执行容量拆成两个限制：

```json
{
  "task_pool": {
    "default_working_limit": 1,
    "default_reserved_limit": 1
  }
}
```

行为：

- `working_limit` 控制真实执行；
- `reserved_limit` 控制预加载；
- agent 有 1 条 working 时，可以预留下一条 dispatched；
- agent 完成当前任务后，若已有 reserved，则无需再等 watcher 选任务。

事实表达建议：

- 不新增 `reserved` lifecycle status；
- 仍使用 `task.json.status = dispatched` 表达“已分配、未 ack”；
- 通过 `claimed_by / claimed_at / claim_reason` 或新增 `reserved_by / reserved_at / reserved_reason` 表达“这是自动续推预留任务”；
- dashboard 的 `reserved_count` 应定义为：`status=dispatched` 且尚无当前轮 `ack.json` 的任务数。

这可以减少交接空窗，同时避免多条任务同时 `working` 造成状态失真。

约束：

- `reserved` **不计入 working，不计入真实吞吐**；
- `reserved` 超时未 ack 时必须自动回退 `pooled` 或进入 PM Inbox；
- `config.json` 已具备 `default_working_limit/default_reserved_limit` 等正式字段，能力可以灰度启用，但不再按“仅试点”口径定义；
- 该能力是最终协作模型的一部分，不是 Phase 1 的临时补丁。

### 4.4 直接派发保护

现状：

- `dispatch-task.sh` 已拒绝 `assigned_agent=auto/auto-dev/unassigned` 的 pending 任务直接 dispatch；
- 因此 `pool-first` 并非从零开始，而是已有一层基础保护。

建议补强：

- execution 任务若 `claim_policy=pull`，默认拒绝直接 dispatch；
- 如确需跳过，必须设置 `FORCE_DIRECT_DISPATCH=1`；
- 跳过时写入 `transitions.jsonl.reason`，说明为什么不用任务池。

这能把“任务池优先”从文档规则进一步收紧为系统默认行为。

### 4.5 连接失败重试与会话健康检查

角色连接与消息投递层应补成三层机制，而不是只有“发一遍消息然后等 ack”：

| 层级 | 目标 | 建议机制 |
|---|---|---|
| 投递重试 | 处理瞬时网络/网关抖动 | 快速重试 3 次，建议退避 `5s -> 15s -> 60s` |
| 会话健康探测 | 区分“会话存在但卡死”和“正常执行中” | 检查 session 是否存在、pane 是否有新输出、是否出现 Working 信号、是否已有 ack/result 新工件 |
| 故障分流 | 不把连接问题误记成业务失败 | 将异常分类为 `delivery_failed / session_unhealthy / execution_blocked / business_failed` |

实现要求：

- 每次投递都记录 `attempt_count / last_attempt_at / last_delivery_error`；
- 重试成功后不升级状态，只更新审计记录；
- 会话存在且已有实际进展迹象时，不再继续盲目重发；
- 控制面告警必须显式写明：这是投递层故障、会话故障，还是执行故障。

### 4.6 三次失败后的回收与转派

建议把“连续 3 次失败”作为连接恢复的硬阈值。若满足以下条件：

- 当前任务仍在 `dispatched / reserved`；
- 连续 3 次投递或健康探测失败；
- 当前轮没有 `ack.json`，也没有 result/review/verify 等实际进展工件；

则系统可以进入恢复动作：

1. **优先转派**：若 `claim_scope` 中存在空闲且无 write_scope 冲突的候选 agent，则转派；
2. **否则回收**：若没有安全候选，则把任务回收到 `pooled`，等待下一次认领；
3. **禁止无限重试**：达到 3 次后不再无上限重发，避免任务与告警风暴；
4. **必须留痕**：写 PM Inbox、Chat/Feishu 事件和 `transitions.jsonl`，说明这是“连接恢复后的回收/转派”。

建议默认原则：

- `dispatched` 但从未 ack 的任务，优先回收或转派；
- 已 ack 进入 `working` 的任务，除非确认会话异常且无真实进展，否则不自动跨人接管；
- 连接失败不等于任务失败，不能直接把任务打成 `blocked/failed`。

## 5. PM 行为优化

### 5.1 PM 的核心指标从派发数改为池健康

PM 每轮应先看：

- dev pool 是否有库存；
- 是否有 pooled 超时；
- 是否有 idle agent；
- 是否有 artifact_invalid；
- 是否有 review/QA 队列积压；
- 是否有 root_request_id 单点串行。

而不是先看“我要给谁派下一条”。

### 5.2 PM 拆任务模板

复杂需求建议强制生成如下清单：

```markdown
## 任务 DAG

| 子任务 | 类型 | write_scope | depends_on | claim_scope | 可并行性 |
|---|---|---|---|---|---|
| 接口契约 | design | docs / schemas | - | arch-1 | 前置 |
| 后端实现 | development | backend/... | 接口契约 | dev-* | 可与前端并行 |
| 前端接线 | development | frontend/... | 接口契约 | dev-* | 可与后端并行 |
| 测试补齐 | development | tests/... | 后端实现,前端接线 | dev-* | 后置 |
| QA 验证 | verification | - | 测试补齐 | qa-1 | 后置 |
```

PM 拆完后批量入池，而不是边做边想下一条。

### 5.3 任务粒度建议

适合入池并行的任务：

- 单一目录或少量文件；
- write_scope 与其他任务不重叠；
- 可在 30-90 分钟内交付；
- 验收标准明确；
- 不需要长时间等 PM 决策。

不适合自由入池的任务：

- 修改多个核心模块；
- 需要生产权限；
- 需求仍不清楚；
- 需要 owner 实时确认；
- 需要跨项目同步部署。

## 6. Dashboard/Gantt 真实性优化

### 6.1 新增阶段口径

以下阶段口径需要区分“已实现主干分段”和“目标态待补齐阶段”。当前实现已覆盖 pooled / reserved / working / review / qa / pm_acceptance 六段主干分段；definition / dependency_wait / blocked 目前更适合作为目标态口径或 milestone/解释层，而不是已完全落地的独立 phase segment。

目标态下，Gantt 不应只展示粗略 lifecycle，而应拆成以下阶段：

| 阶段 | 开始 | 结束 | 含义 |
|---|---|---|---|
| definition | created_at | pool_entered_at 或 dispatched_at | PM 定义任务 |
| pooled_wait | pool_entered_at | claimed_at | 任务池等待 |
| dependency_wait | pool_entered_at | dependencies_ready_at | 已入池但依赖未满足 |
| reserved | claimed_at/lease_acquired_at | ack_at | 已分配但未开工 |
| working | ack_at | result.finished_at | agent 真实执行 |
| review_wait | result.finished_at | review.reviewed_at | 等审查 |
| qa_wait | review.reviewed_at 或 result.finished_at | verify.verified_at | 等 QA |
| pm_acceptance | gate=pm_acceptance_pending 起点 | done | 等 PM 收口 |
| blocked | blocked_at | resumed/cancelled/done | 阻塞时间 |

核心原则：

```text
只有 ack_at -> result_at 才能算 agent working 时间。
pooled/dispatched/review/QA/PM acceptance 都是等待或队列时间。
```

还应补充一条控制面原则：`delivery_failed / session_unhealthy / auto_requeue / reassigned` 属于调度与连接层状态，不等于业务执行失败。Gantt 与统计层应把它们单独归为控制面事件，而不是直接折叠进 working 或 blocked。

还应明确区分：

- **exact**：来自 artifact 字段或标准脚本写入的明确时间（如 `ack.json`、`result.json`、`review.json`、`verify.json`）；
- **inferred**：来自 `transitions.jsonl`、mtime 或补推逻辑的推断时间。

UI 与 query 层不应把 inferred 段伪装成 exact；历史数据也应允许标记为 inferred。

`dependencies_ready_at` 已由 watcher 持久化写入为主；历史回放仍可从 `transitions.jsonl`、标准 artifact 时间或任务状态补推 inferred 值，但新数据应优先以 watcher 记录为准。

### 6.2 看板新增指标

首页建议新增：

- `idle_agents`：当前无 working 且无 reserved 的 agent；
- `pool_ready_count`：当前可认领任务；
- `pool_waiting_dependency_count`：已入池但等依赖；
- `pool_starvation`：空闲 agent > 0、pool_ready_count = 0，且存在推进中的 root request / mature pending / dependency backlog；
- `reserved_count`：已预分配但未 ack，即 `status=dispatched` 且无当前轮 `ack.json`，不是新增 lifecycle status；
- `working_count`：真实执行中；
- `review_queue_count`；
- `qa_queue_count`;
- `artifact_invalid_count`;
- `dispatch_delivery_retry_count`：消息投递重试次数；
- `dispatched_no_ack_timeout_count`：已派发但无 ack 的超时任务数；
- `session_unhealthy_count`：角色会话不健康数；
- `auto_requeue_count`：连接恢复后被自动回收到池中的任务数；
- `reassign_count`：因连接/会话问题触发的转派次数；
- `auto_close_failure_count`：QA/review 已满足但自动收口失败次数；
- `state_invariant_violation_count`：任务状态一致性异常数；
- `mean_ack_after_redelivery_seconds`：重发后到 ack 的平均耗时；
- `oldest_pool_wait_minutes`：最老的任务池等待时长；
- `oldest_review_wait_minutes`：最老的审查等待时长；
- `oldest_qa_wait_minutes`：最老的 QA 等待时长。

### 6.3 单任务详情新增解释

每个任务详情页应显示：

- 为什么还不能认领；
- 当前依赖状态；
- write_scope 冲突对象；
- 当前 agent 是否空闲；
- 当前卡在 Pool Gate、dependency、reserved、working、review、QA、PM acceptance 哪一段；
- 当前是否处于 `delivery_failed / session_unhealthy / auto_requeue / reassigned` 等控制面恢复状态。

这比单纯显示 `status=pooled/working` 更能指导 PM。

### 6.4 修复时间解析一致性

聚合与 Gantt 必须统一时间规范：

- 所有写入 `task.json`、artifact、transitions 的时间都应为带时区 ISO；
- ingest 时把 naive datetime 统一视为本地时区或 UTC，并标记来源；
- query 层计算 duration 前必须归一到 aware datetime；
- 不允许 offset-naive 与 offset-aware 直接相减。

否则阶段耗时会继续失真，甚至导致聚合视图报错。

### 6.5 Gantt 与统计口径必须区分 exact / inferred

建议补充统一规则：

- 只要标准 artifact 中已有时间字段，优先以 artifact 为准；
- 若只能从 `transitions.jsonl` 或文件 mtime 推断阶段边界，必须在 query 结果中带出 `source=inferred`；
- 甘特图 tooltip 与详情页要显示“该阶段时间来自 artifact / transition / mtime 的哪一种来源”；
- 历史数据允许不完美，但不能把推断精度伪装成事实精度。

## 7. Artifact 与状态一致性优化

当前 `artifact_invalid` 会直接阻断自动流转。建议：

> 该项应视为 **Phase 1 前置能力**，而不是系统稳定后的补充优化。没有稳定 artifact，就没有稳定的 pool、watcher 和 Gantt。

### 7.1 提供产物生成命令

不要让 agent 手写 JSON。提供：

```bash
scripts/write-ack.sh <task-id> --agent dev-1
scripts/write-result.sh <task-id> --status done --summary ...
scripts/write-review.sh <task-id> --status approve --summary ...
scripts/write-verify.sh <task-id> --status pass --summary ...
```

脚本负责：

- 填充标准字段；
- 对 `result.json.status` 强制使用正式契约 `done/failed/blocked`，不再把 legacy `success` 当成推荐写法；
- 实现层需区分 raw status 与 normalized status：当前 artifact parser 会把 raw `done` 归一为内部 `normalized_status=success`，reducer / watcher 仍应按 normalized status 做状态归约，避免把“推荐写法”与“内部判定枚举”混为一谈；
- 写当前 round；
- JSON schema 校验；
- 原子写入；
- 失败时不污染已有 artifact。

### 7.2 watcher 对非法 artifact 的处理

非法 artifact 应：

- 只告警一次；
- 写 PM Inbox；
- 定向提醒产生该 artifact 的 agent；
- 不重复刷屏；
- 修复后自动清除告警。

### 7.3 状态一致性不变量检查

除了 artifact JSON 合法性，还应把任务状态一致性当成正式 gate。建议增加 invariant checker，至少校验以下规则：

- 对从任务池认领、reserved 或转派中的 pull 任务，当前轮 `assigned_agent / claimed_by / reserved_by` 应保持一致，或显式标记为 direct-dispatch 例外；
- `claim_scope` 应覆盖当前执行者，避免出现“assigned_agent 已换人，但 scope 里还是旧人”的脏状态；
- `status=working` 必须有当前轮 `ack.json`；
- `ready_for_merge` 的 gate 状态必须与 `review_required / test_required / quality_gate_mode` 自洽；
- `status=done` 时 `merge_gate_state` 必须已经收敛到 `closed`；
- auto-close、resume、reassign、requeue 之后，sentinel 与 retry 计数必须按当前轮重置。

若 invariant 不满足：

- 不应静默继续流转；
- 应写 PM Inbox 与 `state_invariant_violation` 指标；
- 允许触发自动修复或要求 PM/arch 仲裁，但必须保留审计痕迹。

## 8. 实施计划

### Phase 1：规则落地与可观测性（主路径已落地 / 异常链路待 hardening）

目标：让系统先看见瓶颈。

建议按两个切口理解已落地范围：

#### Phase 1A：事实与基础可观测性

已落地重点：

- PM 模板加入“根因未明先 diagnosis / design，再决定是否批量 DAG”硬规则；
- Phase 1 文案中显式区分“现状已存在能力”和“目标态待实现能力”；
- `write-ack.sh / write-result.sh / write-review.sh / write-verify.sh` 落地，统一 artifact 口径；
- 修复 Gantt/query 时间归一化，避免 naive/aware datetime 混用；
- dashboard/CLI 增加最小 pool health：pool ready、dependency waiting、idle agent、artifact_invalid。

#### Phase 1B：调度护栏与 Gantt 细化

已落地重点：

- PM 模板加入“复杂需求必须批量 DAG + pool-first”硬规则；
- `dispatch-task.sh` 增加 direct dispatch 保护；
- PM Inbox 增加 `pool_starvation`；
- Gantt 拆出 pooled/reserved/working/review/QA/PM acceptance，并标记 exact / inferred；
- 单任务详情显示 pooled 阻塞原因。

当前验收口径：

- `list-pool.sh` 能区分可认领、依赖等待、scope 阻塞；
- dashboard 能显示 idle agent 与 pool depth；
- 甘特图不再把 pooled/dispatched 时间算作 working；
- 甘特图能标记 exact / inferred 阶段来源；
- artifact_invalid 下降，并能通过标准脚本生成 artifact；
- 复杂需求至少能一次性入池多个子任务。

### Phase 2：自动续推与 reserved（主路径已落地 / 回收转派待稳定）

目标：减少 agent 空闲时间。

已落地重点：

- watcher 周期性扫描 idle agent；
- idle agent 有可认领任务时自动 `claim-task.sh`；
- auto-claim 前已落地的基础校验包括：依赖满足、claim_scope 命中、write_scope 无冲突、agent working/reserved 容量限制；
- 引入 `reserved_limit`（可灰度启用）；
- done/ready_for_merge 后优先推 reserved 或下一条 pool 任务；
- dispatched 超时未 ack 时可回退 pooled 或 PM Inbox 提醒。

待 hardening：

- owner_approval_required / owner 决策未完成等更高层 gate 例外，还没有纳入统一 auto-claim 护栏；
- 连接失败后的回收/转派虽然已有基础动作，但三次失败阈值、会话健康探测和 invariant 修复仍在补齐。

当前验收口径：

- agent 完成任务后无需 PM 手动派下一条；
- 空闲 agent + pool_ready > 0 时，1 个 scan interval 内出现 reserved/dispatched；
- 同一 agent 仍最多 1 条 working。

### Phase 3：分层并行 review/QA gate（主路径已实现 / 收口异常链路待 hardening）

目标：减少后置流水线串行等待。

已落地改动：

- `merge_gate_state` 支持并行子 gate，例如：

```json
{
  "review_state": "pending",
  "qa_state": "pending",
  "merge_gate_state": "quality_pending"
}
```

- result 后同时触发 review 排队与 QA smoke / 自动校验；
- complex 任务支持 review-1 + arch-1 双审；
- PM acceptance 等所有必需 gate 满足后出现。

当前验收口径：

- review 与 smoke / 自动校验 可以并行等待；
- 完整 QA 是否并行触发由任务类型/风险级别决定，不一刀切；
- Gantt 能分别显示 review_wait 与 qa_wait；
- complex 双审不互相阻塞。

### Phase 3.5：控制面 hardening（必须实现）

目标：让并行调度在异常链路下也能自恢复，而不是只在主路径上可用。

改动：

- 明确区分 `resume` 与 `reassign` 语义，补齐 `reassign-task.sh`；
- `send-to-agent / watcher / queue router` 增加投递重试、会话健康探测与三次失败阈值；
- 连续 3 次失败且无 ack/无实际进展时，按规则执行“优先转派，否则回收 pooled”；
- 增加 task type × quality gate 模板，避免 verification 类任务被错误套用并行 gate；
- 增加 invariant checker，收敛 auto-close、gate 状态与转派后的元数据脏状态；
- dashboard/PM Inbox 单独展示控制面异常，而不是折叠进业务 blocked。

验收：

- `dispatched` 无 ack 的任务能在 3 次失败阈值内自动收敛到 ack / 转派 / 回收三种结果之一；
- 转派后不再遗留旧的 `claimed_by / claim_scope / reserved_by` 脏字段；
- auto-close 失败会被显式标记和收敛，不再出现长时间“QA 已过但任务状态悬空”；
- Gantt / dashboard 能区分连接故障、会话故障与业务阻塞。

### Phase 4：独立 worktree 与集成队列（必须实现）

目标：提升真正代码并行能力。

改动：

- 每个执行任务可分配独立 git worktree；
- result 输出 branch/patch；
- arch-1/integration queue 负责合并；
- write_scope 冲突仍作为入池/认领保护。

验收：

- dev-1/dev-2 可以同时修改同项目不同模块；
- 集成冲突集中暴露在 integration queue；
- dashboard 显示 task branch/worktree 状态。

## 9. 建议优先级

最高优先级不是扩 agent，而是让现有 agent 不饿死。

推荐顺序：

1. “根因未明先 diagnosis / design” + `pool-first` 规则硬化；
2. artifact 生成器与 artifact_invalid 收敛；
3. 控制面 hardening：投递重试、会话健康探测、三次失败后的回收/转派、状态不变量检查；
4. 补齐文档中的现状/目标态分层标注；
5. pool health / idle agent / Gantt 真实阶段；
6. idle agent 自动续推；
7. `dependency_policy` 白名单化（默认 `done_only`）；
8. `1 working + 1 reserved`（后续标准能力）；
9. 分层 review/QA 并行 gate 与 task type 模板化；
10. per-task worktree。

## 10. 成功指标

以下是目标指标集，用于定义成熟态的调度/控制面观测口径；它们不代表已全部进入当前日报或常态化报表。当前已较稳定可聚合的主要是 dashboard/query 层的 pool wait、claim latency、review wait、qa wait、rework_rate 等指标，其余需随后续 hardening 与报表接线逐步补齐。

建议成熟态每日报告这些指标：

| 指标 | 目标 |
|---|---:|
| dev pool ready count | 常态 >= dev agent count |
| dev pool total count | 常态 >= 2 * dev agent count |
| idle agent with ready pool | < 1 scan interval |
| pooled timeout count | 下降 |
| dispatched_no_ack_timeout_count | 下降 |
| artifact_invalid count | 下降 |
| dispatch_delivery_retry_count | 可解释且不持续升高 |
| auto_close_failure_count | 下降 |
| session_unhealthy_count | 下降 |
| auto_requeue_count | 可解释且稳定收敛 |
| reassign_after_connection_failure_count | 可解释且稳定收敛 |
| state_invariant_violation_count | 下降 |
| mean_ack_after_redelivery_seconds | 下降 |
| ack_to_result median | 更接近真实工作耗时 |
| pool_wait / review_wait / qa_wait | 能被单独解释 |
| PM manual dispatch execution ratio | 持续下降 |
| rework rate / review reject rate | 不因并行度提升而恶化 |
| auto-claim false-start count | 持续下降 |
| pool_to_done lead time | 下降，但不以牺牲正确性为代价 |

## 11. 风险与约束

### 风险 1：任务拆得太细，PM 成本上升

缓解：

- 提供 DAG 模板；
- 支持批量 create/pool；
- 让 arch-1 先产出拆分建议。

### 风险 2：自动续推把不成熟任务推给 agent

缓解：

- Pool Gate 必须严格；
- 根因未明时先 diagnosis / design，不直接入修复池；
- pending 不自动续推；
- prod/deploy/integration 不进自由池；
- direct dispatch override 必须留审计原因。

### 风险 3：Gantt 修正后历史数据看起来“变慢”

缓解：

- 明确区分等待时间和真实 working 时间；
- 历史数据标记为 inferred；
- 新任务从标准 artifact 时间字段开始记录。

### 风险 4：reserved 任务变成新的假负载

缓解：

- reserved 不算 working；
- reserved 超时可自动回退 pooled；
- agent 同时最多 1 条 reserved。

### 风险 5：连接重试与自动转派过于激进，导致任务抖动

缓解：

- 把“连续 3 次失败”作为硬阈值，不做无限重试；
- 只有在无 `ack.json`、无 result/review/verify 进展时才允许自动回收或转派；
- 优先在 `claim_scope` 内找空闲且无 write_scope 冲突的候选；
- 所有回收/转派动作必须写历史归档、`transitions.jsonl` 与 PM Inbox，便于复盘。

## 12. 最小落地切口

如果回看本轮已经落地的最小闭环，可以概括为 7 件事：

1. PM 模板强制“根因未明先 diagnosis / design”，成熟后再批量 DAG + pool-first；
2. `write-ack.sh / write-result.sh / write-review.sh / write-verify.sh` 落地，统一 artifact 口径；
3. 先补齐文档中的现状/目标态分层标注，避免 PM 误把目标态当现状；
4. `dispatch-task.sh` 对普通 execution direct dispatch 加保护；
5. dashboard/CLI 显示 pool ready、dependency waiting、idle agent、pool starvation；
6. Gantt 拆出 pooled/reserved/working/review/QA/PM acceptance，并标记 exact / inferred；
7. watcher 对 idle agent 自动 claim 下一条 pooled ready 任务（附安全护栏）。

如果进入下一轮最小 hardening，建议优先追加 4 件事：

1. `send-to-agent` / watcher 的连接失败重试与会话健康探测；
2. 连续 3 次失败后的“优先转派，否则回收 pooled”闭环；
3. `reassign-task.sh` 与 `resume-task.sh` 的语义拆分；
4. artifact + task state invariant checker，避免 auto-close 与转派后遗留脏状态。

这 7 件事完成后，系统会从“PM 人肉串行调度”转向“PM 维护任务库存，watcher 自动喂给空闲 agent”的模式；同时通过 diagnosis 前置、artifact 口径统一和现状/目标态分层标注，避免只是把错误更快地并行放大。
