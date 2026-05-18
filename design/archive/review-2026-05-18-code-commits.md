# 2026-05-18 最近 8 个提交代码审查

审查范围：`95e1c8b^..d3086c1`

覆盖提交：

- `d3086c1` - Implement task worktrees and integration queue visibility
- `c790a80` - fix: start dashboard with repo venv
- `3e31bae` - Harden control-plane recovery flows
- `2c63737` - Enforce task-type quality gate templates
- `5fa5003` - Harden pool gate and auto-claim safeguards
- `ebba696` - feat(control-plane): parallelize review and qa gates
- `7cb4c19` - feat(control-plane): land pool-first orchestration and doc alignment
- `95e1c8b` - docs: add parallelism task pool optimization plan

## Findings

### High: pool 认领路径绕过 worktree 准备，默认 worktree 模式不能闭环

位置：

- `scripts/task-watcher.sh:1458`
- `scripts/task-watcher.sh:1489`
- `scripts/claim-task.sh:232`
- `scripts/claim-task.sh:237`
- `scripts/task-watcher.sh:2750`
- `scripts/task-watcher.sh:2751`

`auto_push_next_task_for_agent` 和 `auto_reserve_next_task_for_agent` 都直接调用 `claim-task.sh`，随后只通知 agent 读取 instruction。`claim-task.sh` 自己把任务从 `pooled` 改成 `dispatched`，但不调用 `ensure-task-workspace.py`，也不把 worktree hint 写入通知。相反，只有 watcher 的 `process_claim_json` 路径会在 `dispatch_task_to_agent` 后调用 `prepare_task_workspace_payload`，但该函数要求任务仍是 `pooled`，因此通过 `claim-task.sh` 成功认领后已经不会再进入这条准备 worktree 的路径。

影响：

- `config.json` 默认 `workspace_mode=worktree`，但 pool-first 的主要认领路径可能不会创建独立 worktree。
- agent 可能继续在主工作区或 agent 目录工作，破坏 d3086c1 的 worktree 隔离目标。
- `workspace_status`、`worktree_path`、`patch_path` 可能缺失或滞后，integration queue visibility 失真。

建议：

- 收敛认领状态机：`claim-task.sh` 只写 `claim.json`，由 watcher 唯一负责 `pooled -> dispatched`、worktree 准备和消息投递。
- 如果保留 `claim-task.sh` 直接改状态，则必须在同一临界区内调用 `ensure-task-workspace.py`，并把 `dispatch_hint` 返回给调用方和 watcher 通知。
- 增加测试：通过 `claim-task.sh` 从 pooled 认领默认 worktree 任务后，断言 `workspace_status=prepared`、`worktree_path` 存在、通知包含 worktree hint。

### High: claim 容量和 write_scope 冲突检查不是原子操作

位置：

- `scripts/claim-task.sh:172`
- `scripts/claim-task.sh:188`
- `scripts/claim-task.sh:190`
- `scripts/claim-task.sh:192`
- `scripts/claim-task.sh:205`
- `scripts/claim-task.sh:211`

`claim-task.sh` 在获取任务本地 `.claim.lock` 之前扫描 active tasks、计算 `working_count` / `reserved_count` / `active_count`，并检查 write_scope 冲突。加锁后只重新检查目标任务状态、pool gate 和依赖，不再重新检查容量和 write_scope。由于锁是每个 task 目录局部锁，两个不同 pooled 任务可以被同一个 agent 并发 claim：两个进程都可能先看到 active count 为空，然后分别拿到各自任务锁并写成 `dispatched`。

影响：

- 可突破 `default_reserved_limit` / `active_limit`。
- 可让同一 agent 同时拿到 write_scope 冲突的多个任务。
- 在多 agent 并行认领时，这个问题会削弱 pool gate 和 auto-claim safeguard 的核心安全性。

建议：

- 增加 agent 级或全局 pool claim 锁，例如 `$STATE_DIR/claim-agent-$agent.lock` 或 `$STATE_DIR/claim-global.lock`。
- 在锁内重跑完整的 claim eligibility，包括 claim_scope、依赖、容量和 write_scope 冲突。
- 增加并发测试：同时 claim 两个任务，断言只能有一个成功；同时 claim 相同 write_scope，断言第二个失败。

### Medium: QA 队列状态按全局清空，会误删无关 QA 当前任务

位置：

- `scripts/task-watcher.sh:2457`
- `scripts/task-watcher.sh:2464`
- `scripts/task-watcher.sh:3640`
- `scripts/task-watcher.sh:3648`
- `scripts/task-watcher.sh:3689`

`clear_qa_queue_state` 会遍历所有 QA agent 并删除各自 queue state。verify artifact 进入 invalid/pass/fail 分支时都调用这个全局清理函数。代码中已经有更安全的 `clear_qa_queue_state_for_task "$task_id"`，但 verify 分支没有使用。review 分支使用的是按 task 清理的 `clear_review_queue_state_for_task`，两者不一致。

影响：

- 某个任务产生 `verify.json` 后，会清掉其他 QA agent 或同一 QA agent 正在处理的无关 QA queue state。
- idle sweep 可能误判 QA agent 没有当前队列任务，从而重复推送新 QA 任务。
- 并行 review/QA gate 下，队列可见性和实际处理状态可能分叉。

建议：

- 将 verify invalid/pass/fail 分支的 `clear_qa_queue_state` 替换为 `clear_qa_queue_state_for_task "$task_id"`。
- 增加与 `test_review_queue_clear_only_removes_matching_task` 对称的 QA 测试：已有 `qa-queue-qa-1.json` 指向 task-b，处理 task-a verify 后不应删除 task-b。

### Medium: worktree patch 捕获对默认 target branch 和新文件不可靠

位置：

- `config.json:169`
- `config.json:172`
- `scripts/create-task.sh:430`
- `scripts/create-task.sh:431`
- `scripts/lib/task_workspace.py:83`
- `scripts/lib/task_workspace.py:90`
- `scripts/lib/task_workspace.py:235`
- `scripts/write-task-artifact.py:130`
- `scripts/write-task-artifact.py:133`
- `scripts/write-task-artifact.py:137`
- `scripts/write-task-artifact.py:140`

默认 `target_branch` 是 `integration`，但当前仓库只有 `main` 和 `origin/main`。`task_workspace._resolve_base_ref` 在找不到 `integration` 时会回退到 `HEAD` 创建 worktree，但 `integration_target_branch` 仍保留为 `integration`。`write-task-artifact.py` 捕获 patch 时先跑 `git format-patch integration..HEAD`，该 ref 不存在时失败；随后只跑 `git diff --binary HEAD`。这只能捕获未提交的已跟踪文件改动，无法捕获已提交到任务分支的提交，也无法捕获未跟踪的新文件。

影响：

- agent 如果在 task branch 上 commit 了改动，且 `integration` ref 不存在，`result.json` 写入时可能得不到 patch。
- agent 如果新增未跟踪文件但未 `git add`，patch 也会漏掉这些文件。
- integration queue 可能显示 `branch_only` 或 patch missing，但没有明确错误，集成 owner 难以判断真实可合入内容。

建议：

- worktree plan 中应持久化实际解析后的 base ref，并让 patch capture 优先使用 `workspace_base_ref..HEAD`，而不是未解析的 `integration_target_branch`。
- 在仓库初始化或配置检查阶段保证 `target_branch` 存在，或者默认改为当前存在的集成分支。
- patch capture 应显式处理 untracked files；至少在 `patch_capture_error` 中记录 `untracked_changes_present`，更理想是通过临时 index 或 `git add -N` 生成包含新文件的 diff。
- 增加测试：target_branch 不存在但 worktree 有 commit；worktree 新增未跟踪文件；两者都应产生可审查 patch 或明确错误。

### Low: `task-state-reducer.py` 对真实 ready_for_merge 任务不具备幂等性

位置：

- `scripts/task-state-reducer.py:100`
- `scripts/task-state-reducer.py:103`
- `scripts/task-state-reducer.py:145`

纯 reducer 先匹配 `result.normalized_status == success`，再处理 `status == ready_for_merge`。真实 `ready_for_merge` 任务通常仍保留当前轮次 `result.json`，因此如果未来把 reducer 接入 watcher，这个分支顺序会反复把已进入 review/QA/PM acceptance 的任务重置为 `ready_for_merge + pending gates`，并重新生成 dispatch_review / dispatch_qa action。当前代码库中 reducer 尚未被 watcher 调用，影响暂时是潜在风险；但测试 fixture 里多个 ready_for_merge 场景没有 `result.json`，没有覆盖真实形态。

建议：

- 将 success result 分支限定为 `status in {'working', 'dispatched'}`，或先处理 `ready_for_merge` gate 收敛。
- 增加测试：`ready_for_merge + result.json + review approve + verify pass` 应输出 `pm_acceptance_pending`，不得重置为 pending。

## 架构一致性结论

整体方向是合理的：8 个提交把任务池、pull-first 认领、并行 review/QA gate、控制面恢复、质量模板、dashboard/Gantt 和 worktree 可视化放到了同一套 control-plane 语言里。提交之间的设计意图基本一致，尤其是 `task_artifacts.py` 对 stale round 的处理、`quality_gate_mode=parallel` 的 gate 状态、以及 dashboard 对并行 Gantt 的展示方向是正确的。

但当前实现还不能视为 fully safe。最大不一致在于 pool-first 认领和 worktree/integration queue 是后叠加的两套路径：直派和 watcher 处理 `claim.json` 会准备 worktree，而 `claim-task.sh` 直接认领不会；这会让默认 worktree 模式在主路径上失效。第二个不一致在于 review 队列按 task 清理，QA 队列却全局清理，和并行 gate 的队列隔离目标冲突。

建议在继续扩大并行度前，先修复前三项 high/medium 风险；第四项 patch 捕获问题应在真正依赖 integration queue 合入前修复；reducer 幂等性可在接入 watcher 前修复。

## 测试与覆盖

已执行：

```bash
python3 -m unittest discover -s tests
```

结果：64 个测试通过。

补充说明：尝试运行 `python3 -m pytest ...` 时当前环境没有安装 `pytest`，因此改用标准库 `unittest`。现有测试覆盖了大量单路径控制面行为，但缺少以下关键覆盖：

- 并发 claim 同一 agent 的容量竞争测试。
- claim-task.sh 成功认领后 worktree 准备测试。
- QA queue state 按 task 清理测试。
- patch capture 对 missing target branch、committed branch changes、untracked new files 的测试。
- reducer 对真实 `ready_for_merge + result.json` 任务的幂等性测试。
