# Phase 1 真实任务目录模板

每个真实任务目录至少包含：

- `task.json`
- `instruction.md`
- `transitions.jsonl`
- `ack.json`（agent 接单后写）
- `result.json`（agent 完成后写）
- `verify.json`（QA 任务由 qa-1 写；watcher 读取其 pass/fail 自动流转）

可选文件：
- `review.md` / `test.md`（人工审查 / 测试结论，先走 artifacts 复用）
- `review-summary.md`（仅 `review_authority=owner` 时，由 PM 写给林总工的审查汇总）

推荐流程：

1. PM 用 `scripts/create-task.sh` 创建任务目录
2. PM 用 `scripts/dispatch-task.sh` 将任务从 `pending` 推进到 `dispatched`
3. agent 写 `ack.json`，watcher 自动推进到 `working`
4. execution / domain / integration 任务写 `result.json`，watcher 自动推进到下一环节（review / QA / PM）
5. QA 任务完成后，qa-1 写 `verify.json`
6. `verify.json` 标记 `pass` 后，watcher 自动执行 `close-task.sh` 收口
7. 若 `review_authority=owner`，PM 汇总 reviewer 意见到 `review-summary.md`，再由 PM 推送林总工决策

## create-task.sh 参数

```bash
/Users/lin/Desktop/work/my-agent-teams/scripts/create-task.sh <task-id-title> <title> <assigned-agent> <domain> <project> [write-scope-csv] [review-required] [test-required] [review-authority] [execution-mode] [target-environment]
```

- `task-id-title` 必须使用不含空格且包含中文的标题式名称，例如：`修复Word生成质量问题`
- `review-authority` 默认 `reviewer`
- 若是设计文档 / 方案稿等需要 owner 决策的任务，可传 `owner`

## QA verify.json 最小格式

```json
{
  "task_id": "验证聊天页搜索高亮",
  "agent": "qa-1",
  "agent_id": "qa-1",
  "verified_at": "2026-04-23T14:40:00+08:00",
  "status": "pass",
  "pass": true,
  "summary": "QA 已完成，核心场景通过，可自动收口。"
}
```
