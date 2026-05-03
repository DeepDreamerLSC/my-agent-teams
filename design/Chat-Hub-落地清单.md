# Chat Hub 落地清单

> 基于 `design/OpenClaw-tmux协作方案优化.md` 第 15.5 章的 **A-Lite → 验证期 → B → C** 路线整理。
> 目标：先验证共享消息区是否能降低 PM 中转负担，再决定是否把 chat 接入任务认领与状态机。
> 更新时间：2026-04-27

---

## 一、总体原则

1. **先通信，后状态机**
   - A-Lite 阶段只解决 agent 之间直接沟通问题
   - 不直接把 `chat/` 变成任务状态事实源

2. **`tasks/` 继续是任务事实源**
   - `task.json / ack.json / result.json / verify.json / transitions.jsonl` 不变
   - chat 中的消息默认只作讨论、公告、同步，不驱动状态变更

3. **关键结论必须回写 feature 上下文**
   - chat 里的关键约束、决策、风险，必须回写：
     - `features/<feature-id>/decisions.log`
     - `notes/dev.md / arch.md / qa.md`

4. **紧急问题继续双通道**
   - chat 负责共享可见
   - `send-to-agent.sh` 负责强制唤醒
   - 生产故障和 critical 任务不能只靠 chat

5. **任务进入 Chat Hub 前必须先过 Dispatch Gate**
   - Chat Hub 只加速沟通，不替代任务定义
   - `task_announce` 之前，任务类型 / 目标 / 边界 / 验收标准 / 环境范围 / 下游动作 / 授权状态必须已明确
   - 不能把“仍在补 instruction 的任务”直接推进 chat 扩散讨论

---

## 二、阶段总览

| 阶段 | 目标 | 是否触碰状态机 |
|------|------|----------------|
| **A-Lite** | 建立最小可用的共享消息区，验证 agent 是否会主动使用 | 否 |
| **验证期（1-2 周）** | 观察是否真的降低 PM 中转负担、是否形成使用习惯 | 否 |
| **B** | 在验证通过后，逐步把 chat 接入通知、认领和已读状态 | 是（谨慎接入） |
| **C** | 扩展私聊、失败重试、搜索、审计与 Scratchpad 平滑迁移 | 是（增强阶段） |

---

## 三、A-Lite 阶段任务清单

### A-Lite-1
- **ID**：A-Lite-1
- **标题**：建立 Chat Hub 基础目录结构
- **状态**：已完成（2026-04-30）
- **描述**：
  - 创建 `chat/general/` 与 `chat/tasks/` 目录
  - 明确 A-Lite 阶段不创建 `chat/agents/`
  - 明确 `tasks/` 继续作为任务状态事实源，`chat/` 仅承载消息流
- **涉及文件**：
  - `chat/general/`
  - `chat/tasks/`
  - `design/OpenClaw-tmux协作方案优化.md`
  - （可选）`README.md`
- **预估复杂度**：低
- **依赖关系**：无
- **验收标准**：
  1. 仓库内存在 `chat/general/` 和 `chat/tasks/` 目录
  2. 文档中明确 A-Lite 不做私聊目录
  3. 文档中明确 `tasks/` 仍是任务状态事实源

### A-Lite-2
- **ID**：A-Lite-2
- **标题**：实现 send-chat.sh 基础消息发送脚本
- **状态**：已完成（2026-04-30）
- **描述**：
  - 新增 `scripts/send-chat.sh`
  - 支持写入：
    - `chat/general/YYYY-MM-DD.jsonl`
    - `chat/tasks/{task-id}.jsonl`
  - 统一处理：
    - `msg_id` 生成
    - `source_type`
    - `reply_to`
    - `thread_id`
    - flock + 原子写入
    - JSON 校验
- **涉及文件**：
  - `scripts/send-chat.sh`
  - `chat/general/`
  - `chat/tasks/`
- **预估复杂度**：中
- **依赖关系**：A-Lite-1
- **验收标准**：
  1. 可通过脚本向 `general` 和 `tasks` 频道发送消息
  2. 生成的消息包含合法 `msg_id`
  3. 并发写入不产生半条 JSON 或损坏文件
  4. 非法参数/非法 JSON 会被脚本拦截

### A-Lite-3
- **ID**：A-Lite-3
- **标题**：固化 Chat Hub Lite 消息协议与示例
- **状态**：已完成（2026-04-30）
- **描述**：
  - 固化 A-Lite 阶段允许的消息类型：
    - `text`
    - `task_announce`
    - `task_done`
    - `question`
    - `answer`
    - `decision`
  - 明确：
    - `task_done` 不是状态事实源
    - `task_claim` / `task_claim_confirmed` 暂不启用
  - 提供 Lite 版示例 JSONL
- **涉及文件**：
  - `design/OpenClaw-tmux协作方案优化.md`
  - （可选）`chat/README.md`
- **预估复杂度**：低
- **依赖关系**：A-Lite-2
- **验收标准**：
  1. 文档中明确允许的消息类型
  2. 文档中明确 chat 不是状态事实源
  3. 提供至少一组 general/task 示例消息

### A-Lite-4
- **ID**：A-Lite-4
- **标题**：更新 Agent 模板，要求主动检查 Chat Hub
- **状态**：已完成（2026-04-30）
- **描述**：
  - 在 PM / dev / arch / qa / review 模板中加入 Lite 版行为准则：
    - 任务间隙检查 `chat/general` 和对应 `chat/tasks/{task-id}.jsonl`
    - 关键结论必须回写 feature 上下文
    - 生产故障 / critical 任务仍以 `send-to-agent.sh` 为准
- **涉及文件**：
  - `design/agent-templates/base.md`
  - `design/agent-templates/pm.md`
  - `design/agent-templates/arch*.md`
  - `design/agent-templates/dev*.md`
  - `design/agent-templates/qa*.md`
  - `design/agent-templates/review*.md`
  - 重新生成后的 `agents/*/AGENT.md / CLAUDE.md`
- **预估复杂度**：中
- **依赖关系**：A-Lite-3
- **验收标准**：
  1. 角色模板中都有 chat 检查规则
  2. 角色模板中都有“关键结论回写 feature 上下文”规则
  3. 生产/critical 任务强制唤醒规则未被弱化

### A-Lite-5
- **ID**：A-Lite-5
- **标题**：支持 PM 发布 task_announce 作为讨论入口
- **状态**：已完成（2026-04-30）
- **描述**：
  - PM 创建并派发任务后，可通过 `send-chat.sh` 向 `chat/tasks/{task-id}.jsonl` 写 `task_announce`
  - 但 `task_announce` 只能用于**已过 Dispatch Gate** 的任务，不能早于任务定义完成
  - 暂不做自动认领，只做“公告 + 讨论入口”
  - 对复杂任务，还应在消息中带上功能目录、关键背景链接、或当前已知结论引用
  - 对生产 / critical 任务，`task_announce` 只算共享可见，仍必须配合 `send-to-agent.sh` 强制唤醒目标 agent
- **涉及文件**：
  - `scripts/send-chat.sh`
  - （可选）`scripts/create-task.sh` / `scripts/dispatch-task.sh`
  - PM 模板文档
- **预估复杂度**：低到中
- **依赖关系**：A-Lite-2、A-Lite-4
- **验收标准**：
  1. PM 可对新任务发布 task_announce
  2. task_announce 只能针对 instruction 已完善、类型/边界/验收标准明确的任务发送
  3. task_announce 会落到对应 task thread
  4. 生产 / critical 任务会同时走 `send-to-agent.sh` 双通道唤醒
  5. 任务讨论可围绕该 thread 展开

---

## 四、验证期（1-2 周）任务清单

### V-1
- **ID**：V-1
- **标题**：建立 Chat Hub Lite 使用观测台账
- **状态**：部分完成（2026-04-30：记录模板已建立，等待真实验证期执行）
- **描述**：
  - 定义验证期需要记录的核心指标：
    - PM 每日手工中转次数
    - task_announce 后是否有 agent 主动跟进
    - chat 中 question / answer 的发生次数
    - 关键结论回写率
    - `instruction.md` 二次补写次数（任务发出后还要不要频繁补定义）
    - `working 超时` 报警次数与 PM 介入次数
    - 生产 / critical 任务是否仍正确走“双通道”（chat + 强制唤醒）
  - 先以手工记录或轻量表格方式收集数据
- **涉及文件**：
  - `design/OpenClaw-tmux协作方案优化.md`
  - （可选）`design/Chat-Hub-验证记录模板.md`
- **预估复杂度**：低
- **依赖关系**：A-Lite 全部完成后启动
- **验收标准**：
  1. 有明确指标定义
  2. PM 知道每天要记录什么
  3. 至少能区分“chat 使用了”还是“仍靠 PM 中转”
  4. 至少能看出“通信效率提升了，但任务定义是否也更稳了”

### V-2
- **ID**：V-2
- **标题**：执行 1-2 周 Lite 版试运行
- **描述**：
  - 选择真实任务链路试运行
  - 要求 agent 在 task thread 中提问、回答、同步关键进展
  - PM 只在需要决策时介入，不再中转每条消息
- **涉及文件**：
  - `chat/general/*.jsonl`
  - `chat/tasks/*.jsonl`
  - `features/*/decisions.log`
  - `notes/*`
- **预估复杂度**：中（主要是流程执行）
- **依赖关系**：V-1
- **验收标准**：
  1. 连续运行 1-2 周
  2. 至少 5 个真实任务 thread 有有效讨论
  3. 未出现因 chat 引入的新任务状态错乱

### V-3
- **ID**：V-3
- **标题**：验证期复盘与是否进入 Phase B 的决策
- **描述**：
  - 根据验证期记录复盘：
    - PM 中转次数是否下降
    - agent 是否主动使用 chat
    - 关键结论是否能回写
    - 是否出现消息太多、没人看、上下文仍未沉淀等问题
    - 派发前定义质量是否提升（例如 instruction 是否更少二次补写、超时是否减少）
  - 输出 go / no-go 结论
- **涉及文件**：
  - `design/OpenClaw-tmux协作方案优化.md`
  - （可选）`design/Chat-Hub-验证复盘.md`
- **预估复杂度**：中
- **依赖关系**：V-2
- **验收标准**：
  1. 给出是否进入 Phase B 的明确判断
  2. 说明进入 / 不进入的原因
  3. 若不进入，明确 Lite 版需要先修什么
  4. 明确判断“chat 是否只提升了消息流转”，还是“连带提升了任务定义质量与推进效率”

---

### A-Lite-6
- **ID**：A-Lite-6
- **标题**：提供 read-chat.sh 轻量读消息脚本
- **状态**：已完成（2026-04-30）
- **描述**：
  - 新增 `scripts/read-chat.sh`
  - 支持读取：
    - `chat/general/YYYY-MM-DD.jsonl`
    - `chat/tasks/{task-id}.jsonl`
  - 支持 `--limit`、`--date`、`--raw`
- **涉及文件**：
  - `scripts/read-chat.sh`
  - `chat/README.md`
- **预估复杂度**：低
- **依赖关系**：A-Lite-2
- **验收标准**：
  1. agent / PM 可快速查看 general 或 task thread 最近消息
  2. 不必手工 `tail/cat` 原始 JSONL 才能读懂内容

### A-Lite-7
- **ID**：A-Lite-7
- **标题**：提供 PM chat 巡检脚本
- **状态**：已完成（2026-04-30）
- **描述**：
  - 新增 `scripts/pm-chat-check.sh`
  - 用于 PM 快速巡检近期需要关注的 chat 消息
  - 默认聚焦：
    - `to=pm-chief`
    - `@pm-chief`
    - `priority=critical`
    - `decision`
    - task thread 中的 `question / task_done`
- **涉及文件**：
  - `scripts/pm-chat-check.sh`
  - `chat/README.md`
- **预估复杂度**：低
- **依赖关系**：A-Lite-2
- **验收标准**：
  1. PM 可快速看到近期 actionable chat 消息
  2. 不必人工翻所有 general / task 文件才能定位重点

### A-Lite-8
- **ID**：A-Lite-8
- **标题**：补充 Chat Hub 协议 lint 与关键消息回写提醒
- **状态**：已完成（2026-04-30）
- **描述**：
  - 新增 `scripts/lint-chat.sh`
  - 校验 chat JSONL 协议：
    - 必填字段
    - type/source_type/priority 枚举
    - `answer` 必须带 `reply_to`
    - `task_announce / task_done / decision` 必须带 `task_id`
  - `send-chat.sh` 对 `decision / answer / task_done` 增加回写提醒
- **涉及文件**：
  - `scripts/lint-chat.sh`
  - `scripts/send-chat.sh`
  - `chat/README.md`
- **预估复杂度**：中
- **依赖关系**：A-Lite-2、A-Lite-3
- **验收标准**：
  1. Chat 协议有可执行 lint
  2. 关键消息发送后会提醒发送者同步回写 feature 上下文

## 五、Phase B（验证通过后）任务清单

> 只有当验证期**明确通过**，证明 Chat Hub 确实降低 PM 中转负担、agent 会主动使用、且派发前定义质量没有继续恶化时，才进入 B 阶段。
> 若通信效率上去了，但 instruction 仍频繁二次补写、生产任务边界仍混乱，则**默认停留在 A-Lite / 验证期**，继续打磨 Lite 版与 Dispatch Gate，不进入状态机接入。

### Phase B 进入前置条件
- Dispatch Gate 已经固化，PM 不再频繁派发“定义未完成”的任务
- 任务 archetype（排查 / 开发 / 验证 / 集成 / 部署）已经稳定执行
- 生产 / critical 任务的双通道唤醒与授权边界已稳定
- 验证期复盘结论明确表明：进入 B 阶段不会把“任务定义不清”放大成“状态机混乱”

> 若以上任一前置条件不成立，B 阶段视为**暂不立项**，不是“边做边试”的默认施工项。

### B-1
- **ID**：B-1
- **标题**：实现 task_claim 原子绑定 task.json
- **描述**：
  - 引入 `task_claim` 与 `task_claim_confirmed`
  - watcher / claim-processor 原子执行：
    - 校验任务可认领
    - 更新 `task.json.assigned_agent`
    - `pending -> dispatched`
    - 追加 `transitions.jsonl`
    - 写 `task_claim_confirmed`
  - 明确：chat 中 claim 只是意图，确认后才是事实
- **涉及文件**：
  - `scripts/task-watcher.sh`
  - （可选）`scripts/chat-claim-processor.sh`
  - `tasks/*/task.json`
  - `tasks/*/transitions.jsonl`
  - `chat/tasks/*.jsonl`
- **预估复杂度**：高
- **依赖关系**：V-3（Go）
- **验收标准**：
  1. `task_claim` 不再造成假认领
  2. 认领成功后 `task.json` 与 chat 记录一致
  3. 并发认领不会造成状态污染

### B-2
- **ID**：B-2
- **标题**：实现 chat-notified.json 通知去重
- **描述**：
  - 引入系统级通知去重
  - 防止 watcher / tmux-watcher / agent 主动检查造成重复提醒
- **涉及文件**：
  - `.omx/chat-notified.json`
  - `scripts/task-watcher.sh`
  - `scripts/tmux-watcher.sh`
- **预估复杂度**：中到高
- **依赖关系**：B-1（可并行，但建议在状态机绑定后做）
- **验收标准**：
  1. 同一消息不会被系统重复通知
  2. 去重不会导致新消息漏提醒

### B-3
- **ID**：B-3
- **标题**：实现 chat-read-pointers.json 已读游标
- **描述**：
  - 为每个 agent 记录 general / tasks / 私聊 thread 的最后已读 `msg_id`
  - 区分：通知过 / 已读 / 已处理
- **涉及文件**：
  - `.omx/chat-read-pointers.json`
  - `scripts/task-watcher.sh`
  - `scripts/tmux-watcher.sh`
- **预估复杂度**：高
- **依赖关系**：B-2
- **验收标准**：
  1. 可以判断 agent 读到哪里
  2. 不再把“通知过”误当“已看过”

### B-4
- **ID**：B-4
- **标题**：扩展 task-watcher 轮询 Chat Hub 新消息
- **描述**：
  - watcher 定期扫描 chat/ 新消息
  - 按 `to / type / priority` 判断要提醒谁
  - 与 `chat-notified.json`、`chat-read-pointers.json` 协同工作
- **涉及文件**：
  - `scripts/task-watcher.sh`
- **预估复杂度**：高
- **依赖关系**：B-2、B-3
- **验收标准**：
  1. 普通消息不骚扰 PM
  2. 关键消息能稳定提醒目标 agent
  3. 不破坏现有任务 watcher 主链路

### B-5
- **ID**：B-5
- **标题**：扩展 tmux-watcher 处理 Chat Hub 空闲提醒
- **描述**：
  - 当 agent 空闲时，检查是否有未读 chat 消息
  - 配合 read pointer 做低打扰提醒
- **涉及文件**：
  - `scripts/tmux-watcher.sh`
- **预估复杂度**：中到高
- **依赖关系**：B-3、B-4
- **验收标准**：
  1. 空闲 agent 会收到未读提醒
  2. 忙碌 agent 不会被普通 chat 打断

### B-6
- **ID**：B-6
- **标题**：实现 critical 任务 chat + send-to-agent 双通道唤醒
- **描述**：
  - critical 任务必须同时：
    - 写 chat
    - `send-to-agent.sh` 强制唤醒
  - 保证生产故障类任务不能只靠共享消息区
- **涉及文件**：
  - `scripts/task-watcher.sh`
  - `scripts/send-chat.sh`
  - `scripts/send-to-agent.sh`
- **预估复杂度**：中
- **依赖关系**：B-4
- **验收标准**：
  1. critical 消息不会只停留在 chat
  2. 生产故障类任务可强制唤醒负责人

---

## 六、Phase C（再扩）任务清单

> C 阶段全部属于**条件性增强项**。只有在 A-Lite 稳定运行、验证期通过、且 B 阶段确实证明值得继续投入时，才考虑单独立项；不要将 C 阶段视为默认排期内容。

### C-1
- **ID**：C-1
- **标题**：引入私聊线程与规范命名
- **描述**：
  - 新增 `chat/agents/`
  - 私聊统一按字典序命名：`arch-1__dev-1.jsonl`
  - 继续使用 `msg_id / reply_to`
- **涉及文件**：
  - `chat/agents/`
  - `scripts/send-chat.sh`
  - `scripts/task-watcher.sh`
- **预估复杂度**：中
- **依赖关系**：Phase B 基础完成后
- **验收标准**：
  1. 一对 agent 只有一个线程文件
  2. 私聊不会分裂成双份

### C-2
- **ID**：C-2
- **标题**：实现通知失败重试与 dead-letter
- **描述**：
  - 若 chat 通知发送失败、目标 session 不在线、唤醒失败
  - 记录日志、有限重试、最终进入死信区
- **涉及文件**：
  - `scripts/task-watcher.sh`
  - （可选）`chat/dead-letter/`
  - 日志目录
- **预估复杂度**：高
- **依赖关系**：B-4、B-5
- **验收标准**：
  1. 失败不会静默丢消息
  2. 可追溯失败原因

### C-3
- **ID**：C-3
- **标题**：实现 Chat Hub 历史搜索与归档策略
- **描述**：
  - 为 general / tasks / agents 设计归档与清理策略
  - 增加按 task_id / from / type / 时间搜索的轻量工具
- **涉及文件**：
  - `chat/`
  - （可选）`scripts/chat-search.sh`
  - 归档脚本
- **预估复杂度**：中
- **依赖关系**：A-Lite 完成即可开始，但建议在 Phase B 后做
- **验收标准**：
  1. 历史消息可检索
  2. 日志/消息量增长后仍可维护

### C-4
- **ID**：C-4
- **标题**：实现 chat 关键结论回写联动
- **描述**：
  - 对 `decision / task_done / 关键 answer`
  - 自动提醒或辅助回写到：
    - `features/<feature-id>/decisions.log`
    - `notes/dev.md / arch.md / qa.md`
- **涉及文件**：
  - `scripts/task-watcher.sh`
  - `features/*`
  - agent 模板
- **预估复杂度**：中到高
- **依赖关系**：B-4
- **验收标准**：
  1. 关键结论不会只留在 chat
  2. feature 上下文持续收敛

### C-5
- **ID**：C-5
- **标题**：将 Chat Hub 记录接入看板 / 审计视图
- **描述**：
  - 让 `task_announce / claim / done / decision` 进入 dashboard / audit 视图
  - 实现任务状态 + 讨论流联动回放
- **涉及文件**：
  - `dashboard/ingest.py`
  - `dashboard/query.py`
  - `dashboard/app.py`
  - `chat/`
- **预估复杂度**：高
- **依赖关系**：B-1、B-4、B-3
- **验收标准**：
  1. 可以从看板看到任务状态之外的沟通轨迹
  2. 不污染现有任务状态口径

### C-6
- **ID**：C-6
- **标题**：Scratchpad 平滑废弃与迁移
- **描述**：
  - 新任务优先用 `chat/tasks/`
  - 老 `tasks/.scratchpad/` 保留只读兼容期
  - 最终评估是否可完全废弃
- **涉及文件**：
  - `tasks/.scratchpad/`
  - `scripts/task-watcher.sh`
  - 设计文档与 agent 规则
- **预估复杂度**：中
- **依赖关系**：C-4、C-5 之后更合适
- **验收标准**：
  1. 新任务不再依赖 scratchpad
  2. 老任务迁移不造成上下文丢失

---

## 七、建议实施顺序

### 先做
1. A-Lite-1
2. A-Lite-2
3. A-Lite-3
4. A-Lite-4
5. A-Lite-5
6. V-1
7. V-2
8. V-3

### 验证通过后再做（未通过则整体后移）
9. B-1
10. B-2
11. B-3
12. B-4
13. B-6
14. B-5

### 最后扩展
15. C-1
16. C-2
17. C-3
18. C-4
19. C-5
20. C-6

---

## 八、落地判断标准

如果只问一句：

> **什么时候值得从 A-Lite 升级到 B？**

我的建议是：
- 至少跑完 **1-2 周真实任务**
- 并且同时满足：
  1. PM 中转次数明显下降
  2. agent 会主动在 chat 中提问/回答
  3. 关键结论能稳定回写
  4. 没有引入新的任务状态混乱

在这之前，**不要急着把 chat 接入任务认领状态机**。
