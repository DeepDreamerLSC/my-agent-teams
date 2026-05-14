# Agent 协作控制面收敛与任务池优化方案

> 创建日期：2026-05-09  
> 修订日期：2026-05-09  
> 状态：实施方案草案（已整合 PM 反馈）  
> 适用范围：`/Users/linsuchang/Desktop/work/my-agent-teams` 的任务协作、task-watcher、Chat Hub、dashboard 与任务池认领机制  
> 背景依据：当前 task-watcher / Chat Hub / 任务池实现审查；既有文档 `任务池认领机制方案.md`、`Chat-Hub-协议补充.md`、`任务协作看板优化方案.md`、`/Users/linsuchang/Desktop/work/design/chiralium-ci/Agent团队效率优化待办.md`（原始日期 2026-05-07）  
> 本次修订重点：补充 `resume-task` 恢复语义、通知三级分流、非法 artifact 一次性告警、PM Inbox / 待 PM 处理总视图、P0 最小契约前置与 5 月 7 日待办文档合并评估。

---

## 0. 一句话结论

当前协作不流畅的根因不是单个脚本缺功能，而是 **`task.json` 事实源、`task-watcher` 自动流转、Chat Hub 消息/时间线三套控制面边界没有完全收敛**。

目标态应改为：

```text
任务事实源：tasks/<task-id>/task.json + 机器产物 JSON + transitions.jsonl
        ↓
编排执行面：task-watcher 只做确定性状态归约、队列续推、通知调度
        ↓
通信时间线：Chat Hub 只记录公告/讨论/系统事件，不驱动任务状态
        ↓
只读视图：dashboard / CLI / PM Inbox 聚合任务池、队列、WIP、待 PM 处理项与时间线
```

其中，**任务池不是 Chat Hub 任务池**，而是：

```text
task.json.status = pooled
+ claim_policy = pull
+ claim_scope / priority / depends_on / write_scope
```

Chat Hub 只承载 `pool_entered / claimed / nudge / blocked` 等事件的时间线与通知，不作为认领状态机事实源。

PM Inbox / 待 PM 处理总视图也是 L4 只读聚合，不是第四套控制面；它只把 `blocked`、各类 `timeout`、`pm_acceptance_pending`、`artifact_invalid` 等需要 PM 动作的事项汇总到一个入口，并指向对应脚本动作。

---

## 1. 当前问题复盘

### 1.1 三套控制面并存

| 控制面 | 当前职责 | 问题 |
|---|---|---|
| `tasks/` 文件事实源 | `task.json`、`ack.json`、`result.json`、`review.md`、`verify.json`、`transitions.jsonl` | 产物契约不统一，legacy Markdown 与新版 JSON 真相源混用 |
| `task-watcher.sh` | 扫描任务、状态流转、自动派发、自动认领、review/QA、close、通知、看板同步 | 职责过重，状态机与通知/队列耦合，容易刷屏或卡状态 |
| Chat Hub | 人类讨论、任务公告、watcher/dispatch/nudge system 事件 | A-Lite 文档定位为消息区，但部分流程期待它像任务池主界面，预期错位 |

### 1.2 已确认的实现差异

1. **Chat Hub A-Lite 明确不做任务认领状态机**
   - Chat Hub 文档定义：`tasks/` 是状态事实源，`chat/` 只承载公告、讨论、问答、简短同步。
   - A-Lite 当前不做：私聊、任务认领状态机、已读游标/去重文件。

2. **任务池已经是逻辑池，但公告链路不完整**
   - `pool-task.sh` 会把任务改为 `status=pooled`。
   - `claim-task.sh` 要求 `status=pooled` 才能认领。
   - 但入池后调用 `send-chat.sh announce` 时，`announce` 当前不允许 `pooled` 状态，且错误被吞掉。
   - 结果：任务已入池，但 ChatHub 可能没有可靠公告，PM/agent 感知割裂。

3. **机器产物契约与方案不一致**
   - 方案要求 `result.status = success / failed / blocked`。
   - 当前 watcher 主要把 `result.status=done` 当完成。
   - 方案要求 `review.json` 是机器真相源。
   - 当前 watcher/close-task 仍解析 `review.md / design-review.md`。

4. **watcher 通知存在重复噪音**
   - review/QA 队列等待通知缺少足够细粒度 sentinel。
   - PM Chat Check 近 1 天可见大量 system event 与 PM mention，且同一任务存在多次“进入 QA 队列”等重复提示。

5. **任务池缺主视图**
   - 目前有 `pool-task.sh / claim-task.sh`，但缺：
     - PM 一眼看池中任务的视图；
     - agent 只看自己可认领任务的视图；
     - 任务为何不可认领的解释；
     - 池中等待超时与升级策略。

6. **PM 待处理事项入口分散**
   - `blocked`、`working_timeout`、`pool_timeout`、`pm_acceptance_pending`、`artifact_invalid`、auto-close 失败等都需要 PM 关注，但当前分散在 watcher 通知、ChatHub system event、任务目录和 dashboard 局部视图中。
   - PM 缺少一个“今天到底要处理什么”的统一入口，容易在降噪后漏看，或在刷屏时重复处理同一任务。

7. **blocked 恢复缺少明确语义**
   - 当 PM 将 blocked 任务恢复为 dispatched 时，如果旧 `ack.json`、旧 blocked `result.json`、旧 `result_route` / `working_timeout` sentinel 没有清理，watcher 可能继续按旧执行状态或旧超时记录发告警。
   - 这不是普通“通知去重”能解决的问题，需要明确 `resume-task` 语义：恢复任务时要归档旧执行工件、清理旧运行态 sentinel、写入恢复事件。

---

## 2. 目标架构：三套控制面收敛策略

### 2.1 控制面分层

目标不是把所有东西合成一个大脚本，而是明确四层边界：

```text
┌──────────────────────────────────────────┐
│  L4 只读视图层                            │
│  dashboard / task-aggregate / list-pool   │
│  pm-inbox                                 │
│  只读聚合，不修改任务事实                   │
└──────────────────────────────────────────┘
                  ▲
                  │ ingest / sync
┌──────────────────────────────────────────┐
│  L3 通信时间线层                          │
│  Chat Hub general/tasks/system            │
│  记录讨论、通知、送达、审计；不驱动状态       │
└──────────────────────────────────────────┘
                  ▲
                  │ append-only events
┌──────────────────────────────────────────┐
│  L2 编排执行层                            │
│  task-watcher + 分拆后的 router/reducer    │
│  读取事实源，做确定性状态归约与队列续推       │
└──────────────────────────────────────────┘
                  ▲
                  │ read/write task facts
┌──────────────────────────────────────────┐
│  L1 任务事实层                            │
│  task.json + ack/result/review/verify JSON│
│  transitions.jsonl append-only 审计         │
└──────────────────────────────────────────┘
```

### 2.2 每层的唯一职责

#### L1：任务事实层

唯一职责：保存可审计事实。

包括：
- `task.json`：生命周期状态、负责人、任务池字段、gate 字段。
- `ack.json`：agent 确认已接单。
- `claim.json`：认领意图/认领记录。
- `result.json`：执行结果机器事实。
- `review.json` / `design-review.json`：审查结论机器事实。
- `verify.json`：QA 验证机器事实。
- `transitions.jsonl`：生命周期与 gate 变化审计。

原则：
- 所有自动状态流转只信 L1。
- Markdown 只做人读说明，不作为目标态机器判定依据。
- 每次状态变化必须写 `transitions.jsonl`。

#### L2：编排执行层

唯一职责：从事实源归约出下一步动作。

包括：
- 状态归约：`pending/pooled/dispatched/working/ready_for_merge/blocked/done`。
- gate 归约：`review_pending/qa_pending/pm_acceptance_pending/review_rejected/qa_failed/closed`。
- 队列续推：任务池、review 队列、QA 队列。
- close 调度：满足 gate 时调用 `close-task`。
- 通知调度：只在状态/gate/队列有新变化时通知。

原则：
- watcher 不直接根据 ChatHub 消息改状态。
- watcher 不重复解释各类 JSON，应调用统一 artifact parser。
- watcher 的每个自动动作必须幂等、有 sentinel、有重试上限。

#### L3：通信时间线层

唯一职责：记录协作过程，给人和看板提供上下文。

包括：
- `chat/tasks/<task-id>.jsonl`：任务讨论、问题、回答、完成短同步。
- `chat/system/watcher/*.jsonl`：watcher 通知。
- `chat/system/dispatch/*.jsonl`：派发事件。
- `chat/system/direct_nudge/*.jsonl`：强制唤醒/重发事件。

原则：
- ChatHub 不是任务状态事实源。
- `task_done` 不是 done；`claim` 消息不是认领成功。
- 关键结论必须回写 L1 或项目上下文。
- critical / prod 仍必须双通道：ChatHub 可见 + `send-to-agent.sh` 强制触达。

#### L4：只读视图层

唯一职责：让 PM、林总工、agent 快速理解状态。

包括：
- Dashboard 任务看板。
- Dashboard 任务池页。
- PM Inbox / 待 PM 处理总视图。
- 单任务 timeline。
- CLI：`list-pool.sh`、`list-pm-inbox.sh`、`task-aggregate.py`、`pm-chat-check.sh`。

原则：
- 只读视图不修改 `task.json`。
- 所有统计都可从 L1/L3 重建。
- 视图错了可以重建，不影响任务事实。

### 2.3 单向数据流

推荐数据流：

```text
create/dispatch/pool/claim/ack/result/review/verify
        ↓ 写入
L1 任务事实层
        ↓ watcher 扫描 + reducer 归约
L2 编排执行层
        ├─ 写回 task.json / transitions.jsonl
        ├─ 调用 close-task
        ├─ 发送 send-to-agent 强制触达
        └─ 写入 ChatHub system events
                  ↓
L3 通信时间线层
                  ↓ ingest
L4 dashboard / CLI 只读视图
```

禁止反向流：

```text
ChatHub message  ─X→ 直接修改 task.json 状态
Dashboard click  ─X→ 绕过脚本直接写任务事实
Markdown verdict ─X→ 目标态作为唯一机器真相源
```

---

## 3. 生命周期与 gate 收敛

### 3.1 任务生命周期状态

目标态只保留以下新任务状态：

| status | 含义 | 谁可写 |
|---|---|---|
| `pending` | 任务已创建，但定义或 gate 未完成 | create/PM |
| `pooled` | 已过 Pool Gate，等待认领 | pool-task / PM |
| `dispatched` | 已指派或认领成功，等待 agent ack | dispatch / claim / watcher |
| `working` | agent 已写 `ack.json`，正式执行中 | watcher |
| `ready_for_merge` | 执行产物已提交，等待 review/QA/PM gate | watcher |
| `blocked` | 需要 PM/owner 仲裁 | watcher / PM |
| `done` | 已收口完成 | close-task |
| `cancelled` | PM 取消 | PM |
| `archived` | 已归档 | archive-task |

Legacy 状态：
- `in_review` / `reviewing` / `merged` 只允许迁移兼容，不作为新任务目标状态。

### 3.2 gate 状态

`merge_gate_state` 目标枚举：

| gate | 含义 | 自动动作 |
|---|---|---|
| `review_pending` | 等 review 机器结论 | 派发/续推 review |
| `qa_pending` | 等 QA 机器结论 | 派发/续推 QA |
| `pm_acceptance_pending` | 等 PM/owner 最终收口 | 通知 PM，允许 close |
| `review_rejected` | review 要求修改 | 进入 blocked，清 review 队列占用 |
| `qa_failed` | QA 失败 | 进入 blocked，清 QA 队列占用 |
| `blocked` | 无法自动判断或外部阻塞 | 通知 PM 仲裁 |
| `closed` | close-task 成功 | 只发一次最终通知 |

### 3.3 状态归约原则

watcher 不应写散落条件判断，而应通过一个纯函数归约：

```text
next = reduce_task_state(task.json, artifacts)
```

输入：
- task metadata；
- artifact parser 输出；
- 当前 status/gate；
- 当前队列/通知 sentinel。

输出：

```json
{
  "status": "ready_for_merge",
  "merge_gate_state": "review_pending",
  "actions": [
    {"type": "dispatch_review", "to": "review-1"},
    {"type": "emit_chat", "event_type": "gate_changed"}
  ],
  "reason": "result.success + review_required=true"
}
```

这样可以用 fixture 覆盖任意产物到达顺序，避免 shell 条件散落。

---

### 3.4 `resume-task` 恢复语义

#### 3.4.1 为什么需要单独语义

`blocked -> dispatched` 不是普通状态回退，而是一次新的执行尝试。恢复时如果沿用旧执行工件，会产生三类风险：

1. **旧 ack 误导 watcher**：任务刚恢复成 `dispatched`，但旧 `ack.json` 仍存在，watcher 可能立即把任务推进 `working`，跳过 agent 对新指令/新边界的确认。
2. **旧 result 误导路由**：旧 `result.json.status=blocked/failed` 仍存在，watcher 可能继续按旧阻塞结论通知 PM，或重新触发 result route。
3. **旧 sentinel 误导告警**：旧 `working_timeout` / `result_route` / resend sentinel 仍存在，watcher 可能不该告警时继续告警，或该通知时被旧 sentinel 抑制。

因此必须把恢复定义为一个显式动作：

```text
blocked --(resume-task)--> dispatched
```

禁止手工只改 `task.json.status` 来恢复任务。

#### 3.4.2 `resume-task` 输入

建议新增：

```bash
scripts/resume-task.sh --task-dir <task-dir> --agent <agent-id> --reason <reason> [--keep-result-history]
```

必填：
- `task_dir`：目标任务目录。
- `agent`：恢复后执行者，默认可取原 `assigned_agent`，但必须显式落盘。
- `reason`：PM/owner 恢复原因，例如“已补齐输入事实”“review rejected 已完成整改”。

可选：
- `--keep-result-history`：仅表示保留归档副本；不允许旧 `result.json` 继续作为当前执行事实。

#### 3.4.3 恢复时必须做的清理

恢复动作必须是原子的，至少包含：

| 对象 | 恢复动作 | 原因 |
|---|---|---|
| `ack.json` | 移动到 `history/ack.<timestamp>.json` 或 `ack.resume-archived-<timestamp>.json` | 强制 agent 重新确认新一轮任务 |
| 当前 `result.json` | 若 `status=blocked/failed` 或对应旧轮次，移动到 `history/result.<timestamp>.json` | 防止 watcher 继续按旧阻塞结论路由 |
| `claim.json` | 视恢复方式清理或重写 | 防止旧认领人与恢复后执行者不一致 |
| watcher `*_result_route` sentinel | 删除当前 task 对应 result route sentinel | 允许新 result 产生后重新路由 |
| watcher `*_working_timeout_notice` sentinel | 删除 | 防止旧超时记录影响新一轮执行 |
| watcher `*_resend` sentinel | 删除 | 允许恢复后按新 dispatched 时间重发 |
| auto-close retry sentinel | 删除 | 新一轮验证/close 重新计数 |
| `merge_gate_state` | 置空或写入 `resumed` 临时字段后归约 | 避免旧 `review_rejected/qa_failed/blocked` gate 残留 |
| `rework_reason` | 写入本次恢复原因或清空旧值 | 让 PM/看板能区分旧阻塞与新执行 |

建议目录：

```text
tasks/<task-id>/
├── history/
│   ├── ack.20260509T103000.json
│   ├── result.20260509T103000.json
│   └── resume.20260509T103000.json
├── task.json
├── transitions.jsonl
└── instruction.md
```

#### 3.4.4 `task.json` 写回字段

恢复后至少写：

```json
{
  "status": "dispatched",
  "assigned_agent": "dev-1",
  "merge_gate_state": null,
  "rework_reason": "PM resumed after blocked input fixed",
  "last_gate_actor": "pm-chief",
  "last_gate_decision_at": "2026-05-09T10:30:00+08:00",
  "resume_round": 1,
  "last_resumed_at": "2026-05-09T10:30:00+08:00",
  "last_resumed_by": "pm-chief"
}
```

并追加 `transitions.jsonl`：

```json
{"from":"blocked","to":"dispatched","at":"...","reason":"resume-task: input fixed","actor":"pm-chief"}
```

#### 3.4.5 watcher 恢复兼容规则

在 `resume-task.sh` 落地前，watcher 也必须具备最低兼容保护：

- 如果发现 `task.status=dispatched`，但 `ack.json` 早于最近一次 `blocked -> dispatched` transition，则忽略旧 ack，并发出一次 `reopen_with_stale_state` 降级告警。
- 如果发现 `task.status=dispatched/working`，但 `result.json` 早于最近一次 resume transition，必须忽略旧 result，不得按旧 result route。
- 如果发现旧 sentinel 时间早于最近一次 resume transition，应视为失效。
- 上述 stale state 只允许一次性通知 PM，之后进入可恢复的等待状态，不允许反复刷屏。

#### 3.4.6 验收标准

- blocked 任务通过 `resume-task.sh` 恢复后，agent 必须重新写 `ack.json` 才能进入 `working`。
- 旧 blocked `result.json` 不会再次触发 result route。
- 旧 working timeout sentinel 不会在恢复后立即触发超时告警。
- transitions 中能看出每一轮 blocked/resume/ack/result 的边界。

---

## 4. task-watcher 拆分方案

### 4.1 拆分目标

当前 `task-watcher.sh` 同时承担：
- 扫描任务目录；
- 状态迁移；
- legacy 状态归一；
- result/review/verify 解析；
- 自动派发 arch/dev；
- pooled 任务认领与 nudge；
- review/QA 队列续推；
- close-task 调用；
- 飞书、tmux、ChatHub 通知；
- dashboard sync；
- heartbeat / pid / log rotate。

目标是把它改成一个薄调度器：

```text
task-watcher.sh
  ├─ 负责单实例、循环扫描、heartbeat、调用模块
  └─ 不再内嵌业务状态机细节
```

### 4.2 推荐模块边界

| 模块 | 形式 | 职责 |
|---|---|---|
| `scripts/lib/task_artifacts.py` | Python lib | 统一解析 ack/result/review/verify/claim，处理 legacy mapping |
| `scripts/task-state-reducer.py` | CLI + lib | 输入 task dir，输出 status/gate/actions JSON；纯归约，不发通知 |
| `scripts/task-pool-router.py` | CLI | 列出可认领任务、判断 agent 是否可接、选择下一条任务 |
| `scripts/task-queue-router.py` | CLI | review / QA 队列候选选择与占用状态 |
| `scripts/task-inbox.py` / `scripts/list-pm-inbox.sh` | Python/CLI | 聚合 blocked/timeout/acceptance/artifact_invalid 等待 PM 处理项，输出 CLI/dashboard JSON |
| `scripts/task-notifier.sh` | shell | 统一 send-to-agent、send-chat、Feishu，带 sentinel 去重 |
| `scripts/task-close-runner.sh` | shell/Python | close-task 重试、退避、失败转 blocked |
| `scripts/task-board-sync.py` | 已有 | 继续负责 dashboard sync |
| `scripts/task-watcher.sh` | shell | 主循环、锁、调度上述模块 |

### 4.3 主循环目标形态

```text
for task in active_tasks:
  reducer_output = task-state-reducer.py --task-dir <dir>
  apply_fact_patches(reducer_output.patches)
  for action in reducer_output.actions:
    task-action-runner.py action
  sync_task_board_if_changed(task)

for idle_agent in agents:
  task-pool-router.py --next --agent <agent>
  task-queue-router.py --next-review/qa --agent <agent>
```

### 4.4 幂等、sentinel 与恢复边界

所有通知和自动动作必须有稳定 key：

```text
<task_id>:<action_type>:<artifact_mtime_or_hash>:<gate_state>:<target_actor>:<resume_round>
```

示例：
- `修复A:notify_review_pending:result_sha:review_pending:review-1:0`
- `修复A:nudge_qa_queue:gate_ts:qa_pending:qa-1:0`
- `修复A:auto_close:verify_sha:qa_pending:watcher:0`
- `修复A:artifact_invalid:result_sha:working:pm-chief:1`

规则：
- 同一 key 只能执行一次。
- artifact 内容变化、gate 变化、或 `resume_round` 增加后才生成新 key。
- 自动 close 失败最多 3 次，指数退避；超过后进入 `blocked`。
- 队列等待类通知必须有冷却时间，不允许每轮扫描写 PM。
- `blocked -> dispatched` 恢复后，旧 sentinel 如果早于最近一次 resume transition，必须视为失效。
- `result.json` 状态为空、非法、JSON 损坏或缺必填字段时，归类为 `artifact_invalid`，只发一次降级告警，并保持任务在可诊断状态；不得每轮都提醒 PM。

### 4.5 通知三级分流

通知体系应分 3 级，避免所有事件都打到 PM 主通道。

| 级别 | 名称 | 触发条件 | 通道 | 要求 |
|---|---|---|---|---|
| L1 | 低噪声默认通知 | gate 真变化、任务真进入新阶段、claim 成功、close 成功 | ChatHub system + dashboard timeline | 默认不打断 PM；同一 gate/action 只通知一次 |
| L2 | 降级告警 | invalid artifact、reopen with stale state、pool timeout、auto-close retry、dispatch resend | PM Inbox + ChatHub degraded；必要时 Feishu 摘要 | 一次性或冷却通知，必须带 recommended_action |
| L3 | 人工强介入 | `blocked`、生产相关故障、反复执行中断、auto-close 连续失败、critical 任务无人接 | PM Inbox 置顶 + send-to-agent/Feishu/PM 直达 + ChatHub 记录 | 必须明确 owner、下一步、是否需要林总工决策 |

#### 4.5.1 典型事件归类

| 事件 | 通知级别 | 说明 |
|---|---|---|
| `result.status=success` 进入 review/QA | L1 | 正常阶段推进 |
| `review.json.status=approve` | L1 | 正常 gate 推进 |
| `verify.json.status=pass` 并 close 成功 | L1 | 完成通知只发一次 |
| `result.json.status` 为空/非法 | L2 `artifact_invalid` | 一次性通知 PM/执行者补产物，不反复刷屏 |
| `review.json` 非法或缺必填字段 | L2 `artifact_invalid` | 停在 review_pending 或 blocked，给出修复动作 |
| `blocked -> dispatched` 但旧 ack/result 未清 | L2 `reopen_with_stale_state` | watcher 兼容保护，一次性提示应走 resume-task |
| pooled 超时无人认领 | L2 `pool_timeout` | 提示 PM 转派/拆小/提高优先级 |
| 任务进入 blocked | L3 | PM 必须仲裁 |
| 生产故障或部署异常 | L3 | 必须强触达，不只写 ChatHub |
| 同一任务反复 working timeout | L3 | 说明执行链路异常，需要人工介入 |

### 4.6 拆分实施顺序

不能一次性推倒重写。建议按保守顺序：

1. **先抽 artifact parser**：保持 watcher 行为不变，只把解析逻辑集中。
2. **再加 reducer fixture**：用当前任务样例锁定状态归约。
3. **再替换 result/review/verify 分支**：watcher 调 reducer 输出。
4. **最后拆 pool/review/QA router**：把队列选择从 watcher 中迁出。

---

## 5. 产物契约统一

### 5.1 统一原则

1. 所有自动流转只消费机器 JSON。
2. Markdown 只做人读解释。
3. legacy 字段由统一 parser 映射，不允许多个脚本各自解析。
4. JSON 非法、缺字段、枚举未知，默认 fail-closed，但通知必须归一为一次性 `artifact_invalid`，不得每轮刷 PM。
5. parser 输出必须包含 `normalized_status`、`is_current_round`、`artifact_hash`、`errors[]`、`warnings[]`，让 watcher 能区分“新产物非法”和“旧轮次残留”。

### 5.2 `ack.json`

```json
{
  "schema_version": 1,
  "task_id": "任务ID",
  "agent": "dev-1",
  "status": "acknowledged",
  "acked_at": "2026-05-09T10:00:00+08:00",
  "summary": "已收到任务并开始执行"
}
```

兼容：
- `agent_id` -> `agent`
- `acknowledged_at` -> `acked_at`

### 5.3 `claim.json`

```json
{
  "schema_version": 1,
  "task_id": "任务ID",
  "agent": "dev-1",
  "claimed_at": "2026-05-09T10:00:00+08:00",
  "reason": "当前空闲，依赖满足，write_scope 无冲突"
}
```

含义：
- `claim.json` 是认领请求/记录。
- `task.status=dispatched + claimed_by` 才是认领成功事实。
- `ack.json` 才是正式进入工作事实。

### 5.4 `result.json`

```json
{
  "schema_version": 1,
  "task_id": "任务ID",
  "agent": "dev-1",
  "status": "success",
  "summary": "完成了核心改动",
  "changed_files": ["path/to/file"],
  "checks": [
    {"name": "pytest", "status": "pass", "evidence": "..."}
  ],
  "risks": [],
  "follow_up_items": [],
  "finished_at": "2026-05-09T10:30:00+08:00"
}
```

枚举：
- `success`：执行成功，可进入 review/QA/PM gate。
- `failed`：执行失败但非外部阻塞，进入 blocked。
- `blocked`：依赖/授权/环境等阻塞，进入 blocked。

兼容：
- legacy `done` 在 parser 中映射为 `success`。
- legacy `files_modified` 映射为 `changed_files`。

非法处理：
- `status` 为空、缺失、拼写未知、JSON 损坏、`task_id/agent` 不匹配，都输出 `artifact_invalid`。
- `artifact_invalid` 不应让 watcher 反复走普通 result route；只发一次 L2 降级告警，提示执行者修正 `result.json`。
- 如果该 `result.json` 早于最近一次 `resume-task`，parser 应标记 `is_current_round=false`，watcher 必须忽略它。

非阻塞后续项：
- `follow_up_items[]` 用于记录执行者在完成任务后发现的可优化项、技术债、观测改进或体验增强。
- `follow_up_items[]` 不影响本任务 gate，不得被 watcher 解释为 `blocked` / `request_changes`。
- PM 可在验收阶段选择忽略、合并到既有任务，或转成 `task_type=optimization` 的新任务进入任务池。

### 5.5 `review.json`

```json
{
  "schema_version": 1,
  "task_id": "任务ID",
  "reviewer": "review-1",
  "status": "approve",
  "summary": "审查通过，未发现阻塞问题",
  "blocking_findings": [],
  "non_blocking_findings": [],
  "files_reviewed": ["path/to/file"],
  "recommended_next_action": "qa",
  "reviewed_at": "2026-05-09T10:50:00+08:00"
}
```

枚举：
- `approve`：允许进入 QA 或 PM 收口。
- `request_changes`：进入 `blocked + review_rejected`。
- `blocked`：审查无法完成，需要 PM/arch 仲裁。

复杂审查：
- 标准审查：`review.json`。
- 架构双审：`design-review.json`。
- gate 取更严格结论：任一 `request_changes/blocked` 即阻断。

### 5.6 `verify.json`

```json
{
  "schema_version": 1,
  "task_id": "任务ID",
  "tester": "qa-1",
  "status": "pass",
  "summary": "关键路径验证通过",
  "checks": [
    {"name": "manual_smoke", "status": "pass", "evidence": "..."}
  ],
  "evidence": ["日志路径或截图路径"],
  "risks": [],
  "non_blocking_findings": [],
  "verified_at": "2026-05-09T11:10:00+08:00"
}
```

枚举：
- `pass`：允许 close。
- `fail`：进入 `blocked + qa_failed`。
- `blocked`：验证无法完成，需要 PM/arch/owner 仲裁。

兼容：
- legacy `ok=true` / `pass=true` 由 parser 映射为 `pass`。
- legacy `ok=false` / `pass=false` 映射为 `fail`。

### 5.7 Markdown 过渡策略

| 阶段 | watcher / close-task 行为 |
|---|---|
| 过渡期 1 | 优先读 JSON；JSON 缺失时允许解析 Markdown fallback，并写 warning |
| 过渡期 2 | 新任务必须有 JSON；Markdown fallback 仅用于历史任务 |
| 目标态 | watcher / close-task 不再从 Markdown 判定机器状态 |

建议设置截止条件：
- 新建任务自本方案实施后必须产出 `review.json`。
- 历史任务保留 fallback 30 天或直到归档。

---

## 6. 任务池视图补全

### 6.1 任务池事实源

任务池事实源仍是 `task.json`：

```json
{
  "status": "pooled",
  "claim_policy": "pull",
  "claim_scope": ["dev-1", "dev-2"],
  "claim_max_concurrency": 1,
  "priority": "high",
  "depends_on": [],
  "write_scope": ["/Users/linsuchang/Desktop/work/chiralium/frontend"],
  "pool_entered_at": "2026-05-09T10:00:00+08:00",
  "pool_timeout_minutes": 120
}
```

### 6.2 必须补的 CLI 视图

#### `scripts/list-pool.sh`

建议支持：

```bash
scripts/list-pool.sh
scripts/list-pool.sh --agent dev-1
scripts/list-pool.sh --json
scripts/list-pool.sh --blocked-only
scripts/list-pool.sh --explain <task-id> --agent dev-1
```

输出字段：
- task_id / title / priority
- pool_wait_minutes
- claim_scope
- dependencies_state
- write_scope_conflict
- suggested_agent
- blocked_reason
- next_action

示例人读输出：

```text
任务池 | 可认领 3 | 阻塞 2 | 超时 1

[high] 修复古琴公开生成限流与输出并发安全
  scope: dev-1, dev-2
  wait: 35m
  dev-1: 可认领
  dev-2: 不可认领（已有 working 任务）
  next: dev-1 空闲后自动续推或手动 claim
```

### 6.3 Dashboard 任务池页

在现有 dashboard 上增加“任务池”视图：

| 区块 | 内容 |
|---|---|
| 池总览 | pooled 数、超时数、按 priority 分布、无人可接数 |
| Agent 可接任务 | 每个 agent 当前可接 TOP N |
| 阻塞原因 | 依赖未完成、write_scope 冲突、WIP 超限、claim_scope 为空 |
| 等待时间 | pool_entered_at 到现在的等待时长 |
| 续推动作 | watcher 最近一次 nudge/claim/失败原因 |

### 6.4 PM Inbox / 待 PM 处理总视图

PM Inbox 是 PM 的统一待办入口，解决“降噪后不知道该看哪、刷屏时不知道哪个还没处理”的问题。它只读聚合，不新增任务状态，也不允许绕过脚本直接改 `task.json`。

#### 6.4.1 进入 Inbox 的事项

| reason_type | 触发事实 | 默认级别 | 推荐动作 |
|---|---|---|---|
| `blocked` | `task.status=blocked`，或 `merge_gate_state=blocked/review_rejected/qa_failed` | L3 | PM 仲裁：转派、拆小、补输入、恢复或取消 |
| `timeout` | `working_timeout`、`dispatch_ack_timeout`、`pool_timeout`、review/QA queue timeout、auto-close retry exhausted | L2/L3 | 续推、转派、提高优先级、释放 WIP 或拆分任务 |
| `acceptance` | `merge_gate_state=pm_acceptance_pending`，或 review/QA 全部通过但仍需 owner/PM 最终收口 | L2 | PM 验收/close，或要求补证据 |
| `artifact_invalid` | `ack/result/review/verify/claim` JSON 损坏、缺必填字段、枚举未知、task_id/agent 不匹配 | L2 | 要求对应 agent 修正机器产物；必要时 blocked |
| `stale_resume` | 恢复后旧 ack/result/sentinel 仍可能影响当前轮次 | L2 | 使用 `resume-task.sh` 正规恢复，或归档旧工件 |
| `critical_decision` | prod/critical/break-glass/安全风险等需要 PM 或林总工决策 | L3 | PM 直达并判断是否飞书通知林总工 |

#### 6.4.2 Inbox item 结构

Inbox item 必须能从 L1/L3 重建，推荐由 `task-state-reducer.py` 输出 `attention_items[]`，或由 `task-inbox.py` 聚合生成：

```json
{
  "item_id": "任务ID:artifact_invalid:result:sha256:resume_round",
  "task_id": "任务ID",
  "title": "任务标题",
  "reason_type": "artifact_invalid",
  "severity": "degraded",
  "priority": "high",
  "source": {"layer": "L1", "path": "tasks/<task-id>/result.json", "hash": "..."},
  "summary": "result.json.status 为空，无法推进 gate",
  "recommended_action": "通知执行 agent 修正 result.json，或由 PM 将任务置为 blocked 并说明原因",
  "owner": "pm-chief",
  "first_seen_at": "2026-05-09T12:00:00+08:00",
  "last_seen_at": "2026-05-09T12:10:00+08:00",
  "age_minutes": 10,
  "links": {"task_dir": "tasks/<task-id>", "timeline": "chat/tasks/<task-id>.jsonl"}
}
```

稳定 key 规则：`<task_id>:<reason_type>:<source_artifact_or_gate>:<artifact_hash_or_gate_ts>:<resume_round>`。同一 key 只通知一次，但在 Inbox 中持续可见，直到底层事实变化后自动消失。

#### 6.4.3 CLI 与 dashboard 形态

建议新增：

```bash
scripts/list-pm-inbox.sh
scripts/list-pm-inbox.sh --json
scripts/list-pm-inbox.sh --reason blocked,timeout,acceptance,artifact_invalid
scripts/list-pm-inbox.sh --severity L3
scripts/list-pm-inbox.sh --explain <task-id>
```

人读输出按 `severity -> priority -> age_minutes` 排序：

```text
PM Inbox | L3 2 | L2 5 | acceptance 3 | oldest 4h20m

[L3][blocked][high] 修复支付回调幂等问题  age=47m
  reason: qa_failed，verify.json 失败 2 项
  next: PM 决定退回 dev-1、拆 rework 任务，或取消本轮上线

[L2][artifact_invalid][normal] 更新商品导入脚本  age=12m
  reason: result.json.status=completed，不在 success/failed/blocked 枚举
  next: 要求 dev-2 修正 result.json；通知只发一次
```

Dashboard 增加 PM Inbox 卡片/页面：

| 区块 | 内容 |
|---|---|
| 总览 | L3/L2/acceptance/invalid artifact 数量、最老待处理时长 |
| 分组 | blocked、timeout、acceptance、artifact_invalid、critical_decision |
| 任务行 | task_id/title/priority/owner/current status/gate/age/recommended_action |
| 跳转 | 单任务 timeline、任务目录、相关 artifact、推荐脚本命令 |

#### 6.4.4 操作边界

- Inbox 不保存独立 `resolved` 状态；事项是否消失由底层事实决定。
- 如果 UI 需要“处理”按钮，只能调用标准脚本：`resume-task.sh`、`dispatch-task.sh`、`close-task.sh`、`archive-task.sh`、或创建 rework 任务；禁止 dashboard 直接写 `task.json`。
- `artifact_invalid`、`timeout` 等 L2 事项应进入 Inbox 并只通知一次；PM 打开 Inbox 时仍能看到，不依赖刷屏提醒。
- L3 事项既进入 Inbox，也必须强触达 PM；critical/prod 按现有规则必要时飞书通知林总工。

#### 6.4.5 Optimization Backlog / 优化建议池（非阻塞优化流程）

PM Inbox 只承载“需要 PM 处理，否则当前任务/队列会卡住”的事项。审查或开发完成后提出的体验优化、重构建议、观测增强、性能余量、测试补强等，如果不影响当前任务验收，应进入独立的 **Optimization Backlog / 优化建议池**，避免把“必须处理”和“可择期优化”混在一起。

##### 进入优化建议池的来源

| 来源 artifact | 推荐字段 | 典型内容 | 是否影响当前 gate |
|---|---|---|---|
| `result.json` | `follow_up_items[]` | 开发者完成后发现的技术债、可简化点、后续性能/体验优化 | 否 |
| `review.json` / `design-review.json` | `non_blocking_findings[]` | reviewer 认为可优化但不构成阻塞的问题 | 否 |
| `verify.json` | `non_blocking_findings[]` | QA 发现的体验瑕疵、测试补强建议、边界场景观察 | 否 |
| `review-summary.md` | “建议项 / 后续优化”段落 | owner 轨道中 PM 汇总出的非阻塞建议 | 否 |

建议项结构推荐：

```json
{
  "id": "opt-001",
  "title": "补充复杂审查双 JSON 场景的 dashboard 提示",
  "summary": "当前 CLI 已能识别，但 dashboard 未突出缺失的 design-review.json。",
  "category": "ux|performance|test|refactor|observability|docs",
  "priority_hint": "low|medium|high",
  "source_artifact": "review.json",
  "source_task_id": "任务ID",
  "suggested_owner": "pm-chief",
  "suggested_scope": ["dashboard/static/js/dashboard.js"],
  "evidence": "review.json#non_blocking_findings[0]"
}
```

##### PM 处理流程

1. 当前任务 gate 仍按 `status`、`blocking_findings`、`verify.status` 等硬事实推进；非阻塞建议不得阻断 `approve/pass/pm_acceptance_pending`。
2. PM 在验收或周度整理时打开优化建议池，按业务价值、风险和上下游时机做三选一：
   - `ignore`：明确不做，可在源任务 timeline 留一句说明。
   - `merge`：合并到已有 task / epic，保留 `source_task_id`。
   - `promote`：转成正式任务，`task_type=optimization`，默认 `status=pooled`，进入任务池等待认领。
3. 转成任务时必须保留来源链路：`source_task_id`、`source_artifact`、原建议摘要、推荐范围和验收标准。
4. 优化建议池默认只读，不保存独立 resolved 状态；是否已转任务可通过 `source_task_id` / `source_suggestion_id` 反查。

##### 与 PM Inbox 的边界

- `blocking_findings[]` 非空且 `status=request_changes/blocked`：进入 PM Inbox，属于必须处理。
- `non_blocking_findings[]` 或 `follow_up_items[]`：进入 Optimization Backlog，属于择期优化。
- 同一条建议如果后来被 PM 提升为 P0/P1 修复任务，才进入正常 task lifecycle；提升前不参与 WIP gate、超时告警和自动续推。

### 6.5 ChatHub 事件补全

不再把入池伪装成 `announce`。新增或约定 system event：

| 事件 | channel | type | 含义 |
|---|---|---|---|
| 入池 | `watcher` 或 `dispatch` | `pool_entered` | 任务已进入 pooled |
| 认领成功 | `dispatch` | `claim_confirmed` | pooled -> dispatched |
| 认领失败 | `watcher` | `claim_rejected` | 不满足条件 |
| 续推提醒 | `direct_nudge` | `nudge` | 已提醒候选 agent |
| 池中超时 | `watcher` | `pool_timeout` | 超过 pool_timeout_minutes |

如果短期不扩 `send-chat.sh` type 枚举，也可先用：
- `type=notify`
- `event_class=system_notice`
- `source_name=task-pool`
- `msg` 中带标准前缀

但中期应扩充 type，避免所有任务池事件都混成 `notify`。

### 6.6 当前入池公告矛盾修复

必须二选一：

方案 A：允许 `announce` 支持 `pooled`
- 优点：改动小。
- 缺点：`announce` 语义变宽，容易混淆“已派发”和“待认领”。

方案 B：新增 `pool`/`pool_entered` 事件
- 优点：语义清晰，适合任务池视图。
- 缺点：要改 `send-chat.sh / lint-chat.sh / ingest`。

推荐：**短期 A，P1 改 B**。

短期立即修：
- `send-chat.sh announce` 允许 `pooled`，或 `pool-task.sh` 不再调用 `announce`。
- `pool-task.sh` 不得吞掉 ChatHub 写入失败，至少要写 log 或 system degraded event。

### 6.7 Dashboard / 看板信息架构优化

当前 dashboard 已经有 Kanban、甘特图、Agent 统计、分析、任务池、PM Inbox 等入口，但整体仍偏“数据展示”，没有充分服务 PM 的日常控制动作；甘特图也因使用相对小时轴、任务名 Y 轴和多段 custom series，导致视觉拥挤且难以定位瓶颈。看板应升级为 **PM Cockpit + 队列治理 + 生命周期分析 + Agent 负载分析**。

#### 6.7.1 首页改为 PM Cockpit / 今日控制塔

首页第一屏不应先展示所有任务卡片，而应先回答 PM 最关心的三个问题：

1. 今天必须处理什么？
2. 哪个队列正在变慢？
3. 哪些 agent 空闲或过载？

推荐首屏结构：

| 区块 | 内容 | 数据来源 |
|---|---|---|
| 顶部 KPI | L3/L2 待处理数、blocked 数、timeout 数、pooled 数、review/QA backlog、今日新增/完成、返工率 | `task-inbox.py`、`task-pool-view.py`、`task_metrics_daily`、`task_stage_durations` |
| PM Inbox 摘要 | L3 必处理、L2 降级告警、待验收事项，按 severity/priority/age 排序 | `task-inbox.py` |
| 队列健康 | pooled、review_pending、qa_pending、pm_acceptance_pending 的数量、最老等待、超 SLA 数 | `task.json` + `merge_gate_state` + stage durations |
| Agent 负载 | 每个 agent 当前 WIP、可接任务数、今日完成、平均执行耗时、是否被 WIP gate 限制 | `tasks` + `task-pool-view.py` + `agent_metrics_daily` |

控制塔只读，不直接改 `task.json`；操作层先提供“复制推荐脚本命令”，例如 `resume-task.sh`、`dispatch-task.sh`、`pool-task.sh`、`close-task.sh`。

#### 6.7.2 Kanban 改为 status + gate 双层视图

当前 Kanban 的 `pending / working / ready_for_merge / blocked / done` 对 PM 来说太粗，`ready_for_merge` 内部实际包含 review、QA、PM acceptance 三种完全不同的等待。建议列改为：

```text
待定义/待派发
待认领
执行中
待审查
待 QA
待 PM 收口
阻塞/返工
已完成
```

映射规则：

| 列 | 触发事实 |
|---|---|
| 待定义/待派发 | `status=pending` 且未入池 |
| 待认领 | `status=pooled` |
| 执行中 | `status=dispatched/working` |
| 待审查 | `status=ready_for_merge` 且 `merge_gate_state=review_pending` |
| 待 QA | `status=ready_for_merge` 且 `merge_gate_state=qa_pending` |
| 待 PM 收口 | `merge_gate_state=pm_acceptance_pending` |
| 阻塞/返工 | `status=blocked` 或 `merge_gate_state=review_rejected/qa_failed/blocked` |
| 已完成 | `status=done/archived/merged` |

任务卡片应从“任务名 + agent”增强为“当前为什么在这里”：

- 当前阶段停留时长 / 是否超 SLA。
- priority、assigned_agent、reviewer、owner_pm。
- `merge_gate_state`、`review_level`、`rework_reason`。
- 最近一次 system event / artifact 结论。
- `recommended_action`（来自 Inbox、pool view 或 reducer actions）。

#### 6.7.3 甘特图重构：从“任务条形图”改为三类时间视图

##### 当前问题

- X 轴是相对最早任务的小时数，不是自然时间，PM 难以关联“今天/昨天/本周”。
- Y 轴任务名过长且截断，任务多时难以阅读。
- 阶段条分散在多个 series，颜色多但含义不突出。
- 不突出等待、执行、审查、QA、blocked 哪个阶段最慢。

##### 视图 A：任务生命周期泳道图

用真实时间轴展示每个任务的阶段：

```text
任务 A | 创建 ─ 等待派发 ─ 执行 ─ review ─ QA ─ PM收口
任务 B |       创建 ─ pooled等待 ─ 执行 ─ blocked
任务 C |              创建 ─ 执行 ─ PM收口
```

颜色建议：

| 阶段 | 颜色 |
|---|---|
| 等待/排队 | 灰色 |
| pooled/认领等待 | 青色 |
| 执行 | 蓝色 |
| review | 紫色 |
| QA | 橙色 |
| PM acceptance | 绿色 |
| blocked/failed | 红色 |
| 超 SLA 风险 | 黄色描边或斜纹 |

数据来源：`task_stage_durations` + `tasks.created_at/dispatched_at/ack_at/completed_at/review_completed_at/verify_completed_at/current_status_at`。X 轴使用真实日期时间，并保留今天/近三天/近七天/自定义筛选。

##### 视图 B：Agent 负载泳道图

按 agent 分行展示任务占用：

```text
dev-1     | 任务A执行 | 空闲 | 任务D执行
dev-2     | 任务B执行 | 任务E执行
review-1  | review A | 等待 | review D
qa-1      | QA A | QA D
```

用途：
- 看谁空闲、谁过载。
- 看 review/QA 是否成为单线程瓶颈。
- 验证自动续推是否真的减少空闲时间。
- 与 WIP gate 联动展示“不可接原因”。

##### 视图 C：阶段耗时瀑布图 / 瓶颈条形图

按任务或按队列展示阶段耗时：

```text
创建→派发      10m
派发→ACK       3m
ACK→结果       48m
结果→审查      90m
审查→QA        15m
QA→收口        20m
```

这比传统甘特更适合回答“慢在哪里”。默认展示 Top N 慢任务和整体 P50/P75/P90。

#### 6.7.4 数据分析增强

已有数据可以进一步分析，不必先引入新事实源。推荐新增以下只读分析：

| 分析 | 指标 | 用途 |
|---|---|---|
| 阶段瓶颈 | 各阶段 P50/P75/P90/max，平均值只作辅助 | 找出系统性慢点，避免被少量极端值误导 |
| 队列老化 | pooled/review_pending/qa_pending/pm_acceptance_pending 的 0-30m、30-60m、1-2h、2-6h、6h+ 分桶 | 判断哪些队列正在积压 |
| Agent 负载 | 当前 WIP、今日完成、平均 ACK 延迟、平均执行耗时、claim 成功/失败、空闲时长 | 判断是否需要转派或调整 WIP |
| 质量指标 | review request_changes 率、QA fail 率、artifact_invalid 率、resume/rework 率、complex review 缺件率 | 判断返工来源和产物契约健康度 |
| 沟通成本 | 每任务沟通条数、PM mention 数、unanswered question 数、system event 噪音趋势 | 衡量 PM 是否真正减负 |
| 优化建议 | `follow_up_items[]`、`non_blocking_findings[]` 数量、已 promote 比例 | 管理非阻塞优化而不污染 PM Inbox |

#### 6.7.5 可补充的数据字段

为了让看板从“展示”升级到“治理”，后续可补充：

| 类别 | 字段 | 作用 |
|---|---|---|
| SLA | `sla_deadline`、`review_deadline`、`qa_deadline` | 风险预警和超时排序 |
| 业务优先级 | `business_priority`、`risk_level`、`source_request_id` | 区分技术 priority 与业务紧急度 |
| 工作量估计 | `complexity_estimate`、`expected_effort_minutes` | 预测任务是否会拖慢队列 |
| 认领快照 | claim rejected reason、candidate agents snapshot、nudge 时间 | 分析为什么池中任务没人接 |
| 质量分类 | `request_changes_reason_type`、`qa_fail_reason_type` | 区分需求遗漏、实现缺陷、测试环境、产物格式等原因 |
| 优化建议 | `source_suggestion_id`、`source_artifact`、`promoted_task_id` | 追踪非阻塞建议是否被转任务 |

#### 6.7.6 Dashboard 操作边界

- Dashboard 短期只读；实际状态变更仍走标准脚本。
- 允许展示“推荐命令”和“复制命令”按钮，但不直接写 `task.json`。
- 若中期增加按钮操作，也必须调用脚本 API，而不是在 dashboard 后端绕过脚本写状态。
- Dashboard 的聚合项应可从 `tasks/`、`transitions.jsonl`、artifact JSON、ChatHub events 重建，避免出现第五套事实源。

---

## 7. WIP 与自动续推策略

### 7.1 WIP 配置

将 WIP 上限进入 `config.json`：

```json
{
  "wip_limits": {
    "pm-chief": 5,
    "dev": 1,
    "reviewer": 2,
    "qa": 2,
    "architect": 2
  }
}
```

### 7.2 WIP 执行点

| 场景 | 卡口 |
|---|---|
| PM 定向派发 | `dispatch-task.sh` |
| agent 主动认领 | `claim-task.sh` |
| watcher 自动续推 | `task-pool-router.py` |
| review/QA 队列续推 | `task-queue-router.py` |

### 7.3 自动续推规则

agent 当前主线满足以下之一，才允许续推下一条 execution 任务：
- 当前任务 `done`；
- 当前任务 `ready_for_merge` 且已进入 review/QA 队列；
- 当前任务 `blocked/cancelled` 且 PM 已裁决可释放 WIP。

禁止：
- agent 仍有 `working` 主线时继续派 execution。
- 下游 QA/review 队列占用被误算成 dev execution WIP。
- 只凭 tmux pane idle 判定可派发；必须结合 task facts。

---

## 8. 实施优先级与里程碑

### 8.1 P0：最小契约统一与噪音止血（1.5 - 2.5 天）

> PM 反馈成立：P0 不应只修 pooled 公告和 list-pool。只要 `result/review/verify` 口径不统一，PM 仍要手动判断结论。因此 P0 必须前移 artifact parser、`result.status=success`、`review.json` 最小闭环和 invalid artifact 一次性告警。

目标：先让 watcher 对“当前任务到底完成、驳回、验证通过还是产物非法”有统一判断，减少 PM 盯状态与人工纠偏。

| 编号 | 任务 | 改动范围 | 验收 |
|---|---|---|---|
| P0-1 | 最小 artifact parser | `scripts/lib/task_artifacts.py` 或等价模块 | `ack/result/review/verify/claim` 可解析；legacy `done/ok/pass/acknowledged_at` 有统一映射；非法产物输出 `artifact_invalid` |
| P0-2 | watcher 接受新版 `result.status=success` | watcher + parser | `success` 与 legacy `done` 都能进入 `ready_for_merge`；空/非法 status 只触发一次 L2 `artifact_invalid` |
| P0-3 | `review.json` 最小接入 | review 指南、watcher、close-task 兼容路径 | 新任务优先用 `review.json` 判定；Markdown 仅 fallback 并带 warning |
| P0-4 | 通知三级分流与 sentinel 降噪 | watcher/notifier sentinel | L1/L2/L3 分类生效；同一 artifact_invalid/gate waiting 不反复刷 PM |
| P0-5 | `resume-task` 恢复语义设计与最小实现 | `resume-task.sh` 或 watcher 兼容规则 | blocked 恢复后旧 ack/result/sentinel 不再影响新一轮执行 |
| P0-6 | 修复入池可见性矛盾 | `pool-task.sh`、`send-chat.sh`、`lint-chat.sh` 可选 | `status=pooled` 任务能稳定产生入池可见事件，失败不静默 |
| P0-7 | PM Inbox 最小只读入口 | `task-inbox.py` / `list-pm-inbox.sh` / reducer `attention_items[]` | PM 可一条命令看到 blocked、timeout、acceptance、artifact_invalid，并获得 recommended_action |

### 8.2 P1：任务池可视化与 reducer fixture（1.5 - 2.5 天）

目标：在 P0 产物契约稳定后，让任务池、PM Inbox 与状态归约可观测、可回归测试。

| 编号 | 任务 | 改动范围 | 验收 |
|---|---|---|---|
| P1-1 | 增加只读任务池 CLI | `list-pool.sh` | PM/agent 可看 pooled、可接、不可接原因、pool timeout |
| P1-2 | reducer fixture | `tests/fixtures/task-state/` | result/review/verify/resume 任意到达顺序可幂等收敛 |
| P1-3 | close-task 只信统一 parser | `close-task.sh` / parser | JSON pass 才 close；非法 JSON fail-closed 且一次性通知 |
| P1-4 | 自动 close 重试退避 | watcher/close runner | close 失败最多 3 次，之后 blocked，不刷屏 |
| P1-5 | reviewer/QA 输出模板更新 | agent 指南/模板 | review-1/qa-1 默认输出机器 JSON，PM 不重新解释 Markdown |
| P1-6 | Dashboard PM Inbox 卡片/页面 | dashboard ingest/query/frontend | dashboard 可按 reason/severity/age 聚合待 PM 处理事项，且不直接写任务事实 |
| P1-7 | 优化建议池只读入口 | parser / `list-optimization-backlog.sh` / dashboard 可选 | 汇总 `follow_up_items[]`、`non_blocking_findings[]`，PM 可筛选、忽略、合并或提升为 `task_type=optimization` 的正式任务 |
| P1-8 | PM Cockpit 首屏重排 | dashboard frontend/query | 首页展示 L3/L2、blocked、timeout、pooled、review/QA backlog、今日新增/完成、返工率与最老等待，不再让 PM 先翻任务卡片 |

### 8.3 P2：watcher 拆分与任务池视图（3 - 5 天）

目标：把任务池、review/QA 队列、通知从 watcher 主体中拆出来，并让 dashboard 从“任务展示”升级为“队列治理”。

| 编号 | 任务 | 改动范围 | 验收 |
|---|---|---|---|
| P2-1 | 拆 `task-state-reducer.py` | watcher + reducer | watcher 主逻辑不再内嵌 result/review/verify 状态机 |
| P2-2 | 拆 `task-pool-router.py` | pool/claim/list | 自动续推与手动 list 使用同一候选选择逻辑 |
| P2-3 | 拆 `task-queue-router.py` | review/QA 队列 | review/QA 可见队列与自动续推一致 |
| P2-4 | Dashboard 任务池页 | dashboard ingest/query/frontend | 可按 agent/priority/阻塞原因看任务池 |
| P2-5 | WIP gate | config + claim/dispatch/router | 超 WIP 不派发，给出等待/转派建议 |
| P2-6 | Kanban status+gate 双层列 | dashboard frontend/query | `ready_for_merge` 拆成待审查、待 QA、待 PM 收口；卡片展示阶段停留时长、gate、最近事件与 recommended_action |
| P2-7 | 甘特图改真实时间生命周期泳道 | dashboard frontend/query | X 轴用真实时间；任务阶段按等待/pooled/执行/review/QA/PM收口/blocked 着色；支持今天/近三天/近七天/自定义筛选 |

### 8.4 P3：清理 legacy 与分析增强（3 - 5 天）

目标：从“能跑”进入“低人工仲裁、可分析”。

| 编号 | 任务 | 改动范围 | 验收 |
|---|---|---|---|
| P3-1 | 停止新任务 Markdown fallback | watcher/close-task | 新任务缺 review.json 不自动通过 |
| P3-2 | 归档 active scan | archive-task + watcher scan | watcher 默认只扫 active；历史任务走索引 |
| P3-3 | 任务池超时升级 | pool router + notifier | pooled 超时产生 degraded event 并提示 PM 转派 |
| P3-4 | 协作指标 | dashboard metrics | 可看 pool wait、claim latency、review/QA wait、rework rate |
| P3-5 | 删除重复解析逻辑 | watcher/close/dashboard | 解析逻辑只剩统一 parser |
| P3-6 | Agent 负载泳道与阶段耗时瀑布图 | dashboard frontend/query | 可按 agent 看任务占用/空闲；可按任务或阶段看耗时 Top N |
| P3-7 | 瓶颈与质量分析增强 | dashboard metrics/query | 输出阶段 P50/P75/P90/max、队列老化分桶、request_changes/QA fail/artifact_invalid/rework/沟通成本指标 |

---

## 9. 迁移策略

### 9.1 兼容原则

- 历史任务不强制补 `review.json`。
- 历史 `result.status=done` 继续兼容，但统一 parser 输出为 `success`。
- 历史 `acknowledged_at` 继续兼容，但统一 parser 输出为 `acked_at`。
- 历史 `verify.ok/pass` 继续兼容，但统一 parser 输出 `status=pass/fail`。

### 9.2 新任务强制口径

自本方案实施后，新任务必须：
- `result.json.status` 使用 `success/failed/blocked`。
- 需要 review 的任务必须产出 `review.json`。
- 需要 QA 的任务必须产出新版 `verify.json.status`。
- watcher/close-task 对缺 JSON 的新任务 fail-closed。

### 9.3 迁移开关

建议在 `config.json` 增加：

```json
{
  "artifact_contract": {
    "schema_version": 1,
    "legacy_markdown_review_fallback": true,
    "legacy_result_done_mapping": true,
    "new_tasks_require_review_json_after": "2026-05-09T00:00:00+08:00",
    "invalid_artifact_notify_once": true
  },
  "resume_policy": {
    "archive_old_ack_on_resume": true,
    "archive_old_blocked_result_on_resume": true,
    "clear_watcher_sentinels_on_resume": ["result_route", "working_timeout", "resend", "auto_close_retry"],
    "ignore_artifacts_before_last_resume": true
  }
}
```

### 9.4 blocked 恢复迁移策略

- 历史上已经手工从 `blocked` 改回 `dispatched/working` 的任务，watcher 应通过 transitions 判断最近一次恢复时间。
- 若没有标准 resume transition，但发现 `updated_at` 晚于旧 `ack/result`，watcher 可保守触发一次 `reopen_with_stale_state`，提示 PM 使用 `resume-task.sh` 修复。
- 新任务或新恢复动作必须走 `resume-task.sh`，禁止只改 `task.json.status`。

---

## 10. 验收标准

第一阶段完成后，应满足：

1. `pooled` 任务在 ChatHub / dashboard / CLI 中都可见，但任务池事实仍来自 `task.json`。
2. `result.status=success` 能稳定推进到 `ready_for_merge`，legacy `done` 仍兼容。
3. `result.json.status` 为空/非法时，只触发一次 L2 `artifact_invalid`，不会每轮提醒 PM。
4. 新 review 任务能通过 `review.json` 推进 gate。
5. `review.md` 不再是新任务自动流转的唯一依据。
6. 同一任务同一 gate 不再重复刷 PM，通知可归类为 L1/L2/L3。
7. blocked 任务通过 `resume-task` 恢复后，旧 ack、旧 blocked result、旧 timeout/result_route sentinel 不影响新一轮执行。
8. PM 可通过任务池视图看到：谁可接、为什么不可接、等了多久、下一步是什么。
9. PM 可通过 PM Inbox 看到：blocked、timeout、acceptance、artifact_invalid、stale_resume 等待处理事项，且每项都有来源事实和 recommended_action。
10. PM Inbox 不引入独立状态；底层事实修复后 item 自动消失，dashboard/CLI 不绕过脚本写 `task.json`。
11. watcher 自动 close 有重试上限，失败进入 blocked。
12. watcher 主体职责减少，状态归约可以用 fixture 测试，fixture 覆盖 resume/stale artifact。
13. Dashboard/CLI 都能重建任务池、PM Inbox 与协作时间线，不修改任务事实源。
14. 归档前，watcher 不因历史 done/cancelled 任务持续产生误触发或明显性能负担。
15. Dashboard 首页能作为 PM Cockpit 使用，直接展示待 PM 处理、队列健康、Agent 负载和今日吞吐，而不是只展示任务列表。
16. Kanban 能按 `status + merge_gate_state` 拆分待审查、待 QA、待 PM 收口等真实队列。
17. 甘特图不再使用相对小时轴作为唯一视图，至少提供真实时间生命周期泳道；P3 后补 Agent 负载泳道和阶段耗时瀑布图。
18. 分析页能识别主要瓶颈阶段、队列老化、质量返工和沟通噪音，支持 PM 判断是否需要转派、拆分、提优先级或调整 WIP。

---

## 11. 非目标

短期不做：

- 不把 ChatHub 升级为任务状态事实源。
- 不引入数据库作为任务事实源替代 `tasks/` 文件。
- 不做私聊 `chat/agents/`。
- 不做完全自动 PM 决策。
- 不做生产部署流程改造；生产部署仍按 CI/部署方案单独推进。
- 不物理迁移任务目录到 `tasks/pool/`；短期坚持逻辑任务池。

---

## 12. 与 2026-05-07《Agent团队效率优化待办》的合并评估

已找到林总工提到的文档：

```text
/Users/linsuchang/Desktop/work/design/chiralium-ci/Agent团队效率优化待办.md
原始创建时间：2026-05-07 22:43:20
最近修改时间：2026-05-08 22:19:08
```

评估结论：**可以选择性合并控制面与 PM 工作流部分，不建议整篇合并**。原因是本方案的适用范围是 `/Users/linsuchang/Desktop/work/my-agent-teams` 的 agent 协作控制面；该待办文档还包含 Chiralium CI、生产部署入口、prod preflight、自动回滚等应用项目治理内容，若整篇合并会扩大本方案边界，并与“生产部署流程改造另案处理”的非目标冲突。

已在本方案吸收或对齐的内容：

| 待办文档主题 | 本方案承接位置 | 合并判断 |
|---|---|---|
| P0 先稳 `task-watcher` gate | 3、4、8.1 | 已合并 |
| `result/review/verify` JSON 作为机器真相源 | 5、8.1、10 | 已合并 |
| Markdown 只做人读说明 | 5.7、9.2 | 已合并 |
| PM checklist 脚本化 | 8.1、9.3、13 | 部分合并；具体 `validate-task.sh` 可作为下游任务补充 |
| 全角色 WIP 限制 | 7、8.3、9.3 | 已合并 |
| 任务工件归档与 watcher 扫描收敛 | 8.4、10、非目标边界 | 已纳入 P3 |
| PM 跟踪阻塞、超时、验收、异常产物 | 6.4 PM Inbox | 本次新增合并 |

暂不并入本方案、建议保留在 Chiralium CI/部署方案中的内容：

- 生产部署唯一入口、prod checkout preflight、break-glass runbook。
- CI Phase 1A/1B/1C、deploy gate dry-run、heavy CI、云端 runner。
- 自动回滚设计与生产 smoke 细节。

因此，两份文档的关系建议是：

```text
Agent协作控制面收敛与任务池优化方案.md
  = my-agent-teams 控制面 / watcher / task pool / PM Inbox 的实施基线

Agent团队效率优化待办.md
  = 跨团队效率治理总待办，其中 CI/部署章节继续指向 chiralium-ci 专项方案
```

如后续要真正“合并成一份总纲”，建议采用“总纲 + 专项方案索引”的方式，而不是把 CI/部署细节直接塞进本控制面方案。

---

## 13. 推荐下一步拆任务

建议立即拆 7 个小任务，不要一个大任务全改；顺序以“最小契约统一”优先：

1. **统一 artifact parser 与 result.status 映射（最优先）**
   - 新增 `scripts/lib/task_artifacts.py`
   - watcher/verify/close 逐步调用。
   - `success` 与 legacy `done` 统一归一；非法产物输出 `artifact_invalid`。

2. **接入 review.json 最小闭环**
   - review 输出规范。
   - watcher 优先读 `review.json`，Markdown 仅 fallback。

3. **watcher 通知三级分流与 artifact_invalid 一次性告警**
   - L1/L2/L3 分类。
   - gate waiting sentinel。
   - invalid result/review/verify 只通知一次。

4. **resume-task 恢复语义**
   - blocked 恢复时归档旧 ack / 旧 blocked result。
   - 清理 result_route / working_timeout / resend / auto_close_retry sentinel。
   - watcher 忽略早于最近 resume 的旧 artifact。

5. **修复任务入池可见性与 ChatHub 事件口径**
   - `pool-task.sh` / `send-chat.sh` / `lint-chat.sh`
   - 停止吞掉入池公告失败。

6. **任务池 CLI 视图**
   - `list-pool.sh --agent --json --explain`
   - 先满足 PM/agent 日常使用。

7. **PM Inbox 最小只读入口**
   - `list-pm-inbox.sh --json --reason --severity --explain`
   - 聚合 blocked、timeout、acceptance、artifact_invalid、stale_resume，并给出 recommended_action。

完成以上 7 个任务后，再进入 watcher 模块化拆分、dashboard 任务池页和 dashboard PM Inbox 页面。
