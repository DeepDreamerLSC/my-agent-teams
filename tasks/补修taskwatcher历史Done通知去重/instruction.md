# 补修 task-watcher 历史 done 通知去重

## 任务类型
development

## 目标
修复 review/QA 指出的最终完成通知风险：task-watcher 重启时不能对历史 `done` 任务批量补发“任务完成/部署完成”通知；同时修正文档中关于 verify 通过与最终通知时机的描述。

## 任务边界
- 只修改 task-watcher 通知去重逻辑和对应设计文档说明。
- 不改任务创建/派发/关闭脚本，除非发现必须同步的最小兼容点并在 result.json 中说明。
- 不做生产部署。

## 输入事实
- 原任务 `/Users/lin/Desktop/work/my-agent-teams/tasks/修正taskwatcher仅在任务最终完成后发飞书通知/review.md` 结论 REQUEST CHANGES。
- QA 结论：当前 `notify_final_done_if_needed()` 仅依赖 sentinel 去重，watcher 重启可能对约 92 个历史 done 任务补发完成通知。
- 文档 `design/OpenClaw-tmux协作方案优化.md` 仍把“verify 通过自动收口”与“最终完成通知发送”写在同一阶段，需改为 done 观察分支统一发送。

## 约束
- write_scope 仅限：
  - `/Users/lin/Desktop/work/my-agent-teams/scripts/task-watcher.sh`
  - `/Users/lin/Desktop/work/my-agent-teams/design/OpenClaw-tmux协作方案优化.md`
- result.json.status 只能使用 `done` / `failed` / `blocked`。
- 必须避免历史任务刷屏；宁可少发历史通知，也不能批量补发误报。

## 交付物
- 修正后的 `task-watcher.sh`。
- 修正后的设计文档段落。
- `result.json`，包含实现策略、验证命令和剩余风险。

## 验收标准
1. watcher 启动/重启不会对已存在的历史 `done` 任务批量发送最终完成通知。
2. 新近从 `ready_for_merge -> done` 收口的任务仍能触发一次最终完成通知。
3. 去重逻辑有明确 sentinel 或时间/transition 判定依据。
4. `bash -n scripts/task-watcher.sh` 通过。
5. 设计文档中明确：verify 通过只负责收口到 done；最终完成类通知由 watcher 的 done 观察分支统一发送。

## 下游动作
完成后进入 review 和 QA；通过后可收口原通知修正链路。

## 授权状态
这是对 review/QA 驳回问题的补修任务，dev 环境执行，不涉及生产部署。
