# Chat Hub 架构审查

> 审查时间：2026-05-03  
> 审查对象：
> 1. `design/Chat-Hub-A-Lite-验证使用说明.md`
> 2. `design/Chat-Hub-落地清单.md`
> 3. `design/Chat-Hub-验证复盘模板.md`
> 4. `design/Chat-Hub-验证记录模板.md`
>
> 对照现有实现：`chat/`、`chat/README.md`、`scripts/send-chat.sh`、`scripts/lint-chat.sh`、`scripts/read-chat.sh`、`scripts/pm-chat-check.sh`、`scripts/task-watcher.sh`、`scripts/dispatch-task.sh`、`scripts/send-to-agent.sh`

---

## 一、总体结论

结论：**Chat Hub A-Lite 的方向是对的，且当前实现已经具备最小可用性；但文档体系仍停留在“流程说明”为主，尚未把协议层、系统事件层、验证口径层收紧到足够可扩展的程度。**

具体判断：
- **A-Lite 是否可继续用**：可以
- **协议是否已足够支撑 Phase B/C 演进**：还不够
- **与看板 `communication_events` 的对齐程度**：方向一致，但契约尚未打通
- **当前最大风险**：Chat 文档默认“只做人类消息线程”，而看板方案已经希望 ingest watcher / dispatch / direct nudge / severity；若不先补统一协议，后续会在 system event 映射和统计口径上反复返工。

一句话结论：
> 现在的 A-Lite 适合继续跑验证，但若准备把 Chat Hub 逐步接到看板、通知和状态机周边，就必须先补一层“协议补充文档”，明确 **消息类型、系统事件映射、严重度、去重键、回放排序规则**。

---

## 二、按审查重点逐项结论

## 2.1 Chat Hub A-Lite 协议设计是否健壮

### 2.1.1 当前 A-Lite 协议的优点
从 `send-chat.sh` / `lint-chat.sh` / `chat/README.md` 看，当前协议有几个优点：

1. **边界清晰**  
   chat 不是状态事实源，状态仍认 `tasks/` 工件。这一点在文档和脚本实现上是一致的，避免了“消息驱动状态变更”的早期混乱。

2. **类型集合足够小**  
   当前允许：
   - `text`
   - `task_announce`
   - `task_done`
   - `question`
   - `answer`
   - `decision`

   这对 A-Lite 来说是正确的，复杂度可控。

3. **最小线程语义已经成立**  
   - `thread_id` 自动补齐
   - `answer` 强制 `reply_to`
   - `task thread` 中 `task_id` 与文件名一致

   这些都是后续做任务时间线和问答链路的好基础。

4. **派发前门禁已接入 `task_announce`**  
   `send-chat.sh announce` 会检查：
   - `task.json`
   - `instruction.md`
   - 关键章节不为空且不是占位
   - 任务状态已进入 `dispatched / working / ready_for_merge / blocked`

   这比“先广播再补任务定义”健壮得多。

### 2.1.2 当前协议的不足：缺“协议版本”和“系统事件层”
当前消息 JSON 大致形态是：
- `msg_id`
- `ts`
- `from`
- `to`
- `source_type`
- `type`
- `msg`
- 可选 `task_id / priority / reply_to / thread_id`
- `announce` 自动附带 `task_type / target_environment / review_level / next_action / owner_approval_required`

这个结构对 A-Lite 足够，但若往看板/审计/系统通知扩展，缺少两类关键字段：

#### 缺 1：协议版本
建议增加：
- `schema_version`

原因：
- 未来如果引入 `severity`、`event_class`、`source_msg_id`、`delivery` 等字段，没有版本号会让 ingest 逻辑越来越多 if/else。
- 看板侧 `communication_events` 也需要知道不同阶段消息的兼容口径。

#### 缺 2：系统事件专用字段
当前 `source_type` 虽允许 `system`，但 `send-chat.sh` 实际写死为 `human`。这意味着：
- watcher/dispatch/send-to-agent 事件如果想进入 chat 或 communication_events，当前没有规范入口；
- 文档里提到的 `notify / direct_nudge / 双通道` 仍是流程描述，不是协议事实。

建议为后续演进预留：
- `event_class`: `human_message | system_notice | delivery_event`
- `source_name`: `send-chat | task-watcher | dispatch-task | send-to-agent`
- `source_msg_id` / `source_event_id`

A-Lite 阶段可以先不强制写，但文档应先定义。

### 2.1.3 类型系统目前“够用但偏扁平”
当前类型：`text / task_announce / task_done / question / answer / decision`

问题不在于太少，而在于**语义层次未分层**：
- `question / answer / decision` 是沟通语义
- `task_announce / task_done` 更像任务线程生命周期事件
- 未来看板想接入的 `notify / nudge / dispatch` 是系统事件

如果未来继续复用 `type` 一个字段硬装所有语义，会导致：
- lint 规则越来越复杂
- PM 巡检很难区分“人类讨论”和“系统通知”
- 看板时间线很难分层展示

#### 建议
协议设计上拆成两层概念：
1. `channel` / `thread_kind`：general / task / agent（未来）
2. `type`：保留当前业务语义
3. 新增 `event_class`：
   - `message`
   - `task_marker`
   - `system_notice`
   - `delivery`

A-Lite 当前只实际使用前两类即可。

### 2.1.4 状态流转处理是“克制的正确”，但文档应更明确边界
A-Lite 现在明确：
- `task_done` 不是终态事实源
- chat 不驱动 task 状态

这是正确的。

但文档还应再明确两点：
1. **chat 消息只能作为“协作证据”，不能替代 `ack.json / result.json / verify.json`**；
2. **Phase B 引入 `task_claim` 时，chat 中的 claim 也只能是意图，最终事实仍需回写 task 工件。**

`Chat-Hub-落地清单.md` 已经提到了 B-1 的这个原则，但建议在 A-Lite 文档里就提前说明，否则读者容易误以为 chat 迟早会自然升级成状态机。

---

## 2.2 与看板方案中 communication_events 的对齐程度

### 2.2.1 方向上是一致的
看板方案希望把以下内容 ingest 到 `communication_events`：
- `chat/general/*.jsonl`
- `chat/tasks/*.jsonl`
- `dispatch-task.sh` 派发消息
- `send-to-agent.sh` 强制唤醒事件
- `task-watcher.sh` 通知事件

Chat Hub 文档也多次强调：
- task thread 是讨论入口
- critical 要双通道
- watcher / dispatch / send-to-agent 后续可能接入

所以从产品目标看，两边方向是一致的。

### 2.2.2 但当前只对齐了“人类消息层”，未对齐“系统事件层”
现状是：
- `chat/` 文件里目前只有人类消息（且 `source_type` 实际恒为 `human`）
- 看板方案中的 `communication_events` 已经预设：
  - `channel=watcher / direct_nudge`
  - `event_type=notify`
  - `severity`

这说明：
- **Chat Hub 文档与看板事件模型只完成了 50% 对齐**；
- “human chat thread” 已经有事实源；
- “system event timeline” 还没有统一协议。

### 2.2.3 当前最大缺口：没有“桥接契约”
建议新增一份桥接文档，例如：
- `design/Chat-Hub-事件协议补充.md`

至少定义：

#### A. Chat JSONL 到 communication_events 的映射
- `msg_id -> source_msg_id / event_id`
- `ts -> happened_at`
- `from -> from_actor`
- `to -> to_actor`
- `type -> event_type`
- `msg -> message_text`
- `thread_id -> thread_id`
- `task_id -> task_id`

#### B. 非 chat 系统事件如何进入同一模型
例如：
- `dispatch-task.sh` -> `event_class=system_notice`、`event_type=dispatch`
- `send-to-agent.sh` -> `event_class=delivery`、`event_type=nudge`
- `task-watcher.sh` -> `event_class=system_notice`、`event_type=notify`

#### C. 时间线排序规则
统一：
1. 优先 `happened_at`
2. 无 `happened_at` 用 `observed_at`
3. 同时间戳以稳定 `event_id` 打散

没有这份桥接契约，后续 dashboard 实现会被迫自行猜测。

---

## 2.3 现有实现与文档描述的一致性

### 2.3.1 一致的部分
以下部分文档与代码是一致的：

#### 目录结构
文档说：
- `chat/general/`
- `chat/tasks/`
- A-Lite 不做 `chat/agents/`

实现上也是这样。

#### 发送入口
文档说统一使用：
- `send-chat.sh general`
- `send-chat.sh task`
- `send-chat.sh announce`

实现一致。

#### 协议 lint
文档说：
- 必填字段
- `type/source_type/priority` 枚举
- `answer` 必须 `reply_to`
- `task_announce / task_done / decision` 必须带 `task_id`
- task thread 中 `task_id` 与文件名一致

`lint-chat.sh` 与之基本一致。

#### PM 巡检与轻量读取
文档提到：
- `read-chat.sh`
- `pm-chat-check.sh`

实现也存在，且行为大体符合说明。

### 2.3.2 不一致/未写清的部分

#### 问题 1：文档写了 `source_type`，但实际没有 system 生产路径
`lint-chat.sh` 允许：
- `human`
- `system`

但 `send-chat.sh` 实际固定写：
- `source_type: human`

这会造成文档层面“仿佛已经支持 system”，但真实运行层并没有。  
建议文档明确：
- **A-Lite 当前只有 human 生产路径**；
- `system` 只是为后续扩展预留，不应让人误以为 watcher 事件已接入。

#### 问题 2：文档谈到 critical 双通道，但脚本未形成结构化闭环
文档多次说：
- critical / 生产任务必须同时走 chat + `send-to-agent.sh`

但从当前实现看：
- `send-chat.sh` 不会自动触发 `send-to-agent.sh`
- `send-to-agent.sh` 也不会回写 chat 或统一事件记录

这意味着“双通道”目前仍主要依赖人工流程纪律，而非协议闭环。  
文档应明确：**当前双通道是操作规范，不是自动保证。**

#### 问题 3：`pm-chat-check.sh` 的聚焦规则与文档描述略有偏差
文档说默认聚焦：
- `to=pm-chief`
- `@pm-chief`
- `priority=critical`
- `decision`
- task thread 中 `question / task_done`

脚本里实际上：
- 会把所有带 `task_id` 的 `question` / `task_done` 都视为 actionable
- 不区分是否真的需要 PM 介入

这会在任务 thread 变多后让 PM 巡检噪声偏高。  
建议文档和脚本一起收紧，至少分：
- 默认 actionable（明确需要 PM）
- 扩展观察项（供 `--all` 查看）

#### 问题 4：验证文档尚未反映“announce gate”的实际规则细节
使用说明里说“创建并派发任务后，PM 发 `task_announce`”，方向没错；但如果要和脚本严格一致，最好明确 announce 的硬门槛：
- 必要章节
- 状态门槛
- 禁止对未完成定义任务公告

这部分 `chat/README.md` 和 `send-chat.sh` 已经很明确，4 份设计文档里应同步强化。

---

## 2.4 验证机制是否充分（验证期指标、复盘流程）

### 2.4.1 验证框架是合理的
现有验证文档分成：
- 使用说明
- 落地清单
- 每日记录模板
- 验证复盘模板

这个结构是合理的，至少把：
- 如何用
- 记录什么
- 怎么复盘

三层都覆盖到了。

### 2.4.2 当前指标足够做“流程体验评估”，但不够做“协议质量评估”
现有关注点主要是：
- PM 中转是否减少
- agent 是否主动使用
- 关键结论是否回写
- instruction 二次补写是否减少
- critical 双通道是否执行

这些都很重要，但还缺少**协议质量和运行质量指标**，例如：

#### 建议增加的验证指标
1. **无效消息率**
   - lint 失败消息数
   - 被脚本拒绝的 announce 次数

2. **线程完整性**
   - `answer` 缺失 `reply_to` 的比例
   - task thread 中缺失 `task_id` / 线程错绑比例

3. **消息可追溯性**
   - 关键决策是否能从 chat 找到对应 task / feature / result / review

4. **响应时延**
   - `question -> first answer` 的中位时长
   - `task_announce -> first follow-up` 的中位时长

5. **噪音率**
   - PM 巡检结果中，真正需要 PM 介入的占比

这些指标可以帮助判断：
- A-Lite 不是“看起来用了”，而是“线程组织真的可维护”。

### 2.4.3 复盘模板还可以补“no-go 的结构化归因”
当前复盘模板有：
- 是否进入 Phase B
- PM 中转是否下降
- agent 是否主动使用
- 关键结论是否回写
- 任务定义质量是否提升
- critical 边界是否稳定

建议再加一节：

#### 协议层问题清单
- 是否存在消息类型不够表达的问题
- 是否出现 thread 误用/错用
- 是否需要引入 severity 或 system notice
- 是否需要调整 PM 巡检规则
- 是否需要把部分规则脚本化，而不是继续靠人工纪律

这样 Phase B 决策会更像架构评审，而不只是流程复盘。

---

## 2.5 协议层面的漏洞或改进空间

### 漏洞 1：没有 schema_version，长期演进会脆弱
这是最明显的问题之一。当前 JSONL 若后续新增字段，很容易出现：
- 老脚本还能写
- 新 ingest 假定字段存在
- 回放历史文件时口径不一致

**建议：新增 `schema_version`，从现在开始固定为 `chat-hub-a-lite-v1` 或数值版 `1`。**

### 漏洞 2：没有稳定的 system event 入口
文档反复提到：
- watcher 通知
- dispatch 事件
- send-to-agent 唤醒

但这些目前没有统一 append 入口。  
如果后面各脚本各自写 JSONL，会很快形成协议分叉。

**建议：统一提供一个 system append 脚本/模块。**
例如：
- `scripts/append-chat-event.py`
- 或 `send-chat.sh --system ...`

要求 system 事件也走同一套 schema 校验与原子写入。

### 漏洞 3：`priority` 与 `severity` 语义未分开
当前已有：
- `priority`

看板方案又提出：
- `severity`

两者不一样：
- `priority`：这条消息/任务有多重要
- `severity`：问题本身有多严重

例如：
- 一个 critical 事故同步可能 priority=critical、severity=critical
- 一个高优先排期公告可能 priority=high，但 severity 可能为空

**建议文档尽早定义：A-Lite 只强制 `priority`；`severity` 为后续 system / incident 事件预留，且二者不可混用。**

### 漏洞 4：没有“编辑/撤销/更正”语义
当前 JSONL 是 append-only，这很好；但若消息发错了，没有正式更正机制。  
后续如果决策被推翻，建议不要修改原消息，而是追加：
- `decision` + `supersedes=<msg_id>`
- 或 `correction_of=<msg_id>`

A-Lite 可以先不做，但文档应说明：
- **消息不可变，纠错靠追加，不靠覆盖。**

### 漏洞 5：缺少 message idempotency / dedupe 设计
现在 `msg_id` 由脚本生成，足够唯一；但如果未来系统事件支持重试写入，可能出现：
- 同一 watcher 通知重复落盘
- 同一 send-to-agent 重试生成多条逻辑重复记录

因此 system 事件需要单独定义：
- `dedupe_key`
- 或 `source_event_id`

否则 dashboard 统计会失真。

### 漏洞 6：general 频道与 task thread 的归因规则未明
现在文档说：
- general 用于公共问题
- task thread 用于具体任务

但如果 general 里提到了具体 task，没有明确 task_id，会导致：
- 看板无法回放到该任务
- 复盘时只能人工猜

建议明确规则：
- 任何与具体任务直接相关的消息，一律发 task thread；
- general 中若确实要提任务，也必须显式带 task_id（未来脚本可支持）。

---

## 2.6 具体改进建议

## 2.6.1 建议新增一份《Chat Hub 协议补充》文档
建议新增：
- `design/Chat-Hub-协议补充.md`

至少定义：
1. `schema_version`
2. 字段字典
3. 枚举值：
   - `type`
   - `source_type`
   - `priority`
   - `severity`（预留）
   - `event_class`（预留）
4. A-Lite 当前启用项 vs 预留项
5. Chat 消息到 `communication_events` 的映射
6. system events 的统一写入方式

这份文档会成为 Chat Hub 与 dashboard 的契约桥梁。

## 2.6.2 建议把“system 事件”从现在起当成独立轨道设计
不要把 watcher / dispatch / send-to-agent 强行装成普通 human chat。  
建议从设计上分两条轨道：

### 轨道 A：human thread
- `task_announce`
- `question`
- `answer`
- `decision`
- `task_done`

### 轨道 B：system events
- `dispatch`
- `notify`
- `nudge`
- `delivery_success`
- `delivery_failed`

两者最终都能映射到 `communication_events`，但不应在 JSONL 源层面混淆。

## 2.6.3 建议优化 `pm-chat-check.sh` 默认过滤策略
当前默认把所有 task question/task_done 都纳入 actionable，后续会给 PM 造成噪音。  
建议改成：

### 默认 actionable
- `to=pm-chief`
- `@pm-chief`
- `priority=critical`
- `type=decision`
- `question` 且 `to=pm-chief` 或显式提及 PM
- 双通道缺失 / delivery_failed（未来 system event）

### 扩展观察（`--all` 或 `--verbose`）
- 所有 `question`
- 所有 `task_done`

## 2.6.4 建议在验证模板中增加协议质量指标
在 `Chat-Hub-验证记录模板.md` 增补：
- 被脚本拒绝的 `announce` 次数
- lint 失败消息数
- question -> first answer 平均/中位响应时间
- PM 巡检噪音率（actionable / scanned）
- thread 错绑/缺字段异常数

这会显著提升验证结论的可信度。

## 2.6.5 建议尽早和看板文档对齐 Phase 顺序
当前 `Chat-Hub-落地清单.md` 中：
- `C-5` 才说把 Chat 接入 dashboard / audit

但看板方案已经把 communication timeline 当成 Phase 1 主能力。  
这两者存在阶段定义不一致。

更合理的对齐方式是：
- **A-Lite 验证继续独立进行**；
- 但 dashboard 对 `chat/tasks/*.jsonl` 的只读 ingest 可以提前到近期阶段；
- 真正的 watcher / nudge / severity / delivery events，再放到后续阶段。

也就是说：
- **“chat 进入看板只读回放”可以前移**；
- **“chat 接入状态机/通知系统”不能前移。**

## 2.6.6 建议补充“消息不可变，纠错靠追加”的约束
在 A-Lite 使用说明和 README 里都建议明确：
- 历史消息不编辑
- 若结论变更，追加新消息并引用旧 msg_id

这对后续审计和时间线回放很重要。

---

## 三、建议的优先级

### P0（建议立即补）
1. 新增 `design/Chat-Hub-协议补充.md`
2. 文档明确：A-Lite 当前只有 human 生产路径，system 仅为预留
3. 文档明确：双通道目前是操作规范，不是自动闭环
4. 验证模板增加协议质量指标

### P1（近期可做）
5. 调整 `pm-chat-check.sh` 默认过滤规则
6. 为 dashboard/communication_events 写桥接映射文档
7. 允许 general 中显式携带 `task_id`（至少协议层允许）

### P2（进入下一阶段前）
8. 统一 system event append 入口
9. 增加 `schema_version`
10. 设计 `severity` 与 `priority` 的分工

---

## 四、最终判断

### 可以保留的部分
- A-Lite 继续把 chat 限定为沟通层，不碰状态事实源
- 现有 `send-chat.sh + lint-chat.sh + read-chat.sh + pm-chat-check.sh` 作为最小工具集
- `task_announce` 经过 Dispatch Gate 才允许发送
- critical 场景继续坚持双通道原则

### 必须补强的部分
- system event 协议与写入入口
- Chat Hub 与 `communication_events` 的桥接契约
- 验证指标中的协议质量与噪音口径
- `priority` / `severity` / `source_type=system` 的语义边界

### 一句话结论
> Chat Hub A-Lite 现在已经够用来做真实验证，但它还是一个“人类协作线程协议”，还不是完整的“协作事件协议”；若要支撑看板回放、系统通知与后续 Phase B/C，必须先把 **协议版本、系统事件、桥接映射、验证口径** 这四层补齐。
