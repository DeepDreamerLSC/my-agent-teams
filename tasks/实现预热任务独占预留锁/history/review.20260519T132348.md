# review-1 审查结论

- 任务：`实现预热任务独占预留锁`
- 结论：`request_changes`
- 审查时间：`2026-05-19T13:20:31+08:00`
- 收口判断：**不可收口，需返修后再审**

## 审查范围

1. `instruction.md`
2. `result.json`
3. `task.json`
4. 交付脚本与测试：
   - `scripts/claim-task.sh`
   - `scripts/task-watcher.sh`
   - `scripts/task-pool-view.py`
   - `scripts/task-pool-router.py`
   - `scripts/reassign-task.sh`
   - `scripts/reserve-task.sh`
   - `scripts/lib/task_state_invariants.py`
   - `tests/test_claim_task_reserved.py`
   - `tests/test_task_pool_and_queue_router.py`
   - `tests/test_reassign_task.py`
   - `tests/test_task_watcher_push_reliability.py`
5. 对照契约：
   - `task-f2adfb6e/design/collaboration/预热任务独占预留机制.md`

## 结论摘要

这批改动的**功能性测试是过的**，我也补跑出了 `47 passed`。但当前仍不能 approve，原因有两个，而且都是阻塞级：

1. **实现没有按已批准的预热独占设计契约落地**；
2. **新的正式入口 `scripts/reserve-task.sh` 还是未跟踪文件，且没有进入 patch artifact**。

所以当前状态更像是“按旧语义跑通了一套本地实现”，而不是“可以稳定进入合并链路的正式交付”。

## 阻塞问题 1：实现契约与已批准设计冲突

已批准的设计文档已经明确冻结：

- 要新增 `pre_reserved_*` 字段；
- **不复用** `reserved_by` 表达预热锁；
- `pooled/dependency_wait` 阶段不得把预热锁落到 `reserved_by`；
- `reserved_by/claimed_by` 只保留给 `dispatched` 未 ack 的 active reservation；
- view/router 的展示与 blocked reason 也要走 `pre_reserved_for:*` / `pre_reserved_count` / `capacity_decision=inherited_pre_reserved_slot` 这套口径。

但当前实现不是这样：

- `scripts/reserve-task.sh` 在 pooled 阶段直接写：
  - `reserved_by`
  - `reserved_at`
  - `reserved_reason`
  - `reservation_expires_at`
- `task-pool-view.py` 也是围绕 pooled `reserved_by` 读锁，并输出 `reserved_for_other:*`；
- `task_state_invariants.py` 也正式放宽为“`status=pooled` 且 `reserved_by` 存在是合法状态”。

这意味着本次实现实际上把“预热前独占权”和“dispatch 后 active reservation”又重新揉回了同一套字段，和刚刚批准的设计决策正面相反。

这不是简单的字段重命名问题，而是**控制面事实源**变了：

- PM/脚本该写什么字段；
- watcher/view/router 该读什么字段；
- invariant 如何判断合法状态；
- review/QA 该按什么口径验收；

现在全都和已批准设计脱节。

### 返修建议

请按已批准契约统一返修：

- 预热阶段改为写 `pre_reserved_*` / `last_pre_reserved_*`；
- `reserved_by/claimed_by` 只保留给 `dispatched` 未 ack；
- `task-pool-view.py` / `task-pool-router.py` / `claim-task.sh` / `task-watcher.sh` / `task_state_invariants.py` / tests 一起切到 `pre_reserved_*` 口径；
- blocked reason / summary 字段同步改为：
  - `pre_reserved_for:*`
  - `pre_reserved_count`
  - `capacity_decision=inherited_pre_reserved_slot`

## 阻塞问题 2：`scripts/reserve-task.sh` 未进入正式交付载荷

这是另一个硬问题。

当前 worktree 里：

- `git status` 显示：`?? scripts/reserve-task.sh`

同时本任务 patch artifact：

- `/Users/linsuchang/Desktop/work/my-agent-teams/tasks/实现预热任务独占预留锁/artifacts/task-e9dcc5f6.patch`

其 `diff --git` 列表**不包含** `scripts/reserve-task.sh`。

也就是说：

- 你确实在本地写了这个新脚本；
- tests 也确实在用它；
- 但它还没进入正式补丁交付物。

这会带来非常直接的问题：

- 如果后续按 patch artifact 集成，这个新入口可能直接丢失；
- `result.json` 里把它写成已交付文件，但实际补丁里没有；
- review/QA 当前看到的是“本地 worktree + 未跟踪文件”的状态，不是完整可合并状态。

### 返修建议

- 把 `scripts/reserve-task.sh` 纳入正式版本控制/交付载荷；
- 重新生成 patch artifact；
- 再确认 `result.json.files_modified`、补丁内容、实际 worktree 三者一致。

## 补充验证

我额外做了以下检查：

```bash
cd /Users/linsuchang/Desktop/work/my-agent-teams/.runtime/worktrees/my-agent-teams/task-e9dcc5f6
/Users/linsuchang/Desktop/work/my-agent-teams/.venv/bin/python -m pytest   tests/test_claim_task_reserved.py   tests/test_task_pool_and_queue_router.py   tests/test_reassign_task.py   tests/test_task_watcher_push_reliability.py -q
```

结果：`47 passed, 1 warning`

warning 仅为 `.pytest_cache` 写入受限，不影响功能判断。

我还额外跑了：

```bash
bash -n scripts/claim-task.sh scripts/task-watcher.sh scripts/reassign-task.sh scripts/reserve-task.sh
python3 -m py_compile   scripts/task-pool-view.py   scripts/task-pool-router.py   scripts/lib/task_state_invariants.py   tests/test_claim_task_reserved.py   tests/test_task_pool_and_queue_router.py   tests/test_reassign_task.py   tests/test_task_watcher_push_reliability.py
```

这些也都通过。

所以这次不是“代码跑不起来”，而是：

- **跑起来的这套实现，不符合已批准契约**；
- **而且正式交付载荷还缺了关键新文件**。

## 非阻塞备注

- 当前任务目录下暂无 `verify.json`；建议后续 QA 复验补写，便于门禁留痕。

## 结论

当前结论：`request_changes`

请先完成以下两件事后再回审：

1. 按已批准设计把 pooled 阶段的预热锁从 `reserved_by` 体系切换到 `pre_reserved_*` 契约；
2. 把 `scripts/reserve-task.sh` 纳入正式交付载荷，并重新生成完整 patch artifact。
