# review-1 审查结论

- 结论：`approve`
- 是否可直接收口：**否**。本轮 review 可放行，但 `qa_gate_state` 仍为 `pending`，需先由 `qa-1` 复验后再收口。

## 本轮重点复核
按 PM 指定的两组返修点复审：

1. 字段契约是否统一为：
   - `pre_reserved_until`
   - `pre_reserved_by_actor`
   - `pre_reserved_origin`
2. `reserve-task.sh` CLI 是否支持：
   - `pending / pooled / dependency_wait`
   - `--force`
   - `--until`

## 审查结果
已确认本轮返修把关键链路收敛到同一口径：

- `scripts/reserve-task.sh`
  - 允许 `pending / pooled / dependency_wait` 进入预留；
  - 支持 `--force`、`--until`、`--by-actor`、`--origin`；
  - 新写入口统一落到 `pre_reserved_until / pre_reserved_by_actor / pre_reserved_origin`；
  - 覆盖替换/释放时会归档到 `last_pre_reserved_*`。
- `scripts/claim-task.sh`
  - 已拦截“任务已预留给其他 agent”场景，避免他人抢 claim。
- `scripts/task-watcher.sh`
  - auto-preheat 通过正式 `reserve-task.sh` 入口落锁；
  - 依赖 ready 后仅把任务 dispatch 给被预留 agent；
  - 预留继承到 dispatched 时会转存 `last_pre_reserved_*`；
  - 超时场景会清理锁并重新开放。
- `scripts/task-pool-view.py` / `scripts/lib/task_state_invariants.py` / `scripts/reassign-task.sh`
  - 已同步使用上述字段契约，并对 actor/origin/expiry 做一致性约束。
- 回归测试
  - 已覆盖 pending 预热、dependency_wait 预热、force override、absolute until、预热后仅能派给被预留 agent、超时清锁回退等关键路径。

## Reviewer 本地补充验证
在任务 worktree 复跑通过：

```bash
bash -n scripts/claim-task.sh scripts/task-watcher.sh scripts/reassign-task.sh scripts/reserve-task.sh
/Users/linsuchang/Desktop/work/my-agent-teams/agents/dev-2/.venv/bin/python -B -m pytest -p no:cacheprovider \
  tests/test_claim_task_reserved.py \
  tests/test_task_pool_and_queue_router.py \
  tests/test_reassign_task.py \
  tests/test_task_watcher_push_reliability.py -q
```

结果：`53 passed`

## 非阻塞说明
- 当前任务目录下仍未见 `verify.json`；本次 review 结论基于 `instruction.md`、`result.json`、write_scope 代码复核，以及 reviewer 本地补跑证据给出。

## 结论
本轮返修已解决上次 review 指出的契约差异，**可以进入 QA 复验**；在 QA 完成前，**暂不可直接收口**。
