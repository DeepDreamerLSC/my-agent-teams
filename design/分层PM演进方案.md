# 分层 PM 演进方案

> 更新时间：2026-04-23
> 实施主目录: `~/Desktop/work/my-agent-teams/`
> 目标：为 OpenClaw-tmux 协作体系提供一套从 **3-5 个 agent** 演进到 **8-10 个 agent**，再到 **12-15 个 agent** 的分层 PM 组织与 schema 草案。  
> 核心原则：**Agent 规模增长时，先升级“控制面 schema”，再升级“运行时组织结构”**。

---

## 一、结论先说

### 1.1 总体判断

分层 PM 不是“多加几个人转发消息”，而是把调度从“单 PM 的上下文记忆”升级为“有明确层级和责任边界的控制面”。

因此整套方案的核心不是先上多少 PM，而是先统一三件事：

1. **控制面**：谁给谁派任务，谁对谁负责，谁有仲裁权
2. **数据面**：任务依赖、交接物、阻塞原因、集成状态怎么落盘
3. **组织面**：PM 的层级、管辖范围、跨域协调路径

### 1.2 推荐演进路径

- **3-5 个 agent**：继续单 PM，但 schema 先做 `hierarchy-ready`
- **8-10 个 agent**：升级为 **总 PM + 子 PM** 的两层结构
- **12-15 个 agent**：从纯职能分域升级为 **Program PM / Domain PM / Pod PM** 的三层或 hybrid 结构

### 1.3 贯穿三阶段不变的规则

1. `task.json` 仍是**任务事实源**
2. `config.json` 负责**组织拓扑、角色映射、路由规则**
3. **控制面走 PM 层级**，**数据面走结构化任务 / 工件**
4. **同一 task / session 只能有一个 owner**，防止重复调度
5. **跨域协作靠任务依赖与 handoff package，不靠自由聊天**

---

## 二、通用设计原则

### 2.1 单 PM ≠ 单点状态机

无论是单 PM 还是分层 PM，都不要把调度逻辑建立在“PM 自己记住所有事情”上。PM 每次做决策，都应重新读取：

- `task.json`
- `pm-state.json`（计划视图）
- `config.json`（组织与权限视图）
- `scratchpad / handoff package`（中间产物）

### 2.2 控制面与数据面分离

- **控制面**：需求拆解、优先级调整、冲突仲裁、资源重分配
- **数据面**：接口契约、交接工件、联调阻塞、测试结果、diff / verify 结果

建议：
- 控制面默认走 PM 层级
- 数据面通过任务系统里的结构化字段和工件传递

### 2.3 “能并行的执行，不能并行的决策”

随着 agent 数量增长：
- 代码实现可以并行
- 但需求理解、优先级、跨域仲裁不能分裂成多个真相中心

因此：
- **总 PM 是控制面真相中心**
- **子 PM / Pod PM 是局部执行面 owner**

### 2.4 组织升级先于运行时升级

推荐顺序：
1. 先给 schema 加字段
2. 再让现有单 PM 按新字段工作
3. 最后真正启用子 PM

这样不会在 agent 数量上涨时同时触发“任务量膨胀 + schema 重构 + 组织重构”三重风险。

---

## 三、基础 schema 原则（适用于三阶段）

### 3.1 `config.json` 职责

`config.json` 负责：
- 组织拓扑
- agent / PM 角色映射
- team / pod 定义
- 汇报链条
- 协调与升级规则
- integration owner / review owner / queue owner

### 3.2 `task.json` 职责

`task.json` 负责：
- 当前任务是谁的
- 属于哪一个需求树
- 属于哪个域 / pod
- 依赖谁、阻塞谁
- 当前在哪个生命周期阶段
- 当前交接物在哪儿
- 谁负责下一步推进

### 3.3 贯穿三阶段的基础字段

#### `task.json` 基础字段建议

```json
{
  "id": "T-20260423-001",
  "root_request_id": "R-20260423-001",
  "parent_task_id": null,
  "task_level": "execution",
  "title": "实现用户列表页筛选",
  "domain": "frontend",
  "status": "working",
  "owner_pm": "pm-chief",
  "assigned_agent": "dev-1",
  "depends_on": [],
  "blocks": [],
  "write_scope": ["frontend/src/pages/admin/**"],
  "artifacts": [],
  "handoff_package": null,
  "created_at": "2026-04-23T10:00:00+08:00",
  "updated_at": "2026-04-23T10:05:00+08:00"
}
```

#### 字段说明

| 字段 | 作用 |
|---|---|
| `root_request_id` | 同一用户需求下所有任务的归并 ID |
| `parent_task_id` | 形成任务树，支持总 PM → 子 PM → agent 逐层拆解 |
| `task_level` | 区分 `epic / domain / execution / review / integration / coordination` |
| `owner_pm` | 当前真正负责推进该任务的人 |
| `assigned_agent` | 真正执行的人，若是 PM 级任务可为空 |
| `depends_on` | 当前任务依赖哪些任务 |
| `blocks` | 当前任务完成后会解锁哪些任务 |
| `handoff_package` | 结构化交接物索引 |

---

# 四、阶段一：3-5 个 agent（当前阶段到近期）

## 4.1 组织形态

### 推荐形态
- **1 个 PM-chief**
- **3-5 个执行 agent**
- 可有 1 个 review / integrator 角色，但不独立成 PM

### 适用特征
- 活跃任务数通常 <= 6
- 跨域冲突可由一个 PM 直接掌握
- 总 PM 还没有明显的上下文爆炸问题

### 当前目标
不是立刻上子 PM，而是：

> **让当前 schema 具备未来分层的兼容性。**

---

## 4.2 `config.json`（3-5 agent 版本）

### 结构重点
- 仍是 `single_pm`
- 但提前加上：`hierarchy_ready`、`integration_owner`、`domains`
- 让后续切到多 PM 时不需要推倒重来

### 示例

```json
{
  "version": 1,
  "orchestration": {
    "mode": "single_pm",
    "hierarchy_ready": true,
    "root_pm": "pm-chief",
    "integration_owner": "review-1",
    "escalation_policy": {
      "cross_domain_conflict": "pm-chief",
      "retries_exhausted": "pm-chief",
      "integration_failure": "pm-chief"
    },
    "domains": {
      "frontend": ["dev-1", "fe-2"],
      "backend": ["dev-2", "be-2"],
      "quality": ["review-1"]
    }
  },
  "agents": {
    "pm-chief": {
      "role": "pm",
      "tmux_session": "pm-chief",
      "responsibility": ["planning", "dispatch", "tracking", "triage"]
    },
    "dev-1": {
      "role": "frontend_dev",
      "tmux_session": "dev-1",
      "domain": "frontend"
    },
    "fe-2": {
      "role": "frontend_dev",
      "tmux_session": "fe-2",
      "domain": "frontend"
    },
    "dev-2": {
      "role": "backend_dev",
      "tmux_session": "dev-2",
      "domain": "backend"
    },
    "be-2": {
      "role": "backend_dev",
      "tmux_session": "be-2",
      "domain": "backend"
    },
    "review-1": {
      "role": "reviewer",
      "tmux_session": "review-1",
      "domain": "quality"
    }
  }
}
```

---

## 4.3 `task.json`（3-5 agent 版本）

### 结构重点
- 单 PM 直接调度
- 但提前预留 `parent_task_id`、`task_level`、`owner_pm`

### 示例

```json
{
  "id": "T-20260423-001",
  "root_request_id": "R-20260423-001",
  "parent_task_id": null,
  "task_level": "execution",
  "title": "为聊天页增加搜索跳转高亮",
  "domain": "frontend",
  "owner_pm": "pm-chief",
  "assigned_agent": "dev-1",
  "status": "working",
  "lease_owner": "pm-chief",
  "lease_acquired_at": "2026-04-23T10:00:00+08:00",
  "lease_expires_at": "2026-04-23T18:00:00+08:00",
  "priority": "high",
  "depends_on": [],
  "blocks": ["T-20260423-003"],
  "integration_owner": "review-1",
  "write_scope": [
    "frontend/src/components/ChatSidebar.tsx",
    "frontend/src/components/MessageBubble.tsx"
  ],
  "artifacts": [
    {
      "type": "instruction",
      "path": "tasks/T-20260423-001/instruction.md"
    }
  ],
  "handoff_package": null,
  "created_at": "2026-04-23T10:00:00+08:00",
  "updated_at": "2026-04-23T10:05:00+08:00"
}
```

---

## 4.4 当前阶段 PM 职责划分

### PM-chief
负责：
- 理解需求
- 拆解任务
- 直接派发给 agent
- 跟踪所有任务状态
- 协调简单跨域依赖
- 决定何时进入 review / integration

### review / integrator（非 PM）
负责：
- 接 review / integration 类型任务
- 对交付结果做 gate
- 不负责全局调度

---

## 4.5 协调机制

### 当前阶段推荐
- **默认全部经 PM-chief 中转**
- agent 之间不直接聊天
- 中间产物通过 `handoff_package` / `artifacts` 传递

### 为什么现在不必过早放开直接协调
因为 3-5 个 agent 阶段，复杂度主要来自“执行细节”，不是“协调网络过大”。此时直接通信收益不大，反而容易造成：
- 信息双轨
- PM 视图不完整
- 谁负责不清楚

---

## 4.6 触发升级到下一阶段的信号

出现以下任意 3 条，说明应准备进入 8-10 agent 的分层 PM：

1. `active_tasks > 8` 连续 3 天
2. `pm_compact_recovery >= 2/周`
3. 前后端 / 测试跨域 blocker 每天很多
4. integration 失败后，PM 要来回协调多个执行者
5. 总 PM 成为明显瓶颈，agent 空闲等待调度
6. `integration_queue_wait > 30 分钟` 持续一周，或同时在线 agent 数量稳定 >= 6

---

# 五、阶段二：8-10 个 agent（中期）

## 5.1 推荐组织结构

### 组织图

```text
林总工
  │
  ▼
PM-chief（总 PM）
  ├── PM-frontend（子 PM）
  │     ├── dev-1
  │     ├── fe-2
  │     └── fe-3
  ├── PM-backend（子 PM）
  │     ├── dev-2
  │     ├── be-2
  │     └── be-3
  └── PM-quality / Integrator
        ├── qa-1
        └── review-1
```

### 说明
这是一个**两层 PM**结构：
- 总 PM：只管全局
- 子 PM：只管本域 2-3 个 agent
- 质量 / 集成可做成子 PM，也可做成集成门负责人

---

## 5.2 推荐分域方式

### 默认推荐：按职能分域
- `frontend`
- `backend`
- `quality`

### 适用原因
- 与当前 agent 能力分工一致
- 迁移成本最低
- 比 feature pod 更容易落地

### 注意
到这个阶段，**总 PM 不再直接派任务给所有执行 agent**。总 PM 只做：
- 需求拆解为域级任务
- 把域级任务派给子 PM
- 看子 PM 汇报

---

## 5.3 `config.json`（8-10 agent 版本）

### 结构变化
相较 3-5 agent 版本，新增：
- `mode = hierarchical_pm`
- `teams`
- `reports_to`
- `coordination`
- `routing_rules`

### 完整示例

```json
{
  "version": 2,
  "orchestration": {
    "mode": "hierarchical_pm",
    "root_pm": "pm-chief",
    "integration_owner": "pm-quality",
    "coordination": {
      "control_plane": "via_root_pm",
      "data_plane": "structured_task_handoff",
      "cross_team_policy": "request_via_coordination_task"
    },
    "routing_rules": {
      "frontend": "pm-frontend",
      "backend": "pm-backend",
      "qa": "pm-quality",
      "review": "pm-quality",
      "integration": "pm-quality"
    },
    "teams": {
      "frontend": {
        "pm": "pm-frontend",
        "reports_to": "pm-chief",
        "agents": ["dev-1", "fe-2", "fe-3"],
        "domains": ["frontend"],
        "max_active_tasks": 6
      },
      "backend": {
        "pm": "pm-backend",
        "reports_to": "pm-chief",
        "agents": ["dev-2", "be-2", "be-3"],
        "domains": ["backend", "data", "api"],
        "max_active_tasks": 6
      },
      "quality": {
        "pm": "pm-quality",
        "reports_to": "pm-chief",
        "agents": ["qa-1", "review-1"],
        "domains": ["qa", "review", "integration"],
        "max_active_tasks": 4
      }
    }
  },
  "agents": {
    "pm-chief": {
      "role": "pm_root",
      "tmux_session": "pm-chief"
    },
    "pm-frontend": {
      "role": "pm_domain",
      "domain": "frontend",
      "tmux_session": "pm-frontend"
    },
    "pm-backend": {
      "role": "pm_domain",
      "domain": "backend",
      "tmux_session": "pm-backend"
    },
    "pm-quality": {
      "role": "pm_domain",
      "domain": "quality",
      "tmux_session": "pm-quality"
    },
    "dev-1": { "role": "frontend_dev", "domain": "frontend", "tmux_session": "dev-1" },
    "fe-2": { "role": "frontend_dev", "domain": "frontend", "tmux_session": "fe-2" },
    "fe-3": { "role": "frontend_dev", "domain": "frontend", "tmux_session": "fe-3" },
    "dev-2": { "role": "backend_dev", "domain": "backend", "tmux_session": "dev-2" },
    "be-2": { "role": "backend_dev", "domain": "backend", "tmux_session": "be-2" },
    "be-3": { "role": "backend_dev", "domain": "backend", "tmux_session": "be-3" },
    "qa-1": { "role": "qa", "domain": "quality", "tmux_session": "qa-1", "home_team": "quality" },
    "review-1": {
      "role": "reviewer",
      "domain": "quality",
      "tmux_session": "review-1",
      "home_team": "quality",
      "can_support": ["frontend", "backend"],
      "borrow_policy": "borrowed_by_task"
    }
  }
}
```

---

## 5.4 `task.json`（8-10 agent 版本）

### 结构变化
新增：
- `team`
- `child_tasks`
- `coordination_channel`
- `report_to`
- `escalation_to`
- `integration_owner`
- `lease_owner`

### 域级任务示例（总 PM → 子 PM）

```json
{
  "id": "T-20260423-100",
  "root_request_id": "R-20260423-100",
  "parent_task_id": null,
  "task_level": "domain",
  "title": "聊天搜索功能前端域任务",
  "domain": "frontend",
  "team": "frontend",
  "owner_pm": "pm-frontend",
  "assigned_agent": null,
  "report_to": "pm-chief",
  "escalation_to": "pm-chief",
  "status": "working",
  "priority": "high",
  "depends_on": ["T-20260423-101"],
  "child_tasks": ["T-20260423-102", "T-20260423-103"],
  "coordination_channel": "coord-task-only",
  "integration_owner": "pm-quality",
  "lease_owner": "pm-frontend",
  "lease_acquired_at": "2026-04-23T10:00:00+08:00",
  "lease_expires_at": "2026-04-23T18:00:00+08:00",
  "artifacts": [],
  "handoff_package": null
}
```

### 执行级任务示例（子 PM → agent）

```json
{
  "id": "T-20260423-102",
  "root_request_id": "R-20260423-100",
  "parent_task_id": "T-20260423-100",
  "task_level": "execution",
  "title": "实现搜索结果组头与命中计数 UI",
  "domain": "frontend",
  "team": "frontend",
  "owner_pm": "pm-frontend",
  "assigned_agent": "fe-2",
  "report_to": "pm-frontend",
  "escalation_to": "pm-chief",
  "status": "working",
  "priority": "medium",
  "depends_on": [],
  "blocks": ["T-20260423-104"],
  "coordination_channel": "coord-task-only",
  "integration_owner": "pm-quality",
  "write_scope": [
    "frontend/src/components/ChatSidebar.tsx"
  ],
  "handoff_package": {
    "type": "ui_patch",
    "consumers": ["pm-quality"],
    "paths": [
      "tasks/T-20260423-102/result.json",
      "tasks/T-20260423-102/summary.md"
    ]
  }
}
```

### 协调任务示例（子 PM 之间的跨域协调）

```json
{
  "id": "T-20260423-104",
  "root_request_id": "R-20260423-100",
  "parent_task_id": "T-20260423-100",
  "task_level": "coordination",
  "title": "确认搜索接口返回 snippet 高亮字段与跳转 anchor",
  "domain": "cross-domain",
  "team": "coordination",
  "owner_pm": "pm-chief",
  "assigned_agent": null,
  "requester_pm": "pm-frontend",
  "target_pm": "pm-backend",
  "report_to": "pm-chief",
  "status": "blocked",
  "depends_on": ["T-20260423-102"],
  "dedup_key": "R-20260423-100|pm-frontend|pm-backend|api_contract_missing|chat-search-api|provide_contract",
  "coordination_payload": {
    "blocker_type": "api_contract_missing",
    "target_object": "chat-search-api",
    "action_required": "provide_contract",
    "question": "后端是否提供 snippet + message_id + session_id + anchor_offset？",
    "required_artifacts": ["api_contract"],
    "deadline": "2026-04-23T15:00:00+08:00"
  },
  "handoff_package": {
    "type": "api_contract",
    "consumers": ["pm-frontend", "pm-quality"],
    "paths": ["tasks/T-20260423-104/api-contract.json"]
  }
}
```

---

## 5.5 8-10 agent 阶段的 PM 职责划分

### PM-chief（总 PM）
负责：
- 理解需求
- 做跨域拆解
- 维护全局优先级
- 处理跨队冲突
- 批准协调任务
- 汇总子 PM 状态
- 决定何时进入 integration / release

### PM-frontend / PM-backend / PM-quality（子 PM）
负责：
- 管理本域 2-3 个 agent
- 派发执行任务
- 跟踪任务状态
- 处理完成通知
- 整理本域 handoff package
- 向总 PM 汇报

### PM-quality 的特殊角色
- 兼任 integration gate owner
- 管 review / QA / 集成验证
- 可以不直接写代码，只推进集成闭环

---

## 5.6 子 PM 之间怎么协调

### 推荐规则
**不要自由私聊，也不要让总 PM 逐条人工转发。**

推荐方式：
- **控制面**：通过总 PM
- **数据面**：通过 `coordination task + handoff package`

### 也就是
- 子 PM A 需要子 PM B 的配合时：
  - 不直接发自然语言消息
  - 创建 `coordination` 级任务
  - 总 PM 可见并有仲裁权
  - 子 PM B 用结构化产物回复

### 这样做的好处
- 保持总 PM 对全局依赖的可见性
- 避免总 PM 成为纯消息泵
- 避免子 PM 私聊导致系统事实源失真

---

## 5.6.1 状态 roll-up 规则（child → domain）

阶段二开始，总 PM 不再直接盯每个 execution task，因此必须定义域级状态汇总。

### child → domain

- **`done`**：所有 child_tasks 都为 `done`，且 integration / verify 通过
- **`blocked`**：任一关键 child_task 为 `blocked`，且阻塞持续 > 30 分钟
- **`waiting_external`**：存在 coordination task 或外部依赖未完成，但本域内无 failed
- **`at_risk`**：出现 failed、重复重试（同类 reason >= 2 次）、integration 失败或 SLA 超时风险

### domain → chief 视图

总 PM 在阶段二看到的不是 execution 明细，而是域汇总：
- 域为 `done`：可进入下一阶段或等待 integration
- 域为 `waiting_external`：说明对外部/跨域有依赖，但不是内部执行崩溃
- 域为 `blocked`：需要总 PM 仲裁或资源重排
- 域为 `at_risk`：需要总 PM 重点关注，可能即将升级为人工介入

## 5.6.2 coordination task 去重规则

阶段二开始必须避免子 PM 因同一 blocker 重复建协调任务。

### 结构化去重主规则

以下 6 个字段**全部匹配**才视为重复：

1. `root_request_id`
2. `requester_pm`
3. `target_pm`
4. `blocker_type`
5. `target_object`
6. `action_required`

即：

```text
dedup_key =
root_request_id
+ requester_pm
+ target_pm
+ blocker_type
+ target_object
+ action_required
```

### 处理规则

- 六字段全部匹配：**不新建 task**，只给已有 coordination task append follow-up / comment
- 任一字段不匹配：**新建 coordination task**
- 已关闭任务再次出现相同问题：新建 task，但可通过 `reopened_from` 或 `same_dedup_key_count` 关联历史

### LLM 语义去重的位置

- **Phase 1 / 2 主机制：不用 LLM 做主去重**
- **Phase 2 辅助能力：** 若结构化字段高度接近、文本描述相似，可提示 PM“可能与某任务重复”，但只做提示，不自动合并

## 5.6.3 字段写权限（field ownership matrix）

阶段二开始，光有 team / owner_pm / coordination task 还不够，必须明确**谁能改哪些字段**，否则多 PM 很快会出现“谁都能改、最后没人负责”的问题。

| 字段 | 总 PM | 子 PM | integrator / quality PM | watcher | agent |
|---|---|---|---|---|---|
| `status` | ✅ 全部可改 | ✅ 仅本 team 任务可改 | ✅ 仅 integration / review 相关状态可改 | ✅ 仅自动推进（如 dispatched→working / timeout） | ❌ 不直接改 |
| `owner_pm` | ✅ | ❌ | ❌ | ❌ | ❌ |
| `assigned_agent` | ✅ | ✅ 仅本 team | ❌ | ❌ | ❌ |
| `team` | ✅ | ❌ | ❌ | ❌ | ❌ |
| `handoff_package` | ✅ | ✅ 可补本 team 产物索引 | ✅ 可补 integration 产物索引 | ❌ | ✅ 仅写自己任务对应产物 |
| `integration_owner` | ✅ | ❌ | ❌ | ❌ | ❌ |
| `lease_owner` | ✅ | ✅ 仅本 team | ✅ 仅 integration queue 中自己接管的任务 | ❌ | ❌ |

### 最小原则

- **总 PM**：唯一可以修改组织归属类字段（`owner_pm` / `team`）
- **子 PM**：只能修改自己 `home_team` 范围内任务的派发与状态
- **integrator / quality PM**：只处理 integration lane / review lane，不重排业务域 owner
- **watcher**：只做机械推进，不做调度决策
- **agent**：不直接改 `task.json`，只通过 `ack.json` / `result.json` / 产物文件表达结果

## 5.6.4 子 PM 边界约束与 borrow 机制

### 边界约束

- 每个 agent 必须且仅有一个 `home_team`
- 子 PM **只能调度自己 `home_team` 下的 agent**
- 子 PM 不能跨 team 直接改 `assigned_agent` 或 `owner_pm`
- 总 PM 才能修改 team / owner_pm / 组织归属类字段

### borrow 机制

对 review / qa / integrator 这类共享资源，不采用“多 team 同时拥有”，而采用：

- `home_team`：唯一归属
- `can_support`：允许支援的 team 列表
- `borrow_policy`：如 `borrowed_by_task`

含义是：
- agent 组织归属保持唯一
- 但可以按 task 临时借调支援其他 team
- 借调结束后自动回到 `home_team`

## 5.6.5 多 PM 容灾与恢复顺序

阶段二启用多 PM runtime 后，恢复顺序必须固定，否则容易出现两个 PM 同时接管同一批任务。

### 恢复顺序

1. **root PM 恢复**：先重建全局组织视图和 team → PM 映射
2. **子 PM 恢复**：各自只重建本 team 的活跃任务与 handoff package 视图
3. **integrator / quality PM 恢复**：恢复 integration queue / review queue
4. **orphan task reclaim**：若任务 `owner_pm` 不在线且 lease 已过期，则由上层 PM 暂时接管，并写入 `reclaimed_by`

### 恢复原则

- `task.json` 永远比 `pm-state.json` 更权威
- 先恢复事实，再恢复计划
- reclaim 只在多 PM runtime 启用后生效

## 5.6.6 lease 语义（Phase 2）

阶段二开始，lease 不再只是观测字段，而变成真正的调度控制语义。

- `lease_owner`：当前谁拥有任务推进权
- `lease_acquired_at`：何时取得所有权
- `lease_expires_at`：在无续租情况下何时可被 reclaim
- `lease_kind`（可选）：如 `ownership` / `borrowed_support`

### reclaim 规则

- 任务 owner 离线或失联，且 `lease_expires_at` 已过 → 可进入 reclaim
- reclaim 默认由上层 PM 执行，而不是同级 PM 抢占
- reclaim 后必须写入：
  - `reclaimed_by`
  - `reclaimed_at`
  - `reclaim_reason`

## 5.7 触发升级到下一阶段的信号

以下任意 4 条成立，说明要考虑从“职能分域 + 两层 PM”升级到更复杂结构：

1. `active_tasks > 8` 连续 3 天
2. `coordination_tasks / execution_tasks > 0.25`
3. `pm_compact_recovery >= 2/周`
4. `integration_queue_wait > 30 分钟` 持续一周
5. 同一需求下出现多个前后端子系统并行推进
6. agent 数量稳定 >= 10

---

# 六、阶段三：12-15 个 agent（长期）

## 6.1 为什么两层 PM 不够了

当 agent 到 12-15 个时，问题不再只是“多几个执行者”，而是：
- 需求树更复杂
- 子 PM 之间协调频繁
- review / integration 成为瓶颈
- 单纯按前后端划分已经不够表达 feature 闭环

此时推荐从“纯职能分域”升级成：

> **Program PM + Domain PM + Pod PM** 的三层或 hybrid 结构

---

## 6.2 推荐组织结构（长期）

### 方案：三层 PM / 混合组织

```text
林总工
  │
  ▼
Program PM（全局项目/需求组合管理）
  ├── Domain PM - Product Surface
  │     ├── Pod PM - Chat Experience
  │     │     ├── FE-1
  │     │     ├── FE-2
  │     │     └── QA-1
  │     └── Pod PM - Growth / Feedback
  │           ├── FE-3
  │           ├── BE-1
  │           └── Review-1
  ├── Domain PM - Platform / Backend
  │     ├── Pod PM - API / Auth / Permissions
  │     │     ├── BE-2
  │     │     ├── BE-3
  │     │     └── BE-4
  │     └── Pod PM - Files / Skills / STT
  │           ├── BE-5
  │           ├── Tool-1
  │           └── QA-2
  └── Domain PM - Hotpick / Data
        ├── Pod PM - Intel
        │     ├── HP-1
        │     ├── HP-2
        │     └── HP-QA
        └── Pod PM - Taxonomy / Reports
              ├── HP-3
              ├── HP-4
              └── Review-2
```

### 设计含义
- **Program PM**：只看全局业务目标、路线图、优先级和跨域仲裁
- **Domain PM**：管理一个大域的资源与依赖
- **Pod PM**：真正推动 2-4 个 agent 交付一个 feature/pod 闭环

这是从“按职能拆”向“按交付单元拆”的演进。

---

## 6.3 `config.json`（12-15 agent 版本）

### 结构变化
相较中期版本，新增：
- `topology = three_level`
- `domains`
- `pods`
- `capacity`
- `coordination_matrix`
- `cross_pod_policy`

### 示例

```json
{
  "version": 3,
  "orchestration": {
    "mode": "multi_level_pm",
    "topology": "three_level",
    "program_pm": "pm-program",
    "cross_pod_policy": "coordination_task_first",
    "integration_owner": "pm-release",
    "domains": {
      "product_surface": {
        "pm": "pm-domain-product",
        "reports_to": "pm-program",
        "pods": ["pod-chat", "pod-growth"]
      },
      "platform_backend": {
        "pm": "pm-domain-platform",
        "reports_to": "pm-program",
        "pods": ["pod-auth-api", "pod-files-skills"]
      },
      "hotpick_data": {
        "pm": "pm-domain-hotpick",
        "reports_to": "pm-program",
        "pods": ["pod-intel", "pod-taxonomy-reports"]
      }
    },
    "pods": {
      "pod-chat": {
        "pm": "pm-pod-chat",
        "reports_to": "pm-domain-product",
        "agents": ["dev-1", "fe-2", "qa-1"],
        "domains": ["chat_ui", "chat_interaction"],
        "max_active_tasks": 6
      },
      "pod-auth-api": {
        "pm": "pm-pod-auth-api",
        "reports_to": "pm-domain-platform",
        "agents": ["be-2", "be-3", "be-4"],
        "domains": ["auth", "api", "permission"],
        "max_active_tasks": 6
      },
      "pod-intel": {
        "pm": "pm-pod-intel",
        "reports_to": "pm-domain-hotpick",
        "agents": ["hp-1", "hp-2", "hp-qa"],
        "domains": ["hotpick_intel"],
        "max_active_tasks": 6
      }
    },
    "coordination_matrix": {
      "chat_ui->auth": "via_domain_pm",
      "chat_ui->hotpick_intel": "via_program_pm",
      "hotpick_intel->permission": "via_domain_pm"
    }
  },
  "agents": {
    "pm-program": { "role": "pm_program", "tmux_session": "pm-program" },
    "pm-domain-product": { "role": "pm_domain", "tmux_session": "pm-domain-product" },
    "pm-pod-chat": { "role": "pm_pod", "tmux_session": "pm-pod-chat" },
    "dev-1": { "role": "frontend_dev", "tmux_session": "dev-1" },
    "qa-1": { "role": "qa", "tmux_session": "qa-1" }
  }
}
```

---

## 6.4 `task.json`（12-15 agent 版本）

### 结构变化
新增：
- `program_id`
- `domain_id`
- `pod_id`
- `routing_path`
- `coordination_scope`
- `release_lane`

### 示例

```json
{
  "id": "T-20260423-900",
  "root_request_id": "R-20260423-900",
  "program_id": "PRG-chat-search-202604",
  "domain_id": "product_surface",
  "pod_id": "pod-chat",
  "parent_task_id": "T-20260423-800",
  "task_level": "execution",
  "title": "移动端聊天搜索入口与折叠态交互",
  "domain": "chat_ui",
  "team": "pod-chat",
  "owner_pm": "pm-pod-chat",
  "report_to": "pm-domain-product",
  "escalation_to": "pm-program",
  "assigned_agent": "dev-1",
  "status": "working",
  "priority": "high",
  "depends_on": ["T-20260423-901"],
  "blocks": ["T-20260423-950"],
  "routing_path": ["pm-program", "pm-domain-product", "pm-pod-chat", "dev-1"],
  "coordination_scope": "cross_pod",
  "integration_owner": "pm-release",
  "release_lane": "release-train-A",
  "write_scope": [
    "frontend/src/components/ChatSidebar.tsx",
    "frontend/src/pages/Chat.tsx"
  ],
  "handoff_package": {
    "type": "pod_delivery",
    "consumers": ["pm-release", "qa-1"],
    "paths": [
      "tasks/T-20260423-900/result.json",
      "tasks/T-20260423-900/transitions.jsonl",
      "tasks/T-20260423-900/summary.md"
    ]
  }
}
```

---

## 6.5 长期阶段 PM 职责划分

### Program PM
负责：
- 需求组合管理
- 跨域优先级
- 跨域冲突仲裁
- release / release train 节奏
- 大范围资源重分配

### Domain PM
负责：
- 管辖某个大域
- 维护域内 capacity
- 处理跨 pod 但同域的协调
- 决定哪些工作进入哪个 pod

### Pod PM
负责：
- 管理 2-4 个 agent 的 feature 闭环
- 保证 pod 内交付速度与稳定性
- 对接 integration / release

---

## 6.6 长期阶段协调机制

### 协调规则

#### Pod 内
- Pod PM 直接调度
- 不需要域 PM 介入

#### 同域跨 Pod
- 先经 Domain PM
- 数据通过 coordination task + handoff package

#### 跨域跨 Pod
- 先创建 coordination task
- 默认升级到 Program PM 作为仲裁者

### 原因
到 12-15 agent 阶段，如果还让所有跨域事务都压到 Program PM，会再次形成瓶颈；但如果放开 pod 间自由直连，又会丢失全局控制面。因此需要：

> **Pod 闭环自治，跨 pod 受控协调，跨域由 Program PM 仲裁。**

---

## 6.6.1 状态 roll-up 规则（child → pod/domain → program）

阶段三开始，状态汇总要从单域提升到 pod / domain / program 三层。

### child → pod
- `done`：所有 child 为 `done` 且 pod 内集成通过
- `blocked`：任一关键 child `blocked` 且超过阈值
- `waiting_external`：主要在等其他 pod / 外部依赖
- `at_risk`：重复失败、重试耗尽、integration 连续失败

### pod → domain
- `done`：domain 下所有 pod 完成
- `blocked`：任一 pod blocked 且影响同域计划
- `waiting_external`：同域 pod 等待跨 pod 协调
- `at_risk`：任一 pod at_risk

### domain → program
- `done`：所有 domain 完成
- `blocked`：任一 domain blocked 超过阈值
- `waiting_external`：仅有外部依赖等待，无内部失败
- `at_risk`：任一 domain 进入 at_risk

建议阈值：
- `blocked`：阻塞持续 > 30 分钟
- `waiting_external`：依赖等待 > 15 分钟但未到 blocked 门槛
- `at_risk`：同类失败重试 >= 2 次，或 integration 失败 >= 1 次

## 6.7 触发进入三层结构的信号

当 8-10 agent 阶段出现以下情况时，说明应从两层 PM 升级：

1. `active_tasks > 8` 连续 3 天（按 domain 或 pod 统计）
2. `coordination_tasks / execution_tasks > 0.25` 连续一周
3. `pm_compact_recovery >= 2/周`
4. `integration_queue_wait > 30 分钟` 持续一周
5. 某些需求已经天然形成 feature pod 闭环
6. 多个需求并行时，总 PM 无法只看域级状态就做决策

---

# 七、三阶段对比总结

## 7.1 组织结构对比

| 阶段 | 规模 | 组织结构 | 主目标 |
|---|---:|---|---|
| 阶段一 | 3-5 agent | 单 PM | 先把 schema 做 hierarchy-ready |
| 阶段二 | 8-10 agent | 总 PM + 子 PM | 控制面分层、上下文降压 |
| 阶段三 | 12-15 agent | Program PM + Domain PM + Pod PM | 从职能调度升级为交付单元调度 |

## 7.2 `config.json` 变化重点

| 阶段 | 关键字段 |
|---|---|
| 阶段一 | `mode`, `root_pm`, `integration_owner`, `domains` |
| 阶段二 | `teams`, `reports_to`, `routing_rules`, `coordination` |
| 阶段三 | `topology`, `domains`, `pods`, `coordination_matrix`, `release_lane` |

## 7.3 `task.json` 变化重点

| 阶段 | 新增重点 |
|---|---|
| 阶段一 | `root_request_id`, `parent_task_id`, `task_level`, `owner_pm`, `lease_owner`, `lease_expires_at` |
| 阶段二 | `team`, `child_tasks`, `coordination_channel`, `lease_owner`, `lease_expires_at`, `escalation_to` |
| 阶段三 | `program_id`, `domain_id`, `pod_id`, `routing_path`, `coordination_scope`, `release_lane` |

---

# 八、推荐落地顺序

## 8.1 现在就该做的（不等 8 个 agent）

1. 给 `config.json` 加上 `mode / root_pm / integration_owner / domains`
2. 给 `task.json` 加上 `root_request_id / parent_task_id / task_level / owner_pm`
3. 引入 `coordination` / `handoff_package` 的概念
4. 统一 task 树与依赖表达方式
5. 先让单 PM 按未来分层 schema 工作

## 8.2 到 6-8 个 agent 时启动的

1. 真正新增子 PM
2. 总 PM 不再直派执行 agent
3. 启用 coordination task 作为子 PM 间协作手段
4. 让质量 / integration 成为单独 lane

## 8.3 到 12+ 个 agent 时再做的

1. 引入 pod 视角
2. 把组织从纯职能分域升级到 hybrid 结构
3. 增加 domain/program 级容量和 release 节奏管理

---

# 九、通知与汇报机制演进

> 核心原则：**agent 越多，推送给林总工的信息越少、越精炼。**
> 分层 PM 解决的是"谁来管"，通知演进解决的是"谁来告诉林总工"。否则只是换了种方式被信息淹没。

## 9.1 为什么需要演进通知机制

当前 2-3 个 agent 时，每个任务完成、异常、verify 结果都直推飞书，一天约 10-20 条，可逐条查看。

但 8+ agent 时，子 PM 的定期汇报、coordination task 通知、异常告警叠加，一天轻松 50-100 条。12+ agent 时可能 200+ 条。不分级推送，飞书变成噪音，林总工会选择全部忽略。

## 9.2 阶段一（3-5 agent）：全量直推

### 通知策略
- 所有事件实时推送，不做分级
- 格式：自然语言，详细描述

### 推送内容
```
每个任务完成 → 立即推送
每个 verify 结果 → 立即推送
每个异常（failed/blocked/timeout）→ 立即推送
PM 状态变更 → 立即推送
```

### 示例
```
✅ T-001 完成：聊天搜索高亮功能已实现，verify 通过，等待集成
❌ T-003 失败：数据库迁移端口冲突，正在重试（第 1 次）
⚠️ T-005 被阻塞：等待 T-002 前端接口定义完成
```

### 频率
实时，预计日均 10-20 条

---

## 9.3 阶段二（8-10 agent）：分级 + 聚合

### 通知分级

| 级别 | 定义 | 推送方式 | 频率 |
|------|------|----------|------|
| **P0 紧急** | 需林总工人工介入 | 实时推送 | 即时 |
| **P1 重要** | 需林总工关注 | 聚合推送 | 每小时一次 |
| **P2 信息** | 可延后查看 | 日报 | 每日一次 |

### P0 紧急（实时推送）
- 任务 failed 且重试耗尽
- 跨域 blocker 超过 1 小时未解决
- PM 上下文丢失需恢复
- 安全/合规相关异常
- 子 PM 自身异常（session 挂掉、API 过载）

### P1 重要（每小时聚合）
- 任务完成 + verify 通过
- 任务完成 + verify 失败（含失败原因）
- 子 PM 状态变更（域内任务汇总）
- coordination task 的关键进展

### P2 信息（日报）
- 子 PM 定期状态汇报
- 任务创建/分配记录
- agent 上下文 compact 记录
- 工作量统计

### 聚合推送格式
```
📊 过去一小时状态汇总（10:00-11:00）

✅ 完成（3）：
  T-001 前端搜索高亮 → verify 通过
  T-005 后端搜索API → verify 通过
  T-008 权限重构 → verify 通过

❌ 失败（1）：
  T-003 数据库迁移 → 端口冲突，已重试 2 次均失败，需人工介入

⏳ 进行中（4）：
  T-002 前端接口定义（dev-1，预计 11:30 完成）
  T-006 前后端联调（blocked，等待 T-005 集成）
  T-009 审查任务（review-1，进行中）
  T-010 通知服务改造（be-2，进行中）

⚠️ 需关注：
  T-003 失败需人工介入
  T-006 跨域阻塞已持续 45 分钟
```

### 实现机制
- 开罗尔本地维护通知队列，按优先级缓冲
- P0 立即调用 feishu-push.sh 推送
- P1 每小时定时触发聚合，生成摘要后推送
- P2 写入 `memory/daily-report-{date}.md`，次日心跳时推送前日日报

---

## 9.4 阶段三（12-15 agent）：看板 + 异常驱动

### 通知策略
- P0 仍实时推送（同阶段二）
- P1 降为子 PM 级别聚合（每个子 PM 每小时一次摘要）
- P2 取消主动推送，只在林总工主动询问时返回
- 新增轻量看板，支持随时查询

### 看板设计

维护一个 markdown 文件作为实时看板，林总工随时可以问"当前状态如何"，开罗尔从看板读取返回：

```markdown
# 项目状态看板
> 最后更新：2026-04-23 11:00

## Program: 聊天搜索功能
| Pod | 状态 | 进度 | 阻塞 |
|-----|------|------|------|
| Pod-Chat | 🔄 进行中 | 2/4 done | 0 |
| Pod-API | ⚠️ 部分阻塞 | 1/3 done | 1 |
| Pod-QA | 🔄 进行中 | 0/2 done | 1 (等待 Pod-API) |

## Program: 权限系统改造
| Pod | 状态 | 进度 | 阻塞 |
|-----|------|------|------|
| Pod-Auth | ✅ 即将完成 | 3/4 done | 0 |
| Pod-Files | 🔄 进行中 | 1/3 done | 0 |

## 汇总
- 今日完成：5 个任务
- 活跃阻塞：2 个（跨域 1 个，域内 1 个）
- 待集成：3 个
- 需人工介入：0 个
- 各子 PM 上下文健康：✅ 全部正常
```

### 子 PM 级别聚合示例
```
📊 PM-frontend 小时报（10:00-11:00）

域内任务：4 个活跃
  ✅ T-102 搜索高亮UI → done
  🔄 T-103 搜索结果分页 → fe-2 执行中（预计 11:20）
  🔄 T-104 移动端适配 → fe-3 执行中
  ⏳ T-105 动画优化 → pending，等待 T-104 完成

跨域需求：
  🔗 T-200 协调任务：需后端确认接口字段，等待 pm-backend 回复（已 30min）

域内健康：正常，无阻塞
```

### 交互模式变化
- 林总工问"状态如何" → 开罗尔从看板读取，返回摘要（不是逐条转发消息历史）
- 林总工问"前端怎么样" → 开罗尔从看板读取 Pod-Chat 行，返回前端域摘要
- 林总工说"我看看 T-003" → 开罗尔从 task.json 和 transitions.jsonl 读取，返回该任务的完整链路
- 不再主动推送日常进度，只推 P0 异常和里程碑完成

---

## 9.5 三阶段通知对比

| 维度 | 阶段一（3-5） | 阶段二（8-10） | 阶段三（12-15） |
|------|-------------|-------------|--------------|
| 推送频率 | 实时全量 | 分级：实时+小时聚合+日报 | 异常驱动+看板 |
| 日均推送量 | 10-20 条 | 5-10 条（P0 实时）+ 聚合 | 3-5 条（P0 实时） |
| 推送内容 | 逐条详情 | P0 详情 + P1 摘要 | P0 详情 + 看板查询 |
| 信息密度 | 低（逐条） | 中（聚合摘要） | 高（按需查询） |
| 开罗尔负担 | 转发即可 | 需维护通知队列+聚合逻辑 | 需维护看板+查询接口 |
| 林总工体验 | 逐条看 | 每小时扫一眼 | 需要时才看 |

---

## 9.6 开罗尔在通知中的角色变化

| 阶段 | 开罗尔角色 | 能力要求 |
|------|-----------|---------|
| 阶段一 | 消息转发器 | 转发 PM/agent 的通知 |
| 阶段二 | 通知调度器 | 分级缓冲、聚合生成、定时推送 |
| 阶段三 | 信息看板 + 异常路由 | 维护看板、按需查询、只推 P0 |

### 开罗尔需要的增强
- 阶段二起需要通知队列（简单的 JSON 文件或 Redis list）
- 聚合模板（按 P1/P2 预定义摘要格式）
- 定时触发能力（cron 或心跳中判断时间窗口）
- 阶段三起需要看板维护能力（读写 markdown 状态文件）

---

# 十、最终建议

如果要一句话概括这份 schema 草案：

> **3-5 个 agent 阶段先把 schema 做成 hierarchy-ready；8-10 个 agent 阶段上两层 PM；12-15 个 agent 阶段再升级成 program/domain/pod 的三层组织。**

不要等到真的 8 个 agent 才开始重构，因为那时你会同时面对：
- agent 数量上涨
- 活跃任务上涨
- 跨域依赖上涨
- PM 上下文压力上涨
- schema 还不支持分层

最优策略是：

> **现在就改 schema，稍后再启用分层 PM runtime。**

