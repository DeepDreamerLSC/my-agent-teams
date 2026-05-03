# Chat Hub 协议补充

> 创建时间：2026-05-03  
> 适用范围：`chat/`、`scripts/send-chat.sh`、`scripts/lint-chat.sh`、后续 `communication_events` ingest 设计  
> 目标：在 A-Lite 继续可用的前提下，补齐 **协议版本、system 事件、priority/severity 分工、与看板 communication_events 的桥接契约**。

---

## 一、定位

当前 Chat Hub A-Lite 已经具备最小可用性，但主文档更偏流程说明。为了支撑：
- 后续把 chat / watcher / dispatch / direct nudge 接入看板
- 后续扩展 `communication_events`
- 后续做通知降噪与 timeline 回放

需要先补一层协议约束，避免实现阶段各脚本各写各的事件格式。

---

## 二、协议版本

从本补充文档开始，建议所有新写入的 chat / system 事件都带：

```json
{
  "schema_version": 1
}
```

### 说明
- `schema_version` 是**协议版本**，不是任务 schema 版本。
- A-Lite 旧消息可以没有该字段，但 ingest 层必须按“无版本 = v0 兼容输入”处理。
- 新增字段（如 `severity`、`event_class`、`source_name`）时，不应破坏旧消息可读性。

---

## 三、消息分层模型

建议把一条沟通/通知事件拆成四个概念：

1. **channel**：消息出现在哪类通道
2. **event_class**：人类消息 / 系统通知 / 投递事件
3. **type**：具体业务语义
4. **source_type**：human / system

### 3.1 channel
| channel | 说明 |
|---|---|
| `general` | `chat/general/YYYY-MM-DD.jsonl` |
| `task` | `chat/tasks/{task-id}.jsonl` |
| `watcher` | task-watcher 产生的系统通知 |
| `dispatch` | dispatch-task 产生的派发事件 |
| `direct_nudge` | send-to-agent / 强制唤醒类事件 |

### 3.2 event_class
| event_class | 说明 |
|---|---|
| `message` | 人类对话消息 |
| `task_marker` | 任务线程中的轻量里程碑消息，如 `task_announce` / `task_done` |
| `system_notice` | watcher / dispatch / 聚合器产生的系统通知 |
| `delivery` | 强制唤醒 / 投递成功失败 / 重试这类送达事件 |

### 3.3 当前 A-Lite 已启用的 type
| type | 当前状态 | 说明 |
|---|---|---|
| `text` | 已启用 | 普通消息 |
| `task_announce` | 已启用 | 任务公告 |
| `task_done` | 已启用 | “我已写 result.json”的线程同步 |
| `question` | 已启用 | 提问 |
| `answer` | 已启用 | 回答 |
| `decision` | 已启用 | 需要被感知的决策 |
| `notify` | 预留 | watcher 系统通知 |
| `dispatch` | 预留 | 派发完成的结构化事件 |
| `nudge` | 预留 | send-to-agent 强制唤醒 / 重试 |

> A-Lite 当前只有前六类由 `send-chat.sh` 直接生产；`notify / dispatch / nudge` 先作为协议预留，等系统事件正式落盘时启用。

---

## 四、source_type / source_name 约束

### 4.1 source_type
| 值 | 当前状态 | 说明 |
|---|---|---|
| `human` | 已启用 | 来自 PM / dev / arch / qa / reviewer / kael / linsceo 的人工消息 |
| `system` | 预留 | 来自 watcher / dispatch / ingest / direct_nudge 的系统事件 |

### 4.2 source_name（建议新增）
当 `source_type=system` 时，建议再带：

```json
{
  "source_name": "task-watcher | dispatch-task | send-to-agent | chat-metrics"
}
```

当前 A-Lite 文档必须明确：
- **现阶段 `send-chat.sh` 只生产 `human` 消息**；
- `system` 是为后续 event ingest / timeline 扩展预留，不应误解为 watcher 已经直接写进 chat。

---

## 五、priority 与 severity 分工

这是本轮最需要收紧的边界之一。

### 5.1 priority
`priority` 表示**任务或消息的重要程度**，主要用于：
- 业务优先级
- 是否需要 PM 优先查看
- 是否需要 task_announce 带更高关注度

建议枚举：
- `low`
- `medium`
- `high`
- `critical`

### 5.2 severity
`severity` 表示**事件严重度**，主要用于：
- 告警降噪
- 风险面板
- 区分可观察退化与必须立即打断的事故

建议枚举：
- `info`
- `degraded`
- `critical`

### 5.3 两者区别
| 字段 | 回答的问题 |
|---|---|
| `priority` | 这件事业务上多重要？ |
| `severity` | 这个事件技术上/运行上多危险？ |

例子：
- 一个普通功能任务在业务上可能是 `priority=high`，但其 thread 中一条“已发 task_announce”消息仍然只是 `severity=info`
- 一次 `429` 或单次重发不一定是 `priority=critical`，但可视为 `severity=degraded`

---

## 六、与 communication_events 的桥接映射

后续看板 ingest 建议统一映射如下：

| Chat/系统字段 | communication_events 字段 |
|---|---|
| `msg_id` | `source_msg_id` / `event_id`（若可直接复用） |
| `schema_version` | `payload_json.schema_version` 或独立列 |
| `ts` | `happened_at` |
| `from` | `from_actor` |
| `to` | `to_actor` |
| `type` | `event_type` |
| `msg` | `message_text` |
| `thread_id` | `thread_id` |
| `task_id` | `task_id` |
| `source_type` | `source_type` |
| `priority` | `priority` |
| `severity` | `severity` |
| `source_name` | `payload_json.source_name` 或独立列 |

### 6.1 非 chat 系统事件的桥接
| 事件来源 | 建议映射 |
|---|---|
| `dispatch-task.sh` | `channel=dispatch`, `event_class=system_notice`, `event_type=dispatch` |
| `task-watcher.sh` | `channel=watcher`, `event_class=system_notice`, `event_type=notify` |
| `send-to-agent.sh` | `channel=direct_nudge`, `event_class=delivery`, `event_type=nudge` |

### 6.2 event_id 规则
- 对 human chat：优先使用 `msg_id`
- 对 system events：用稳定去重键生成，如：
  - `source_name + task_id + happened_at + kind + hash(payload)`

---

## 七、时间线排序规则

统一 timeline 排序建议：
1. 优先 `happened_at`
2. 若缺失，回退 `observed_at`
3. 若仍相同，用稳定 `event_id` 排序打散

说明：
- task 详情页只默认消费：
  - `chat/tasks/{task-id}.jsonl`
  - 显式带 `task_id` 的 general 消息
  - 与该 task 相关的 system_notice / delivery events
- **不做模糊文本匹配归因**

---

## 八、A-Lite 当前与后续阶段的边界声明

### 当前 A-Lite 已启用
- `general / task` 两类公开通道
- `text / task_announce / task_done / question / answer / decision`
- `human` 消息生产路径

### 当前 A-Lite 未启用
- `chat/agents/` 私聊
- `task_claim / task_claim_confirmed`
- `system` 事件直接写入 chat
- `severity` 强制落盘
- 已读游标 / 通知去重状态机

### 后续若进入看板/通知增强阶段
必须优先复用本补充文档中的：
- `schema_version`
- `event_class`
- `priority/severity` 分工
- `communication_events` 桥接映射
- timeline 排序规则

---

## 九、推荐落地顺序

1. 先让 `Chat-Hub-落地清单.md`、`A-Lite-验证使用说明.md`、验证模板引用本协议
2. 再由看板方案中的 `communication_events` 直接复用这里的映射规则
3. 最后才让 system events 真正进入 dashboard ingest

> 一句话结论：**A-Lite 可以继续跑，但所有后续 system event / communication timeline 能力都必须先挂到这份协议上。**
