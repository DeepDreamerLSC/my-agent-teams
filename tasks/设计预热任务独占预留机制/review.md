# review-1 审查结论

- 任务：`设计预热任务独占预留机制`
- 结论：`approve`
- 审查时间：`2026-05-19T13:02:30+08:00`
- 收口判断：**可收口**

## 审查范围

1. `instruction.md`
2. `result.json`
3. `task.json`
4. 交付文档：
   - `design/collaboration/预热任务独占预留机制.md`
5. 兼容性对照：
   - `scripts/task-pool-view.py`
   - `scripts/task-pool-router.py`
   - `scripts/task-watcher.sh`
   - `scripts/claim-task.sh`

## 审查结论

本轮返修已经解决我上一轮指出的阻塞问题，可以通过。

上次的核心问题是：

- 文档一边说 pre-reserve 计入 reserved slot；
- 一边又要求依赖解锁后只有“还有 spare reserved slot”才能派发；
- 这会在 `default_reserved_limit=1` 下造成任务卡死在 `pooled + pre_reserved`。

本次返修已把这点明确收敛为 **方案 A**，且口径前后一致：

- pre-reserve **从写入起**就占用 reserved slot；
- 但 `dependency_ready -> dispatched` 是**同一 slot 的继承转换**；
- 因此对同一任务、同一 agent 的派发/claim，**不能再额外要求 spare reserved slot**；
- capacity gate 必须按“**排除当前任务**”的口径计算；
- 文档还补上了 `default_reserved_limit=1` 不自锁的显式验收断言。

这使下游实现不再需要自行猜测“pre-reserve 到底算不算占坑、dispatch 时要不要再过一次 reserved_limit”，关键语义已经冻结清楚。

## 我确认通过的点

1. **字段与主决策清楚**
   - 仍坚持新增 `pre_reserved_*`，没有退回到复用 `reserved_by` 的模糊状态；
   - 方案 A 的容量语义已单点冻结。

2. **状态机闭环完整**
   - pending / pooled / dependency_wait / dispatched / working 的写入、继承、清理、超时规则仍然完整；
   - 返修后对 `pooled/dependency_wait -> dispatched` 的容量判断已不再冲突。

3. **脚本兼容要求可落地**
   - `reserve-task.sh` 的容量校验改成 `reserved_count_excluding_current_task(...)`；
   - `task-pool-view.py` / `task-pool-router.py` 明确区分 `new_slot_required` 与 `inherited_pre_reserved_slot`；
   - `claim-task.sh` / `task-watcher.sh` 也都明确要求对“当前任务自身占用的 pre-reserve slot”做继承转换，而不是按新增 slot 拒绝。

4. **事故防复发断言到位**
   - 文档现在不仅阻止 `dev-1` 抢认领；
   - 还明确覆盖了 `default_reserved_limit=1` 时预热任务不应自锁的场景。

## 补充验证

我本轮额外做了以下静态复核：

```bash
git -C /Users/linsuchang/Desktop/work/my-agent-teams/.runtime/worktrees/my-agent-teams/task-f2adfb6e   show --stat --format=fuller aaf739be318f84d3b4e9848d1c05ec60e30eae2f --   design/collaboration/预热任务独占预留机制.md

git -C /Users/linsuchang/Desktop/work/my-agent-teams/.runtime/worktrees/my-agent-teams/task-f2adfb6e   diff --check HEAD~1..HEAD -- design/collaboration/预热任务独占预留机制.md
```

并交叉对照了当前门禁实现：

- `task-pool-view.py:192-198, 279-295`
- `task-watcher.sh:1450-1457, 1634-1639`
- `claim-task.sh:182-227`

确认返修后的文档已经对这些现有 `reserved_count < reserved_limit` 口径给出了明确、可执行的实现约束，不再保留上一版的自锁冲突。

## 非阻塞备注

1. 任务目录下仍无 `verify.json`；但这不影响本次设计审查结论。
2. 本任务仍然只是冻结设计契约；真正把 helper / view / router / watcher / claim 代码改出来，仍需下游实现任务继续完成。

## 结论

本次返修已消除上一轮 blocker，当前可 `approve`，并交回 PM 收口 / 推进下游实现。
