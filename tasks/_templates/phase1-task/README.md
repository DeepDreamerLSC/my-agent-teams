# Phase 1 真实任务目录模板

每个真实任务目录至少包含：

- `task.json`
- `instruction.md`
- `transitions.jsonl`
- `ack.json`（agent 接单后写）
- `result.json`（agent 完成后写）
- `verify.json`（watcher / verify.sh 写）

可选文件：
- `review.md` / `test.md`（人工审查 / 测试结论，先走 artifacts 复用）
- `review-summary.md`（仅 `review_authority=owner` 时，由 PM 写给林总工的审查汇总）

推荐流程：

1. PM 用 `scripts/create-task.sh` 创建任务目录
2. PM 用 `scripts/dispatch-task.sh` 将任务从 `pending` 推进到 `dispatched`
3. agent 写 `ack.json`，watcher 自动推进到 `working`
4. agent 写 `result.json`，watcher 自动调用 `verify.sh`
5. 若 `review_required=false` 且 `test_required=false`，watcher 自动推进到 `done`
6. 若需要 review / test，则 watcher 先推进到 `ready_for_merge` 并通知 PM
7. 若 `review_authority=owner`，PM 汇总 reviewer 意见到 `review-summary.md`，watcher 检测到后推送林总工决策

## create-task.sh 参数

```bash
./scripts/create-task.sh <task-id> <title> <assigned-agent> <domain> [write-scope-csv] [review-required] [test-required] [review-authority]
```

- `review-authority` 默认 `reviewer`
- 若是设计文档 / 方案稿等需要 owner 决策的任务，可传 `owner`
