# OpenClaw + tmux 协作方案优化

> 创建时间:2026-04-22
> 修订时间:2026-04-30 v13
> 实施主目录: `~/Desktop/work/my-agent-teams/`
> 文档定位:面向当前 OpenClaw + tmux + Claude Code / Codex 的**实操优化方案**,优先解决任务追踪、消息可靠性、选择性隔离开发、真实校验与联调成功率问题。

**2026-04-27 v13：** 新增 15.5 公共消息区（Chat Hub）A-Lite 版——先落地 `chat/general/` 与 `chat/tasks/` 两类公开沟通通道，用于任务公告、讨论与问答；`tasks/` 继续作为状态事实源。A-Lite 阶段**不启用私聊、不接入 `task_claim` 状态机、不替代现有派发链路**，是否进入更重的 B/C 阶段取决于验证期结果。

**2026-04-24 v11：** 补充监听服务能力文档

**2026-04-23 v10：** 新增第二十一章"分层 PM 演进方案"——覆盖 3-5 / 8-10 / 12-15 三个 agent 数量级的组织架构、config.json 与 task.json schema 演进、协调机制、通知汇报机制。核心结论：现在就做 schema hierarchy-ready，8+ agent 时启动两层 PM，12+ 时升级为 Program/Domain/Pod 三层。完整草案见 [分层PM演进方案.md](./分层PM演进方案.md)。

**2026-04-24 v11：** 补充监听服务能力文档

1. 新增 5.6 tmux-watcher 职责说明——权限确认自动处理、支持 Codex i 模式、冷却去重
2. 新增 5.7 task-watcher 职责说明——任务状态文件监控（ack/result/review/verify）、自动状态流转、PM 通知、飞书推送、兜底重发机制
3. 两个 watcher 脚本统一存放于 `scripts/` 目录，通过 tmux session 常驻运行

**2026-04-23 v9：** 全文审查修订 + 角色定义分层方案：

### 修订记录
1. 新增第二十章"角色定义与 Prompt 分层管理"——三层分离（身份层 config.json / 能力层 prompts/{role}-base.md / 任务层 instruction.md），明确"宪法由立法者写，PM 是执法者"的权力边界
2. 修复 13.1 保护路径说明——澄清保护针对 agent 的 git diff，不限制 watcher/PM 的文件系统操作；prompts/ 纳入保护路径
3. 补充 5.4 事件模型——增加 Agent 离线事件
4. 新增 5.5 Watcher 职责汇总——将散落在 4.1/4.3/5.4/16.6 的 watcher 职责统一列出
5. 定义 instruction.md 最小模板（5.1）
6. 十一章与十八章优先级定位澄清
7. 十章延后项增加多项目支持和聚合指标
8. 更新第十七章待办事项

**2026-04-23 v8：** 补充 Claude Code 源码分析的新发现（第 4/6/7 章）：
1. 第十六章新增 16.9 Transition 字段防恢复死循环——PM 重试前扫描 transitions 做去重，相同原因超过 2 次强制升级人工介入
2. 第十六章新增 16.10 多层压缩策略——PM 结构化输出、主动摘要、分批处理，延缓上下文膨胀
3. 第十六章新增 16.11 Prompt 静态/动态分离与审查并行化——agent prompt 拆为 base.md（跨任务缓存）+ instruction.md（每次不同），利用 prompt cache 降本；审查可拆分为多维度并行（Phase 2+）
4. 更新第十七章待办事项和第十八章优先级

**2026-04-22 v7：** 基于 Claude Code 源码逆向分析（五层纵深防御、Coordinator 模式、权限单调递减）进一步强化方案：
1. 新增第十三章"安全与权限控制"——保护路径清单 + verify 硬检查、agent 不可自改 task.json 关键字段、Handoff 语义审查、Permission Mode 与沙箱长期方向
2. 新增第十五章"通信模型与 Scratchpad"——确立 PM 中转 + Scratchpad 异步共享架构，含三场景分析（延迟容忍、PM 崩溃、agent 扩展）和 Scratchpad 形式化定义
3. 补充第十四章——agent 启动初始化协议、PM 容灾与状态恢复（pm-state.json 最小 schema）
4. 新增第十九章附录——Claude Code 五层纵深防御模型及其对本方案的映射
5. 修正章节编号跳跃（原文缺少十三、十五）
6. 更新第十七章立即可做事项和第十八章优先级建议

**2026-04-22 审查修订：** 经架构审查后，本文档在原方案基础上融合了以下补充：
1. 完善状态机——补充完整状态转换矩阵（4.3），明确每个转换的触发者和前置条件，消除实现歧义
2. 强化 agent 可靠性——增加 agent 健康检查（4.1）、协议合规校验（5.3）、取消协议（16.6），应对 LLM agent 不遵守约定的风险
3. 补全集成流程——增加冲突分类处理策略和回滚策略（8.2/8.4），确保 integration 分支始终可用
4. 明确角色交接界面——细化开罗尔→PM 交接物格式（14.3）、PM 验收范围和状态持久化（14.6）、架构师产出边界（14.2）
5. 标注设计模式落地约束——对第十六章各模式逐一评估 Phase 分期和执行机制可行性
6. 补充基础设施——任务清理流程（16.5）、transitions 日志（16.7）、flock 锁机制（5.4）、配置与运行时数据分离（12.8）、消息派发协议（5.1）

## 一、现状分析

### 当前架构

```text
用户(飞书)
  │
  ▼
开罗尔(OpenClaw Agent)
  │ tmux send-keys / watcher / task-router
  ▼
┌─────────┐  ┌─────────┐  ┌─────────┐
│ 大蔡     │  │ 小蔡     │  │ 小克     │
│ (dcai)  │  │ (xcai)  │  │ (xke)   │
└─────────┘  └─────────┘  └─────────┘
  tmux session + Claude Code / Codex
```

### 当前核心问题

| # | 问题 | 严重程度 | 表现 |
|---|------|---------|------|
| 1 | 通信脆弱 | 🔴 高 | `not in a mode`、消息拆行丢失、无可靠 ACK |
| 2 | 无任务管理 | 🔴 高 | 派发靠手动、状态靠猜、完成靠问 |
| 3 | 结果不可靠 | 🔴 高 | agent 说改了,但未必真的改了 |
| 4 | 协作松散 | 🟡 中 | 上下游依赖不清楚、重复劳动 |
| 5 | 缺少隔离 | 🟡 中 | 多任务混在同一工作区,冲突难排查 |
| 6 | 联调脆弱 | 🔴 高 | 各自能做完,一集成就炸 |
| 7 | 调试靠人肉 | 🟡 中 | capture-pane 不稳定,缺少结构化工件 |

---

## 二、评审后的折中结论(大蔡视角 × 架构视角)

| 议题 | 大蔡(实操) | 我(架构) | 本文最终折中 |
|---|---|---|---|
| `task.json` | 唯一事实源,但 Phase 1 字段要少 | 希望状态统一,避免后续重构 | **Phase 1 只保留最小字段;扩展字段后置** |
| worktree | 方向对,但 `/tmp` 路径有坑 | 隔离仍然重要 | **改为可配置 sibling worktree root,且按任务选择性启用** |
| 契约 | 先 contract-test 化,不强推全量 OpenAPI | 长期应走机器可验契约 | **先对高风险接口做 contract test,再逐步外显为 OpenAPI/JSON Schema** |
| ACK | 文件与 pane 双轨冗余 | 结构化输出有利调试 | **`ack.json` 做事实源,pane/log 只做调试** |
| dashboard / SDK 分层 | 不是当前瓶颈 | 长期有价值 | **保留为后续项,不放在当前主线** |

### 当前优先做什么

按照大蔡的实操建议,当前最值得先落地的是:

1. `task.json` 最小闭环
2. `ack.json / result.json / verify.json`
3. 基于真实 `git diff` 的结果校验
4. **选择性** worktree 隔离
5. integration 分支上的自动验证

---

## 三、设计原则

1. **先做最小闭环**:优先解决"发了没、做了没、真改了没、能不能合"。
2. **`task.json` 是唯一事实源**:其他文件是附属工件,不再做第二事实源。
3. **状态宁少勿多**:Phase 1 不拆过细状态,不先做复杂治理。
4. **选择性隔离**:不是所有任务默认上 worktree;路径敏感任务可暂留主工作区。
5. **校验要基于真实 diff**:不接受"只看文件存在"的伪校验。
6. **联调由唯一集成者负责**:integration worktree 只允许 integrator 写。
7. **契约先务实**:先用 contract test 固化关键接口,再逐步标准化。

---

## 四、Phase 1 最小闭环方案

### 4.1 任务目录结构

每个任务一个目录:

```text
~/.openclaw/workspace/tasks/{task-id}/
├── task.json      # 唯一事实源
├── ack.json       # agent 已收到任务
├── result.json    # agent 完成后的结构化结果
└── verify.json    # 开罗尔自动校验结果（含协议合规检查）
```

> 说明:`events.jsonl`、dashboard 数据、复杂统计先不做,避免 Phase 1 变重。

#### Agent 健康检查

除了任务状态流转，还需要对 agent 进程本身做存活检测。tmux session 意外关闭、Claude Code 上下文溢出、Codex 超时退出都是高频故障，最小健康检查机制如下：

- watcher 定期检查 agent 对应的 tmux session 是否存活（`tmux has-session -t $SESSION 2>/dev/null`）
- 如果 session 不存在,将该 agent 所有 `working` 状态的任务标记为 `failed`,`last_error` 写 `"agent session lost"`
- 不做复杂的 heartbeat 文件机制(Phase 1 保持简单),tmux session 存活即为健康

### 4.2 `task.json`:Phase 1 最小字段

```json
{
  "id": "20260422-001",
  "title": "实现 users CRUD API",
  "assigned_agent": "dcai",
  "review_required": true,
  "review_authority": "reviewer",
  "reviewer": "xke",
  "review_round": 0,
  "max_review_rounds": 3,
  "test_required": true,
  "status": "working",
  "created_at": "2026-04-22T09:35:00+08:00",
  "updated_at": "2026-04-22T09:50:00+08:00",
  "timeout_minutes": 30,

  "base_branch": "main",
  "base_commit": "abc1234",
  "target_branch": "integration",

  "workspace_mode": "worktree",
  "worktree_path": "/repo-parent/.openclaw-worktrees/chiralium/20260422-001",
  "task_branch": "agent/20260422-001",

  "write_scope": ["backend/app/api/**", "backend/tests/**"],
  "depends_on": [],
  "blocks": [],
  "artifacts": [],
  "contract_files": ["tests/contracts/users.contract.ts"],

  "result_summary": null,
  "last_error": null
}
```

#### 参与角色链（Phase 1）

不是每个任务都需要所有角色参与。Phase 1 默认按**参与角色链**工作：

```text
PM → assigned_agent → (可选 reviewer) → (可选 tester) → PM 验收
```

规则：
- `assigned_agent`：唯一执行者，必须明确
- `review_required=true`：任务必须进入审查链，`reviewer` 可在 task.json 明确写死；若为空则按 config.json 中该 domain 的 `default_reviewer` 解析
- `test_required=true`：任务必须进入测试链；Phase 1 为保持 schema 最小，默认不单独落 `tester` 字段，而是按 config.json 中该 domain 的 `default_tester` 解析
- 审查和测试都是**按需参与**，不是所有任务都必须经过全部角色

#### 双轨审查机制（Phase 1 落地版）

为避免“所有任务都走同一套审查闭环”导致流程过重，Phase 1 引入 **双轨审查机制**。通过 `task.json.review_authority` 区分两条路径：

- `review_authority = "reviewer"`（默认）
  - 适用于：代码任务、测试任务、配置实现任务
  - 审查者拥有终审权
- `review_authority = "owner"`
  - 适用于：设计文档、方案稿、方向文档等需要林总工拍板的任务
  - 审查者只提意见，不做终审；最终由 owner 决策

##### A. reviewer 闭环（代码 / 测试）

```text
agent 提交 result.json
→ reviewer 审查
→ 若有意见：PM 打回给 agent 修改
→ agent 再提交
→ reviewer 再审
→ approved → 合入 / 进入 integration
```

约束：
- `max_review_rounds = 3`，默认不超过 3 轮
- `review_round` 记录当前第几轮审查
- 若超过 3 轮仍未通过，任务升级给 PM，由 PM 决定是否拆任务、降级目标或人工介入

##### B. owner 决策（设计文档）

```text
agent 提交 result.json
→ reviewer 审查并给出意见
→ PM 汇总 reviewer 意见，写 review-summary.md
→ watcher 检测到 review-summary.md 且 review_authority=owner
→ 飞书推送给林总工
→ 林总工决策
→ 开罗尔传达 PM
→ PM 再传达给 agent 修改
```

约束：
- 审查者在 owner 轨道中只输出意见，不直接给 approved/reject 终态
- `review-summary.md` 是 PM 面向 owner 的汇总稿，不是 reviewer 原始意见本体
- owner 轨道默认不由 watcher 自动推进到 done，必须等 owner 决策回流后由 PM 决定下一步

##### Phase 1 的最小字段

- `review_authority`: `reviewer | owner`，默认 `reviewer`
- `review_round`: 当前轮次，初始为 `0`
- `max_review_rounds`: 默认 `3`

#### Phase 1 复用原则：不新增 review/test 独立 JSON

Phase 1 先遵循“**能复用就复用**”原则：

- 不新增 `review.json` / `test-result.json`
- `task.json` 只负责表达：
  - 是否需要 review / test
  - reviewer 是谁
  - assigned_agent 是谁
- 执行者交付仍统一写 `result.json`
- reviewer / tester 的详细结论先走 `artifacts`，例如：
  - `review.md`
  - `test.md`
  - 或其他文本 / markdown 产物

原因：
1. Phase 1 团队规模小，先把最小闭环打通，比引入更多 JSON 工件更重要
2. `result.json`、`verify.json`、`task.json` 已足够表达当前控制面和机械校验结果
3. reviewer / tester 若回写独立 JSON，会增加所有权和并发写复杂度，当前阶段收益不高

升级条件：只有当后续出现以下情况时，再考虑拆出独立结构化工件：
- 一个任务需要多轮 review
- reviewer / tester 需要并行工作
- review / test 结果需要被脚本自动消费
- 一个任务需要多个 reviewer / 多个 tester

到那时，再引入 `review.json` / `test-result.json` 也不晚。

### 4.3 Phase 1 状态:只保留最小必要集

```text
pending
→ dispatched
→ working
→ ready_for_merge
→ done

异常分支:failed / timeout / blocked / cancelled
```

说明:
- `acked` 不单独做成状态,**ACK 是否存在由 `ack.json` 表达**。
- `merged_to_integration` / `integration_testing` 等更细状态,先不放进 Phase 1 主状态机,避免状态爆炸。
- 如需查看集成结果,看 `verify.json` 与日志,不靠再新增一层状态。

#### 完整状态转换矩阵

Phase 1 需要固化以下矩阵，避免实现时各脚本作者各自猜测导致不一致。

| 当前状态 | 可转到 | 触发者 | 前置条件 |
|----------|--------|--------|----------|
| `pending` | `dispatched` | 开罗尔/PM | tmux send 成功 |
| `pending` | `cancelled` | 开罗尔/PM | 人工取消 |
| `dispatched` | `working` | watcher | `ack.json` 出现且格式合规 |
| `dispatched` | `timeout` | watcher | 超过 `timeout_minutes` 仍无 `ack.json` |
| `dispatched` | `cancelled` | 开罗尔/PM | 人工取消 |
| `working` | `ready_for_merge` | agent | 写出合规的 `result.json` |
| `working` | `failed` | agent / watcher | agent 报错或超时 |
| `working` | `blocked` | agent / PM | 发现上游依赖问题 |
| `working` | `cancelled` | 开罗尔/PM | 人工取消 |
| `ready_for_merge` | `done` | integrator | `verify.json.ok=true` 且 integration 验证通过 |
| `ready_for_merge` | `failed` | integrator | `verify.json.ok=false` 或 integration 验证失败 |
| `failed` | `pending` | PM | 决定重试,重新派发 |
| `failed` | `cancelled` | 开罗尔/PM | 确认放弃 |
| `timeout` | `pending` | PM | 决定重试 |
| `timeout` | `cancelled` | 开罗尔/PM | 确认放弃 |
| `blocked` | `pending` | PM | 上游问题解决后重新派发 |
| `blocked` | `cancelled` | 开罗尔/PM | 确认放弃 |

关键约束:
- **`dispatched → working` 由 watcher 触发**:watcher 检测到合规的 `ack.json` 后自动更新 `task.json.status`。这意味着 watcher 需要有写 `task.json` 的权限,但仅限于状态字段。
- **异常状态均可回退到 `pending`**:通过 PM 创建重试决策,不直接跳回 `working`。
- **`done` 和 `cancelled` 是终态**:不可再转出。

### 4.4 附属工件格式

#### `ack.json`

```json
{
  "task_id": "20260422-001",
  "agent": "dcai",
  "acked_at": "2026-04-22T09:36:08+08:00"
}
```

#### `result.json`

```json
{
  "task_id": "20260422-001",
  "status": "ready_for_merge",
  "summary": "已实现 users CRUD API",
  "files_modified": ["backend/app/api/users.py", "backend/tests/test_users.py"]
}
```

#### `verify.json`

```json
{
  "task_id": "20260422-001",
  "verified_at": "2026-04-22T10:05:00+08:00",
  "ok": true,
  "actual_files": ["backend/app/api/users.py", "backend/tests/test_users.py"],
  "diff_base": "abc1234",
  "notes": ["diff 与声明一致", "未越过 write_scope"]
}
```

### 4.5 任务主流程(Phase 1)

```text
开罗尔创建 task.json
→ 发消息并标记 dispatched
→ agent 写 ack.json
→ agent 开发并写 result.json
→ 开罗尔基于真实 diff 写 verify.json
→ 可合则进入 integration 验证
→ 通过则 done,失败则 blocked / failed
```

---

### 4.6 共享任务池与主动认领机制

> **设计参考**：Claude Code Agent Teams 的共享任务列表 + 主动认领模式。
> **动机**：当前方案中任务只能由 PM 手动派发（dispatch），dev 处于被动等待状态。
> 当 PM 上下文繁忙或离线时，空闲的 dev 无法推进工作，造成资源浪费。
> 引入共享任务池后，PM 只需将任务投入池中，dev 可主动认领，大幅降低 PM 的调度瓶颈。

#### 4.6.1 任务目录结构变更

在现有 `tasks/` 目录下新增 `pool/` 子目录：

```text
tasks/
├── pool/                          # 待认领任务池（新增）
│   ├── 20260427-pool-001/         # 已入池但未被认领
│   │   ├── task.json              # status = "pooled"
│   │   ├── instruction.md
│   │   └── claim.json             # （认领后生成）
│   └── 20260427-pool-002/
│       ├── task.json
│       └── instruction.md
├── 20260422-001/                  # 已认领 / 已派发 / 已完成（现有流程不变）
│   ├── task.json
│   ├── ack.json
│   └── result.json
└── ...
```

#### 4.6.2 新增状态：`pooled`

在 4.3 状态机中新增 `pooled` 状态，作为 `pending` 的子状态：

```text
pending ──(PM 放入池中)──→ pooled ──(agent 认领)──→ dispatched ──(watcher 检测 ack)──→ working
                              │
                              └──(PM 直接派发，跳过池)──→ dispatched
```

**状态转换补充（追加到 4.3 矩阵）：**

| 当前状态 | 可转到 | 触发者 | 前置条件 |
|----------|--------|--------|----------|
| `pending` | `pooled` | 开罗尔/PM | task.json + instruction.md 创建完成，放入 pool/ |
| `pooled` | `dispatched` | agent（主动认领） | agent 写入合规的 claim.json |
| `pooled` | `dispatched` | PM（强制指派） | PM 指定 assignee，走现有 dispatch 流程 |
| `pooled` | `cancelled` | 开罗尔/PM | 人工取消 |

**关键设计决策：**

1. **`pooled` 不是独立终态**：它只是 `pending → dispatched` 之间的等待状态，agent 认领后立即进入 `dispatched`。
2. **PM 仍可强制指派**：紧急任务 PM 可以直接 dispatch，跳过池子。池子是"默认路径"，不是"唯一路径"。
3. **认领后走现有流程**：`claim.json` 生成后，后续的 ack.json / result.json / verify.json 流程完全不变。

#### 4.6.3 `claim.json` 格式

```json
{
  "task_id": "20260427-pool-001",
  "agent": "dev-2",
  "claimed_at": "2026-04-27T11:00:00+08:00",
  "reason": "该任务涉及后端 API 修改，在我的能力范围内"
}
```

- `reason` 是可选字段，但建议 agent 填写，方便 PM 了解认领动机。
- watcher 检测到 `claim.json` 后，将任务从 `pool/` 移出到 `tasks/` 根目录，更新 `status=dispatched`，并通知 PM。

#### 4.6.4 认领规则

1. **单认领**：一个任务只能被一个 agent 认领。watcher 以 `claim.json` 的 `claimed_at` 时间戳判断先到先得。
2. **角色匹配**：task.json 中的 `suggested_roles`（新增字段）列出建议角色，非建议角色也可认领但需要 PM 确认。
3. **并发冲突**：如果两个 agent 同时写 claim.json，watcher 只认第一个（flock 文件锁保证原子性）。
4. **超时回收**：`pooled` 任务超过 `pool_timeout_minutes`（默认 60 分钟，可配置）未被认领，watcher 通知 PM 决定是否强制指派。

#### 4.6.5 task.json 新增字段

```json
{
  "task_id": "20260427-pool-001",
  "title": "修复 DeepSeek 聊天接口超时",
  "status": "pooled",
  "assignee": null,
  "suggested_roles": ["dev-2"],
  "suggested_reason": "涉及后端 API，dev-2 更熟悉该模块",
  "pool_timeout_minutes": 60,
  "created_at": "2026-04-27T10:55:00+08:00",
  "pooled_at": "2026-04-27T10:55:00+08:00",
  "priority": "high",
  "write_scope": ["backend/app/api/"],
  "depends_on": []
}
```

新增字段说明：

| 字段 | 必填 | 说明 |
|------|------|------|
| `suggested_roles` | 否 | 建议认领角色列表，PM 可在入池时指定 |
| `suggested_reason` | 否 | 建议理由，帮助 agent 判断是否认领 |
| `pool_timeout_minutes` | 否 | 池中等待超时，默认 60，0 表示不限 |
| `pooled_at` | 入池时填写 | 入池时间戳 |
| `priority` | 否 | `low / medium / high / critical`，影响池中排序 |

#### 4.6.6 watcher 变更

task-watcher.sh 新增以下职责：

1. **轮询 `pool/` 目录**：检测新入池任务和 claim.json
2. **认领处理**：
   - 发现 `claim.json` → 验证格式 → flock 锁 → 检查是否已被认领 → 移动到 tasks/ 根目录 → 更新 status=dispatched → 通知 PM
   - 已被认领 → 通知后来的 agent（通过 tmux send-keys）
3. **超时检查**：`pooled` 任务超时 → 通知 PM
4. **优先级排序**：agent 查看池中任务时，按 priority 排序

#### 4.6.7 Agent 如何查看和认领池中任务

Agent 通过以下方式与任务池交互：

**查看池中任务：**
```bash
# Agent 在自己的 session 中执行
ls ~/Desktop/work/my-agent-teams/tasks/pool/
# 或读取任务摘要
cat ~/Desktop/work/my-agent-teams/tasks/pool/*/task.json | jq '{id, title, priority, suggested_roles}'
```

**认领任务：**
```bash
# Agent 写入 claim.json
echo '{"task_id":"20260427-pool-001","agent":"dev-2","claimed_at":"'$(date -Iseconds)'","reason":"后端 API 修改"}' > ~/Desktop/work/my-agent-teams/tasks/pool/20260427-pool-001/claim.json
```

**Agent 的 CLAUDE.md / AGENT.md 新增指引：**
```markdown
## 任务池
- 当你完成当前任务后，检查 `tasks/pool/` 目录是否有可认领的任务
- 认领前确认：任务在你的能力范围内、与你当前工作不冲突
- 写入 claim.json 后，等待 watcher 确认认领成功
- 不要认领你无法完成的任务
```

#### 4.6.8 与现有流程的兼容性

| 现有流程 | 变更 |
|---------|------|
| PM 直接 dispatch | **不变**，PM 可以跳过池直接派发 |
| create-task.sh | **不变**，新增可选参数 `--pool` 入池 |
| dispatch-task.sh | **不变**，认领后自动走 dispatch 流程 |
| task-watcher.sh | **扩展**，增加 pool/ 轮询和 claim 处理 |
| 看板系统 | **扩展**，新增 pooled 列 |
| agent CLAUDE.md | **扩展**，新增池交互指引 |

#### 4.6.9 Phase 分期

| Phase | 内容 |
|-------|------|
| **Phase 1（立即）** | pool/ 目录 + pooled 状态 + claim.json + watcher 轮询 + agent 手动查看认领 |
| **Phase 2** | agent prompt 自动引导检查池 + 飞书通知池中任务 + 看板 pooled 列 |
| **Phase 3** | Scratchpad 集成（agent 认领前可在 scratchpad 讨论方案）+ 认领协商（多 agent 竞争同一任务时） |

---

## 五、通信与结果确认

### 5.1 消息发送脚本

保留 `tmux-send.sh`，但做两个收敛：

- 长消息走文件 / buffer，不直接依赖单个 shell 参数
- send 成功后只更新 `task.json.status=dispatched`

具体协议：任务初始派发仍依赖 `tmux send-keys`，但 agent 可能处于确认 prompt、thinking 状态或 buffer 满，send-keys 可能被吞或拼接错误。因此"长消息走文件"需要明确实现方式：

- 将任务指令写入 `tasks/{task-id}/instruction.md`
- 通过 tmux send-keys 只发一行引导命令：`cat ~/.openclaw/workspace/tasks/{task-id}/instruction.md`（或等效的 Read 操作）
- 这样 send-keys 只承担"唤醒"职责，实际内容从文件读取，不再依赖 shell 参数传递

#### `instruction.md` 最小模板

`instruction.md` 是任务的动态 prompt 层（见第二十章），由 PM 生成，agent 启动时读取。最小模板如下：

```markdown
# 任务：{title}

## 目标
（一句话说明要做什么）

## 约束
- write_scope: {write_scope}
- 依赖上游任务: {depends_on}（如无则写"无"）
- 禁止修改: {protected paths 提醒}

## 验收标准
1. （具体的、可验证的标准）
2. ...

## 上游产物引用
- 契约文件: {contract_files}（如有）
- Scratchpad 文件: {scratchpad 文件路径}（如有）

## 备注
（PM 认为 agent 需要知道的额外上下文，如有）
```

PM 生成 instruction.md 时，必须填充以上所有带 `{}` 的字段。"约束"和"验收标准"是必填项，"上游产物引用"和"备注"在无内容时可省略。

#### 5.1.1 派发前硬门槛（Dispatch Gate）

仅有 `task.json` 标题和占位 `instruction.md` 不能派发。PM 在调用 `dispatch-task.sh` 前，必须逐项确认以下内容已经明确：

1. **任务类型**：排查 / 方案 / 开发 / 验证 / 集成 / 部署之一。
2. **任务目标**：一句话说清“这次要产出什么”。
3. **任务边界**：明确“不做什么”，避免排查和修复、修复和部署混在一起。
4. **输入事实**：生产现象、上游任务结论、日志、配置项、接口返回、样例数据等，至少给出当前任务真正需要的事实基础。
5. **交付物**：必须写明完成时交什么，例如 `result.json` / `review.md` / `verify.json` / 提交 hash / 部署结果。
6. **验收标准**：必须可验证，禁止写成“看起来正常”“大致可用”。
7. **write_scope 或只读属性**：
   - 开发任务：`write_scope` 不能为空；
   - 只读排查任务：必须显式标注 `read_only=true`（或等效字段），此时 `write_scope=[]` 才合法。
8. **下游动作**：完成后是 review、QA、合入还是部署，PM 必须在派发前就知道下一步要接什么。
9. **环境范围**：dev / prod / 只读生产 / 本地验证，必须明确，不能让 agent 自己猜。
10. **授权状态**：凡涉及生产部署、生产配置、生产数据清理，必须写清是否已获林总工授权。

建议把这 10 项收敛为 `dispatch-checklist`，作为 PM 派发前的固定检查步骤。最重要的硬规则是：

- `instruction.md` 仍包含“（待 PM 填写）”或其它占位语时，**禁止派发**；
- 任务类型未明确时，**禁止派发**；
- 任务目标 / 边界 / 验收标准三者任一缺失时，**禁止派发**。

### 5.2 ACK 机制：文件做事实源，pane 只做调试

这是本轮评审中最明确的收敛点。

**最终决定：**
- `ack.json` 是唯一 ACK 事实源
- pane 中的结构化输出、tmux log 只用于排错和人工调试
- watcher 不再要求"文件 + pane 双确认"才能推进状态

这样做的好处：
- 事实源单一
- 状态判断更简单
- 减少误判和冗余逻辑

### 5.3 真实 diff 校验（核心）

开罗尔的校验必须基于：

```bash
git -C "$WORKTREE" diff --name-only "$BASE_COMMIT"...HEAD
```

最少校验项：
1. 当前工作目录/分支是否正确
2. 是否确实有 diff
3. `result.json.files_modified` 与真实 diff 是否一致
4. 是否越过 `write_scope`
5. 必要时补充文件存在性与测试结果检查
6. `ack.json` / `result.json` 格式合规性检查（字段是否齐全、类型是否正确、task_id 是否匹配）
7. agent 是否在 worktree 之外留下了意外文件变更

> 结论：**verify 以真实 diff 为核心，不再以"声称改了哪些文件"作为主依据。**

LLM agent 不一定会遵守协议——可能忘记写 ack、写出格式错误的 JSON、越过 write_scope。因此 verify 脚本应同时承担"协议合规检查"的职责，而不仅仅是 diff 校验。这是整个方案可靠性的基石。

### 5.4 主动通知机制：文件状态驱动 + 定时兜底（不依赖屏幕输出）

#### 为什么不抓关键词

当前 tmux-watcher 如果继续依赖 pane 输出里的关键词（如“确认提示”“已完成”），会有天然缺陷：

- pane 输出格式不可控（换行、ANSI 颜色码、滚动丢失）
- 不同 agent 输出风格不同，关键词难以穷举
- 上下文 compact 后历史输出会丢
- 本质上是在**非结构化数据里做模式匹配**，稳定性不够

因此，通知机制应当继续坚持：**文件是事实源，屏幕输出只做调试，不做通知判断。**

#### 事件模型

| 事件 | 触发条件 | 通知内容 |
|------|---------|---------|
| 任务派发 | `task.json.status=dispatched` | 📋 已派发给 xxx：任务标题 |
| ACK 确认 | `ack.json` 首次出现或内容更新 | ✅ xxx 已确认收到 |
| 任务完成 | `result.json` 首次出现或内容更新 | ✅ xxx 已完成：摘要 |
| 校验通过 | `verify.json.ok=true` 且签名变化 | 🧪 校验通过，准备合并 |
| 校验失败 | `verify.json.ok=false` 且签名变化 | ❌ 校验失败：原因 |
| 任务超时 | `task.json.status=timeout` | ⚠️ 任务超时，请关注 |
| 任务阻塞 | `task.json.status=blocked` | 🚫 任务阻塞：原因 |
| Owner 审查汇总 | `review-summary.md` 出现且 `review_authority=owner` | 📝 设计审查意见待林总工决策 |
| Agent 离线 | tmux session 不存在（4.1 健康检查触发） | 🔴 xxx 的 session 已丢失，相关任务标记为 failed |

这里的关键变化是：**不是只看“文件是否存在”，而是看“事件签名是否变化”。**

#### 对 `fswatch` 的评估与最终结论

`fswatch` 可以用，但**不能作为唯一可靠性来源**。它更适合做“触发器”，而不是“唯一保证”。

边界情况包括：

1. **重复事件**：一次写入可能触发多次事件
2. **丢事件**：watcher 重启、系统繁忙或事件积压时，可能错过瞬时变化
3. **启动盲区**：watcher 启动前已经落盘的 `ack.json/result.json/verify.json` 不会自动补通知
4. **半写入读取**：如果 agent 直接覆盖写 JSON，watcher 可能在文件未写完时读到脏数据
5. **工具可用性**：`fswatch` 在不同环境安装情况不一定一致，不能假设所有机器都有

**最终方案：**
- `fswatch` 只负责“唤醒一次扫描”
- **定时全量 reconcile** 负责兜底（例如每 5~10 秒扫一次）
- watcher 启动时先做一次**全量补扫**
- `ack.json/result.json/verify.json` 必须采用**原子写入**：先写 `.tmp`，再 `mv`
- 若环境没有 `fswatch`，自动退化为纯轮询模式

#### `.notified` 标记的问题与修正

当前 `.ack_notified/.result_notified/.verify_notified` 的思路不够稳，主要有两个问题：

1. **竞态问题**：多个 watcher 并发运行时，可能同时判断“还没通知”并重复发送
2. **无法表达更新**：例如 `verify.json` 先失败后成功，单个 `.verify_notified` 会把后续成功通知也吞掉

因此，不建议继续使用简单的 `.notified` 空文件做幂等标记。

#### 改进方案：`notify-state.json` + 单实例锁

每个任务目录新增一个 watcher 私有状态文件：

```text
~/.openclaw/workspace/tasks/{task-id}/notify-state.json
```

示例：

```json
{
  "status": "dispatched",
  "ack_sig": "sha256:9d4c...",
  "result_sig": "sha256:ab81...",
  "verify_sig": "sha256:f212...",
  "updated_at": "2026-04-22T10:12:00+08:00"
}
```

规则：
- `task.json` 仍然是业务事实源
- `notify-state.json` 只是 watcher 的**通知去重状态**，不参与业务判断
- 每次扫描时计算当前签名，与 `notify-state.json` 比较
- **只有签名变化才发通知**
- 只读取正式文件，忽略 `*.tmp`
- 对某一条通知，只有在**该条推送成功后**才更新对应签名
- 如果飞书推送失败，**不要更新 `notify-state.json`**，让下一轮 reconcile 自动重试

为了避免多个 watcher 并发重复推送，再增加一个**单实例锁**：

- 推荐 watcher 启动时先抢全局锁（如 `mkdir "$TASKS_DIR/.watcher.lock"` 或 `flock`）
- 抢锁失败说明已有 watcher 在运行，直接退出
- 若进程异常退出留下陈旧锁，启动脚本需支持人工清锁或基于 PID/时间戳做 stale lock 清理

注意：`mkdir` 做锁在进程被 `kill -9` 时不会释放。优先使用 `flock`（进程退出时内核自动释放），`mkdir` 仅作为 `flock` 不可用时的降级方案。如切换为 `flock`：

```bash
exec 200>"$TASKS_DIR/.watcher.lock"
flock -n 200 || { echo "task-watcher already running"; exit 0; }
```

#### 建议的实现方式

```bash
#!/bin/bash
# scripts/task-watcher.sh
# 文件驱动通知：fswatch 负责唤醒，reconcile 负责最终正确性

TASKS_DIR="$HOME/.openclaw/workspace/tasks"
CONFIG_PATH="${CONFIG_PATH:-$HOME/.openclaw/workspace/config/config.json}"
PUSH_SCRIPT="${PUSH_SCRIPT:-$(jq -r '.notifications.push_script' "$CONFIG_PATH" 2>/dev/null)}"
LOCK_FILE="$TASKS_DIR/.watcher.lock"
SCAN_INTERVAL=5

if command -v flock >/dev/null 2>&1; then
  exec 200>"$LOCK_FILE"
  flock -n 200 || {
    echo "task-watcher already running"
    exit 0
  }
else
  mkdir "$LOCK_FILE.dir" 2>/dev/null || {
    echo "task-watcher already running"
    exit 0
  }
  trap 'rmdir "$LOCK_FILE.dir"' EXIT
fi

file_sig() {
  [ -f "$1" ] || return 0
  shasum -a 256 "$1" | awk '{print $1}'
}

update_state_field() {
  field="$1"
  value="$2"
  state_file="$3"

  if [ -f "$state_file" ]; then
    jq --arg f "$field" --arg v "$value" '.[$f] = $v' "$state_file" > "$state_file.tmp"
  else
    jq -n --arg f "$field" --arg v "$value" '{($f): $v}' > "$state_file.tmp"
  fi
  mv "$state_file.tmp" "$state_file"
}

push_once() {
  field="$1"
  current="$2"
  previous="$3"
  message="$4"
  state_file="$5"

  [ -n "$current" ] || return 0
  [ "$current" = "$previous" ] && return 0

  if printf '%s\n' "$message" | "$PUSH_SCRIPT"; then
    update_state_field "$field" "$current" "$state_file"
  fi
}

reconcile_once() {
  for task_dir in "$TASKS_DIR"/*/; do
    [ -d "$task_dir" ] || continue
    task_file="$task_dir/task.json"
    state_file="$task_dir/notify-state.json"
    [ -f "$task_file" ] || continue

    status=$(jq -r '.status // empty' "$task_file" 2>/dev/null)
    ack_sig=$(file_sig "$task_dir/ack.json")
    result_sig=$(file_sig "$task_dir/result.json")
    verify_sig=$(file_sig "$task_dir/verify.json")

    prev_status=$(jq -r '.status // empty' "$state_file" 2>/dev/null)
    prev_ack_sig=$(jq -r '.ack_sig // empty' "$state_file" 2>/dev/null)
    prev_result_sig=$(jq -r '.result_sig // empty' "$state_file" 2>/dev/null)
    prev_verify_sig=$(jq -r '.verify_sig // empty' "$state_file" 2>/dev/null)

    push_once status "$status" "$prev_status" "task status changed: $status" "$state_file"
    push_once ack_sig "$ack_sig" "$prev_ack_sig" "ack arrived" "$state_file"
    push_once result_sig "$result_sig" "$prev_result_sig" "result arrived" "$state_file"
    push_once verify_sig "$verify_sig" "$prev_verify_sig" "verify updated" "$state_file"
  done
}

# 启动后先补扫一次，处理 watcher 重启前遗漏的通知
reconcile_once

# 有 fswatch 就事件触发 + 定时兜底；没有就纯轮询
if command -v fswatch >/dev/null 2>&1; then
  fswatch -o "$TASKS_DIR" | while read _; do
    sleep 0.3  # debounce，等 .tmp -> 正式文件的原子 mv 完成
    reconcile_once
  done &
fi

while true; do
  sleep "$SCAN_INTERVAL"
  reconcile_once
done
```

#### 为什么这个版本更稳

1. **fswatch 只做加速，不做唯一依赖**
2. **启动补扫 + 定时兜底** 可以覆盖重启和漏事件
3. **原子写入 + debounce** 能减少读到半文件的概率
4. **`notify-state.json` 按签名去重**，比 `.notified` 更能处理“同一文件多次更新”
5. **单实例锁** 能避免多 watcher 并发重复推送
6. **推送失败不更新状态**，天然具备重试能力

#### 对 agent 的唯一要求

agent 只需要继续遵守已有约定：

- 写 `ack.json`
- 写 `result.json`
- 由开罗尔写 `verify.json`
- 若是 owner 审查轨道，PM 会额外写 `review-summary.md`
- 所有 JSON 文件都采用 **`.tmp + mv` 原子写入**

不要求 agent 输出任何特定格式的屏幕文本。

#### 对 tmux-watcher 的影响

- tmux-watcher 仍保留，但职责只限于 pane 交互（如自动按 Enter 处理确认提示）
- 主动通知完全由 `task-watcher` 接管
- pane/log 只用于排错，不参与通知事实判断

### 5.5 Watcher 职责汇总

Watcher（task-watcher.sh）是系统的核心守护进程，其职责散布在多个章节中，此处统一列出。

#### 做什么

| 职责 | 来源章节 | 说明 |
|------|---------|------|
| **Agent 健康检查** | 4.1 | 定期检查 tmux session 存活，session 丢失则标记相关任务为 failed |
| **状态推进** | 4.3 | 检测到合规 ack.json → 更新 task.json.status 为 working |
| **通知推送** | 5.4 | 基于 notify-state.json 签名去重，状态变化时推送飞书通知 |
| **取消信号传递** | 16.6 | 检测到 task.json.status=cancelled → 向 agent tmux session 发送中断信号 |
| **超时检测** | 4.3 | dispatched 超过 timeout_minutes 无 ack → 标记为 timeout |

#### 不做什么

- **不做业务判断**——不看代码内容、不评估 diff 质量
- **不做重试决策**——只通知 PM "有任务 failed 了"，重试由 PM 决定（16.3）
- **不解析 pane 输出**——不抓屏幕关键词，只读文件（5.4 核心原则）
- **不写 result.json / verify.json**——这两个分别由 agent 和 integrator/开罗尔写

## 六、选择性 worktree 隔离

### 5.6 tmux-watcher 职责说明

tmux-watcher（`scripts/tmux-watcher.sh`）是权限确认自动处理守护进程，与 task-watcher 互补。

#### 做什么

| 职责 | 说明 |
|------|------|
| **权限确认自动处理** | 每 3 秒轮询所有 tmux session，检测权限确认提示（"Do you want to"、"Allow this tool" 等），自动按 Enter 确认 |
| **飞书通知** | 检测到确认提示时推送飞书通知给林总工 |
| **冷却去重** | 每个 session 10 秒内不重复触发，避免连续按键 |

#### 不做什么

- 不读文件、不做任务状态判断
- 不发送任务指令、不通知 PM
- 不区分 agent 类型（所有 session 一视同仁）

#### 运行方式

```bash
tmux new-session -d -s tmux-watcher "/bin/bash scripts/tmux-watcher.sh"
```

#### 注意事项

- Codex session（omx 启动）需先按 `i` 进入插入模式才能输入消息，tmux-watcher 只处理确认提示不涉及发消息，无此问题
- 重启机器后需手动拉起

### 5.7 task-watcher 职责说明

task-watcher（`scripts/task-watcher.sh`）是任务状态监控守护进程，是系统自动化的核心。

#### 做什么

| 职责 | 触发条件 | 行为 |
|------|---------|------|
| **ack 检测** | dispatched 状态下出现 ack.json | 更新 task.json.status → working |
| **result 检测** | 出现 result.json（status=done） | 更新 status → ready_for_merge，通知 PM，飞书推送 |
| **result 检测** | 出现 result.json（status=blocked） | 更新 status → blocked，通知 PM，飞书推送 |
| **review 检测** | 出现 review.md（通过） | 通知 PM 推进下游任务，飞书推送 ✅ |
| **review 检测** | 出现 review.md（未通过） | 通知 PM 安排修复，飞书推送 ❌ |
| **verify 检测** | 出现 verify.json | 通知 PM 合并或修复 |
| **兜底重发** | dispatched 超 60 秒无 ack | 自动重新发送指令给对应 agent（区分 Codex/Claude Code），飞书推送 🔄 |

#### 通知机制

- **PM 通知**：通过 `tmux send-keys` 发送到 pm-chief session
- **飞书通知**：通过 `feishu-push.sh` 推送给林总工
- **去重**：通过 `.task-watcher/` 目录下的标记文件防止重复通知
- **兜底重发间隔**：至少 120 秒才重发一次

#### Codex vs Claude Code 兼容

兜底重发时自动区分客户端类型：
- **Codex（omx）**：先发 `i` 进入插入模式，再发消息
- **Claude Code**：直接发消息

#### 运行方式

```bash
tmux new-session -d -s task-watcher "/bin/bash scripts/task-watcher.sh"
```

#### 不做什么

- 不做业务判断、不评估代码质量
- 不写 result.json / review.md / verify.json
- 不做重试决策（只通知 PM）
- 不解析 pane 输出（只读文件）

## 六、选择性 worktree 隔离

### 6.1 为什么不再默认 `/tmp`

大蔡指出这一点非常关键:很多项目存在固定路径、运行目录、相对路径加载、脚本 cwd 假设。直接把 worktree 放到 `/tmp`,很容易引出环境偏差。

### 6.2 worktree 路径策略(最终方案)

优先使用**项目同级的固定目录**,而不是 `/tmp`:

```text
{repo_parent}/.openclaw-worktrees/{repo_name}/{task_id}
```

例如:

```text
/Users/lin/Desktop/work/.openclaw-worktrees/chiralium/20260422-001
```

优点:
- 更接近原项目路径结构
- 不易被系统清理
- 相对路径假设更容易保持一致

### 6.3 worktree 不是全量默认,而是按任务选择

#### 适合 worktree 的任务
- 纯代码修改
- 文档修改
- 测试补充
- 与固定运行目录耦合较低的任务

#### 暂不强制 worktree 的任务
- 明显依赖固定绝对路径/固定 cwd 的项目
- 重度依赖本地运行目录的服务联调任务
- 含大量生成文件/本地缓存/环境绑定的任务

这类任务可以先:
- `workspace_mode=main`
- 继续在主工作区执行
- 但仍然遵守 `write_scope` 和 `verify.json` 校验

### 6.4 分歧标注

> **大蔡视角:** 先选择性 worktree,别让路径问题变成新的主故障。
> **架构视角:** 长期仍然应尽量把可隔离任务迁到 worktree。
> **当前落地:** Phase 1 采用"选择性启用",不搞一刀切。

---

## 七、接口契约:先 contract-test 化,再逐步标准化

### 7.1 当前不强推"全量 contract-first"

这是本轮评审的另一个重要收敛点。

**不现实的做法:** 一上来要求所有接口都先写完整 OpenAPI / JSON Schema。
**更现实的做法:** 先把最容易出联调问题的关键接口做成 contract test。

### 7.2 当前推荐的最小做法

优先把高风险接口固化为以下任一形式:

- 契约测试文件,如 `tests/contracts/users.contract.ts`
- 响应 fixture,如 `tests/contracts/fixtures/users-response.json`
- 针对关键字段的 schema 或断言测试

此时 `contract_files` 可以先指向这些测试工件,而不要求都是 OpenAPI 文件。

### 7.3 长期目标(保留架构方向)

当接口稳定、复用增多时,再逐步外显为:

- `OpenAPI`
- `JSON Schema`
- 自动生成的前端类型

推荐演进路径:

```text
contract test / fixture
→ 局部 schema
→ OpenAPI / JSON Schema
→ generated types
```

### 7.4 分歧标注

> **大蔡视角:** 先把 contract-test 跑起来,比补一堆文档更有价值。
> **架构视角:** 长期仍应收敛到统一机器可验契约。
> **当前落地:** 先做"选择性 contract-test 化",不强推全量 OpenAPI 化。

---

## 八、联调与集成流程

### 8.1 integration 分支优先,不直接进 main

统一流程:

```text
task branch
→ integration
→ 自动验证
→ 通过后才考虑 main
```

原因:
- main 尽量保持可发布
- agent 产出需要缓冲区
- 文本 merge 成功 ≠ 真正可联调

### 8.2 联调阶段设唯一集成者

联调阶段只保留一个 **integrator**:

- 只有 integrator 拥有 `integration worktree` 的写权限
- 其他 agent 继续在各自 task worktree 或主工作区工作
- integrator 负责 merge、冲突处理、联调验证和回退决策

> 这条继续保留,因为它是解决"隔离开发后谁来兜底集成"的关键。

#### 冲突处理策略

不同类型的冲突应走不同路径：

| 冲突类型 | 处理方式 | 负责人 |
|----------|---------|--------|
| 纯文本冲突（import 顺序、空行等） | integrator 直接解决 | integrator |
| 语义冲突（同一函数被两人修改） | 打回给原 agent，附带冲突上下文 | 原 agent |
| 契约不兼容（接口签名变更导致） | 升级给 PM，重新协调两个 agent 的契约 | PM |

#### 回滚策略

integration 验证失败后，必须先恢复 integration 分支到已知良好状态，再处理修复：

- integration 验证失败后，integrator **必须先 revert 有问题的 merge commit**，恢复 integration 分支到已知良好状态
- 然后再创建修复任务派发给原 agent
- 原 agent 在自己的 worktree 修复后，重新走 `ready_for_merge → integration` 流程

### 8.3 pre-merge / integration 自动验证

当前应优先落地的验证项:

1. `build`
2. `lint`
3. `unit test`
4. `contract test`(仅针对已固化的关键接口)
5. `smoke test`

说明:
- 这里的 `contract test` 不是要求"全量 OpenAPI 验证"
- 而是先对最关键的跨 Agent 接口跑契约测试

### 8.4 集成失败后的回路

```text
ready_for_merge
→ integrator 先 revert 有问题的 merge（恢复 integration 到已知良好状态）
→ 标记原任务为 failed
→ 新建修复任务
→ 原 agent 在自己的 workspace 修复
→ 再次进入 integration
```

---

## 九、migration / dependency 规则:保留最小约束,不做重治理

大蔡认为这块偏超前,我认同"**不是当前主瓶颈**";但考虑到它们一旦碰到就容易炸,因此文档保留**最小规则**,不展开复杂治理。

### 9.1 仅在任务实际涉及时才标记

如果任务涉及:
- 数据库 schema / migration
- `package.json` / `poetry.lock` / `requirements*.txt` / lockfile

则在 `task.json` 中追加可选字段:

```json
{
  "schema_change": true,
  "dependency_change": false
}
```

### 9.2 当前只做最小约束

- migration 进入 integration 前必须额外跑一次相关检查
- lockfile / dependency 文件视为高冲突资产
- 同一时间尽量只允许一个活跃任务改同一套依赖文件

> 不额外做 dashboard、审批流、复杂策略引擎;先把显式标记和串行约束做起来。

---

## 十、当前不优先做的内容(延后项)

以下内容保留为后续方向,但**不进入当前核心实施清单**:

1. dashboard / TUI 看板
2. 飞书卡片式团队看板
3. OpenAI Agents SDK 分层接入
4. 全量 contract-first 改造
5. 过细状态治理(`merge_status` / `integration_status` / `verification_status` 全拆)
6. 复杂的 migration / dependency 治理平台
7. **多项目支持**——当前方案假设单项目（chiralium）。多项目需要扩展 task.json（加 `project` 字段）、worktree 目录结构、scratchpad 目录和 integration 分支策略。config.json 的 `projects` 字段已预留，但上层还未适配
8. **系统级聚合指标**——基于 transitions 数据做聚合统计：平均任务耗时、agent 利用率、每日完成数、失败率、各阶段停留时长。用于评估系统健康度和 agent 效率，辅助 PM 优化派发策略

### 分歧标注

> **大蔡视角:** 这些都不是当前最大痛点。
> **架构视角:** 长期有价值,但现在做会分散注意力。
> **当前落地:** 延后,不占 Phase 1 / Phase 2 预算。

---

## 十一、实施优先级（基础设施）

> 本章聚焦基础设施的落地顺序。安全与高级特性的优先级见第十八章。

### P0:立刻做

1. `task.json` 最小 schema 落地
2. `ack.json / result.json / verify.json` 落地
3. 基于真实 diff 的 verify 脚本
4. integration 分支与唯一 integrator 流程
5. build / lint / test / smoke 的最小自动验证

### P1:稳定后补上

1. 选择性 worktree 策略与路径配置
2. 高风险接口的 contract-test 化
3. `write_scope` 校验增强
4. 失败任务的重试与保留 worktree 排查

### P2:后续演进

1. 把部分 contract test 外显为 OpenAPI / JSON Schema
2. 更细状态模型
3. dashboard / 飞书卡片看板
4. SDK 分层整合

---

## 十二、跨主机快速复用

### 12.1 目标

一套任务协作系统,能够在多台主机间快速部署复用,只需修改配置文件,不改动任何脚本或逻辑代码。

### 12.2 可移植性分析

| 组件 | 可移植性 | 说明 |
|------|---------|------|
| task.json schema | ✅ 通用 | 纯 JSON,无环境依赖 |
| ack/result/verify.json | ✅ 通用 | 纯数据文件 |
| tmux-send.sh | ✅ 通用 | bash 脚本,任何 *nix 可用 |
| verify 脚本 | ✅ 通用 | 基于 git diff,不依赖具体项目 |
| worktree 路径 | ❌ 主机相关 | 硬编码了 `/Users/lin/Desktop/work/` |
| agent 名称映射 | ❌ 主机相关 | `dcai`/`xcai`/`xke` 写死 |
| 飞书推送配置 | ❌ 主机相关 | 依赖 open_id / webhook |
| 项目路径 | ❌ 主机相关 | 绝对路径 |
| tmux session 名 | ❌ 主机相关 | 各主机 agent 配置可能不同 |

**结论:** 逻辑层天然可移植,需要抽离的是配置层。

### 12.3 配置与逻辑分离

所有主机相关变量收归一份**全局配置文件**：

```json
// ~/.openclaw/workspace/config/config.json
{
  "version": 1,
  "orchestration": {
    "mode": "single_pm",
    "hierarchy_ready": true,
    "root_pm": "pm-chief",
    "integration_owner": "arch-1",
    "domains": {
      "frontend": ["fe-1"],
      "backend": ["be-1"],
      "quality": ["qa-1", "review-1"]
    }
  },
  "agents": {
    "pm-chief": {
      "role": "pm",
      "tmux_session": "pm-chief",
      "home_team": "coordination"
    },
    "fe-1": {
      "role": "frontend_dev",
      "tmux_session": "fe-1",
      "home_team": "frontend"
    },
    "be-1": {
      "role": "backend_dev",
      "tmux_session": "be-1",
      "home_team": "backend"
    },
    "qa-1": {
      "role": "qa",
      "tmux_session": "qa-1",
      "home_team": "quality",
      "can_support": ["frontend", "backend"],
      "borrow_policy": "borrowed_by_task"
    },
    "review-1": {
      "role": "reviewer",
      "tmux_session": "review-1",
      "home_team": "quality",
      "can_support": ["frontend", "backend"],
      "borrow_policy": "borrowed_by_task"
    }
  },
  "domain_policies": {
    "frontend": {
      "default_reviewer": "review-1",
      "default_tester": "qa-1"
    },
    "backend": {
      "default_reviewer": "review-1",
      "default_tester": "qa-1"
    }
  },
  "dispatch_policy": {
    "steps": [
      "domain_match",
      "idle_first",
      "write_scope_no_conflict",
      "fallback_manual_review"
    ]
  },
  "worktree_root": "/Users/lin/Desktop/work/.openclaw-worktrees",
  "notifications": {
    "feishu_open_id": "ou_xxx",
    "push_script": "/Users/lin/.openclaw/workspace/system/scripts/feishu-push.sh"
  }
}
```

### 配置命名规则

- **只有一份全局配置文件叫 `config.json`**，用于组织拓扑、agent 映射、默认 reviewer/tester、dispatch_policy 等全局控制面信息
- **任务级配置不要再叫 `config.json`**，避免和全局配置混淆
- 如果未来某个任务确实需要独立配置，优先两种方式：
  1. 直接嵌到 `task.json` 的扩展字段中
  2. 单独命名为 `task-config.json`

原则：**`config.json` = 全局控制面；`task.json` = 单任务事实源。**

### 12.4 脚本改造原则

所有脚本遵循同一模式:**无硬编码,从 config.json 读变量。**

```bash
#!/bin/bash
# scripts/task-dispatch.sh
# 用法: task-dispatch.sh <config-path> <task-id> <assignee> <message>

CONFIG_PATH="${1:-$HOME/.openclaw/workspace/config/config.json}"
TASK_ID="$2"
ASSIGNEE="$3"
MESSAGE="$4"

# 从配置文件读取
TMUX_SESSION=$(jq -r ".agents[\"$ASSIGNEE\"].tmux_session" "$CONFIG_PATH")
WORKTREE_ROOT=$(jq -r '.worktree_root' "$CONFIG_PATH")
PUSH_SCRIPT=$(jq -r '.notifications.push_script' "$CONFIG_PATH")

# ... 后续逻辑全部使用变量,不硬编码
```

### 12.5 新主机部署流程

目标:**5 分钟内完成部署。**

```bash
# 1. 克隆任务系统
git clone <repo> ~/.openclaw/workspace/tasks/

# 2. 复制配置模板
cp ~/.openclaw/workspace/tasks/config.example.json \
   ~/.openclaw/workspace/config/config.json

# 3. 修改配置(只改与本机相关的值)
vim ~/.openclaw/workspace/config/config.json
#   - agents.*.tmux_session(如果 session 名不同)
#   - worktree_root(改为本机路径)
#   - projects.*.path(改为本机项目路径)
#   - notifications.feishu_open_id(如需推送)

# 4. 验证
bash ~/.openclaw/workspace/tasks/scripts/self-check.sh

# 5. 开始使用
```

### 12.6 自检脚本

部署后运行自检,确认所有配置正确:

```bash
#!/bin/bash
# scripts/self-check.sh
# 检查项:
# - config.json 是否存在且格式正确
# - 各 agent 的 tmux session 是否存在
# - worktree_root 目录是否可写
# - 项目路径是否存在且是 git 仓库
# - 推送脚本是否可执行
# - git remote 是否可达
```

### 12.7 配置模板

提供 `config.example.json` 作为模板,新主机只需 `cp + 改`:

```bash
cp config.example.json config.json
# 只需修改标注了 # TODO 的字段
```

模板中用注释标注哪些是必改项、哪些可以保留默认值。

### 12.8 与 OpenClaw 的关系

- 任务系统不依赖 OpenClaw 运行时
- 可以独立运行在任何有 bash + tmux + git 的主机上
- 如果主机有 OpenClaw,开罗尔自动充当调度器
- 如果没有 OpenClaw,也可以手动调用脚本派发任务

这样即使你在另一台没有装 OpenClaw 的服务器上,这套任务管理照样能用。

注意：config.json 不宜与运行时任务数据混放在同一个 git repo 目录中，否则 git status 会很脏。建议将配置和运行时数据分开：

- `~/.openclaw/workspace/config/` — 配置文件、脚本模板（纳入 git）
- `~/.openclaw/workspace/tasks/` — 运行时任务数据（gitignore 或独立管理）

---

## 十二点九、环境隔离（Phase 1）

当前本机同时存在：
- 开发目录：`~/Desktop/work/chiralium/`
- 生产目录：`~/Desktop/prod/chiralium/`
- 协作系统目录：`~/Desktop/work/my-agent-teams/`

如果不显式建模环境，agent 很容易把“开发任务”和“生产任务”混写到同一套 write_scope 中。因此，Phase 1 先把环境隔离收敛到三个点：

### 12.9.1 projects 注册表

`config.json` 新增 `projects`，显式登记项目边界：

```json
{
  "projects": {
    "chiralium": {
      "dev_root": "/Users/lin/Desktop/work/chiralium",
      "prod_root": "/Users/lin/Desktop/prod/chiralium"
    },
    "my-agent-teams": {
      "dev_root": "/Users/lin/Desktop/work/my-agent-teams",
      "prod_root": "/Users/lin/Desktop/prod/my-agent-teams"
    }
  }
}
```

### 12.9.2 task.json 新增环境字段

Phase 1 新增：
- `project`
- `execution_mode`: `dev | deploy`
- `target_environment`: `dev | prod`

语义：
- `execution_mode=dev`：普通开发任务，只能落在项目 `dev_root`
- `execution_mode=deploy`：部署 / 发布任务，允许触达 `prod_root`，**执行者统一为 `arch-1`**
- `target_environment=prod`：表示目标是生产环境，但**不等于自动允许执行**；仍需单独的 owner 授权字段

### 12.9.3 前置校验：create-task.sh + dispatch-task.sh

环境隔离不能只靠 verify 兜底，必须前移：

1. **create-task.sh**
   - 校验 `project` 是否已注册
   - 校验 `write_scope` 是否在项目边界内
   - 开发任务只允许落在 `dev_root`
   - prod 路径只允许部署类任务触达
   - 若 `execution_mode=deploy` 或 `target_environment=prod`，则 `assigned_agent` 必须是 `arch-1`
   - 同时要求显式补充授权字段，例如：
     - `owner_approval_required=true`
     - `owner_approved_by`
     - `owner_approved_at`

2. **dispatch-task.sh**
   - 派发前再校验一次，防止 task.json 被手工篡改
   - 若 `execution_mode=deploy` 且 `assigned_agent != arch-1`，直接拒绝
   - 若 `target_environment=prod` 且没有 owner 授权信息，直接拒绝
   - 若普通开发任务的 `write_scope` 解析到 `prod_root`，直接拒绝

### 12.9.4 部署约束（Phase 1）

Phase 1 先约束到：
- 生产目录不作为普通开发任务 write_scope
- 生产变更只允许部署 / 发布类任务触发
- **部署执行者固定为 `arch-1`**
- **生产部署必须由林总工明确授权后才能执行**
- 部署统一走 `deploy.sh`（项目脚本），不允许 agent 自己拼 prod 命令乱改目录

> `source_commit`、回滚策略、deploy_runner 等更细设计，留到 Phase 2 再补。

## 十三、安全与权限控制

> 参考 Claude Code 五层纵深防御模型（详见第十九章附录），本方案在当前 tmux + 文件系统架构下落地可行的安全层。

### 13.1 保护路径清单（P0）

以下路径属于系统核心资产，任何 agent 的 diff **不得触碰**。verify 脚本对这些路径做**硬拒绝**——只要 `git diff` 输出中出现以下路径，`verify.json.ok` 直接为 `false`，不进入后续校验。

```json
{
  "protected_paths": [
    ".git/**",
    ".claude/**",
    "tasks/*/task.json",
    "tasks/*/verify.json",
    "tasks/*/notify-state.json",
    "config.json",
    "scripts/**",
    "prompts/**"
  ]
}
```

放置位置：`config.json` 顶层字段，所有 verify 脚本启动时读取。

校验逻辑伪代码：

```bash
# verify 脚本中的保护路径检查
PROTECTED=$(jq -r '.protected_paths[]' "$CONFIG_PATH")
CHANGED=$(git -C "$WORKTREE" diff --name-only "$BASE_COMMIT"...HEAD)

for file in $CHANGED; do
  for pattern in $PROTECTED; do
    if matches "$file" "$pattern"; then
      echo "REJECT: $file matches protected pattern $pattern"
      write_verify_fail "protected path violation: $file"
      exit 1
    fi
  done
done
```

**重要澄清：** 此保护针对的是 **agent 的 git diff 产出**——即 agent 在 worktree 中的代码提交不得包含对这些路径的修改。它**不限制** watcher/PM 通过文件系统直接操作这些文件（例如 watcher 写 task.json.status、PM 写 pm-state.json）。两者的区别在于：agent 的修改走 git，由 verify 脚本拦截；watcher/PM 的修改是系统级操作，不经过 verify。

**为什么是硬检查而不是软警告：** 保护路径的修改一旦漏过，可能导致任务状态被篡改（task.json）、自动化脚本被注入（scripts/）、git 状态被破坏（.git/）、角色权限被篡改（prompts/）。这些后果不可逆，必须在 verify 层硬拦截。

### 13.2 Agent 不可自改 task.json 关键字段（P0）

Agent 在任务执行过程中，**只能写以下文件**：

| 文件 | 谁写 | 说明 |
|------|------|------|
| `ack.json` | agent | 确认收到任务 |
| `result.json` | agent | 报告完成结果 |
| 业务代码（write_scope 内） | agent | 实际开发产出 |

Agent **不可修改**的 task.json 字段：

| 字段 | 原因 |
|------|------|
| `status`（终态：done/cancelled） | 终态只能由 PM/integrator 设置 |
| `assignee` | agent 不能把任务转给别人 |
| `write_scope` | agent 不能扩大自己的写权限 |
| `timeout_minutes` | agent 不能给自己延时 |
| `base_branch` / `target_branch` | agent 不能改变集成目标 |

**执行机制：** verify 脚本在校验时，对比 task.json 的当前内容与 `base_commit` 时的内容。如果 agent 的 diff 中包含对 task.json 的修改，直接拒绝。这与 13.1 的保护路径机制一致——task.json 已在保护路径清单中。

> 注意：agent 写 `result.json` 时可以声明 `status: "ready_for_merge"`，但这**不等于直接修改 task.json.status**。watcher/PM 读取 result.json 后，由 watcher/PM 去更新 task.json.status。

### 13.3 Handoff 语义审查（P0）

当任务状态从 `working` 变为 `ready_for_merge` 时，PM 不能只看 verify.json 的机械校验结果，还需做**轻量级语义审查**：

| 审查项 | 说明 | 审查方式 |
|--------|------|---------|
| **diff 大小合理性** | 一个小需求产出 2000 行 diff 明显异常 | PM 对比任务描述与 diff 规模 |
| **文件范围合理性** | 只要求改 API，却改了数据库迁移文件 | PM 检查 diff 文件列表 vs 任务描述 |
| **测试覆盖** | 有新增代码但无新增/修改测试 | PM 检查 diff 中是否包含 test 文件 |
| **遗留调试代码** | console.log、print、TODO HACK 等 | PM 做关键词扫描 |

**实现方式：** PM 在 `ready_for_merge` 时调用一个语义检查脚本（`scripts/semantic-review.sh`），输出审查报告。PM 根据报告决定是否放行或打回。

```text
ready_for_merge
→ verify.json 机械校验（自动）
→ PM 语义审查（半自动）
→ 通过 → 进入 integration
→ 不通过 → 打回给 agent，附带审查意见
```

### 13.4 Permission Mode 与沙箱（P2 长期方向）

当前架构下，agent 的权限控制依赖：
- **文件层**：write_scope + verify 硬检查（已有）
- **进程层**：tmux session 隔离（已有）
- **角色层**：CLAUDE.md / AGENTS.md 中的角色 prompt（软约束）

长期应向以下方向演进：

1. **Permission Mode 分级**：
   - `strict`：agent 每次写操作都需要 PM 确认（类似 Claude Code 的 plan mode）
   - `normal`：write_scope 内自由写，scope 外拒绝（当前方案）
   - `permissive`：信任模式，仅做事后审计（适用于成熟 agent）

2. **沙箱执行环境**：
   - 将 agent 的命令执行放入容器/沙箱，限制文件系统访问、网络访问、进程创建
   - 这需要基础设施支持（Docker / gVisor / Firecracker），不适合 Phase 1

3. **工具级权限过滤**：
   - 结合 16.8 的渐进式工具过滤，在 agent 启动时注入角色对应的工具白名单
   - 当前通过 CLAUDE.md / AGENTS.md 配置实现，长期可通过 hooks 做运行时拦截

---

## 十四、Agent 角色分工与协作模式

### 14.1 层级结构

```text
林总工（决策者）
  │
  ▼
开罗尔（助手）— 理解意图、传达反馈、日常沟通、信息过滤
  │
  ▼
PM Agent — 需求分析、任务拆解、角色分配、进度跟踪、异常处理
  │
  ├── 架构师（小蔡）— 方案设计、技术选型、文档规范
  ├── 后端开发（大蔡）— API、数据库、业务逻辑实现
  ├── 前端开发（待定）— 页面、组件、样式、接口联调
  └── 审查者（小克）— 代码审查、文档审阅、测试建议
```

### 14.2 各角色职责边界

| 角色 | 做什么 | 不做什么 |
|------|--------|---------|
| **林总工** | 提需求、做决策、验收最终成果 | 不关心任务怎么拆、谁来做 |
| **开罗尔** | 理解意图并翻译给 PM、PM 产出把关后呈现给林总工、日常沟通、信息过滤 | 不写业务代码、不做任务调度 |
| **PM Agent** | 分析需求、拆解任务、分配角色、跟踪进度、处理异常、初步验收 | 不写代码、不直接跟林总工对话 |
| **架构师** | 方案设计、技术选型、文档规范、契约文件编写（contract test / schema）、集成与部署执行（在已获授权时） | 不承担日常业务实现，不替代 reviewer 做代码审查 |
| **后端开发** | API 实现、数据库、业务逻辑 | 不做架构决策、不审方案 |
| **前端开发** | 页面开发、组件实现、样式、接口联调 | 不碰后端 API 实现 |
| **审查者** | 代码审查、文档审阅、测试建议 | 不自己写代码、不负责合入或部署、不做技术决策 |

### 14.3 核心协作规则

**1. 角色不交叉**
- 架构师不写业务代码，开发不做架构决策，审查者不改代码
- 每个角色只做自己职责范围内的事

**2. 审者不改**
- 审查者发现问题只提建议，不动手修改
- 修改由对应角色的 agent 执行，修改后再审

**3. 沟通分阶段：调度仍归 PM，技术讨论可直连**
- **A-Lite 启用前**：agent 之间不直接对话，统一经 PM 中转
- **A-Lite 启用后**：技术讨论允许通过 `chat/general` / `chat/tasks/{task-id}.jsonl` 直接发生，PM 不再中转每条消息
- 但无论哪个阶段：
  - 任务状态事实源仍然只能是 `tasks/`
  - 调度裁决权仍归 PM
  - 关键结论必须回写 `tasks/` 或 `features/<feature-id>/notes/*`，不能只留在 chat 里
- PM 汇总状态后向开罗尔汇报
- 开罗尔过滤和整理后向林总工汇报
- 开罗尔传给 PM 的交接物必须是结构化的需求描述（而非自然语言聊天记录），至少包含：目标、约束、优先级、验收标准

**4. 专业对口审**
- 代码 → 审查者（review-1）审
- 方案/架构 → 架构师（arch-1）审
- 集成 / 部署 → 架构师（arch-1）执行（生产部署仍需林总工授权）
- PM 不做技术审，只做进度和质量把控

**5. 一次介入原则**
- 一个任务在同一个 agent 手里只走一遍，不反复来回
- 审查者提意见 → 开发改一次 → 审查者确认，最多两轮
- 对于明显的格式/typo/import 缺失等问题，审查者可标注为 `auto-fixable`，由自动化脚本（如 lint --fix）处理，不占用审查轮次

### 14.4 典型工作流

```text
林总工："开发一个用户管理模块"
  │
  ▼
开罗尔：理解需求，传达给 PM
  │
  ▼
PM：分析需求，输出任务清单
  ├── T1: 架构师 → 设计数据库和 API 接口（输出 docs/ + contract）
  ├── T2: 后端开发 → 实现 CRUD API（依赖 T1 的 contract）
  ├── T3: 前端开发 → 实现用户列表页（依赖 T1 的 contract）
  └── T4: 审查者 → 审查代码（依赖 T2、T3）
  │
  ▼
PM 按依赖顺序派发，跟踪进度
  │
  ▼
PM 初步验收 → 开罗尔把关 → 林总工确认
```

### 14.4.1 生产问题四件套排查模板

凡是 AI / 搜索 / 第三方能力 / 生产故障类问题，PM 拆排查任务时默认必须同时要求 agent 检查以下四类事实：

1. **代码实现**：当前链路实际走哪条代码路径，最近是否有回退 / 旧实现未清理。
2. **生产配置**：环境变量、数据库配置、provider 配置、feature flag 是否与代码契约一致。
3. **运行时接口返回**：真实线上接口 / 健康探针 / capability 接口此刻返回什么，而不是只看代码猜测。
4. **上游依赖状态**：第三方接口是否退化、限流、鉴权失败、短时抖动，是否会放大为用户感知故障。

排查任务的 `result.json` 建议固定输出：
- 根因分类
- 证据
- 影响范围
- 是否代码问题
- 是否配置问题
- 是否上游问题
- 推荐后续动作

如果这四件套没有同时覆盖，排查任务就容易把“代码问题 / 配置问题 / 上游问题”混在一起，导致后续修复走偏。

### 14.4.2 超时提醒后的 PM 介入 SOP

watcher 报警本身不是处理，PM 收到“working 超过 N 分钟”提醒后必须有固定动作：

```text
1. 先看 ack.json / result.json 是否缺失
2. 再看 instruction.md 是否充分、目标是否变更过
3. 判断当前卡点属于哪类：
   - 信息不足
   - 权限不足
   - 环境问题
   - 实现复杂度过高
   - 下游阻塞（review / QA / 集成未接续）
4. 立即做一个动作，而不是只等待：
   - 补 instruction
   - 缩小任务边界
   - 拆子任务
   - 改派 / 升级人工仲裁
```

默认规则：
- 超时提醒不是“提醒一下就结束”，而是进入 **PM 介入态**；
- PM 介入后必须在 `transitions.jsonl` 或 task 备注中留下动作记录，便于事后追溯“为什么卡住、PM 做了什么”。

### 14.5 为什么需要独立的 PM Agent

当前开罗尔同时承担五项职责：理解需求、拆任务、派发、盯进度、汇报。每项都做不精。

引入 PM 后：
- **开罗尔** 专注做"人"的事——理解意图、沟通协调、信息过滤
- **PM** 专注做"流程"的事——任务管理、进度跟踪、质量把控
- **各 agent** 专注做"专业"的事——只管自己角色范围内的工作

### 14.6 PM Agent 的实现

短期：tmux agent 方式，跟现有大蔡/小蔡/小克类似
中期：迁移到 OpenAI Agents SDK，利用其 Handoff 和 Tracing 能力
长期：考虑 Sandbox Agent + 自主调度

PM 的核心工具：
- 读/写 `tasks/` 目录（任务状态管理）
- 读取 config.json（agent 角色映射、项目配置）
- 调用飞书推送（状态变化通知开罗尔）
- 读 git 状态（代码变更跟踪）

**PM Agent 实现注意事项：**

#### PM 派发决策流程（结构化匹配）

PM 派发任务时，不应凭记忆拍脑袋指定 agent，而要按固定流程做选择：

```text
0. 先过 Dispatch Gate：任务类型 / 目标 / 边界 / 输入事实 / 交付物 / 验收标准 / write_scope / 环境 / 下游动作 / 授权状态 全部明确
1. 读取 config.json，获取 agent 列表、domains、default reviewer/tester、dispatch_policy
2. 读取当前活跃 task.json，判断各 agent 当前是否已有 working/dispatched 任务
3. 按 task.domain 匹配候选 agent（domain_match）
4. 在候选里优先选 idle agent（idle_first）
5. 检查 write_scope 是否与当前活跃任务冲突（write_scope_no_conflict）
6. 按任务 archetype 补全任务属性：
   - 排查任务：只读、不可顺手修复
   - 开发任务：write_scope 非空
   - 验证任务：明确验证对象和结论产物
   - 集成 / 部署任务：明确授权来源和目标环境
7. 选出 assignee，并同时确定：
   - review_required / reviewer
   - test_required / default_tester
   - 完成后的下游动作（review / QA / 合入 / 部署）
8. 若没有安全候选，进入 `blocked` 或交由 PM 人工决策（fallback_manual_review）
```

最小原则：
- `assigned_agent` 必须唯一
- `review_required` 和 `test_required` 在拆任务时就定好
- PM 在派发前必须先读当前任务事实源，不依赖自己记忆“谁正忙”
- `instruction.md` 仍包含占位语或缺少验收标准时，禁止派发

PM 需要同时跟踪多个任务状态、做依赖分析、判断派发时机，这需要长期记忆和复杂推理。但 Claude Code 在长时间运行后会 compact 上下文，PM 很可能丢失之前的任务记忆。应对措施：

- PM 每次做决策前，**必须重新读取所有活跃任务的 task.json**，不依赖对话记忆
- PM 的"初步验收"范围明确为：跑测试、检查 diff 大小合理性、确认 verify.json 通过
- PM 维护一个 `pm-state.json` 文件，持久化当前需求的拆解结果和派发计划，避免 compact 后丢失全局视图

### 14.7 PM 容灾与状态恢复（P1）

PM Agent 在长时间运行中可能因上下文 compact、tmux session 崩溃、主机重启等原因丢失状态。`pm-state.json` 是 PM 的持久化记忆，PM 启动/恢复时必须从此文件重建全局视图。

#### `pm-state.json` 最小 schema

```json
{
  "version": 1,
  "active_requirement": {
    "id": "REQ-20260422-001",
    "title": "用户管理模块",
    "source": "林总工",
    "received_at": "2026-04-22T09:00:00+08:00",
    "acceptance_criteria": ["CRUD API 可用", "单元测试覆盖", "契约测试通过"]
  },
  "task_plan": [
    {
      "task_id": "20260422-001",
      "title": "设计数据库和 API 接口",
      "assignee": "xcai",
      "depends_on": [],
      "planned_order": 1
    },
    {
      "task_id": "20260422-002",
      "title": "实现 CRUD API",
      "assignee": "dcai",
      "depends_on": ["20260422-001"],
      "planned_order": 2
    }
  ],
  "dispatch_cursor": "20260422-001",
  "last_decision": {
    "at": "2026-04-22T09:35:00+08:00",
    "action": "dispatch",
    "detail": "派发 T1 给架构师"
  },
  "updated_at": "2026-04-22T09:35:00+08:00"
}
```

#### 多 PM 扩展说明（与第二十一章衔接）

当前 14.7 的恢复协议以单 PM 为主；当第二十一章中的分层 PM 启用后，恢复顺序扩展为：

1. **root / program PM** 先恢复全局组织视图
2. **子 PM / domain PM** 再恢复本域活跃任务
3. **integrator / quality PM** 恢复 integration queue / review queue
4. **orphan task reclaim**：若 `owner_pm` 不在线且 lease 过期，则由上层 PM 临时接管

原则不变：`task.json` 永远比 `pm-state.json` 更权威。

#### PM 启动恢复协议

```text
PM 启动（新启动或 compact 后恢复）
→ 1. 读取 pm-state.json，恢复需求上下文和派发计划
→ 2. 扫描所有 tasks/*/task.json，获取各任务当前真实状态
→ 3. 对比 pm-state.json 的计划与 task.json 的实际状态
     - 计划中 pending 但实际已 working → 正常，继续监控
     - 计划中 dispatched 但实际已 failed → 需要重试决策
     - 计划中无记录但 tasks/ 下存在 → 可能是人工创建，纳入跟踪
→ 4. 恢复后立即做一次全量 reconcile，推进可派发的任务
→ 5. 更新 pm-state.json
```

**关键原则：pm-state.json 是计划，task.json 是事实。两者冲突时，以 task.json 为准。**

### 14.8 Agent 启动初始化协议（P1）

每个 agent（包括 PM）在 tmux session 中启动时，必须执行以下初始化序列：

```text
Agent 启动
→ 1. 读取 config.json，确认自身角色、权限、项目配置
→ 2. 注入角色 prompt（从 CLAUDE.md / AGENTS.md 加载角色定义）
→ 3. 扫描 tasks/ 目录，查找 assignee 为自己的任务
     - 有 status=working 的任务 → 恢复执行（读取 task.json + instruction.md）
     - 有 status=dispatched 的任务 → 写 ack.json，开始执行
     - 无任务 → 进入待命状态，等待新任务派发
→ 4. 确认 worktree 状态（如果是 worktree 模式）
     - worktree 存在 → 切换到 worktree 继续工作
     - worktree 不存在但任务要求 worktree → 重新创建
→ 5. 输出启动确认日志（写入 tasks/.agent-boot/{agent-id}.json）
```

启动确认文件格式：

```json
{
  "agent": "dcai",
  "booted_at": "2026-04-22T09:30:00+08:00",
  "role": "后端开发",
  "resumed_tasks": ["20260422-002"],
  "config_version": 1
}
```

watcher 检测到 agent-boot 文件后，可用于确认 agent 已就绪。

---

## 十五、通信模型与 Scratchpad

> 本章确立 agent 间通信的架构选择：PM 中转为主，Scratchpad 异步共享为辅。

### 15.1 通信架构选择

**结论：PM 中转 + Scratchpad 异步共享。**

在多 agent 协作中，通信模型有两个极端：
- **全连接**：agent 之间直接通信（N×N 通道）
- **星形中转**：所有通信经过 Coordinator（PM）

本方案选择**星形中转**，理由如下：

| 维度 | 全连接 | PM 中转 | 本方案选择 |
|------|--------|---------|-----------|
| 通信复杂度 | O(N²) | O(N) | ✅ PM 中转 |
| 信息一致性 | 难保证，各 agent 视图不同 | PM 是唯一信息汇聚点 | ✅ PM 中转 |
| 权限控制 | 需要 agent 间互信 | PM 做访问控制网关 | ✅ PM 中转 |
| 延迟 | 直接通信更快 | 多一跳 | ⚠️ 全连接（但可接受） |
| PM 单点故障 | 无 | PM 挂了全停 | ⚠️ 需容灾（见 14.7） |
| 可观测性 | 分散，难追踪 | PM 天然是审计节点 | ✅ PM 中转 |

**但有一个场景 PM 中转不够用**：agent 之间需要共享中间产物（如架构师产出的契约文件需要被开发 agent 读取）。这类共享如果全走 PM 转发，PM 会变成瓶颈。因此引入 Scratchpad 作为补充。

### 15.2 Scratchpad 形式化定义（P1）

Scratchpad 是一个**按任务组共享的异步读写区域**，用于 agent 之间共享中间产物，无需经过 PM 转发。

#### 目录结构

```text
tasks/.scratchpad/{task-group-id}/
├── {source-agent}_{artifact-name}.{ext}
├── {source-agent}_{artifact-name}.{ext}
└── ...
```

`task-group-id` 是一组相关联任务的共同标识（通常等于 PM 拆解的需求 ID，如 `REQ-20260422-001`）。

示例：

```text
tasks/.scratchpad/REQ-20260422-001/
├── xcai_api-schema.json          # 架构师产出的 API schema
├── xcai_db-design.md             # 架构师产出的数据库设计
├── dcai_integration-notes.md     # 后端开发的集成备注
└── xke_review-findings.md        # 审查者的审查发现
```

#### 读写规则

| 操作 | 谁可以 | 条件 |
|------|--------|------|
| **创建目录** | PM | PM 拆解需求时创建 |
| **写入文件** | PM 或被分配到该 task-group 的 agent | 文件名必须以 `{自己的agent-id}_` 为前缀 |
| **读取文件** | PM 或被分配到该 task-group 的任何 agent | 只读，不能修改他人文件 |
| **删除/清理** | PM | 需求完成后由 PM 统一清理 |

#### 命名约定

- 文件名前缀 = 产出者的 agent-id，防止覆盖冲突
- agent 只能写以自己 id 为前缀的文件
- 写入同样采用 `.tmp + mv` 原子写入

#### 清理策略

- 需求完成（所有关联任务 done/cancelled）后，PM 将 scratchpad 目录归档到 `tasks/.scratchpad-archive/{task-group-id}/`
- 归档保留 7 天后自动删除（由 task-cleanup.sh 处理）
- 活跃需求的 scratchpad 不做自动清理

### 15.3 Scratchpad 消息通知触发机制

> Scratchpad 解决了"agent 之间如何共享信息"，但还需要解决"agent 如何知道有新信息"。

#### 设计选择：三路并行，统一去重

同时实施三种通知机制，覆盖不同场景，并通过统一的去重文件防止重复打扰 agent：

| 机制 | 实时性 | 触发条件 | 覆盖场景 |
|------|--------|---------|---------|
| **Agent 主动检查** | 低 | 任务间隙（agent 自觉） | agent 正在活跃工作时 |
| **tmux-watcher 空闲提醒** | 中 | session 空闲 60s + 有新 scratchpad | agent 空闲但忘了检查 |
| **task-watcher 轮询通知** | 高 | 每 5s 轮询 + 发现新文件 | 确保不漏，兜底保障 |

**三路之间的关系：不是互为 backup，而是互补。** Agent 主动检查最快但不可靠（依赖 LLM 记得）；tmux-watcher 在 agent 空闲时补位；task-watcher 作为兜底确保 100% 不漏。

#### 统一去重机制

三路通知共享同一个去重状态文件，防止同一个文件被多次推送给同一个 agent：

```text
.omx/scratchpad-notified.json
```

**去重规则：**

1. **每个通知源在发送前必须先检查此文件**：如果目标文件已存在于该 agent 的已通知列表中，**跳过通知**。
2. **写入时使用 flock 文件锁**：防止 tmux-watcher 和 task-watcher 同时读写产生竞态。
3. **写入后立即生效**：下一个通知源读到的就是最新状态。
4. **Agent 主动检查不算"通知"**：agent 自己读到文件不算被通知，不写入去重文件。只有 watcher 发送了 tmux 消息才记录。

```json
{
  "_meta": {
    "version": 1,
    "updated_at": "2026-04-27T11:20:00+08:00"
  },
  "dev-2": {
    "REQ-20260422-001_arch-1_api-schema.json": {
      "notified_at": "2026-04-27T11:00:00+08:00",
      "notified_by": "tmux-watcher"
    }
  },
  "dev-1": {
    "REQ-20260422-001_arch-1_db-design.md": {
      "notified_at": "2026-04-27T11:05:00+08:00",
      "notified_by": "task-watcher"
    }
  }
}
```

字段说明：
- `_meta.version`：格式版本号，便于未来迁移
- `notified_at`：通知时间
- `notified_by`：`tmux-watcher` / `task-watcher`，便于调试

**去重检查伪代码（所有通知源共用）：**

```bash
should_notify() {
  local agent_id="$1"
  local file_key="$2"   # 格式: {task-group-id}_{source-agent}_{filename}
  local notifier="$3"   # 调用者标识

  # flock 防竞态
  (
    flock -x 200
    # 检查是否已通知
    if jq -e ".\"$agent_id\".\"$file_key\"" "$NOTIFIED_JSON" > /dev/null 2>&1; then
      echo "SKIP: already notified"
      return 1
    fi
    # 写入通知记录
    jq --arg agent "$agent_id" \
       --arg key "$file_key" \
       --arg time "$(date -Iseconds)" \
       --arg by "$notifier" \
       '.[$agent][$key] = {"notified_at": $time, "notified_by": $by}' \
       "$NOTIFIED_JSON" > "${NOTIFIED_JSON}.tmp" && mv "${NOTIFIED_JSON}.tmp" "$NOTIFIED_JSON"
    echo "NOTIFY"
    return 0
  ) 200>"${NOTIFIED_JSON}.lock"
}
```

#### 机制一：Agent 主动检查

在每个 agent 的 CLAUDE.md / AGENT.md 中新增规则：

```markdown
## Scratchpad 检查
- 每次完成当前任务后（写出 result.json 之后），检查 `tasks/.scratchpad/` 是否有给你的新文件
- 检查方式：`ls tasks/.scratchpad/*/{其他agent-id}_*`，查看是否有你不认识的文件
- 如果发现新文件，读取内容并判断是否需要响应
- 如果需要响应，在你的目录下写入回复文件（以自己的 agent-id 为前缀）
- 注意：主动检查不算"被通知"，不需要写入 scratchpad-notified.json
```

**特点：** 最轻量，零基础设施，但依赖 LLM 遵守 prompt。适合 agent 正在活跃工作时，任务间隙自然检查。

#### 机制二：tmux-watcher 空闲提醒

扩展 tmux-watcher.sh，在现有职责基础上新增 scratchpad 检查：

```text
现有职责：检测确认提示 → 自动按 Enter
新增职责：检测 session 空闲 → 检查 scratchpad → 去重 → 有新消息则提醒

触发条件（全部满足才触发）：
- agent session 连续 60 秒无新输出（空闲状态）
- tasks/.scratchpad/ 下存在该 agent 所属 task-group 的新文件
- 新文件未被去重文件记录为已通知

提醒方式：
- tmux send-keys 发送："📋 Scratchpad 有新消息，请检查 tasks/.scratchpad/{task-group-id}/"
- 调用 should_notify() 写入去重记录
```

**特点：** 复用现有 tmux-watcher 进程，不新增常驻服务。只在 agent 空闲时提醒，避免打断正在工作的 agent。

#### 机制三：task-watcher 轮询通知

扩展 task-watcher.sh，在现有任务状态轮询基础上新增 scratchpad 轮询：

```text
现有职责：轮询 tasks/*/ 状态文件 → 自动状态流转 → 通知 PM
新增职责：轮询 tasks/.scratchpad/ → 发现新文件 → 去重 → 通知目标 agent

轮询逻辑（每 5 秒）：
1. 扫描 tasks/.scratchpad/*/ 下所有文件
2. 对每个文件，根据文件名前缀排除写入者自身（arch-1 写的文件不需要通知 arch-1）
3. 根据 config.json 的 task-group → agent 分配关系，确定应该通知哪些 agent
4. 对每个目标 agent，调用 should_notify() 检查去重
5. 未通知过的 → tmux send-keys 通知 + 写入去重记录

通知消息格式：
"📋 [{source-agent}] 在 {task-group-id} 中写入了新文件: {filename}"
```

**特点：** 最可靠，确保不漏。task-watcher 已经在 5s 轮询，加一个目录扫描的开销很小。

#### 三路时序关系示例

```text
T+0s   arch-1 写入 tasks/.scratchpad/REQ-001/arch-1_api-schema.json

T+3s   dev-2 正好完成任务，主动检查 scratchpad → 发现新文件 → 直接读取 ✅
       （不需要任何 watcher 通知）

T+30s  task-watcher 轮询发现新文件
       → should_notify(dev-2, ...) → 检查去重文件 → dev-2 还没被通知过
       → 通知 dev-2 → 写入去重记录 ✅

T+45s  tmux-watcher 检测到 dev-2 session 空闲 + 有新 scratchpad
       → should_notify(dev-2, ...) → 检查去重文件 → 已被 task-watcher 通知过
       → 跳过 ✅（不重复打扰）

T+60s  task-watcher 下一轮轮询
       → should_notify(dev-2, ...) → 已通知 → 跳过 ✅
```

**去重保障：** 无论哪个 watcher 先到，去重文件确保同一个文件只被通知一次。三路并行 = 三个机会窗口，但 agent 只被打扰一次。

#### 通信流程示例

```text
1. arch-1 完成 API 设计，写入 scratchpad
   tasks/.scratchpad/REQ-20260422-001/arch-1_api-schema.json

2. task-watcher 在 5s 内检测到新文件
   → 通知 dev-2（tmux send-keys）+ 写入去重记录

3. dev-2 读取 api-schema.json → 开始基于 schema 开发后端 API

4. dev-2 开发中遇到问题，写入 scratchpad
   tasks/.scratchpad/REQ-20260422-001/dev-2_db-question.md

5. task-watcher 检测到新文件 → 通知 arch-1 + 写入去重记录

6. arch-1 读取问题 → 回复
   tasks/.scratchpad/REQ-20260422-001/arch-1_db-answer.md

7. task-watcher 检测到回复 → 通知 dev-2（如 dev-2 之前已主动检查则跳过）
```

### 15.4 场景分析

#### 场景一：延迟容忍

> 架构师完成 API 设计后，后端开发需要尽快拿到 schema。

- **PM 中转模式**：架构师 → result.json → PM 读取并转发给开发 → 开发开始工作。延迟取决于 PM 的轮询/响应速度。
- **Scratchpad 模式**：架构师直接将 schema 写入 scratchpad → PM 通知开发"schema 已就绪" → 开发直接从 scratchpad 读取。PM 只做通知，不做内容转发。
- **结论**：对于大文件/复杂产物，Scratchpad 更高效。PM 仍然控制"何时通知"，但不搬运内容。

#### 场景二：PM 崩溃

> PM 的 tmux session 意外退出。

- **影响**：新任务无法派发，状态无法推进，但**已在执行的 agent 不受影响**（agent 读的是 task.json 和 scratchpad，不依赖 PM 在线）。
- **恢复**：PM 重启后按 14.7 的恢复协议重建状态。Scratchpad 中的文件不受 PM 崩溃影响（纯文件系统）。
- **结论**：PM 崩溃的爆炸半径有限——正在执行的任务继续，只是新任务和状态推进暂停。这是星形架构可接受的代价。

#### 场景三：Agent 扩展（3 → 5 个 agent）

> 团队扩展，新增两个 agent。

- **全连接**：通信通道从 3×2=6 条增加到 5×4=20 条，复杂度暴增。
- **PM 中转**：新增 agent 只需在 config.json 注册，PM 的通信通道从 3 条增加到 5 条，线性增长。
- **Scratchpad**：新 agent 自动获得所属 task-group 的 scratchpad 读写权限，无需额外配置。
- **结论**：星形架构的扩展成本远低于全连接。

> **当前状态说明：** 15.4 Scratchpad 属于上一版通信思路保留章节，用于解释历史设计与对比取舍；当前执行主线已转向 15.5 的 Chat Hub A-Lite，Scratchpad 不再作为优先落地方案。

---

## 十五点五、公共消息区（Chat Hub）——从星形中转到共享空间

> **设计动机**：v12 及之前的方案中，所有 agent 间通信必须经过 PM 中转（第十五章"PM 中转 + Scratchpad 为辅"）。
> 实践发现：PM 中转是整个协作链路的**最大瓶颈**——PM 忙时消息积压、PM 不主动时流程停滞、
> Scratchpad 机制复杂但未落地。需要一种更简单、更直接的通信方式。
>
> **核心转变**：先从"PM 中转"升级为"共享空间"。  
> 第一阶段只解决**直接沟通**问题，不立刻把任务认领状态机迁入 chat。PM 从中转站变成参与者（有调度权限），agent 之间可以直接通信，PM 可见所有消息但不需要参与每一条；任务状态事实源仍保持在 `tasks/`。

### 15.5.1 架构对比

```
v12（星形中转）：
  agent-A → PM → agent-B     （每条消息都要 PM 转发）
  林总工 → 开罗尔 → PM → dev  （指令链路长）

v13 A-Lite（共享空间 Lite 版）：
  agent-A → chat/ → agent-B     （直接通信，PM 可见）
  林总工 → 开罗尔 → chat/      （所有 agent 可见）
  PM → chat/tasks/ 发任务公告   （仅公告/讨论，真实派发仍走 task.json）
```

### 15.5.2 目录结构

```text
my-agent-teams/
├── chat/                       # 公共消息区（与 tasks/ scripts/ 平级）
│   ├── general/                # 公共频道，所有 agent 可见可发
│   │   └── 2026-04-27.jsonl   # 按天分文件，便于归档和追溯
│   ├── tasks/                  # 任务相关讨论
│   │   └── {task-id}.jsonl     # 每个任务一个讨论串
```

> 注意：**A-Lite 阶段不做私聊目录 `chat/agents/`，也不把真实任务目录物理迁入 `features/` 或 `chat/`**。  
> `tasks/` 继续作为状态事实源，`chat/` 只承载消息流；二者通过 `task_id` / `feature_id` 关联。

### 15.5.3 消息格式

每条消息为 JSONL 格式，追加写入（原子写入 `.tmp + mv`）：

```json
{
  "msg_id": "general-2026-04-27-000001",
  "ts": "2026-04-27T15:00:00+08:00",
  "from": "pm-chief",
  "to": "all",
  "source_type": "human",
  "type": "task_announce",
  "msg": "新建任务：修复 DeepSeek 联网搜索配置，@dev-2 认领？",
  "task_id": "修复DeepSeek联网搜索配置",
  "priority": "high"
}
```

**字段说明：**

| 字段 | 必填 | 说明 |
|------|------|------|
| `msg_id` | 是 | 消息唯一 ID。用于去重、已读游标、回复关联，不能只靠时间戳 |
| `ts` | 是 | ISO 8601 时间戳 |
| `from` | 是 | 发送者 agent-id 或 `kael`（开罗尔）/ `linsceo`（林总工） |
| `to` | 是 | `all`（公共频道）/ agent-id（定向）/ `pm-chief`（给 PM） |
| `source_type` | 是 | `human` / `system`。区分人工意图与系统确认事实 |
| `type` | 否 | 消息类型：`text`（默认）/ `task_announce` / `task_done` / `question` / `answer` / `decision` |
| `msg` | 是 | 消息内容 |
| `task_id` | 否 | 关联任务 ID |
| `priority` | 否 | 消息优先级：`low` / `medium` / `high` / `critical` |
| `reply_to` | 否 | 被回复消息的 `msg_id`，用于 question/answer/讨论串关联 |
| `thread_id` | 否 | 线程 ID；默认可取 `task_id` 或 `msg_id` |

**type 枚举：**

| type | 触发场景 | 说明 |
|------|---------|------|
| `text` | 任意对话 | 默认类型 |
| `task_announce` | PM/开罗尔发布任务 | A-Lite 阶段只表示“任务公告 / 讨论入口”，不直接驱动状态机 |
| `task_done` | agent 完成任务 | 只是“我已写 result.json”的通知，不直接等于任务终态 |
| `question` | agent 提问 | 任何人可回答 |
| `answer` | 回答问题 | 必须带 `reply_to` 指向原始 question |
| `decision` | PM/林总工做决策 | 需要所有人知晓的决策 |

> 关键约束：  
> **`task_done` 不是状态事实源。**  
> 真实状态仍然只能由 `task.json`、`ack.json`、`result.json`、`verify.json`、`transitions.jsonl` 决定。
>
> `task_claim / task_claim_confirmed` **保留为后续 Phase B/C 预留类型**，A-Lite 阶段不启用。

### 15.5.4 消息发送方式

**方式一：agent 主动写入（推荐，零依赖）**

agent 在任务间隙或被唤醒时，直接往 chat 文件追加消息：

```bash
# dev-1 在公共频道发言
echo '{"ts":"'$(date -Iseconds)'","from":"dev-1","to":"all","type":"text","msg":"这个接口我改完了，arch-1 帮忙看看"}' >> /Users/lin/Desktop/work/my-agent-teams/chat/general/$(date +%Y-%m-%d).jsonl
```

**方式二：通过 send-chat.sh 脚本（封装，带格式校验）**

```bash
/Users/lin/Desktop/work/my-agent-teams/scripts/send-chat.sh general "这个接口我改完了，arch-1 帮忙看看"
/Users/lin/Desktop/work/my-agent-teams/scripts/send-chat.sh task "修复DeepSeek联网搜索配置" "这条任务我先看一下上下文"
```

> A-Lite 阶段当前只启用 `general` 与 `task` 两类公开消息；`agent` 私聊命令保留为后续阶段预留，不属于当前落地范围。

脚本自动处理：
- JSON 格式化和校验
- `msg_id` 生成
- 写入正确的文件（A-Lite 阶段仅 `general / tasks`）
- flock + 原子写入（.tmp + mv）
- 通知 watcher 有新消息

> 建议默认使用 `send-chat.sh`，不要直接 `echo >>`。  
> 直接追加适合临时调试，但正式实现必须统一由脚本负责：
> - `msg_id` 生成
> - 私聊文件名排序
> - flock 原子写
> - JSON 校验

### 15.5.5 消息通知机制（A-Lite 先收缩）

A-Lite 阶段先不引入新的 chat 通知状态机，先用**最小可运行模式**验证“agent 是否会主动使用共享消息区”：

| 机制 | 职责 |
|------|------|
| **agent 主动检查** | 任务间隙主动读取 `chat/general` 与自己任务的 `chat/tasks/{task-id}.jsonl` |
| **PM / 关键任务定向唤醒** | 关键事项仍通过 `send-to-agent.sh` 强制唤醒目标 agent |
| **PM 主动查阅** | PM 定期查看 `chat/general/`，只在需要决策时介入 |

> 也就是说，A-Lite 阶段先验证“共享消息区有没有用”，而不是立刻把 watcher / tmux-watcher / 去重 / 已读游标一整套全做出来。

**PM 通知规则：**
- PM 不需要被每条消息打扰
- A-Lite 阶段仅以下消息建议显式通知 PM：
  - `decision`
  - `@pm-chief` 定向消息
  - 生产故障 / critical 任务的 task thread 变化
- 普通对话（`text`、`question`、`answer`）不主动通知 PM，PM 可主动查阅

**紧急任务补充规则：**
- `priority=critical` 的 `task_announce` 不能只依赖 chat 提醒
- 必须同时通过 `send-to-agent.sh` 对目标 agent 做强制唤醒
- 生产故障 / 安全风险 / 明确点名修复任务，仍保留“chat 共享 + 定向唤醒”双通道

### 15.5.6 任务池与 chat 的融合

Lite 版阶段**暂不做任务池与 chat 的融合**。  
任务仍然由现有 `task.json + create-task.sh + dispatch-task.sh` 驱动，chat 只承担：
- 任务公告
- 任务讨论
- 问答澄清
- 简短完成同步

也就是说，A-Lite 阶段里：
- `task_announce` = “任务公告 / 讨论入口”
- **不是**“可以直接认领并改变状态机”

```text
当前（Lite 版）：
  PM → create-task.sh / dispatch-task.sh → tasks/{task-id}
  PM → chat/tasks/{task-id}.jsonl 发 task_announce 作为讨论入口
  dev / arch / qa / review 在 chat/tasks/{task-id}.jsonl 中交流
```

**A-Lite 阶段示例：**

```jsonl
{"msg_id":"tasks-修复登录页样式-000001","ts":"...","from":"pm-chief","to":"all","source_type":"human","type":"task_announce","msg":"新建任务：修复登录页样式，@dev-1 认领？","task_id":"修复登录页样式","priority":"medium"}
{"msg_id":"tasks-修复登录页样式-000002","ts":"...","from":"dev-1","to":"all","source_type":"human","type":"question","msg":"arch-1，登录页的按钮颜色应该用哪个？","task_id":"修复登录页样式"}
{"msg_id":"tasks-修复登录页样式-000003","ts":"...","from":"arch-1","to":"all","source_type":"human","type":"answer","reply_to":"tasks-修复登录页样式-000002","msg":"用 primary-blue，跟导航栏一致","task_id":"修复登录页样式"}
{"msg_id":"tasks-修复登录页样式-000004","ts":"...","from":"dev-1","to":"all","source_type":"human","type":"task_done","msg":"完成，已写 result.json","task_id":"修复登录页样式"}
```

**好处：**
- 任务讨论和任务状态在同一个地方，不用在 pool/ 和 scratchpad/ 之间跳转
- PM 发布任务时就能同步发一条消息，降低“状态在 tasks/，上下文在脑子里”的割裂
- 所有人能看到任务从发布到完成的完整讨论记录

> **后移说明：**  
> `task_claim` 原子绑定 `task.json`、`task_claim_confirmed`、任务池迁移到 chat —— 全部延后到验证期之后，再决定是否值得把 chat 接入状态机中枢。

### 15.5.7 Agent 行为准则更新

各角色模板中新增 chat 相关规则：

**PM：**
- 发布任务时，在 chat/tasks/ 中发 task_announce 消息
- 定期查阅 chat/general/ 了解团队动态
- 只在需要决策时回复，不需要参与每条讨论
- 仍保留最终调度仲裁权；chat 自由交流不等于放弃任务状态裁决

**开发（dev-1/dev-2）：**
- 任务间隙检查 chat/ 新消息
- 遇到问题优先在 chat/ 中提问（@对应 agent），而不是等 PM 转达
- 生产故障/critical 任务被 `send-to-agent.sh` 定向唤醒时，应优先处理，不等普通 chat 轮询
- chat 中形成的关键结论必须回写 `features/<feature-id>/decisions.log` 或 `notes/dev.md`

**架构师（arch-1）：**
- 在 chat/ 中回答技术问题
- 方案设计中的讨论记录保留在 chat/tasks/ 中
- 对关键设计结论，同样需要回写 `CONTEXT.md` / `notes/arch.md`，不能只留在聊天里

**QA（qa-1）：**
- 测试结果在 chat/tasks/ 中简要同步
- 关键回归结论必须回写 `notes/qa.md` 或 `verify.json`

**审查（review-1）：**
- 审查意见在 chat/tasks/ 中简要同步
- 审查结论仍以 `review.md / design-review.md` 为准，chat 只作沟通补充

### 15.5.8 与现有方案的兼容

| 现有机制 | 变更 |
|---------|------|
| task.json / ack.json / result.json / verify.json | **不变**，仍然是任务状态的事实源 |
| task-watcher | **A-Lite 暂不改状态机**，先观察是否需要新增 chat 通知逻辑 |
| tmux-watcher | **A-Lite 暂不扩展**，紧急事项继续用 `send-to-agent.sh` |
| Scratchpad（15.2） | **暂不废弃**，先让 chat/tasks 与其并存，验证后再决定是否平滑迁移 |
| 共享任务池（4.6） | **A-Lite 不合并**，任务认领仍保持现有方案或现有 PM 派发方式 |
| send-to-agent.sh | **保留**，用于需要 tmux send-keys 唤醒的场景 |
| config.json | **不变** |
| features/<feature-id>/ | **保留并强化**，稳定上下文仍放 BRIEF/CONTEXT/notes；chat 只承载过程讨论 |
| 保护路径 | **扩展**，chat/ 目录所有 agent 可写，但不能删除他人消息 |

### 15.5.9 Phase 分期（先 Lite 验证，再决定是否接入状态机）

| Phase | 内容 |
|-------|------|
| **Phase A-Lite（先做）** | 仅做 `chat/general/` + `chat/tasks/` + `send-chat.sh` + `msg_id/source_type/reply_to` 基础协议 + PM 发 `task_announce` + agent 主动检查；**不碰任务认领状态机，不做私聊，不做已读游标** |
| **验证期（1-2 周）** | 观察 agent 是否主动使用、PM 中转次数是否下降、关键结论是否能稳定回写 feature 上下文；只验证通信价值，不改任务事实源 |
| **Phase B（验证通过后）** | 再评估是否值得引入 `task_claim` 原子绑定 `task.json`、`task_claim_confirmed`、chat-notified / read-pointers、紧急任务自动唤醒联动 |
| **Phase C（再扩）** | 私聊线程、失败重试/死信、历史搜索、看板集成 chat 记录、Scratchpad 平滑废弃等重型能力 |

### 15.5.10 验证期目标与验收标准

**验证周期：** 先跑 **1-2 周**，只验证 Lite 版是否真能减少 PM 中转负担并被 agent 主动使用。

**验证目标：**
1. agent 是否会主动在 `chat/general/` 与 `chat/tasks/{task-id}.jsonl` 中交流，而不是继续完全依赖 PM 中转
2. PM 的中转次数是否明显下降
3. 任务讨论是否更容易被后续 agent 看见
4. chat 中形成的关键结论是否能被回写到 `features/<feature-id>/decisions.log` / `notes/*`

**核心观察指标：**
- PM 每天手工中转消息次数是否下降
- `task_announce` 发出后，agent 是否会在 task thread 中主动跟进
- agent 是否主动在 chat 里提问 / 回答，而不是继续等 PM 转达
- 每周抽样检查：关键结论是否有回写上下文

**通过标准（建议）：**
1. 连续 1-2 周内，PM 手工中转次数有明显下降（至少能观察到趋势性减少）
2. 至少有若干真实任务（建议 5 个以上）在 `chat/tasks/` 中产生实际讨论记录
3. 关键讨论不是只停留在 chat 里，能看到回写 `decisions.log` / `notes/*`
4. 没有因为 A-Lite 引入新的任务状态错乱、假认领或消息系统级阻塞

若以上标准不成立，则应先迭代 Lite 版使用方式，而不是贸然推进 B 阶段状态机改造。

### 15.5.11 已知限制与待讨论

1. **消息顺序与唯一性**：JSONL 追加写入天然近似有序，但必须依赖 `msg_id + flock`，不能只靠时间戳。
2. **A-Lite 不碰认领状态机**：`task_claim` 原子绑定、`task_claim_confirmed`、任务池迁移到 chat，全部后移到验证期之后。
3. **A-Lite 不做已读游标**：`chat-read-pointers.json` 与系统级“未读/已读/已处理”区分后移到验证期之后。
4. **A-Lite 不做私聊目录**：`chat/agents/` 与私聊线程规范后移，先验证公共频道 + 任务讨论串是否足够。
5. **紧急任务不能只靠 chat 提醒**：生产故障、critical 任务、林总工直接点名任务，仍必须通过 `send-to-agent.sh` 强制唤醒。
6. **关键结论必须回写 feature 上下文**：chat 里形成的关键约束/决策，必须回写 `features/<feature-id>/decisions.log` 或 `notes/*`；否则仍会出现“改了东边不知道西边会塌”。
7. **失败重试 / 死信尚未设计完整**：若 chat 写入成功但 watcher 未通知、或通知失败、或目标 session 不在线，需要后续补重试与 dead-letter 机制。
8. **PM 仍需保留最终仲裁权**：共享空间不是去中心化调度，任务优先级冲突、长期无人认领、认领后卡住等情况，最终仍由 PM 收束。
9. **林总工参与方式**：通过开罗尔代发消息到 chat/，或者直接在飞书上指示开罗尔发。
10. **消息量与归档**：按天分文件短期足够；若后续引入私聊与历史搜索，再统一设计 general / tasks / agents 的归档与清理策略。

---

## 十六、参考：Claude Code 架构设计中的可迁移模式

> 来源：[claude-code-sourcemap-learning-notebook](https://github.com/dadiaomengmeimei/claude-code-sourcemap-learning-notebook)（⭐168）
> 对 Claude Code 512K+ 行 TypeScript 源码的逆向工程分析，提取了可迁移设计模式。涵盖第 3 章（权限与安全）、第 4 章（查询循环）、第 5 章（多 Agent）、第 6 章（技能系统）、第 7 章（Prompt 工程）的关键发现。

### 16.1 "默认隔离，显式共享"原则

Claude Code 创建子 Agent 时，默认隔离所有可变状态（文件缓存、记忆、取消控制器），需要共享必须显式声明。

**对我们的启发：**
- 当前方案通过文件系统间接隔离（worktree），但缺少代码层面的强制
- PM 派发任务时，默认不应共享上游 agent 的完整上下文，只共享必要的契约和摘要
- 如果某个任务确实需要另一个 agent 的完整上下文，必须在 task.json 中显式声明 `shared_context: ["upstream-task-id"]`

```
task.json 新增可选字段：
{
  "shared_context": [],       // 默认空，不共享任何上下文
  "shared_artifacts": [],     // 可选，共享指定工件（contract、文档等）
  "inherit_tools": false      // 是否继承父任务的工具集
}
```

**Phase 分期：** 原则完全正确，但这三个字段在 Phase 1 会增加 task.json 复杂度，与第三章"状态宁少勿多"矛盾。Phase 1 只用已有的 `contract_files` 和 `depends_on` 表达依赖关系，这三个字段推迟到 Phase 2 需要精细化上下文控制时再引入。

### 16.2 读写锁并发模型

Claude Code 的工具执行引擎：读操作可以并行，写操作必须独占。

**对我们的启发：**
- 这就是"唯一集成者"的理论基础——多个 agent 可以同时读（审查、分析），但只有一个能同时写
- 可以在 task.json 中标记任务类型：
```json
{
  "access_mode": "read",   // 只读任务（审查、分析）
  "access_mode": "write"   // 写入任务（开发、修改）
}
```
- 同一时刻，同一个 `write_scope` 范围内只允许一个 `access_mode=write` 的任务执行

**强制执行机制：** PM 派发任务时做前置检查——扫描所有 `working` 状态的任务，如果存在 write_scope 重叠，则新任务进入 `blocked` 等待。

### 16.3 分层错误恢复

Claude Code 对错误设计三阶段恢复：先简单重试 → 不行升级处理 → 最后才放弃。

**对我们的启发：**
- 当前方案只有 `failed` 和 `timeout`，缺少中间恢复层
- 建议细化错误恢复状态：

```text
failed
→ auto_retry (自动重试一次，attempt+1)
→ manual_review (需要人工介入)
→ blocked (需要上游修复)
→ cancelled (确认放弃)
```

- 自动重试规则：
  - 超时任务：保留 worktree，直接重试
  - 验证失败：通知 agent 修复，不自动重试
  - API 错误（网络、过载）：等 30 秒后自动重试
  - 上下文溢出：/compact 后重试

**重试职责划分：** 重试决策由 PM Agent 做出（PM 读 task.json 发现 failed，判断是否可重试，若是则将 status 改回 pending 重新派发），watcher 只负责通知 PM "有任务 failed 了"。重试上限为 2 次自动重试，超过后进入 `manual_review` 等待人工介入。

### 16.4 Fork 与 Prompt Cache 共享

Claude Code fork 子 Agent 时继承父级的 prompt cache，节省 token。

**对我们的启发：**
- 当前派发任务时附带上游摘要和契约文件，本质上就是"上下文共享"
- 可以进一步优化：agent 启动时先加载一个"项目基础 prompt"（项目结构、技术栈、编码规范），所有任务共享这个基础，只附加任务特定的部分
- 项目基础 prompt 可以缓存，避免每次任务都重新生成

### 16.5 确定性清理（12 步 finally 块）

Claude Code 的 Agent 结束后有 12 步清理流程，用 finally 块保证每一步都执行。

**对我们的启发：**
- 当前方案没有定义任务结束后的清理流程
- 建议定义任务清理清单：

```bash
# 任务完成后必须执行的清理
1. 更新 task.json.status 为最终状态
2. 如果是 worktree 模式：评估是否回收 worktree
   - done/failed 且无下游依赖 → 回收
   - blocked/failed 且需要排查 → 保留，标记 .preserve
3. 杀死 agent 可能遗留的后台进程
4. 归档任务日志到 tasks/archive/
5. 更新看板/通知状态
```

**Phase 分期：** 这是最实用的模式之一，**Phase 1 就应落地**，至少包括步骤 1（更新状态）、2（worktree 回收策略）、4（日志归档）。不做清理的话 worktree 会越积越多，磁盘很快就满。新增 `scripts/task-cleanup.sh`，在任务进入终态（done/cancelled/failed 超过重试上限）时自动执行。

### 16.6 三层级联取消

Claude Code 的 AbortController 层级：父取消 → 子自动取消 → 孙自动取消。

**对我们的启发：**
- 取消一个任务时，应该自动取消依赖它的下游任务
- 取消一个 PM 管理的整个需求时，该需求下所有子任务都应级联取消
- 在 task.json 的 `depends_on` 基础上实现：

```text
取消任务 A
→ 查找所有 depends_on 包含 A 的任务 B、C
→ 级联取消 B、C
→ 递归查找依赖 B、C 的任务...
→ 通知受影响的 agent
```

**取消协议（agent 侧）：** 级联取消的逻辑已定义，但 agent 收到取消信号后的行为也需明确：

- PM/开罗尔 将 `task.json.status` 改为 `cancelled`
- watcher 检测到 `cancelled` 后，向对应 agent 的 tmux session 发送中断指令（如 `Ctrl+C` 或写入 `tasks/{task-id}/cancel.json`）
- agent 侧约定：启动时 watch cancel.json，发现后停止当前工作、清理临时文件、不再写 result.json
- 如果 agent 无法优雅停止（已经在 thinking），watcher 在超时后可强制 `tmux send-keys C-c`

### 16.7 状态机 + 转换日志

Claude Code 的 query loop 是一个 while(true) + State 对象的状态机，每次状态转换都记录原因。

**对我们的启发：**
- 我们的任务状态机也应该记录每次转换的原因和时间
- 但**不要把不断增长的转换日志塞回 `task.json`**，否则会带来并发写冲突、文件膨胀和事实源污染
- 统一采用追加式 `transitions.jsonl`：

```text
~/.openclaw/workspace/tasks/{task-id}/transitions.jsonl
```

```json
{"from": "pending", "to": "dispatched", "at": "...", "reason": "tmux send success"}
{"from": "dispatched", "to": "working", "at": "...", "reason": "ack.json received"}
{"from": "working", "to": "ready_for_merge", "at": "...", "reason": "result.json received"}
{"from": "ready_for_merge", "to": "done", "at": "...", "reason": "verify passed"}
```

- `task.json` 继续只承载当前状态与最小元数据，`transitions.jsonl` 负责状态审计与恢复分析
- 这对调试"任务卡在某状态"非常有用——不用猜，直接看日志

**Phase 分期：** 实用且实现成本低，Phase 1 就应加入，但格式统一为 `transitions.jsonl`。也可以兼做最基础的可观测性数据——从 jsonl 事件可以直接算出任务耗时、卡在哪个阶段最久。

### 16.8 渐进式工具过滤

Claude Code 的子 Agent 工具集通过多层过滤确定：基础工具集 → Agent 定义级过滤 → 运行时权限检查。

**对我们的启发：**
- 不同角色的 agent 应该有不同的工具集：
  - 架构师：文件读、搜索、分析（无写入权限）
  - 开发：文件读写、命令执行、git
  - 审查者：文件读、搜索、diff（无写入权限）
  - PM：任务管理、通知推送、git status（无业务文件写入权限）
- 在 config.json 的 agent 定义中增加 `allowed_tools` 字段

**落地约束：** 在当前 tmux + Claude Code / Codex 架构下，config.json 的 `allowed_tools` **不可直接强制执行**——agent 实际可用工具取决于各自的权限配置文件（Claude Code 为 CLAUDE.md / `.claude/settings.json`，Codex 为 AGENTS.md），而非 config.json。要实现真正的工具过滤，需要：(a) 通过各 agent 的 CLAUDE.md（Claude Code）或 AGENTS.md（Codex）配置不同权限，或 (b) 利用 Claude Code 的 hooks 做运行时拦截。Phase 1 先通过对应配置文件区分角色权限，`allowed_tools` 作为长期目标保留。

### 16.9 Transition 字段防恢复死循环

> 来源：第 4 章 查询循环（Query Loop）

Claude Code 的查询循环中，每次迭代都记录一个 transition 字段——"为什么继续这次循环"。这不是普通日志，而是**恢复策略去重机制**：如果系统发现即将采取的恢复手段已经出现在历史 transitions 中，就跳过该手段，尝试下一级恢复或直接放弃。Claude Code 曾因缺少此机制而在某个恢复路径上烧掉数千次 API 调用。

**对我们的启发：**
- 16.7 已引入 `transitions.jsonl` 记录状态变更，但不仅可做审计，也可用于恢复策略去重
- 需要进一步利用 transitions 做**重试去重**：PM 在决定重试一个 failed 任务时，检查 transitions 中是否已有相同原因的 `failed → pending` 记录
- 重试阈值规则：

```text
PM 决定重试任务 T
→ 读取 T 的 transitions.jsonl
→ 统计 reason 相同的 failed → pending 转换次数
→ 次数 < 2：允许自动重试
→ 次数 = 2：强制升级为 manual_review，通知人工介入
→ 次数 > 2：不应发生（manual_review 后人工决定是否继续）
```

- 这与 16.3 的分层错误恢复互补——16.3 定义了恢复层级，16.9 防止在同一层级无限循环

**Phase 分期：** `transitions.jsonl` Phase 1 已计划落地（16.7），重试去重逻辑随 PM Agent 一起实现。成本极低——只是在重试前多做一次 jsonl 扫描。

### 16.10 多层压缩策略与上下文管理

> 来源：第 4 章 查询循环（上下文管理部分）

Claude Code 对上下文膨胀设计了四级渐进压缩：

| 级别 | 策略 | 触发条件 | 信息损失 |
|------|------|---------|---------|
| L1 | **snip** | 工具输出过长 | 极低（只截断工具结果，保留摘要） |
| L2 | **microcompact** | 接近上下文窗口 | 低（压缩早期对话，保留关键决策） |
| L3 | **context collapse** | 上下文严重膨胀 | 中（折叠整段历史为摘要） |
| L4 | **autocompact** | 上下文即将溢出 | 高（全量压缩，仅保留当前任务核心） |

**对我们的启发：**
- PM Agent 长时间运行时必然面临上下文膨胀。14.7 的 pm-state.json 解决了"compact 后恢复"问题，但没有解决"如何延缓 compact"
- 建议 PM 的 instruction.md 中明确要求：
  - **结构化输出**：PM 的中间推理不要写成长段自然语言，而是用 JSON/表格，便于后续 compact 时保留关键信息
  - **主动摘要**：PM 每完成一个任务的全流程后，主动将该任务的关键决策写入 pm-state.json，不依赖对话历史
  - **分段处理**：如果需求拆出的任务超过 5 个，PM 分批处理（先派发前 3 个，完成后再处理后续），避免同时跟踪过多任务导致上下文爆炸
- agent 侧也应控制输出量：result.json 的 summary 字段限制在 500 字以内，详细信息放在 worktree 的文件中，不要全塞进 JSON

### 16.11 Prompt 静态/动态分离与审查并行化

> 来源：第 7 章 Prompt 工程 + 第 6 章 /simplify 技能

两个可迁移的设计发现：

#### Prompt 静态/动态分离

Claude Code 的 prompt 总量达 **150KB+，分布在 40+ 个文件中**——这说明 prompt 工程是被严重低估的工作量。其核心设计是将 prompt 分为两层：

| 层级 | 内容 | 生命周期 | 缓存策略 |
|------|------|---------|---------|
| **静态层** | 角色定义、编码规范、项目结构、工具使用说明 | 跨请求不变 | 可缓存，利用 API prompt cache |
| **动态层** | 当前任务描述、上游产物摘要、实时状态 | 每次请求变化 | 不缓存，每次重新生成 |

静态层放在 prompt 前部、动态层放在后部，利用 Anthropic API 的 prompt cache 机制（前缀匹配缓存），静态部分命中缓存后只计费动态部分，**可节省 50%+ 的 token 成本**。

**对我们的启发：**
- 当前方案 14.8 定义了 agent 启动时"注入角色 prompt"，但没有明确静态/动态分离
- 建议将 agent prompt 拆为两个文件：
  - `prompts/{role}-base.md` — 静态层：角色定义、权限边界、协作规则、项目编码规范（跨任务不变）
  - `tasks/{task-id}/instruction.md` — 动态层：具体任务描述、上游产物引用、验收标准（每次不同）
- agent 启动时先加载静态 prompt，再附加动态 prompt。静态部分在 Claude Code 中天然命中 prompt cache
- **prompt 维护应作为正式工作量纳入排期**，不是"写个 system prompt 就行"

#### 审查并行化

Claude Code 的 `/simplify` 技能在做代码简化时，会同时启动三个并行子 Agent，分别从**代码复用、代码质量、执行效率**三个维度审查，然后综合结果。

**对我们的启发：**
- 当前方案中审查者（小克）是单一角色，所有审查维度串行完成
- 可以将审查拆分为多维度并行任务（Phase 2+）：

```text
PM 派发审查任务
→ 并行启动：
  ├── 审查子任务 A：代码质量（命名、结构、可读性）
  ├── 审查子任务 B：安全与合规（注入、越权、敏感数据）
  └── 审查子任务 C：性能与效率（复杂度、资源使用）
→ PM 综合三份审查结果，合并为统一审查意见
→ 派发给开发 agent 修复
```

- 当前 Phase 1 不需要这样做（任务量不大），但架构上不应阻塞这种扩展——保持审查任务的 task.json 结构与开发任务一致，未来拆分时无需改 schema

---

## 十七、立即可以做的事

1. [ ] 创建 `tasks/{task-id}/task.json` 目录结构
2. [ ] 落地 `ack.json / result.json / verify.json` 三类附属工件
3. [ ] 实现基于 `git diff` 的 `verify` 脚本（含协议合规检查：JSON 格式校验、task_id 匹配、write_scope 越界检测）
4. [ ] **verify 脚本增加保护路径硬检查**（config.json 中定义 protected_paths，diff 触碰即拒绝）
5. [ ] 建 integration 分支与唯一 integrator 的集成流程（含回滚策略）
6. [ ] 给现有 `tmux-send.sh` 改成文件 / buffer 发送（send-keys 只做唤醒，内容从文件读取）
7. [ ] 把 worktree 根目录改成项目同级 `.openclaw-worktrees/` 可配置路径
8. [ ] 先挑 1~2 个高风险接口做 contract test
9. [ ] 在任务派发时支持 `workspace_mode=main|worktree`
10. [ ] 增加 `transitions.jsonl`，每次状态变更追加 from/to/at/reason
11. [ ] 实现 `task-cleanup.sh`：任务进入终态后回收 worktree、归档日志
12. [ ] watcher 增加 agent tmux session 存活检测
13. [ ] 画完整状态转换矩阵并固化到代码中（参考 4.3 补充的矩阵表）
14. [ ] **实现 `semantic-review.sh`**：PM 在 ready_for_merge 时做轻量级语义审查（diff 大小、文件范围、测试覆盖、调试代码扫描）
15. [ ] **定义 pm-state.json 最小 schema 并实现 PM 启动恢复协议**
16. [ ] **定义 agent 启动初始化序列**（读 config → 注入角色 prompt → 扫描任务 → 恢复/待命）
17. [ ] **创建 Scratchpad 目录结构和读写规则**（tasks/.scratchpad/{task-group-id}/，文件名前缀 = agent-id）
18. [ ] **PM 重试决策增加 transitions 去重检查**（相同 reason 的 failed→pending 超过 2 次强制升级人工介入）
19. [ ] **拆分 agent prompt 为静态/动态两层**（prompts/{role}-base.md + tasks/{task-id}/instruction.md），利用 prompt cache 降低 API 成本
20. [ ] **创建 prompts/ 目录并编写各角色的 base.md**（backend-dev、architect、reviewer、frontend-dev、pm），纳入 protected_paths 保护
21. [ ] **定义 instruction.md 最小模板**（目标、约束、验收标准、上游产物引用），PM 每次派发任务时按模板生成

---

## 十八、优先级建议（安全与高级特性）

> 本章聚焦安全机制和高级协作特性的优先级。基础设施落地顺序见第十一章。

### 新增 P0（本轮新增，直接影响方案安全性和可靠性）

- **保护路径硬检查**——verify 脚本中对 protected_paths 做硬拒绝，防止 agent 篡改系统核心文件（task.json、scripts/、.git/ 等）。这是整个权限模型的基石，不做则 write_scope 和角色边界形同虚设
- **agent 不可自改 task.json**——通过 verify 硬检查保证。agent 只能写 ack.json 和 result.json，不能直接修改自身的权限、状态终态或 assignee
- **Handoff 语义审查**——PM 在 ready_for_merge 时做 diff 大小/文件范围/测试覆盖/调试代码的轻量检查，防止"verify 机械通过但语义不合理"的情况

### 原有 P0（继续保留）

- **`transitions.jsonl` 日志**——成本极低（每次状态变更追加一行 JSON），但调试价值极高，是排查状态异常的第一手数据
- **任务清理脚本**——不做会导致 worktree 和磁盘持续膨胀，长期运行时成为系统瓶颈
- **verify 脚本的协议合规检查**——不做则整个 ACK/result 流程的可靠性无法保证，这是方案从"设计正确"到"运行正确"的关键一环

### 新增 P1

- **Scratchpad 形式化**——目录结构、读写规则、清理策略。解决 agent 间中间产物共享问题，避免全走 PM 转发成为瓶颈
- **PM 容灾（pm-state.json + 启动恢复协议）**——PM 是系统中枢，compact/崩溃后必须能快速恢复全局视图
- **Agent 启动初始化协议**——标准化 agent 启动序列（读 config → 注入角色 → 扫描任务 → 恢复/待命），确保 agent 重启后不丢活
- **PM 重试去重（transitions 扫描）**——PM 重试 failed 任务前检查 transitions 中相同 reason 的重试次数，超过 2 次强制升级人工介入，防止恢复死循环（16.9）
- **Prompt 静态/动态分离**——将 agent prompt 拆为 `prompts/{role}-base.md`（跨任务缓存）+ `tasks/{task-id}/instruction.md`（每次不同），利用 prompt cache 可节省 50%+ token 成本（16.11）
- **角色定义文件创建**——编写各角色的 `prompts/{role}-base.md`，纳入 protected_paths 保护，确保 PM 和 agent 不能自行修改角色权限边界（第二十章）

### 新增 P2（长期方向）

- **Permission Mode 分级**——strict/normal/permissive 三级模式，按 agent 成熟度和任务风险动态调整
- **沙箱执行环境**——将 agent 命令执行放入容器，限制文件系统/网络/进程访问，需基础设施支持
- **审查并行化**——将审查拆分为代码质量/安全合规/性能效率三个维度并行执行，PM 综合结果（16.11）

---

## 十九、附录：Claude Code 五层纵深防御模型

> 来源：[claude-code-sourcemap-learning-notebook](https://github.com/dadiaomengmeimei/claude-code-sourcemap-learning-notebook) 第三章
> Claude Code 对 agent 权限和安全的设计是当前工业级实践的标杆，其核心思想可迁移到任何多 agent 协作系统。

### 19.1 五层防御概览

```text
Layer 1: Permission Rules（deny > ask > allow）
  ↓
Layer 2: Permission Mode（bypassPermissions / default / plan）
  ↓
Layer 3: Tool-specific Checks（每个工具内置的安全检查）
  ↓
Layer 4: Path Safety（protected paths 硬拦截）
  ↓
Layer 5: Sandbox（Docker / seatbelt / 网络隔离）
```

**关键设计原则：**
- **deny 优先**：规则匹配顺序是 deny > ask > allow，先拒绝再放行
- **权限单调递减**：子 agent 的权限只能是父 agent 权限的子集，不能扩大
- **Agent 不能自己改权限**：权限由上层设置，agent 只能在边界内行动
- **默认隔离，显式共享**：子 agent 创建时不继承父 agent 的可变状态

### 19.2 对本方案的映射

| Claude Code 层级 | 本方案对应机制 | 当前状态 | 目标 Phase |
|------------------|---------------|---------|-----------|
| **Layer 1: Permission Rules** | config.json 中的角色权限定义 + CLAUDE.md/AGENTS.md | ⚠️ 软约束 | Phase 1（通过角色配置文件） |
| **Layer 2: Permission Mode** | 13.4 中定义的 strict/normal/permissive 三级 | ❌ 未实现 | Phase 2（PM 可切换 agent 模式） |
| **Layer 3: Tool-specific Checks** | verify 脚本的协议合规检查（5.3）+ 语义审查（13.3） | ✅ Phase 1 实现中 | Phase 1 |
| **Layer 4: Path Safety** | 13.1 保护路径清单 + verify 硬拒绝 | ✅ Phase 1 新增 | Phase 1 |
| **Layer 5: Sandbox** | 13.4 中的容器化方向 | ❌ 未实现 | Phase 3+（需基础设施） |

### 19.3 权限单调递减在本方案中的体现

```text
林总工（全部权限）
  → 开罗尔（通信 + 调度，不写业务代码）
    → PM（任务管理 + 状态控制，不写业务代码）
      → 架构师（读 + 文档/契约写，不写业务代码）
      → 开发（write_scope 内读写，不碰 tasks/ 和 scripts/）
      → 审查者（只读，不写任何文件）
```

每一层的权限都严格小于上一层。agent 不能通过任何方式扩大自己的权限（13.2 保证）。

### 19.4 Coordinator 模式

Claude Code 的多 agent 系统采用 Coordinator 模式：worker 之间不直接通信，所有信息流经 Coordinator。

本方案的 PM Agent 就是 Coordinator：
- agent 之间不直接对话（14.3 规则三）
- 所有状态变更经过 PM
- Scratchpad 是受控的异步共享通道，PM 控制其生命周期（15.2）

**与纯 Coordinator 的差异**：Scratchpad 允许 agent 绕过 PM 直接共享产物文件（但不是消息），这是对纯星形架构的务实妥协——避免大文件频繁经过 PM 转发。PM 仍然控制"谁能访问哪个 scratchpad"和"何时清理"。

---

## 二十、角色定义与 Prompt 分层管理

> 角色定义是整个权限模型的源头。本章确立"谁写规矩、谁执行规矩、规矩存在哪"。

### 20.1 核心原则：宪法由立法者写，PM 是执法者

角色定义（能做什么、不能做什么）决定了 agent 的权限边界。**被约束的人不能修改约束本身**——这与 13.2（agent 不可自改 task.json）和 19.1（agent 不能自己改权限）是同一个逻辑。

因此：

| 操作 | 谁做 | 说明 |
|------|------|------|
| **创建/修改** 角色定义 | 林总工（或开罗尔代笔） | 宪法级文件，必须人工确认 |
| **起草建议** | PM 可以 | PM 发现缺少角色或定义不合理时，写建议稿到 scratchpad（如 `pm_role-proposal.md`），人工审核后手动迁入 prompts/ |
| **读取使用** | PM + 所有 agent | PM 派发时参考，agent 启动时加载 |
| **修改保护** | verify 硬拒绝 | prompts/ 已纳入 13.1 保护路径清单 |

PM 口头告诉角色定义有一个致命缺陷——**PM 会 compact**。14.6 已经踩过这个问题：PM 必须每次重新读取，不依赖对话记忆。所以角色定义必须落盘为文件，PM 读取而非记忆。

### 20.2 三层分离架构

角色定义分三层，与 16.11 的 prompt 静态/动态分离一脉相承：

```text
身份层（config.json）  → 谁是谁、在哪个 tmux session
能力层（prompts/）     → 能做什么、不能做什么、怎么做
任务层（instruction.md）→ 这次具体做什么
```

| 层级 | 文件 | 内容 | 生命周期 | 谁写 | 谁读 |
|------|------|------|---------|------|------|
| **身份层** | `config.json` | agent-id、tmux session、model、基础角色标签 | 部署时写，极少改 | 林总工 | watcher、脚本、PM |
| **能力层** | `prompts/{role}-base.md` | 详细职责边界、权限范围、协作规则、编码规范 | 跨任务不变，偶尔调整 | 林总工 | agent（启动时加载）、PM（派发时参考） |
| **任务层** | `tasks/{task-id}/instruction.md` | 具体任务描述、验收标准、上游产物引用 | 每次任务不同 | PM | agent（执行时读取） |

身份层已存在于 config.json（12.3），任务层已有模板定义（5.1）。**缺的是能力层**。

### 20.3 能力层文件规范

#### 目录结构

```text
prompts/
├── backend-dev-base.md    # 后端开发
├── architect-base.md      # 架构师
├── reviewer-base.md       # 审查者
├── frontend-dev-base.md   # 前端开发
└── pm-base.md             # PM
```

#### 模板

```markdown
# 角色：{角色名}

## 你是谁
（一句话定义角色身份）

## 你能做什么
- （列举允许的操作，如"在 write_scope 范围内读写代码"）
- ...

## 你不能做什么
- （列举禁止的操作，如"不碰 tasks/、scripts/、config.json、prompts/"）
- （"不做架构决策"、"不审查其他 agent 的代码"等角色边界）
- ...

## 工作流程
1. 读取 instruction.md 理解任务
2. 写 ack.json 确认收到
3. （角色特定的工作步骤）
4. 写 result.json 报告完成

## 协作规则
- 只与 PM 沟通，不直接与其他 agent 对话
- 需要上游产物时从 scratchpad 读取
- （其他角色特定的协作约定）

## 编码规范
（项目级编码规范，所有开发角色共享；审查者/PM 可省略此节）
```

#### 示例：后端开发

```markdown
# 角色：后端开发

## 你是谁
后端开发 agent，负责 API 实现、数据库、业务逻辑。

## 你能做什么
- 在 write_scope 范围内读写代码
- 执行测试命令（pytest、npm test 等）
- 读取 scratchpad 中的上游产物（契约文件、设计文档）
- 写 ack.json 和 result.json

## 你不能做什么
- 不碰 tasks/、scripts/、config.json、prompts/
- 不做架构决策（有疑问通过 result.json 反馈给 PM）
- 不审查其他 agent 的代码
- 不直接与其他 agent 通信
- 不修改 task.json 的任何字段

## 工作流程
1. 读取 instruction.md 理解任务
2. 写 ack.json 确认收到
3. 读取 scratchpad 中的契约文件和设计文档
4. 在 write_scope 内开发，遵循编码规范
5. 运行测试确保通过
6. 写 result.json 报告完成

## 协作规则
- 只与 PM 沟通，不直接与其他 agent 对话
- 需要上游产物时从 scratchpad 读取，不要求 PM 转发
- 遇到阻塞问题，在 result.json 中声明 status: "blocked" 并说明原因

## 编码规范
（按项目实际情况填写）
```

### 20.4 与现有机制的关系

#### 与 CLAUDE.md / AGENTS.md 的关系

- **CLAUDE.md** — 项目通用规范（所有 agent 共享，如代码风格、commit 格式）
- **prompts/{role}-base.md** — 角色专属定义（不同 agent 加载不同文件）

CLAUDE.md 是项目级的，一个项目只有一份，无法区分角色。`prompts/{role}-base.md` 解决的是"不同角色有不同权限和行为规范"的问题。

#### 与 14.8 agent 启动协议的关系

14.8 定义的启动序列第 2 步"注入角色 prompt"，现在明确为：

```text
Agent 启动
→ 1. 读取 config.json，确认自身角色
→ 2. 加载 prompts/{role}-base.md（能力层，静态）
→ 3. 扫描 tasks/ 目录，找到自己的任务
→ 4. 读取 tasks/{task-id}/instruction.md（任务层，动态）
→ 5. ...（后续步骤不变）
```

#### PM 的使用方式

PM 派发任务时的决策流程：

```text
PM 准备派发任务 T
→ 读 config.json，获取所有 agent 列表和基础角色
→ 读 prompts/{role}-base.md，确认候选 agent 的能力边界
→ 选择匹配的 agent
→ 生成 tasks/{task-id}/instruction.md（任务层）
→ 派发
```

PM 不需要"记住"谁能干什么，每次决策前读文件。这与 pm-state.json 的设计理念一致——**文件是记忆，对话是临时的**。

### 20.5 PM 的角色定义边界

PM 是执法者，不是立法者。PM 的 `prompts/pm-base.md` 中应明确写入：

```markdown
## 你不能做什么
- 不能创建或修改 prompts/ 目录下的任何文件
- 不能修改 config.json
- 不能给 agent 授予超出其角色定义的权限
- 如果认为角色定义需要调整，将建议稿写入 scratchpad（pm_role-proposal.md），等待人工审核
```

这确保了权限模型的闭环：**权限由上层设置（林总工写 prompts/），PM 和 agent 只能在边界内行动**。

---

## 二十一、分层 PM 演进方案

> 完整草案见 [分层PM演进方案.md](./分层PM演进方案.md)，本章节为摘要。

### 21.1 核心结论

分层 PM 不是"多加几个人转发消息"，而是把调度从"单 PM 的上下文记忆"升级为"有明确层级和责任边界的控制面"。

**推荐演进路径：**
- **3-5 个 agent**：继续单 PM，但 schema 做 hierarchy-ready
- **8-10 个 agent**：总 PM + 子 PM 两层结构
- **12-15 个 agent**：Program PM / Domain PM / Pod PM 三层结构

**贯穿三阶段不变的规则：**
1. task.json 是任务事实源
2. config.json 负责组织拓扑、角色映射、路由规则
3. 控制面走 PM 层级，数据面走结构化任务/工件
4. 同一 task/session 只能有一个 owner
5. 跨域协作靠任务依赖与 handoff package，不靠自由聊天

### 21.2 阶段一（3-5 agent）：单 PM + hierarchy-ready schema

**组织形态：** 1 个 PM-chief + 3-5 个执行 agent

**config.json 新增字段：**
```json
{
  "orchestration": {
    "mode": "single_pm",
    "hierarchy_ready": true,
    "root_pm": "pm-chief",
    "integration_owner": "arch-1",
    "domains": {
      "frontend": ["fe-1", "fe-2"],
      "backend": ["be-1", "be-2"],
      "quality": ["review-1"]
    }
  }
}
```

**task.json 新增字段：**
```json
{
  "root_request_id": "R-20260423-001",
  "parent_task_id": null,
  "task_level": "execution",
  "owner_pm": "pm-chief",
  "lease_owner": "pm-chief",
  "lease_expires_at": "2026-04-23T18:00:00+08:00",
  "domain": "frontend"
}
```

**lease 最小语义（Phase 1）：**
- 只定义 `lease_owner / lease_acquired_at / lease_expires_at`
- Phase 1 只做观测和告警，不做自动回收
- 续租由当前 owner 在状态推进时顺带刷新
- 自动 reclaim 要到 Phase 2 多 PM runtime 才启用

**通知：** 全量实时推飞书，日均 10-20 条

**触发升级信号：** `active_tasks > 8` 连续 3 天、`pm_compact_recovery >= 2/周`、跨域 blocker 频繁

### 21.3 阶段二（8-10 agent）：两层 PM

**组织形态：**
```
PM-chief（总 PM）
  ├── PM-frontend → fe-1, fe-2, fe-3
  ├── PM-backend  → be-1, be-2, be-3
  └── PM-quality  → qa-1, review-1
```

**config.json 新增字段：**
```json
{
  "orchestration": {
    "mode": "hierarchical_pm",
    "coordination": {
      "control_plane": "via_root_pm",
      "data_plane": "structured_task_handoff"
    },
    "teams": {
      "frontend": {
        "pm": "pm-frontend",
        "reports_to": "pm-chief",
        "agents": ["fe-1", "fe-2", "fe-3"],
        "max_active_tasks": 6
      }
    }
  }
}
```

**task.json 新增字段：**
```json
{
  "team": "frontend",
  "child_tasks": ["T-102", "T-103"],
  "report_to": "pm-frontend",
  "escalation_to": "pm-chief",
  "lease_owner": "pm-frontend",
  "coordination_channel": "coord-task-only"
}
```

**补充规则：**
- 子 PM 只能调度自己 `home_team` 下的 agent
- agent 必须且仅有一个 `home_team`
- review / qa 等共享角色通过 `borrow` 机制临时支援其他 team，不产生多重归属
- Phase 2 开始启用 lease 自动回收；Phase 1 只有字段和续租语义，不做自动 reclaim

**协调机制：** 子 PM 间不自由聊天，通过 coordination task + handoff_package 协调。控制面走 PM 层级，数据面走结构化工件。coordination task 采用结构化去重：`root_request_id + requester_pm + target_pm + blocker_type + target_object + action_required` 六个字段全部匹配才视为重复；不匹配则新建。LLM 语义相似判断仅作为 Phase 2 的辅助提示，不作为主去重规则。

**通知：** P0 实时推送 + P1 每小时聚合 + P2 日报，日均 5-10 条推送

**触发升级信号：** `active_tasks > 8` 连续 3 天、`coordination_tasks / execution_tasks > 0.25`、`pm_compact_recovery >= 2/周`、agent 数量稳定 >= 10

### 21.4 阶段三（12-15 agent）：三层 PM

**组织形态：**
```
Program PM（全局优先级和仲裁）
  ├── Domain PM - Product Surface
  │     ├── Pod PM - Chat Experience → fe-1, fe-2, qa-1
  │     └── Pod PM - Growth → fe-3, be-1, review-1
  ├── Domain PM - Platform
  │     ├── Pod PM - API/Auth → be-2, be-3, be-4
  │     └── Pod PM - Files/Skills → be-5, tool-1, qa-2
  └── Domain PM - Hotpick/Data
        ├── Pod PM - Intel → hp-1, hp-2, hp-qa
        └── Pod PM - Taxonomy → hp-3, hp-4, review-2
```

从"按职能拆"演进到"按交付单元拆"，每个 Pod 是一个 feature 闭环。

**config.json 新增字段：**
```json
{
  "orchestration": {
    "mode": "multi_level_pm",
    "topology": "three_level",
    "program_pm": "pm-program",
    "domains": {
      "product_surface": {
        "pm": "pm-domain-product",
        "reports_to": "pm-program",
        "pods": ["pod-chat", "pod-growth"]
      }
    },
    "pods": {
      "pod-chat": {
        "pm": "pm-pod-chat",
        "reports_to": "pm-domain-product",
        "agents": ["fe-1", "fe-2", "qa-1"],
        "max_active_tasks": 6
      }
    }
  }
}
```

**协调规则：** Pod 内自治、同域跨 Pod 经 Domain PM、跨域经 Program PM 仲裁。状态需要做 roll-up：child → pod/domain → program。

**通知：** P0 实时推送 + 看板按需查询，日常不主动推，日均 3-5 条

**继续复杂化的信号：** `coordination_tasks / execution_tasks > 0.25` 连续一周、`integration_queue_wait > 30 分钟` 持续一周、同域跨 Pod 协调成为常态。

#### 阶段二/三的状态 roll-up 规则

- **child → domain/pod**：
  - `done`：所有 child 为 `done`，且 integration / verify 通过
  - `blocked`：任一关键 child 为 `blocked`，且阻塞超过阈值
  - `waiting_external`：存在 coordination / 外部依赖未完成，但当前域内无 failed
  - `at_risk`：存在 failed、重复重试、integration 失败或超时风险
- **domain/pod → program**：
  - `done`：所有 domain/pod 为 `done`
  - `blocked`：任一 domain/pod 进入 `blocked` 且超过阈值
  - `waiting_external`：仅有外部依赖等待，无内部失败
  - `at_risk`：任一 domain/pod 为 `at_risk`

建议阈值：
- `blocked`：阻塞持续 > 30 分钟
- `waiting_external`：依赖等待 > 15 分钟但未到 blocked 门槛
- `at_risk`：同类失败重试 >= 2 次，或 integration 失败 >= 1 次

#### 多 PM 容灾与恢复顺序

1. **root / program PM 恢复**：先恢复全局组织视图、读取所有 domain/pod 任务树
2. **子 PM / domain PM 恢复**：各自只重建本域的活跃任务与 handoff package 视图
3. **integrator / quality PM 恢复**：恢复 integration queue、review queue 和待 gate 任务
4. **orphan task reclaim**：若某任务 `owner_pm` 不在线且 lease 过期，则由上层 PM 暂时接管，并写入 `reclaimed_by`

恢复原则：
- `task.json` 永远比 `pm-state.json` 权威
- 恢复先重建事实，再恢复计划
- reclaim 只在多 PM runtime 启用后生效，单 PM 阶段不自动触发

### 21.5 通知与汇报机制演进

| 维度 | 3-5 agent | 8-10 agent | 12-15 agent |
|------|-----------|------------|------------|
| 推送频率 | 实时全量 | P0 实时 + P1 小时聚合 + P2 日报 | P0 实时 + 看板按需 |
| 日均推送 | 10-20 条 | 5-10 条 | 3-5 条 |
| 开罗尔角色 | 消息转发器 | 通知调度器（分级缓冲+聚合） | 看板维护 + 异常路由 |

**P0 紧急（实时）：** 任务重试耗尽、跨域 blocker 超时、PM 上下文丢失、安全异常

**P1 重要（聚合）：** 任务完成、verify 结果、子 PM 状态变更。聚合格式示例：
```
📊 过去一小时汇总
✅ 完成：3 个（T-001、T-005、T-008）
❌ 失败：1 个（T-003 端口冲突，需人工介入）
⏳ 进行中：4 个
⚠️ 需关注：T-006 跨域阻塞已 45 分钟
```

### 21.6 三阶段 schema 字段演进总结

| 字段 | 阶段一 | 阶段二 | 阶段三 |
|------|--------|--------|--------|
| `mode` | single_pm | hierarchical_pm | multi_level_pm |
| `root_pm` / `integration_owner` | ✅ | ✅ | ✅ |
| `domains` | ✅ | ✅ | ✅ |
| `root_request_id` / `parent_task_id` / `task_level` / `owner_pm` | ✅ | ✅ | ✅ |
| `teams` / `reports_to` / `routing_rules` / `coordination` | — | ✅ | ✅ |
| `child_tasks` / `escalation_to` / `lease_owner` / `lease_expires_at` | — | ✅ | ✅ |
| `topology` / `pods` / `coordination_matrix` / `release_lane` | — | — | ✅ |
| `program_id` / `domain_id` / `pod_id` / `routing_path` | — | — | ✅ |

### 21.7 落地顺序

**现在就做：**
1. config.json 加 `mode / root_pm / integration_owner / domains`
2. task.json 加 `root_request_id / parent_task_id / task_level / owner_pm`
3. 引入 coordination / handoff_package 概念
4. 先让单 PM 按未来分层 schema 工作

**6-8 agent 时启动：**
1. 真正新增子 PM，总 PM 不再直派执行 agent
2. 启用 coordination task 作为跨域协作手段
3. 通知升级为分级聚合

**12+ agent 时再做：**
1. 引入 Pod 视角，升级为三层组织
2. 通知升级为看板 + 异常驱动
