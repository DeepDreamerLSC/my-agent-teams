# 协作框架控制面优化实施方案（架构评审版）

> 评审日期：2026-05-25  
> 评审角色：arch-1  
> 状态：架构评审通过，建议按调整后的优先级实施  
> 来源：基于 PM 方案《协作框架优化方案-2026-05-25》及对 3 个 P0 任务 review 流转问题的专项排查结论整理

---

## 1. 总体判断

当前瓶颈判断成立：

```text
不是 agent 数量不足，
而是输入缺口 + 控制面状态脏化 + 可消费库存不可见 + review/QA 队列闭环不完整。
```

建议保留现有框架骨架：

- `task.json + artifact JSON` 作为事实源
- `watcher / reducer / router` 作为编排层
- `chat / send-to-agent` 作为通信层
- `dashboard / pool view / PM inbox` 作为观测层

不建议引入新数据库或复杂队列系统。优先通过 schema、脚本、watcher 执行顺序、队列 lease 和 dashboard 视图把控制面收敛。

---

## 2. 架构修正：三种语义必须分离

### 2.1 `status`：生命周期

保留现有生命周期，不要继续细拆：

- `pending`
- `pooled`
- `dispatched`
- `working`
- `ready_for_merge`
- `blocked`
- `done`
- `cancelled`
- `archived`

### 2.2 `task_health`：当前可推进性

用于回答：**这个任务现在为什么不能继续推进？**

建议枚举：

- `healthy`
- `waiting_gate`
- `artifact_invalid`
- `state_inconsistent`
- `dependency_blocked`
- `input_missing`
- `session_unhealthy`
- `queue_stalled`

### 2.3 `blocker_*`：阻塞归因

只在 `blocked` 或阻塞传播场景中使用：

```json
{
  "blocker_type": "internal | external",
  "blocker_code": "missing_unseen_source_pdfs",
  "blocker_owner": "owner | pm | dev | qa | reviewer | infra",
  "unblock_requirements": []
}
```

### 2.4 关键修正

- 不建议新增 `blocked_internal / blocked_external` 作为 `status`
- 应保持 `status=blocked`
- 用 `blocker_type` 区分 `internal / external`
- 下游任务不要直接改成 `blocked`，而应显示为：
  - `task_health=dependency_blocked`
  - `health_reasons=["dependency_external_blocked:<task-id>:<blocker_code>"]`

---

## 3. PM 方案采纳 / 修正判断

### 3.1 采纳

以下方向应正式采纳：

- 引入 `task_health`
- 引入状态清洗器 `sanitizer`
- 将 `blocked` 的归因显式化
- 为 review/QA queue 增加 preflight 与 lease 闭环
- 增加 `PM Inbox`
- 建立 agent 重启恢复协议
- 强化 communication 分层与 dashboard 可见性

### 3.2 修正

需要按以下方式修正 PM 原方案：

- 不把 `blocked internal / external` 做成新的生命周期状态
- 不把 `task_health`、`blocker_*`、queue 状态混成一个大字段
- 不让下游任务因为上游 external blocker 直接变成 `blocked`
- review/QA queue 问题优先按“lease/ack/zombie reclaim”收敛，而不是重做整个队列系统

### 3.3 PM 日常治理规则

- 默认先报告，不直接粗暴改状态
- watcher / PM 决定 `resume / keep / reroute`
- `external blocked` 不自动 `resume`

---

## 4. P0 实施方案

## P0-1：引入任务健康态与归约规则

### 目标
补足 `status` 不能表达“当前能否推进”的缺口。

### 落地项
- 在 `task.json` 增加：

```json
{
  "task_health": "healthy",
  "health_reasons": []
}
```

- 在 `task-state-reducer` 中增加统一 health 归约
- 为任务详情、dashboard、PM Inbox 输出 `health_reasons`
- 补回归测试

### 归约示例
- `ready_for_merge + review 已过 + verify 缺失` → `waiting_gate`
- `result.json.status` 非法 → `artifact_invalid`
- `assigned_agent != claimed_by` → `state_inconsistent`
- 外部样本源缺失 → `input_missing`

---

## P0-2：实现任务状态清洗器并接入 watcher

### 目标
把常见可自动修复的脏状态前移到 watcher，而不是持续由 PM 手工修。

### 脚本
新增：`scripts/task-state-sanitizer.py`

### 首批职责
1. 清理 `assigned_agent != claimed_by/reserved_by`
2. 修复 `claim_scope` 不包含当前执行者
3. 检测旧轮次 `ack/review/result/verify` 是否应归档
4. 检查 artifact 状态值是否合法
5. 对 `ready_for_merge` 缺 gate 条件的任务补写明确 `merge_gate_state`

### 配套字段
```json
{
  "sanitized_at": "ISO-8601",
  "sanitizer_actions": ["clear_stale_claimed_by", "align_claim_scope"],
  "state_invariant_violation_count": 0
}
```

### 控制要求
- 先 dry-run，再 apply
- P0 只修低风险字段
- 所有修复动作写入 `transitions` / `sanitizer_actions`

---

## P0-3：固化 internal / external blocker schema

### 目标
让系统明确知道 blocked 是团队内部可解，还是缺 owner / 外部输入。

### 落地项
- 在 `task.json` 增加 `blocker_type / blocker_code / blocker_owner / unblock_requirements`
- pool view / PM inbox 使用这些字段
- BlindHoldout 作为回归样例

### 约束
- `external blocked` 必须有 `blocker_code`
- 必须有 `unblock_requirements`
- 必须说明为什么团队内部无法解除
- `QA fail` 不自动等于 `external`

---

## P0-4：Review / QA router 前置硬校验

### 目标
避免非法 artifact 或前置条件不满足的任务进入 review/QA 队列。

### 落地项
- 增强 `scripts/task-queue-router.py`
- 非法 artifact 不入队
- 任务写明 `health_reason`
- queue 只暴露真正可消费候选

### 价值
把“队列可见”与“队列可执行”明确区分，减少 reviewer / QA 被无效任务打断。

---

## P0-5：Review / QA queue lease 闭环

### 目标
补齐当前 review/QA 流程“只入队提醒、不形成执行闭环”的缺口。

### 当前问题
当前 review queue 更像：

```text
queue visible + nudge
```

而不是：

```text
assigned -> acked -> in_progress -> done / stale_reclaimed
```

### 落地项
- 在现有 `queue_state` 上补 lease 字段：
  - `assigned_at`
  - `acked_at`
  - `last_seen_at`
  - `stale_at`
  - `source_task_id`
- 增加 queue zombie 回收
- 增加 pending reason 输出到 dashboard / PM Inbox
- 增加 review/QA ack 可见性

### 目标效果
- watcher 不再只是“把任务放进队列”
- 而是能判断 reviewer / QA 是否真正接单
- 且能自动回收僵尸占位

---

## 5. P1 实施方案

## P1-1：Pool claimable 视图

新增真正“可消费库存”视图，区分：
- pool 有库存
- pool 可派发
- pool 因依赖 / blocker 暂不可派发

## P1-2：Agent recover protocol

新增：`scripts/agent-recover-check.sh`

目标：
- agent 重启后自动识别手头任务
- watcher / PM 决定 `keep / resume / reroute`
- 避免 working 僵尸任务长期滞留

## P1-3：通信分层标准化

必须固化到：
- `design/chat-hub/protocol.md`
- `design/collaboration/feature-shared-context.md`
- `design/agent-templates/*.md`

固定职责：

| 层 | 用途 |
|---|---|
| `task artifacts` | 唯一事实源 |
| `chat/tasks` | 讨论与补充 |
| `watcher events` | 状态推进与异常 |
| `send-to-agent` | 催办、硬提醒、转派 |
| `owner/alert-card` | 外部输入、关键决策、生产风险 |

## P1-4：PM Inbox

新增：`scripts/list-pm-inbox.py`

聚合：
- `artifact_invalid`
- `state_inconsistent`
- `input_missing`
- `blocked_external`
- `working_timeout`
- `queue_stalled`
- `ready_for_merge waiting close`

后续由 dashboard 增加页面。

---

## 6. P2 实施方案

## P2-1：PM 批量治理脚本

新增：
- `scripts/pm-close-ready.sh`
- `scripts/pm-fix-artifacts.sh`
- `scripts/pm-fix-state-inconsistency.sh`
- `scripts/pm-reroute-stalled.sh`
- `scripts/pm-blocker-report.sh`

前置条件：
- P0 sanitizer 已稳定
- P0 health schema 已落地

## P2-2：阶段 span 化

dashboard 聚合层新增：
- `task_stage_spans`
- `task_health_events`
- `pm_actions`

用于分析：
- 返工率
- 状态修理次数
- `external blocker` 占比
- queue zombie 时长
- agent recover 成本

## P2-3：External blocker 自动建议前置任务

例如：

```json
{
  "blocker_code": "missing_unseen_source_pdfs",
  "suggested_task": "补充 unseen blind PDF 来源并登记 provenance"
}
```

仅做建议，不自动创建，除非 PM 明确触发。

---

## 7. watcher 推荐执行顺序

建议每轮 watcher 固定顺序：

1. scan tasks
2. task-state-sanitizer
3. task-state-reducer / health reducer
4. dependency / blocker propagation
5. queue preflight validation
6. review / qa queue lease handling
7. close-task
8. notification / nudge throttling
9. dashboard sync / system events

### 关键约束
- sanitizer 幂等
- direct nudge 有 sentinel
- `external blocked` 不再催执行者
- queue zombie 必须回收
- 所有自动修复写入 `transitions / sanitizer_actions`

---

## 8. 推荐任务拆分

### P0 任务包
1. 引入任务健康态与归约规则
   - 改 `task-state-reducer.py`
   - 写 schema 文档
   - 补 tests
2. 实现任务状态清洗器并接入 watcher
   - 新增 `task-state-sanitizer.py`
   - watcher 前置调用
   - 补 dry-run / apply 模式
3. 固化 internal/external blocker schema
   - 增加 blocker 字段
   - pool-view / PM inbox 使用
   - BlindHoldout 作为回归样例
4. Review/QA router 前置硬校验
   - 增强 `task-queue-router.py`
   - 非法 artifact 不入队
   - 写 health reason
5. Review/QA queue lease 闭环
   - queue state 增加 assigned / acked / stale
   - 增加 zombie 回收
   - dashboard / inbox 输出 pending 原因

### P1 任务包
- pool claimable 视图
- PM Inbox
- recover protocol
- communication 分层固化

### P2 任务包
- PM 批量治理脚本集
- span / health 统计
- external blocker 自动建议

---

## 9. 主要风险与迁移策略

### 风险 1：字段过多再次变成“第二状态机”

控制策略：
- `status` 只表达生命周期
- `task_health` 只表达可推进性
- `blocker_*` 只表达阻塞归因
- `queue_state` 只表达 review/QA 队列租约

### 风险 2：sanitizer 误修

控制策略：
- 先 dry-run
- P0 只修低风险字段
- 每次修复写 `sanitizer_actions`
- PM 可回溯 `transitions`

### 风险 3：external blocked 被滥用

控制策略：
- 必须有 `blocker_code`
- 必须有 `unblock_requirements`
- 必须说明为什么团队内部无法解除
- `QA fail` 不自动等于 `external`

### 风险 4：review queue 改造过重

控制策略：
- 不引入新队列系统
- 先在现有 `queue_state` 上补 lease 字段
- 先只解决 zombie 占位和 ack 可见性

---

## 10. 最终建议

正式采纳该方案，但实施顺序调整为：

- `P0-1 task_health`
- `P0-2 sanitizer`
- `P0-3 blocker schema`
- `P0-4 queue preflight`
- `P0-5 review/QA queue lease 闭环`
- `P1 pool claimable + PM inbox + recover protocol`
- `P2 批量治理 + span 分析 + 自动建议`

### 一句话落地原则

```text
先让系统知道“为什么不能推进”，
再让 watcher 自动修复“能安全修的脏状态”，
最后再把 PM 高频治理动作批量化。
```
