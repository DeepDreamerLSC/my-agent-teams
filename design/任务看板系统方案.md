# 任务看板系统方案

## 0. 结论摘要

- **Decision**：任务看板数据库落在 `/Users/lin/Desktop/work/my-agent-teams/.omx/task-board/task-board.sqlite3`，作为运行时状态，不进入业务代码目录，也不要求纳入任务 `write_scope`。
- **Decision**：采集链路采用 **`task-watcher.sh` 负责触发、独立 Python ingest 脚本负责规范化与写 SQLite** 的分层方式；不把 SQL/字段清洗逻辑塞进 shell。
- **Decision**：Phase 1 采用 **`tasks` + `task_events`** 两张核心表；Agent 统计先按查询实时计算，不单独落 `agent_daily_stats`，避免双份真相源。
- **Decision**：看板只暴露 5 个列状态：`pending / working / ready_for_merge / blocked / done`；`dispatched` 映射到 `pending`，`merged/archived` 映射到 `done`，`failed/cancelled/timeout` 映射到 `blocked`。
- **Decision**：页面采用 **单页 tabs**（看板 / 甘特图 / Agent 统计），页面路由为 `/`，数据接口统一挂在 `/api/*`。

---

## 1. Evidence（来自现有代码/任务目录的事实）

### 1.1 任务源数据与状态推进

- `scripts/create-task.sh` 会创建 `task.json`、`instruction.md`、空的 `transitions.jsonl`，初始状态为 `pending`。
- `scripts/dispatch-task.sh` 会把 `task.json.status` 改成 `dispatched`，并在 `transitions.jsonl` 追加一条 `pending -> dispatched` 事件。
- `scripts/task-watcher.sh` 的职责是轮询 `tasks/*/`：
  - 发现 `ack.json` 后把状态推进到 `working`
  - 发现 `result.json` 且 `status=done` 后把状态推进到 `ready_for_merge`
  - 发现 `result.json` 且 `status=blocked` 后把状态推进到 `blocked`
  - `review.md` / `verify.json` 目前主要用于通知与补充采集，不是稳定的主状态源

### 1.2 当前任务语料的结构性问题（2026-04-24 实际扫描）

- 当前 `tasks/` 下有 **20 个**任务目录带 `task.json`。
- 其中有 **18 个 `ack.json`**、**17 个 `result.json`**、**6 个 `review.md`**、**0 个 `verify.json`**。
- 所有任务合计只有 **23 条 `transitions.jsonl` 记录**；绝大多数任务只有派发那 1 条，说明 `transitions.jsonl` 历史上明显不完整。
- 当前 `task.json.status` 分布为：
  - `ready_for_merge`: 17
  - `working`: 1
  - `dispatched`: 1
  - `pending`: 1
- 结论：**当前状态面板应以 `task.json.status` 为主真相源，`transitions.jsonl` 只能做“尽量补全时间线”，不能做唯一事实源。**

### 1.3 历史字段不统一

`ack.json` 至少存在以下变体：

- 主流格式：`task_id + agent_id + acknowledged_at + status + notes`
- 旧格式：`task_id + agent + timestamp + status`
- 混合格式：同时出现 `agent/agent_id`、`acknowledged_at/acked_at`

`result.json` 至少存在以下不一致：

- agent 字段：`agent` vs `agent_id`
- 完成时间：当前样本主要是 `completed_at`，但任务说明要求兼容 `reported_at`
- 成功状态：当前 watcher 实际使用 `status=done` 触发 `ready_for_merge`

### 1.4 review / verify 的现状

- `review.md` 是纯 Markdown 文件，不是结构化 JSON；时间线只能依赖：
  1. watcher 将来补采集到的结构化事件
  2. 历史文件的 `mtime`
- 当前扫描到 **0 个 `verify.json`**，因此 `verify` 不能作为 Phase 1 看板/Gantt 的必备前提，只能是可选里程碑。

### 1.5 已有实现方向（用于对齐，不改变本文决策）

当前代码库里已经有与本方案一致的实现骨架：

- `dashboard/db.py`
- `dashboard/ingest.py`
- `dashboard/query.py`
- `scripts/task-board-sync.py`
- `dashboard/app.py`

这些文件已经采用：`.omx/task-board/task-board.sqlite3`、`tasks + task_events`、以及 `/api/health|board|gantt|agents` 方向，因此本文建议与当前实现骨架是对齐的。

---

## 2. Decision（总体架构）

### 2.1 组件边界

```text
tasks/*/task.json|ack.json|result.json|review.md|verify.json|transitions.jsonl
        ↓
  scripts/task-watcher.sh
  - 轮询文件变化
  - 推进 task.json.status
  - 触发 sync-task
        ↓
  scripts/task-board-sync.py
  - backfill / sync-task CLI
        ↓
  dashboard/ingest.py
  - 字段规范化
  - 生命周期提取
  - UPSERT tasks / task_events
        ↓
  SQLite (.omx/task-board/task-board.sqlite3)
        ↓
  dashboard/query.py
  - board / gantt / agent stats 查询聚合
        ↓
  Flask + ECharts
```

### 2.2 为什么不把 SQLite 逻辑直接塞进 `task-watcher.sh`

- shell 适合“检测到什么文件变化 -> 调哪个动作”，**不适合**承载：
  - JSON 字段兼容
  - 时间戳归一化
  - review 文本判定
  - SQL schema 演进
  - backfill 与增量复用
- 如果 SQL 写在 shell：
  - backfill 逻辑会重复写一遍
  - 单测困难
  - 字段兼容规则难维护
- 因此 **Decision**：watcher 只负责触发，Python ingest 统一负责“读任务目录 -> 归一化 -> 写库”。

---

## 3. Decision（SQLite 数据模型）

### 3.1 SQLite 文件落点

**Decision**：数据库文件放在：

`/Users/lin/Desktop/work/my-agent-teams/.omx/task-board/task-board.sqlite3`

理由：

1. `.omx/` 已经被项目定义为运行时状态目录，语义正确。
2. `.gitignore` 已忽略 `.omx/`，不会把运行时数据库误提交。
3. 该路径同时方便 watcher、backfill CLI、Flask API 共用。
4. 与代码目录 `dashboard/` 分离，避免“代码文件”和“运行时数据文件”混放。

### 3.2 核心表：`tasks`

**Decision**：`tasks` 作为“当前快照表”，一行代表一个任务当前归一化视图。

建议字段：

| 字段 | 类型 | 说明 |
|---|---|---|
| `task_id` | TEXT PK | 任务唯一标识 |
| `title` | TEXT NOT NULL | 标题 |
| `project` | TEXT | 所属项目 |
| `domain` | TEXT | frontend/backend/quality |
| `assigned_agent` | TEXT | 当前执行者 |
| `reviewer` | TEXT | reviewer |
| `owner_pm` | TEXT | 任务 owner PM |
| `parent_task_id` | TEXT | 父任务 |
| `root_request_id` | TEXT | 根请求 ID |
| `review_required` | INTEGER | 0/1 |
| `test_required` | INTEGER | 0/1 |
| `current_status` | TEXT | 原始 `task.json.status` |
| `board_status` | TEXT | 映射后的五列状态 |
| `created_at` | TEXT | 创建时间 |
| `dispatched_at` | TEXT | 派发时间 |
| `ack_at` | TEXT | ACK 时间 |
| `completed_at` | TEXT | agent 成功交付时间（result 完成时间） |
| `review_completed_at` | TEXT | review 完成时间 |
| `verify_completed_at` | TEXT | verify 完成时间 |
| `current_status_at` | TEXT | 当前状态最近一次成立时间 |
| `ack_agent` | TEXT | ack 的 agent |
| `result_agent` | TEXT | result 的 agent |
| `lease_acquired_at` | TEXT | task.json 中的 lease 时间 |
| `updated_at` | TEXT | task.json.updated_at |
| `summary` | TEXT | result.summary / task.result_summary |
| `review_state` | TEXT | `approved / changes_requested / present / null` |
| `verify_ok` | INTEGER NULL | `1 / 0 / null` |
| `task_dir` | TEXT | 任务目录绝对路径 |
| `task_json_path` | TEXT | task.json 绝对路径 |
| `write_scope_json` | TEXT | JSON 字符串 |
| `artifacts_json` | TEXT | JSON 字符串 |
| `last_ingest_source` | TEXT | 本次由谁触发同步 |
| `last_synced_at` | TEXT | 最近入库时间 |

### 3.3 事件表：`task_events`

**Decision**：`task_events` 作为“生命周期事件表”，一行代表一个被观察到的里程碑或状态跳转。

| 字段 | 类型 | 说明 |
|---|---|---|
| `event_key` | TEXT PK | 幂等事件键 |
| `task_id` | TEXT FK | 归属任务 |
| `event_type` | TEXT | `created / status_transition / ack / result / review_completed / verify_completed` |
| `event_at` | TEXT NULL | 事件时间 |
| `source` | TEXT | 来源文件，如 `task_json / ack_json / review_md` |
| `status_from` | TEXT NULL | 旧状态 |
| `status_to` | TEXT NULL | 新状态 |
| `artifact_path` | TEXT | 来源文件路径 |
| `payload_json` | TEXT | 附加信息 JSON |
| `observed_at` | TEXT | 本次采集观察到该事件的时间 |

### 3.4 为什么 Phase 1 不单独落 `agent_daily_stats`

**Decision**：Phase 1 不落物化统计表，Agent 统计先基于 `tasks` 表查询时计算。

理由：

- 当前任务量很小（当前样本 20 个），实时计算成本极低。
- 如果同时维护 `tasks` 与 `agent_daily_stats`，会引入第二套状态同步问题。
- 统计口径还在演进（例如是否把 `ready_for_merge` 计入负载），Phase 1 先用查询层保持口径可改。

如后续任务量上升到数千级，再增加物化视图/日汇总表。

### 3.5 主键、索引、幂等策略

**Decision**：

- `tasks.task_id` 作为快照表主键，使用 UPSERT。
- `task_events.event_key` 作为事件表主键，使用 UPSERT/INSERT OR REPLACE。

建议索引：

- `ix_tasks_board_status(board_status, current_status_at DESC)`
- `ix_tasks_assigned_agent(assigned_agent, current_status_at DESC)`
- `ix_tasks_project_status(project, board_status, current_status_at DESC)`
- `ix_task_events_task_time(task_id, event_at)`
- `ix_task_events_type_time(event_type, event_at)`

幂等写入规则：

1. **任务快照幂等**：同一 `task_id` 重复同步只会覆盖当前快照，不会新增脏行。
2. **单例事件幂等**：`created / ack / result / review / verify` 使用固定 `event_key`：
   - `task_id:created`
   - `task_id:ack`
   - `task_id:result`
   - `task_id:review`
   - `task_id:verify`
3. **transition 事件幂等**：用 `task_id + line_number + sha1(from,to,at,reason,raw)` 生成稳定键；对同一个 `transitions.jsonl` 重复回填不会重复插入。
4. **同步策略幂等**：任意触发器再次执行 `sync-task` 都允许“整目录重读 + UPSERT”；不要试图在 shell 层做复杂 diff 判定。

---

## 4. Decision（生命周期事件提取与规范化规则）

### 4.1 规范化字段规则

| 规范化字段 | 优先级 |
|---|---|
| `canonical_agent` | `agent_id` → `agent` → `task.json.assigned_agent` |
| `canonical_ack_at` | `acknowledged_at` → `acked_at` → `timestamp` → `ack.json mtime` |
| `canonical_completed_at` | `completed_at` → `reported_at` → `result.json mtime` |
| `canonical_verify_ok` | `ok` → `pass` |
| `review_state` | Markdown 文本关键字：通过/approve=approved；驳回/reject/request changes=changes_requested；否则 `present` |

### 4.2 每个关键时间点从哪里来

| 里程碑 | 取值优先级 | 说明 |
|---|---|---|
| `created` | `task.json.created_at` → `task.json mtime` | `create-task.sh` 会写 `created_at`，历史缺失时回退 mtime |
| `dispatched` | `transitions.jsonl` 首条 `to=dispatched` → `task.json.lease_acquired_at` → `task.json.updated_at` | 因为 `dispatch-task.sh` 会同时写 status 与 transition |
| `ack` | `ack.json.acknowledged_at` → `ack.json.acked_at` → `ack.json.timestamp` → `ack.json mtime` | 兼容新旧 ACK 格式 |
| `result done` | `result.json.completed_at` → `result.json.reported_at` → `result.json mtime` → 首条 `to=ready_for_merge` transition | 仅当 `result.status` 归一化为成功态时使用 |
| `review completed` | transition 中带 review 语义的 reason → `review.md mtime` | 历史数据基本只能依赖 mtime |
| `verify completed` | `verify.json.verified_at` → `verify.json.completed_at` → `verify.json.reported_at` → `verify.json mtime` | 当前样本基本为空，允许 null |
| `current status` | `task.json.status` | 当前状态以 `task.json` 为主真相源 |
| `current_status_at` | 最后一条 `to=current_status` transition → `task.json.updated_at` → `verify/review/completed/ack/dispatched/created` | 用于排序和“最后变化时间” |

### 4.3 result.status 归一化

**Decision**：对 `result.json.status` 做以下归一化：

| 原值 | 归一化结果 | 用途 |
|---|---|---|
| `done` | `success` | watcher 会把任务推到 `ready_for_merge` |
| `ready_for_merge` | `success` | 兼容未来更严格的 result 协议 |
| `blocked` | `blocked` | 进入 blocked 口径 |
| `failed` | `failed` | 进入 blocked 口径 |
| 其他/缺失 | `unknown` | 不用于完成时间，保留原值供排查 |

### 4.4 review / verify 的时间线策略

**Decision**：

- `review_completed_at` 和 `verify_completed_at` 都允许为空。
- 甘特图前端必须支持“某些 milestone 为 null”的情况。
- 不允许为了图好看去伪造 review/verify 时间。

---

## 5. Decision（看板状态映射规则）

### 5.1 五列映射

| 原始状态 `current_status` | 看板列 `board_status` | 说明 |
|---|---|---|
| `pending` | `pending` | 未派发/未开始 |
| `dispatched` | `pending` | 已派发但 agent 尚未 ACK；前端卡片上显示 badge `dispatched` |
| `working` | `working` | agent 已接单并执行中 |
| `ready_for_merge` | `ready_for_merge` | agent 已交付，等待 review/integration |
| `blocked` | `blocked` | 显式阻塞 |
| `failed` | `blocked` | 终态失败也进入 blocked 列，badge 展示 `failed` |
| `cancelled` | `blocked` | 被取消也进入 blocked 列，badge 展示 `cancelled` |
| `timeout` | `blocked` | 超时也进入 blocked 列 |
| `merged` | `done` | 已合入 |
| `archived` | `done` | 已归档 |
| 未知状态 | `blocked` | 为了保证前端永远只有 5 列，未知状态强制落到 blocked，并展示原始状态 badge |

### 5.2 为什么 `dispatched` 映射到 `pending`

**Decision**：`dispatched` 放在 `pending` 列。

理由：

1. 用户指定的看板列没有 `dispatched`。
2. 业务语义上，`dispatched` 仍属于“未真正开始执行”；agent 还没 ACK。
3. 如果单独给第 6 列，会让前端复杂度与用户心智都上升。

前端要求：卡片保留 `current_status` 徽标，避免把 `pending` 和 `dispatched` 混成不可区分。

---

## 6. Decision（采集层扩展方式）

### 6.1 backfill + incremental 的统一入口

**Decision**：新增独立 CLI：

```bash
python3 /Users/lin/Desktop/work/my-agent-teams/scripts/task-board-sync.py backfill --tasks-root /Users/lin/Desktop/work/my-agent-teams/tasks
python3 /Users/lin/Desktop/work/my-agent-teams/scripts/task-board-sync.py sync-task --task-dir /Users/lin/Desktop/work/my-agent-teams/tasks/<task-id> --source <trigger>
```

- `backfill`：首次把所有历史任务导入 SQLite。
- `sync-task`：增量时每次只同步一个任务目录。
- 两者都复用同一套 `dashboard/ingest.py` 逻辑。

### 6.2 watcher 的职责边界

**Decision**：`task-watcher.sh` 只做 3 件事：

1. 继续维护现有通知与状态推进逻辑。
2. 在关键事件后调用 `sync-task`。
3. 对 `task.json / transitions.jsonl / ack.json / result.json / review.md / verify.json` 做 mtime 级别补采集。

### 6.3 增量触发点

最少覆盖：

- `ack.json` 被发现或 mtime 变化
- `result.json` 被发现或 mtime 变化
- `review.md` 被发现或 mtime 变化
- `verify.json` 被发现或 mtime 变化
- `task.json` 变化（尤其用于 `dispatched`、`merged`、`archived` 等状态变化）
- `transitions.jsonl` 变化（用于补充时间线）

### 6.4 如何避免重复写库

**Decision**：不在 shell 层做复杂去重，而是让 Python ingest 以“整目录重建单任务快照 + 事件 UPSERT”的方式保证幂等。

这意味着：

- watcher 即使重复触发 `sync-task`，SQLite 结果也不会重复膨胀。
- backfill 跑完再跑一遍，也只是重复覆盖同一快照与同一事件键。
- 这比在 shell 中维护一套“哪个字段已经写过”的状态更稳。

### 6.5 故障策略

**Decision**：SQLite 同步失败不能阻断 watcher 的主流程。

- watcher 记录日志：`任务看板同步失败: <task_dir> (<source>)`
- 主任务通知和状态推进继续执行
- 后续 mtime 或手动 backfill 会把数据库补齐

即：**任务看板允许 eventual consistency，不应反向影响主任务系统。**

---

## 7. Decision（Flask + ECharts 页面结构与接口契约）

### 7.1 页面组织

**Decision**：采用单页 dashboard + tabs。

页面 URL：

- `GET /`：返回 dashboard HTML
- `GET /static/*`：静态 JS/CSS

三大 tabs：

1. `看板`
2. `甘特图`
3. `Agent 统计`

理由：

- 三个视图都依赖同一份过滤条件（`project` / `agent`）。
- 不需要引入前端路由、打包链或多模板跳转。
- 与“Flask + 原生 JS + ECharts CDN”的轻量目标一致。

### 7.2 JSON API 列表

#### `GET /api/health`

用途：健康检查 + 数据库概览。

响应 shape：

```json
{
  "status": "ok",
  "generated_at": "2026-04-24T18:30:00+08:00",
  "db_path": "/Users/lin/Desktop/work/my-agent-teams/.omx/task-board/task-board.sqlite3",
  "task_count": 20,
  "event_count": 43,
  "last_synced_at": "2026-04-24T18:29:58+08:00",
  "board_status_counts": {
    "pending": 2,
    "working": 1,
    "ready_for_merge": 15,
    "blocked": 1,
    "done": 1
  }
}
```

#### `GET /api/board?project=<project>&agent=<agent>`

用途：看板列数据。

响应 shape：

```json
{
  "generated_at": "2026-04-24T18:30:00+08:00",
  "filters": {
    "project": "my-agent-teams",
    "agent": null
  },
  "summary": {
    "task_count": 20,
    "column_counts": {
      "pending": 2,
      "working": 1,
      "ready_for_merge": 15,
      "blocked": 1,
      "done": 1
    }
  },
  "columns": [
    {
      "key": "pending",
      "label": "pending",
      "count": 2,
      "tasks": [
        {
          "task_id": "任务看板系统架构设计",
          "title": "设计任务看板系统的数据模型、采集链路与接口契约",
          "project": "my-agent-teams",
          "domain": "backend",
          "assigned_agent": "arch-1",
          "current_status": "dispatched",
          "board_status": "pending",
          "summary": null,
          "created_at": "...",
          "dispatched_at": "...",
          "ack_at": null,
          "completed_at": null,
          "review_completed_at": null,
          "verify_completed_at": null,
          "current_status_at": "...",
          "review_state": null,
          "verify_ok": null
        }
      ]
    }
  ]
}
```

前端依赖约束：

- `board_status` 必须始终落在五列集合里。
- `current_status` 必须原样保留，供 badge 展示。
- 时间字段允许为 `null`。

#### `GET /api/gantt?project=<project>&agent=<agent>`

用途：甘特图时间线。

响应 shape：

```json
{
  "generated_at": "2026-04-24T18:30:00+08:00",
  "filters": {
    "project": "my-agent-teams",
    "agent": null
  },
  "items": [
    {
      "task_id": "任务看板采集与后端实现",
      "title": "实现任务看板 SQLite 采集层与 Flask 后端",
      "project": "my-agent-teams",
      "assigned_agent": "be-1",
      "current_status": "ready_for_merge",
      "board_status": "ready_for_merge",
      "display_start_at": "2026-04-24T18:09:00+08:00",
      "display_end_at": "2026-04-24T18:28:00+08:00",
      "duration_seconds": 1140,
      "milestones": {
        "created": "2026-04-24T18:04:35+08:00",
        "dispatched": "2026-04-24T18:06:13+08:00",
        "ack": "2026-04-24T18:09:00+08:00",
        "completed": "2026-04-24T18:28:00+08:00",
        "review_completed": null,
        "verify_completed": null,
        "current_status": "2026-04-24T18:28:01+08:00"
      }
    }
  ]
}
```

前端依赖约束：

- `items[*].milestones` 键集合固定，哪怕值为 `null`。
- `display_start_at` / `display_end_at` 是前端画主条形图的直接字段。
- 甘特图允许“只有 created + dispatched + ack + completed，没有 review/verify”。

#### `GET /api/agents?project=<project>`

用途：Agent 统计。

响应 shape：

```json
{
  "generated_at": "2026-04-24T18:30:00+08:00",
  "filters": {
    "project": "my-agent-teams"
  },
  "summary": {
    "agent_count": 6,
    "total_active_tasks": 3
  },
  "agents": [
    {
      "agent_id": "fe-1",
      "active_task_count": 1,
      "blocked_task_count": 0,
      "ready_for_merge_count": 4,
      "completed_task_count": 5,
      "current_load_count": 1,
      "total_tracked_work_seconds": 8640,
      "active_tasks": [
        {
          "task_id": "任务看板前端可视化实现",
          "title": "实现任务看板 Flask 模板与 ECharts 可视化界面",
          "current_status": "working",
          "board_status": "working"
        }
      ]
    }
  ]
}
```

前端依赖约束：

- `total_tracked_work_seconds` 为数值秒。
- `current_load_count` 是当前执行负载，不等于 `ready_for_merge_count`。
- `active_tasks` 用于展示 tooltip / 明细列表。

---

## 8. Decision（指标定义）

### 8.1 Agent 工作时长

**Decision**：

- 主口径：`ack_at -> completed_at`
- 若任务未完成：`ack_at -> 当前时间`
- 若历史任务缺失 `ack_at`：回退 `dispatched_at -> completed_at/当前时间`；再缺失则回退 `created_at`
- 所有负值一律 clamp 到 0

公式：

```text
task_work_seconds = max(effective_end_at - effective_start_at, 0)

effective_start_at = ack_at || dispatched_at || created_at
effective_end_at   = completed_at || now(当任务仍未完成)
```

说明：

- 这满足用户要求的主口径“ack→完成 / ack→当前时间”。
- 同时对历史脏数据保留 fallback，避免统计页大量空值。
- 如果用了 fallback，后端可在将来补一个 `data_quality` 字段，但 Phase 1 不是硬性要求。

### 8.2 完成任务数

**Decision**：`completed_task_count = count(completed_at IS NOT NULL)`，按 `assigned_agent` 聚合。

理由：

- 这表示“agent 已经成功交付 result”的任务数。
- 它比 `done` 更贴近 agent 产能，因为 `merged/archived` 受 reviewer/PM 流程影响。
- 若要展示“系统终态 done 数”，单独用 `board_status=done` 统计，不和 `completed_task_count` 混用。

### 8.3 当前负载

**Decision**：

- `current_load_count = count(current_status in {pending, dispatched, working, blocked})`
- `ready_for_merge_count` 单独展示，不并入当前执行负载

理由：

- `ready_for_merge` 本质上是“等待 review/integration”，不一定是 agent 当前正在消耗的执行负载。
- 这样前端既能展示“我手头还有多少任务”，又能展示“我已交付但还未合入多少任务”。

---

## 9. Decision（给下游 agent 的实现契约）

### 9.1 给 `be-1`（后端/采集层）的契约

1. Flask API 的 `board_status` 必须稳定映射到五列之一。
2. `current_status` 原值必须透出，前端靠它做 badge。
3. `milestones` 中缺失时间必须返回 `null`，不能省字段。
4. backfill 与 incremental 必须共用同一套 ingest 代码，不允许维护两套字段规范化逻辑。
5. watcher 的 shell 改动应最小，只做触发，不做 SQL。

### 9.2 给 `fe-1`（前端可视化）的契约

1. 只消费 `/api/*`，不要直接读 `tasks/` 目录或 SQLite。
2. 看板列使用 `board_status`，卡片细节使用 `current_status`。
3. 甘特图必须容忍 `review_completed` / `verify_completed` 为 `null`。
4. Agent 统计默认展示：`completed_task_count`、`current_load_count`、`total_tracked_work_seconds`。

### 9.3 给 `qa-1` / `review-1` 的验证重点

1. backfill 后任务总数应与 `tasks/` 目录任务数一致。
2. `dispatched` 必须落在 `pending` 列，但卡片可见 `dispatched` badge。
3. 历史没有 `verify.json` 的任务，甘特图仍可正常展示。
4. 字段变体（`agent/agent_id`、`acknowledged_at/acked_at/timestamp`）必须都能入库。

---

## 10. Unknown / Risk（实现期仍需验证的点）

1. **verify 数据稀缺**：当前样本里没有 `verify.json`，所以 verify 时间线和 verify 统计只能按“可选字段”设计，真正口径还需要后续任务验证。
2. **review 语义依赖关键词**：`review.md` 目前只能靠关键词推断 `approved / changes_requested`，极端文案可能误判；若后续 review 流程变复杂，应新增结构化 review artifact。
3. **transitions 历史不完整**：Gantt 不能承诺每个任务都有完整状态跳转；UI 需要接受 null milestone 与不完整 span。
4. **done 终态样本偏少**：当前任务多数停在 `ready_for_merge`，`merged/archived` 的真实展示效果还需要联调任务再确认。
5. **verify 协议与历史 result/ack 协议并不完全一致**：当前任务语料大量使用 `status=done`、`agent_id`、`acknowledged_at`；后续如果要收敛协议，应该在不破坏历史兼容的前提下进行。

---

## 11. 最终建议（实施顺序）

1. 先按本文 schema 初始化 SQLite。
2. 先跑一次 `backfill`，确认历史任务可导入。
3. 再把 `task-watcher.sh` 的触发器接到 `sync-task`。
4. 之后完成 `/api/board`、`/api/gantt`、`/api/agents`。
5. 最后由前端接单页 tabs，并由联调任务验证 3 个视图 + watcher 增量写库。

如果当前分支实现与本文不一致，**以本文的数据口径与接口契约为准进行收敛**；如果收敛成本过高，则由 PM 明确拍板偏差项。
