# Chat Hub A-Lite 验证使用说明

> 用于指导 PM 与各角色在验证期（V-1 / V-2 / V-3）中如何实际使用 A-Lite。  
> 目标不是“立刻改状态机”，而是验证：共享消息区是否真能降低 PM 中转负担，并被 agent 主动使用。

---

## 一、A-Lite 当前范围

当前只启用：
- `chat/general/`
- `chat/tasks/{task-id}.jsonl`
- `scripts/send-chat.sh`
- human 任务/公共消息生产路径
- 受控 system 事件路径（`watcher / dispatch / nudge`）

当前**不启用**：
- `chat/agents/` 私聊
- `task_claim` / `task_claim_confirmed`
- `chat-notified.json`
- `chat-read-pointers.json`
- watcher 驱动的 chat 状态流转

也就是说：
- **任务状态仍看 `tasks/`**
- **任务讨论开始用 `chat/`**
- **若后续要把 watcher / dispatch / direct nudge 接到 timeline，请先遵循 `design/Chat-Hub-协议补充.md`，不要在 A-Lite 文档里自行扩字段**

---

## 二、谁该怎么用

## 二点五、协议补充阅读要求

- 若任务涉及 chat 协议、看板 ingest、system 通知、severity / priority 口径，必须同时阅读：
  - `design/Chat-Hub-协议补充.md`
- 当前验证期主验证对象仍是 **human message thread**；system 事件已可写入 `chat/system/...`，但主要用于时间线、审计和指标补强。

### 1. PM（pm-chief）

#### PM 要做什么
1. 创建并派发任务后，向对应 thread 发一条 `task_announce`
2. 每天固定 1-2 次查看 `chat/general/`
3. 只在以下情况介入：
   - `@pm-chief`
   - `decision`
   - 生产故障 / critical 任务
   - 多人讨论后仍无法收敛
4. 每天更新一次：
   - `design/Chat-Hub-验证记录模板.md`

#### PM 示例
```bash
/Users/lin/Desktop/work/my-agent-teams/scripts/send-chat.sh announce 修复登录页样式 "新建任务：修复登录页样式。功能目录：features/登录体验优化/，请相关同学在此 thread 讨论。"
```

---

### 2. 开发（dev-1 / dev-2）

#### dev 要做什么
1. 开始任务前看：
   - `chat/tasks/{task-id}.jsonl`
2. 任务中遇到问题，优先在 task thread 提问
3. 完成后可发 `task_done` 简短同步
4. 若讨论里形成了关键结论，必须回写：
   - `features/<feature-id>/decisions.log`
   - 或 `notes/dev.md`

#### dev 示例
```bash
/Users/lin/Desktop/work/my-agent-teams/scripts/send-chat.sh task 修复登录页样式 "@arch-1 登录页按钮颜色是否继续用 primary-blue？" --type question
```

```bash
/Users/lin/Desktop/work/my-agent-teams/scripts/send-chat.sh task 修复登录页样式 "完成，已写 result.json。" --type task_done
```

---

### 3. 架构师（arch-1）

#### arch 要做什么
1. 在 task thread 中回答设计/接口问题
2. 如果结论影响范围较大，必须回写：
   - `CONTEXT.md`
   - `notes/arch.md`
   - `decisions.log`

#### arch 示例
```bash
/Users/lin/Desktop/work/my-agent-teams/scripts/send-chat.sh task 修复登录页样式 "按钮颜色继续用 primary-blue，保持与导航栏一致。" --type answer --reply-to <question-msg-id>
```

---

### 4. QA（qa-1）

#### QA 要做什么
1. 测试中发现回归，先在 task thread 简短同步
2. 关键结论仍必须写回：
   - `verify.json`
   - `notes/qa.md`

---

### 5. 审查（review-1）

#### reviewer 要做什么
1. 审查中的简短说明可发 task thread
2. 最终审查结论仍以：
   - `review.md`
   - `design-review.md`
   为准

---

## 三、什么消息应该发到哪里

### 发到 `chat/general/`
适合：
- 全员可见的提醒
- 非单任务的共性问题
- PM 的公共公告

不适合：
- 某个具体任务的澄清
- 某个 feature 的细节讨论

### 发到 `chat/tasks/{task-id}.jsonl`
适合：
- 任务公告（`task_announce`）
- 任务中的 question / answer
- review / QA 的简短同步
- 完成提醒（`task_done`）

这是 A-Lite 验证期的**主战场**。

---

## 四、关键约束

### 1. chat 不是状态事实源
以下都**不改变任务状态**：
- `task_announce`
- `question`
- `answer`
- `task_done`

任务状态仍然只认：
- `task.json`
- `ack.json`
- `result.json`
- `review.md`
- `verify.json`
- `transitions.jsonl`

### 2. 不发起私聊
A-Lite 阶段不要使用一对一私聊模式。  
所有沟通优先：
- `chat/general/`
- `chat/tasks/{task-id}.jsonl`

### 3. 关键结论必须落盘
如果讨论形成了真正的设计约束 / 实施规则 / 风险判断：
- 不能只留在 chat 中
- 必须回写到 feature 上下文

---

## 五、紧急事项处理

生产故障 / critical 事项：
- chat 只负责共享可见
- **必须同时使用** `send-to-agent.sh`

也就是说：
- chat ≠ 唤醒机制
- `send-to-agent.sh` 仍然是强制触达手段

---

## 六、验证期怎么记录

PM 每天至少记录一次：
- 今天手工中转了多少次
- 哪些任务 thread 里 agent 主动提问/回答
- 有没有关键结论回写
- 有没有“chat 明明有，但大家还是回来找 PM”的情况

统一模板：
- `design/Chat-Hub-验证记录模板.md`

### 6.5 指标采集建议
可结合脚本：
```bash
/Users/lin/Desktop/work/my-agent-teams/scripts/chat-metrics.py --days 1
/Users/lin/Desktop/work/my-agent-teams/scripts/pm-chat-check.sh --days 1 --limit 20
```
用于自动采集：task_announce、question/answer、PM @、critical 双通道、未答复问题等核心验证指标。

---

## 七、1-2 周后如何判断值不值得继续

如果出现以下现象，说明 A-Lite 值得继续：
1. PM 手工中转次数下降
2. agent 会主动在 task thread 中沟通
3. 关键结论能稳定回写
4. 没有引入新的任务状态混乱

如果出现以下现象，则先不要进 Phase B：
1. 没人主动看 chat
2. 大家还是默认找 PM 转达
3. chat 里讨论很多，但决策不落盘
4. 噪音过高，thread 混乱

---

## 八、最小执行建议

如果今天就开始跑验证：
1. PM 对新任务都发 `task_announce`
2. dev / arch / qa / review 在对应 task thread 里沟通
3. PM 每天下班前更新一次验证记录
4. 跑满 1-2 周后再决定是否进入 B 阶段
