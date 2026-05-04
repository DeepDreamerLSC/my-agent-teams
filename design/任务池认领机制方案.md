# 任务池认领机制方案

> 创建时间：2026-05-04  
> 适用仓库：`~/Desktop/work/my-agent-teams/`  
> 背景：将当前任务分发机制从 **PM 指派制** 调整为 **任务池认领制**，解决单 PM 一次性派发过多任务给同一 agent，导致多条任务同时 `working` 超时、执行顺序与依赖脱节的问题。  
> 目标：让 PM 从“逐条派发者”转变为“任务审核者 + 队列调度者”，让执行者在约束下按优先级、依赖和能力主动认领。

---

## 一、问题定义

昨天暴露出的核心问题不是“某个人做得慢”，而是：

1. **PM 一次性把多条任务推给同一 agent**
2. agent 收到后全部进入 `working`，但真实执行只能串行
3. `task.json.status=working` 与真实“是否可开工”脱节
4. QA 也被过早拉入 `working`，形成“前置未完成，但下游已启动”的错位

这说明当前模式的主要缺陷是：

- **任务进入执行态过早**
- **执行顺序由 PM 猜，而不是由 agent 在就地上下文中选择**
- **依赖、负载、write_scope 冲突没有在“启动执行之前”被足够严格控制**

因此，需要一个新的原则：

> **任务先入池；watcher 负责在主线完成后自动续推下一条可执行任务；agent 只做轻量确认/接单，只有 `ack.json` 之后才进入真正的 working 主链路。**

---

## 二、总体原则

### 2.1 核心转变
从：
```text
PM 创建任务 -> 直接指派给具体 agent -> agent 被动接收
```
变为：
```text
PM 创建任务 -> 放入公共任务池 -> watcher 维护可执行顺序 -> agent 完成主线后，watcher 自动续推“唯一下一条可执行任务” -> agent 写 ack -> 进入现有执行主链路
```

### 2.2 不变的底层原则
即使改成认领制，下列原则保持不变：

1. **`task.json` 仍然是唯一任务事实源**
2. **`ack.json / result.json / verify.json / transitions.jsonl` 继续生效**
3. **Chat Hub 不是状态事实源，只是协作沟通入口**
4. **生产 / critical 任务仍保留 PM 强制介入能力**
5. **PM 仍然保留最终仲裁权**

### 2.3 认领制不等于放弃调度
改成认领制后，PM 的工作减少的是“逐条喊人开工”，不是“放弃调度”。

PM 仍然负责：
- 判断任务是否允许入池
- 控制优先级
- 识别长期无人认领/认领错误/认领后卡死
- 对 critical / deploy / integration 任务决定是否允许自由认领

---

## 三、任务创建与入池流程

## 3.1 新的任务创建流程

### 旧流程
```text
create-task.sh -> assigned_agent=dev-1 -> dispatch-task.sh -> send-to-agent.sh
```

### 新流程
```text
create-task.sh -> assigned_agent=auto -> status=pending -> 进入任务池
PM 补全 instruction / gate 校验通过 -> status=pooled -> 等待 agent 认领
```

### 关键设计
- `assigned_agent` 默认改为：
  - `auto`
  - 或 `auto-dev`（仅开发执行池）
- 任务并不是创建后立刻 `dispatched`
- 任务先进入一个可认领态，例如：
  - `pending`（未完成任务定义）
  - `pooled`（已完成 gate，可认领）

---

## 3.2 入池前门禁（Pool Gate）

不是所有任务创建后都能立即进池，必须先过 **Pool Gate**：

### 入池必备条件
1. `instruction.md` 已补全，且无占位字段
2. `task_type` 明确
3. `write_scope` 明确
4. `depends_on` 已声明
5. `priority` 已声明
6. `review_level / test_required / target_environment` 已声明
7. 若是 `prod / deploy / integration`：不能进自由认领池

### 建议状态流转
```text
pending --(PM补完定义并通过 pool gate)--> pooled
```

### 例外任务
以下任务默认 **不进入自由认领池**：
- `deployment`
- `integration`
- `prod`
- owner 明确点名任务
- 高风险跨域协调任务

这些仍由 PM 定向指派或仅限特定角色认领。

---

## 3.3 任务池目录形态

### 推荐方案 A：逻辑任务池（优先推荐）
不移动目录，只通过 `task.json.status=pooled` 表达“在池中”。

优点：
- 不打断现有 `tasks/{task-id}/` 结构
- watcher / board sync / dashboard 无需学习第二套目录语义
- 与现有脚本兼容性最好

### 推荐字段
```json
{
  "id": "补齐看板阶段耗时持久化与回填",
  "status": "pooled",
  "assigned_agent": "auto",
  "claim_policy": "pull",
  "claim_scope": ["dev-1", "dev-2"],
  "claim_max_concurrency": 1,
  "depends_on": ["补齐看板Schema迁移与回填策略"],
  "pool_entered_at": "2026-05-04T10:00:00+08:00",
  "pool_timeout_minutes": 120
}
```

### 不推荐方案 B：物理 `pool/` 目录
虽然历史设计里提过 `tasks/pool/`，但当前仓库所有 watcher / board /脚本都围绕 `tasks/<task-id>/task.json` 工作，物理迁移成本更高。  
因此本轮建议先采用**逻辑任务池**，后续如有必要再物理分层。

---

## 四、混合制续推流程

## 4.1 续推时机

watcher 在以下时机为 agent 自动续推下一条任务：

1. 当前主线任务进入 `done`
2. 当前执行类主线任务进入 `ready_for_merge`（实现已完成，进入 review/QA 阶段）
3. agent 当前没有其它 `working/dispatched` 主线任务

### 基本原则
- **续推是半自动，不是全自动开工**
- watcher 只负责“挑出下一条并提醒”
- agent 仍然必须写 `ack.json` 才进入真正的 `working`
- 同一时间每个 agent 默认只保留 1 条主线

---

## 4.2 续推流程（逻辑）

```text
当前主线任务完成/进入待审
-> watcher 检查该 agent 是否已无其它 active 主线
-> 在 pooled 任务池中筛出该 agent 可接的候选任务
-> 按顺序选出“唯一下一条可执行任务”
-> watcher 调用 claim-task.sh 原子认领
-> task.json: pooled -> dispatched
-> transitions.jsonl 记录 claim
-> watcher 用 send-to-agent.sh 定向提醒该 agent
-> agent 阅读 instruction 并写 ack.json
-> dispatched -> working
```

### 关键点
- **watcher 续推 ≠ watcher 替 agent 开工**
- watcher 只负责挑出和推送下一条
- agent 仍然必须通过 `ack.json` 明确接单
- 这样既避免“PM 一次塞太多”，也避免“agent 做完就闲着”

## 4.2.1 候选任务选择顺序

watcher 应按以下顺序为某个 agent 选择下一条任务：

1. `status = pooled`
2. `claim_scope` 命中当前 agent
3. 依赖已满足（默认 `done_only`，允许任务级策略放宽到 `ready_for_merge_ok`）
4. 与该 agent 当前 active tasks 无 `write_scope` 冲突
5. `priority` 最高优先
6. 同优先级下，`pool_entered_at` 最早优先

> 结论：选择逻辑由 watcher 固化，不再依赖 agent 自己记得去池里扫任务。

---

## 4.3 claim 记录形式

建议新增：
- `claim.json`

示例：
```json
{
  "task_id": "补齐看板阶段耗时持久化与回填",
  "agent": "dev-2",
  "claimed_at": "2026-05-04T10:05:00+08:00",
  "reason": "当前空闲，具备 dashboard 后端实现能力，且上游依赖已满足"
}
```

### 说明
- `claim.json` 现在既可以由 agent 主动写入，也可以由 watcher 在自动续推时通过 `claim-task.sh` 产生
- `claim.json` 仍然不是最终 working 事实
- 最终执行事实点仍然是 `ack.json`

---

## 4.4 原子确认机制

为防并发冲突，当前实现采用统一的 claim 原子路径（`claim-task.sh` + watcher 规则），由 watcher 在续推时直接走同一套约束：

### 原子步骤
1. `flock` 锁定任务目录或 task.json
2. 读取当前 `task.json`
3. 校验：
   - 状态仍为 `pooled`
   - 依赖已满足
   - 该 agent 当前未超认领上限
   - 与已有 active tasks 无 write_scope 冲突
4. 若通过：
   - `assigned_agent = <agent>`
   - `status = dispatched`
   - 写 `lease_owner = owner_pm`
   - 写 `claimed_by / claimed_at`
   - 追加 `transitions.jsonl`
5. 若失败：
   - 保持 `pooled`
   - 给 agent 一个“认领失败原因”通知

---

## 五、认领约束设计

## 5.1 每个 agent 同时最多认领 N 条任务

### 建议
- 默认：`N = 1`
- 最多不超过：`2`

### 原因
昨天的问题已经证明：
> 只要一个 agent 同时进入多条 `working`，执行顺序就会失真。

因此当前阶段建议：
- **每个执行 agent 默认只能有 1 条 working 主线任务**
- 可以允许额外持有 1 条 `dispatched but not started` 的轻量后续任务（可选）
- QA 也应限制同类并发，避免验证任务先后错乱

### 推荐口径
- `working_count <= 1`
- `claimed_active_count <= 2`

---

## 5.2 依赖链未完成，不能认领下游

### 规则
若 `depends_on` 中任一任务未进入允许状态，则不能认领。

### 建议允许状态
对上游依赖，至少应满足：
- `done`
- 某些场景可允许 `ready_for_merge`（需 PM 配置）

### 默认策略
- 保守起见：默认只接受 `done`
- 如是并行可接续型任务，可由 PM 显式设置：
  - `dependency_policy = ready_for_merge_ok`

---

## 5.3 write_scope 冲突检测

### 规则
认领前必须检查该 agent 当前 active tasks 的 `write_scope` 是否冲突。

### 冲突定义
若两个任务的 scope：
- 相同路径
- 父子路径
- 目录整体覆盖
则视为冲突

### 结果
- 有冲突：禁止认领
- 无冲突：允许继续

### 说明
当前 `create-task.sh` / `dispatch-task.sh` 已有 scope overlap 逻辑，可直接复用到 claim 流程。

---

## 5.4 角色与能力匹配

### 推荐字段
```json
{
  "claim_scope": ["dev-1", "dev-2"],
  "suggested_roles": ["backend_dev"],
  "suggested_reason": "需要 dashboard SQLite / ingest 经验"
}
```

### 策略
- 默认优先匹配：
  - `claim_scope`
  - `domains`
  - `role`
- 不匹配但强行认领：
  - 允许，但需 PM 审核
  - 或者直接拒绝（当前更建议拒绝）

### 特殊任务
- `integration`：只允许 `arch-1`
- `deployment`：只允许 `arch-1`，且需要 owner 授权
- `design`：优先 `arch-1`
- `verification`：优先 `qa-1`

---

## 5.5 池中超时与回收

### 情况 A：长期无人认领
若任务处于 `pooled` 超过阈值：
- 默认 `pool_timeout_minutes = 120`
- watcher 通知 PM
- PM 决定：
  - 降级优先级
  - 收缩边界
  - 强制定向指派

### 情况 B：认领后长期不 ack
若任务已 `dispatched` 但 agent 不写 `ack.json`：
- 继续沿用现有 dispatched 超时机制
- 超时后：
  - 可回退到 `pooled`
  - 或仍由 PM 决定是否强制指派给他人

### 建议
不要自动无脑回池。  
因为这会掩盖“agent 已看见但没执行”的问题。应保留 PM 仲裁点。

---

## 六、PM 角色转变

## 6.1 从派发者变为审核者和调度者

### PM 不再负责
- 逐条指定所有执行任务给哪个 dev
- 过早把 QA/下游任务推成 `working`

### PM 仍然负责
1. **创建任务**
2. **补全 instruction**
3. **决定是否允许入池**
4. **定义 claim_scope / priority / depends_on**
5. **监控认领是否合理**
6. **对长期无人认领/认领错误/排队失控做介入**

---

## 6.2 PM 需要重点监控的异常

### 异常 1：长期无人认领
说明：
- 任务太难
- 边界太模糊
- 优先级不合理
- claim_scope 过窄

### 异常 2：同一 agent 仍在囤积任务
说明：
- claim 限制失效
- watcher 未阻止超认领
- agent 操作准则未执行到位

### 异常 3：下游任务过早被认领
说明：
- depends_on 校验失效
- ready_for_merge / done 边界不清

### 异常 4：多 agent 竞争同一任务
说明：
- 需要原子锁
- 需要认领失败反馈

---

## 6.3 PM 可保留的强制介入手段

以下情况 PM 仍可绕过任务池，直接指派：
- 生产故障
- critical 安全问题
- owner 明确点名任务
- 长期无人认领的关键任务
- 需要特定 agent 的上下文续做任务

也就是说：
> **任务池认领制是默认路径，不是唯一路径。**

---

## 七、与现有机制的兼容设计

## 7.1 与 `dispatch-task.sh` 的兼容

### 当前问题
`dispatch-task.sh` 要求：
- `status = pending`
- `assigned_agent` 必须是明确 agent
- `auto` 会直接报错

### 建议改造
把现有 `dispatch-task.sh` 拆成两层：

#### A. `dispatch-task.sh`（保留）
仍只负责：
- **已确定 agent 的任务**
- `pending -> dispatched`
- 定向唤醒
- task_announce

#### B. 新增 `pool-task.sh` 或 `queue-task.sh`
负责：
- `pending -> pooled`
- 校验 Pool Gate
- 不发定向唤醒
- 可发 task_announce（可选）

### 结论
不要强行让 `dispatch-task.sh` 同时承担“入池”和“派发”两种职责，否则语义会越来越混乱。

---

## 7.2 与 `ack.json` 的兼容

完全兼容，且更重要：
- `ack.json` 继续作为“真正开始执行”的证据
- 认领成功后只到 `dispatched`
- 写出 `ack.json` 后才到 `working`

这正好解决昨天的核心问题：
> **任务不应一被指到某人名下就算 working。**

---

## 7.3 与 `result.json` 的兼容

完全兼容：
- 认领后的执行过程不变
- `result.json -> review / QA / close` 的链路保持不变

---

## 7.4 与 `task-watcher` 的兼容

当前 `task-watcher.sh` 已经存在：
- `AUTO_ASSIGN_MARKERS=auto,auto-dev,unassigned`
- `auto_claim_pending_dev()`
- dispatched 超时重发
- working 超时提醒

### 现实判断
仓库实际上已经有一个“半成品认领机制”：
- `assigned_agent=auto`
- watcher 在 pending execution task 上做 auto claim

### 问题
当前这个实现仍然不够完整：
1. 它更像 watcher 替 agent 直接认领，而不是 agent 主动 claim
2. 没有显式 `pooled` 状态
3. 没有 `claim.json` 意图层
4. 没有明确的并发/配额/依赖策略可见性
5. QA/下游任务也可能被过早推进

### 建议
现有 `task-watcher` 不要推倒，改造成：

#### Phase 1（最小改造）
- 引入 `pooled`
- watcher 只做：
  - 发现可认领任务
  - 评估候选 agent
  - 发送“可认领提醒”
- agent 写 `claim.json`
- watcher 做原子确认

#### Phase 2（进一步自动化）
- 再考虑 watcher 在明确 idle、明确能力匹配时，代 agent 发起 auto-claim
- 但依然应在 task.json / transitions 中留下清晰 claim 轨迹

---

## 八、推荐字段扩展

## 8.1 `task.json` 新增字段建议

```json
{
  "status": "pooled",
  "assigned_agent": "auto",
  "claim_policy": "pull",
  "claim_scope": ["dev-1", "dev-2"],
  "claim_max_concurrency": 1,
  "pool_entered_at": "2026-05-04T10:00:00+08:00",
  "pool_timeout_minutes": 120,
  "dependency_policy": "done_only",
  "claimed_by": null,
  "claimed_at": null,
  "claim_reason": null
}
```

### 字段说明
- `claim_policy`
  - `pull`：任务池认领
  - `push`：PM 直接指派
- `claim_scope`
  - 哪些 agent 可认领
- `claim_max_concurrency`
  - 当前任务类型对 agent 并发占用上限
- `dependency_policy`
  - `done_only`
  - `ready_for_merge_ok`
- `claimed_*`
  - 记录最终认领事实

---

## 8.2 `claim.json` 建议

```json
{
  "task_id": "补齐看板阶段耗时持久化与回填",
  "agent": "dev-2",
  "claimed_at": "2026-05-04T10:05:00+08:00",
  "reason": "当前空闲且上游已完成，具备 dashboard 后端实现能力"
}
```

---

## 九、建议实施步骤

## Phase A：方案落盘（先做）
1. 补设计文档
2. 明确 `pooled` 状态
3. 明确 `claim.json` 契约
4. 明确 PM / watcher / agent 的职责边界

## Phase B：最小实现
1. 新增 `pool-task.sh` / `queue-task.sh`
2. create-task 支持 `assigned_agent=auto`
3. task-watcher 支持：
   - `pending -> pooled`
   - 处理 `claim.json`
   - 原子确认 claim
4. dev / qa / arch 角色模板增加“任务池认领规则”

## Phase C：执行收敛
1. 默认 execution 任务走任务池
2. PM 只对特殊任务强制指派
3. 观察是否仍出现多条 `working` 同时超时

---

## 十、最终建议

### 推荐结论
**建议采用“逻辑任务池 + watcher 自动续推 + agent ack 确认 + ack 才算 working”的混合制方案。**

这是当前成本最低、与现有系统兼容性最高的改法：
- 不需要重构整个 `tasks/` 目录
- 不打断现有 `ack/result/verify` 链路
- 能直接解决昨天暴露出来的“任务过早进入 working”问题

### 一句话结论
> 把“是否开始执行”的决定，从 PM 的一次性推送，改成“PM 排队 + watcher 自动续推下一条 + agent 写 ack 明确开工”的混合机制，才能同时避免“塞太多”和“做完就闲着”两个极端。
