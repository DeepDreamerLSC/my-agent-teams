# Code Review - 修正taskwatcher仅在任务最终完成后发飞书通知

## 结论
**REQUEST CHANGES**

## 审查范围
- `/Users/lin/Desktop/work/my-agent-teams/scripts/task-watcher.sh`
- `/Users/lin/Desktop/work/my-agent-teams/README.md`
- `/Users/lin/Desktop/work/my-agent-teams/design/OpenClaw-tmux协作方案优化.md`
- `/Users/lin/Desktop/work/my-agent-teams/tasks/修正taskwatcher仅在任务最终完成后发飞书通知/result.json`
- `/Users/lin/Desktop/work/my-agent-teams/tasks/修正taskwatcher仅在任务最终完成后发飞书通知/verify.json`

## 通过项
1. `result.json(status=done)` 分支已不再直接发送“【任务完成】/【部署完成】”类飞书，`ready_for_merge` 只承担待审 / 待验语义，这一点符合需求。
2. 最终完成通知改为统一挂在 `done` 观察分支，方向上确实能覆盖 QA 自动收口与手工 `close-task.sh` 这两类合法 done 路径。
3. `README.md` 中 `ready_for_merge` 的说明已同步为“检测到 result.json，进入待审 / 待验阶段”，不再误导为最终完成。

## 阻塞问题

### 1. HIGH — 当前实现会对历史 `done` 任务补发一轮最终完成通知
- 代码位置：`/Users/lin/Desktop/work/my-agent-teams/scripts/task-watcher.sh:1633-1656,1704-1708`
- 问题说明：`notify_final_done_if_needed()` 仅依赖 `$STATE_DIR/${task_id}_done_notice` 做去重，但没有“只对**新近进入** done 的任务触发”的判定。主循环会对所有 `status=done` 的任务直接调用该函数。
- 直接证据：当前任务池里已有 **92** 个 `task.json.status=done` 任务，而 `/Users/lin/.openclaw/workspace/.task-watcher` 下现有 `*_done_notice` 标记数为 **0**。这意味着 watcher 部署/重启后，会把这批历史已完成任务逐条当成“首次 done”来补发 `【任务完成】/【部署完成】`。
- 风险：会造成明显的历史任务刷屏 / 误报，且与“最终完成通知只对应当前生命周期真正收口”这一目标不一致。
- 修复建议：把通知触发条件收窄为“首次从 `ready_for_merge -> done` 进入终态”而不是“扫描到 done 即发”；或在 watcher 启动时先为历史 done 任务补种 sentinel 而不推送，再只对后续新增 done 任务发通知。

### 2. MEDIUM — 主方案文档仍与当前实现不一致
- 代码位置：`/Users/lin/Desktop/work/my-agent-teams/design/OpenClaw-tmux协作方案优化.md:930`
- 问题说明：文档仍写成“`verify.json`（通过）→ 自动收口到 done，并发送最终完成类飞书通知”。但当前实现已经改为 watcher 观察到 `task.json.status=done` 后统一发送最终完成通知。
- 风险：后续维护者会继续按旧机制理解通知时机，文档与实现发生偏差。
- 修复建议：把该段更新为“verify 通过只负责触发收口到 done；最终完成类通知由 watcher 的 done 观察分支统一发送”。

## 备注
- 当前 `verify.json` 时间戳早于本轮 `result.json`，不能作为本轮修复已验证通过的证据；本次结论基于当前代码直读。
- 我已复核 `bash -n /Users/lin/Desktop/work/my-agent-teams/scripts/task-watcher.sh`，语法层面通过，但上述逻辑阻塞仍需修复。
