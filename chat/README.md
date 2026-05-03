# Chat Hub（A-Lite）

> Chat Hub 是 agent 之间的**公共消息区**。  
> A-Lite 阶段主做：
> - `chat/general/` 公共频道
> - `chat/tasks/` 任务讨论串
>
> 同时为后续看板 / watcher / dispatch / direct nudge 事件预留：
> - `chat/system/watcher/`
> - `chat/system/dispatch/`
> - `chat/system/direct_nudge/`
>
> 当前**不做**：
> - 私聊 `chat/agents/`
> - 任务认领状态机
> - 已读游标 / 去重文件

## 目录约定

```text
chat/
├── general/
│   └── YYYY-MM-DD.jsonl
├── tasks/
│   └── {task-id}.jsonl
└── system/
    ├── watcher/
    │   └── YYYY-MM-DD.jsonl
    ├── dispatch/
    │   └── YYYY-MM-DD.jsonl
    └── direct_nudge/
        └── YYYY-MM-DD.jsonl
```

## 角色边界

- `tasks/` 仍然是任务状态事实源
- `chat/` 只承载：
  - 任务公告
  - 讨论
  - 提问 / 回答
  - 简短完成同步

## 使用方式

统一使用：

```bash
/Users/lin/Desktop/work/my-agent-teams/scripts/send-chat.sh general "消息内容"
/Users/lin/Desktop/work/my-agent-teams/scripts/send-chat.sh task <task-id> "消息内容"
/Users/lin/Desktop/work/my-agent-teams/scripts/send-chat.sh announce <task-id> "任务公告内容"
/Users/lin/Desktop/work/my-agent-teams/scripts/send-chat.sh watcher <task-id> "系统通知" --to pm-chief --severity degraded
/Users/lin/Desktop/work/my-agent-teams/scripts/send-chat.sh dispatch <task-id> "任务已派发" --to dev-1 --severity info
/Users/lin/Desktop/work/my-agent-teams/scripts/send-chat.sh nudge <task-id> "已强制唤醒" --to dev-2 --severity critical
```

### `task_announce` 前置条件

`announce` 不是“先发出去再补定义”，而是任务已经过完派发前硬门槛之后的**公告动作**。

因此，`send-chat.sh announce` 现在会在发送前校验目标任务：
- `task.json` 与 `instruction.md` 存在
- `instruction.md` 中至少以下章节已填完且不是占位：
  - `任务类型`
  - `目标`
  - `任务边界`
  - `验收标准`
  - `下游动作`
- 任务状态已经进入可公告阶段（如 `dispatched / working / ready_for_merge / blocked`）

如果这些条件不满足，脚本会直接拒绝发送 `task_announce`。

### 自动附带的任务元数据

对 `announce` 消息，脚本会自动补充以下字段（如果 task.json 中存在）：
- `task_type`
- `target_environment`
- `review_level`
- `next_action`
- `owner_approval_required`

## 关键规则

1. `task_done` 只是“我已写 result.json”的通知，不是终态事实
2. chat 中形成的关键结论，必须回写：
   - `features/<feature-id>/decisions.log`
   - `notes/dev.md / arch.md / qa.md`
3. 生产故障 / critical 事项仍必须配合 `send-to-agent.sh` 强制唤醒，不只靠 chat
4. `decision / answer / task_done` 这类关键消息发送后，发送脚本会提示回写 feature 上下文；这是提醒，不是可省略建议

## 常用辅助工具（第二批）

### 1. 查看消息
```bash
/Users/lin/Desktop/work/my-agent-teams/scripts/read-chat.sh general --limit 20
/Users/lin/Desktop/work/my-agent-teams/scripts/read-chat.sh task <task-id> --limit 50
/Users/lin/Desktop/work/my-agent-teams/scripts/read-chat.sh watcher --limit 20
/Users/lin/Desktop/work/my-agent-teams/scripts/read-chat.sh dispatch --limit 20
/Users/lin/Desktop/work/my-agent-teams/scripts/read-chat.sh nudge --limit 20
```

### 2. PM 巡检
```bash
/Users/lin/Desktop/work/my-agent-teams/scripts/pm-chat-check.sh --days 1 --limit 20
```

默认会聚焦：
- `to=pm-chief`
- `@pm-chief`
- `priority=critical`
- `decision`
- task thread 中的 `question / task_done`

### 3. 协议校验
```bash
/Users/lin/Desktop/work/my-agent-teams/scripts/lint-chat.sh
/Users/lin/Desktop/work/my-agent-teams/scripts/lint-chat.sh /Users/lin/Desktop/work/my-agent-teams/chat/tasks
```

会校验：
- JSONL 格式
- 必填字段
- `type / source_type / priority` 枚举
- `answer` 必须带 `reply_to`
- `task_announce / task_done / decision` 必须带 `task_id`
- task thread 中 `task_id` 与文件名一致


## 协议补充（schema_version / system / severity）

当前写入的新消息建议统一带：
- `schema_version=1`
- `channel`
- `event_class`
- `source_type`

其中：
- `priority` = 任务/消息的重要程度
- `severity` = 事件严重度（`info/degraded/critical`）

更多约束见：`design/Chat-Hub-协议补充.md`。

### system 事件生产路径
- `send-chat.sh` 现已支持：
  - `watcher`
  - `dispatch`
  - `nudge`
- 这些通道默认写入 `chat/system/...`，用于后续 communication timeline / dashboard ingest。

### 常用 system 示例
```bash
/Users/lin/Desktop/work/my-agent-teams/scripts/send-chat.sh dispatch <task-id> "任务已派发并完成定向唤醒" --to dev-1 --severity info
/Users/lin/Desktop/work/my-agent-teams/scripts/send-chat.sh watcher <task-id> "QA 未通过，需 PM 仲裁" --to pm-chief --severity degraded
/Users/lin/Desktop/work/my-agent-teams/scripts/send-chat.sh nudge <task-id> "critical 任务已强制唤醒" --to dev-2 --severity critical
```


### 4. 指标采集
```bash
/Users/lin/Desktop/work/my-agent-teams/scripts/chat-metrics.py --days 1
/Users/lin/Desktop/work/my-agent-teams/scripts/chat-metrics.py --days 7 --json
```

用于采集：
- `task_announce_count`
- `question/answer` 数与比例
- `pm_mention_count`
- `critical_dual_channel_count`
- `unanswered_question_count`
- `schema_version_coverage`
