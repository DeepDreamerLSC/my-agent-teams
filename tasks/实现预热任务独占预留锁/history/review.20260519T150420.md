# 审查说明：实现预热任务独占预留锁

## 结论

**审查未通过（request_changes）。当前不可收口。**

## 已确认通过项

1. 这轮返工已经把上一轮的工程性问题修掉一部分：
   - `scripts/reserve-task.sh` 已纳入正式 patch artifact；
   - 预热独占主链路测试可以稳定通过。

2. 我补充复跑了以下验证：

```bash
cd /Users/linsuchang/Desktop/work/my-agent-teams/.runtime/worktrees/my-agent-teams/task-e9dcc5f6 && \
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/prewarm-review-pycache \
/Users/linsuchang/Desktop/work/my-agent-teams/.venv/bin/python -B -m pytest -p no:cacheprovider \
  tests/test_claim_task_reserved.py \
  tests/test_task_pool_and_queue_router.py \
  tests/test_reassign_task.py \
  tests/test_task_watcher_push_reliability.py
```

结果：`48 passed in 42.19s`

另外 `bash -n` 与 `py_compile` 也都通过。

这些说明“事故链路已能跑通”，但**还不足以证明实现已经对齐本任务要求的正式契约**。

## 阻塞问题

### 1. 预热锁事实字段仍未对齐已批准的 `pre_reserved_*` 契约

已批准设计要求的事实字段是：

- `pre_reserved_by`
- `pre_reserved_at`
- `pre_reserved_until`
- `pre_reserved_by_actor`
- `pre_reserved_reason`
- `pre_reserved_origin`

但当前实现和测试仍在统一使用：

- `pre_reserved_expires_at`

并且没有落盘：

- `pre_reserved_by_actor`
- `pre_reserved_origin`

这不是纯命名问题，而是**契约未对齐**：

- `reserve-task.sh` 仍读写 `pre_reserved_expires_at`
- `task-pool-view.py` 对外输出的也是 `pre_reserved_expires_at`
- `task_state_invariants.py` 校验的还是 `pre_reserved_expires_at`
- `task-watcher.sh` / `reassign-task.sh` 清理、继承、超时回收也都围绕旧字段名展开
- 测试也把旧字段名固化成了断言基线

对应证据：

- 设计：`.../task-f2adfb6e/design/collaboration/预热任务独占预留机制.md:56-80,316-333`
- 实现：
  - `scripts/reserve-task.sh:130-143,194-195,234-256`
  - `scripts/task-pool-view.py:39-54,417-418`
  - `scripts/lib/task_state_invariants.py:135-147`
  - `scripts/task-watcher.sh:1170-1172,2975,3237`
  - `scripts/reassign-task.sh:177-194,225-228`
- 测试：
  - `tests/test_task_pool_and_queue_router.py:102`
  - `tests/test_reassign_task.py:106,125`
  - `tests/test_task_watcher_push_reliability.py:384,401,482`

**为什么这会阻塞：**
`task.json.rework_reason` 已明确要求“实现必须对齐已批准的 pre_reserved_* 契约”。当前虽然从旧的 `reserved_by` 预热迁移到了 `pre_reserved_*` 语义，但字段名和必需元数据仍未对齐，所以下游 PM / view / reporting / invariant 仍会看到错误或不完整的事实面。

### 2. `reserve-task.sh` 的 CLI / 状态支持仍低于批准方案

设计要求的入口能力包括：

- 允许状态：`pending / pooled / dependency_wait`
- `--release`
- `--force`
- `--until <ISO8601>`
- 与 `claim_scope` / agent 合法性 / active 锁冲突 / reserved slot 的正式校验

但当前 `reserve-task.sh`：

- usage 只有 `--ttl-seconds` / `--release`
- 没有 `--force`
- 没有 `--until`
- 直接限制 `status == pooled`

对应证据：

- 设计：`.../预热任务独占预留机制.md:233-260`
- 实现：`scripts/reserve-task.sh:16-35,180-182,219-221,234-259`

**为什么这会阻塞：**
本任务目标明确要求“依赖未 ready 时也要能预留”“需要提供 PM/系统可调用的正式入口”。当前脚本还不能覆盖 `pending / dependency_wait` 的正式预热，也缺少 PM 覆盖旧锁与绝对到期时间入口，因此还不能算完成整个预热独占机制。

## 建议返修方向

1. 把事实字段统一收敛到已批准契约：
   - `pre_reserved_expires_at` → `pre_reserved_until`
   - 补齐 `pre_reserved_by_actor`
   - 补齐 `pre_reserved_origin`

2. 同步修正以下链路：
   - reserve / release
   - watcher 继承 dispatch
   - timeout 回收
   - reassign
   - pool view 输出
   - invariant 校验
   - 测试夹具与断言

3. 扩展 `reserve-task.sh`：
   - 支持 `pending / pooled / dependency_wait`
   - 支持 `--force`
   - 支持 `--until`
   - 如尚未补齐，按 `config.agents` 增加 agent 合法性校验

4. 返修后建议至少补一组测试：
   - pending / dependency_wait 预热成功
   - `--force` 覆盖旧锁
   - `--until` 绝对时间写锁
   - view / invariant / watcher 对外口径统一使用 `pre_reserved_until`

## 总结

当前实现已经把“预热后被其他 agent 抢走”的主事故链路修到了**可运行**，但还没有修到**与已批准方案完全一致**。因此本轮结论应为 **request_changes**，暂不建议收口。
