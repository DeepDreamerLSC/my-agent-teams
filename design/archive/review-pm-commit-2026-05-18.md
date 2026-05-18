# 审查：pm-chief commit 6dacd6b

审查对象：`6dacd6b fix(task-watcher): harden watcher reliability and backfill closed merge gates`

结论：变更方向合理，但当前提交不建议直接视为可靠性收口完成。核心风险在 watchdog 的退出语义和 `teamctl.sh` 对启停结果的处理，可能导致 `teamctl stop_watcher` 停不干净、watcher 被重新拉起，甚至后续出现不可见的 watchdog 实例。

## Findings

### High：watchdog 收到 TERM 后不会退出，`teamctl stop_watcher` 无法可靠停干净

位置：`scripts/task-watcher-watchdog.sh:44-52`、`scripts/task-watcher-watchdog.sh:323-329`、`scripts/teamctl.sh:377-379`

本次新增的 trap 是：

```bash
trap cleanup_watchdog_runtime EXIT INT TERM
```

`cleanup_watchdog_runtime` 只删除 watchdog pid file，没有 `exit`。在 bash 中，给 `TERM`/`INT` 设置 trap 后，trap 执行完不会自动恢复默认退出行为；watchdog 仍会继续 `while true` 循环。结果是：

- `teamctl stop_watcher` 对 watchdog 发 `TERM` 后，watchdog 可能只删除 pid file 但继续运行。
- `stop_pid_file` 会等待并报警 `still running after TERM`，但 `stop_watcher` 又用 `|| true` 吞掉失败。
- 随后 `teamctl` 杀掉 task-watcher，仍在运行的 watchdog 会在下一轮检测到 pid 缺失/进程退出并重新启动 watcher。
- 因为 watchdog pid file 已被删除，后续 `start_watcher` 还可能再启动一个新的 watchdog，形成不可见旧 watchdog 与新 watchdog 并存的风险。

建议：给 `TERM`/`INT` 使用独立 shutdown handler，例如 `cleanup_watchdog_runtime; exit 0`；必要时记录日志。`teamctl stop_watcher` 应继续尝试停止 watcher，但最终返回真实失败状态，不能无条件吞掉。

### Medium：`teamctl start_watcher` 不能迁移已有 standalone watcher 到 watchdog 监管

位置：`scripts/teamctl.sh:332-344`

本次 `teamctl start_watcher` 先检查 watchdog pid；如果没有 watchdog，但发现旧的 `task-watcher.pid` 仍在运行，会直接返回 `task-watcher already running`。这会让升级前已存在的 standalone watcher 继续裸跑，无法获得本次提交引入的 watchdog 监管能力。

建议：当 watchdog 不存在但 watcher 存在时，应该启动 watchdog 并让它接管/监管现有 watcher；或者显式执行 replace 流程，先停旧 watcher 再由 watchdog 拉起。

### Medium：`teamctl stop_watcher` 吞掉停止失败，降低运维可观测性

位置：`scripts/teamctl.sh:377-379`

当前实现：

```bash
stop_pid_file "$STATE_DIR/task-watcher/task-watcher-watchdog.pid" task-watcher-watchdog || true
stop_pid_file "$STATE_DIR/task-watcher/task-watcher.pid" task-watcher || true
```

这会让 CLI 在 watchdog 或 watcher 未能停止时仍返回成功。对于“harden watcher reliability”的目标，这会掩盖最关键的启停失败信号，也会让上层脚本误判已完成清理。

建议：保留“两者都尝试停止”的行为，但累积返回码；只要任一进程未停干净，`stop_watcher` 最终返回非零。

### Low：JSON parse fallback 过于静默，可能隐藏控制面数据错误

位置：`scripts/task-watcher.sh:879-883`、`scripts/task-watcher.sh:1726-1729`

把 malformed invariant report 或 patch JSON 兜底为 `{}` 可以避免 watcher 崩溃，方向上合理；但当前没有日志、没有错误状态，也没有保留旧 invariant 报警。副作用是：

- invariant report 解析失败会被等同于“无违规”，可能清掉已有 `state_invariant_violations`。
- patch JSON 解析失败会导致 gate/status 元数据字段静默丢失，调用方仍可能看到“无变化”而非明确失败。

建议：至少写入 task-watcher log；对 invariant report 解析失败应保留原违规状态或标记 parse error；对 patch JSON 解析失败应返回失败，不应静默降级为 `{}`。

### Low：回填范围与提交描述不一致，建议拆分或补充说明

用户描述为“61 个历史 done 任务补 closed merge_gate_state”，但基于 `6dacd6b^..6dacd6b` 的实际 diff：

- `tasks/*/task.json` 共 59 个发生变化。
- 其中 49 个是修改，10 个是新增。
- 提交后这 59 个任务均为 `status=done` 且 `merge_gate_state=closed`。

字段结果本身符合“done task 关闭 merge gate”的方向，但这不是纯粹的“61 个历史任务回填”：它混入了新增 task record，且数量不一致。建议把数据回填与 watcher 代码可靠性修复拆成不同 commit，或在提交说明中明确选择口径、实际数量、为何新增 task.json。

## 变更合理性

合理部分：

- `teamctl` 改为经 watchdog 启动 watcher，方向正确，能让 watcher 退出/heartbeat 卡死后自动恢复。
- watchdog pid file 与单实例检查是必要补强，能提升重启和运维可见性。
- 对历史 terminal done 任务补 `merge_gate_state=closed`，如果选择范围确实限定为终态任务，有助于减少 legacy 任务导致的 invariant false positive。

需要修正部分：

- watchdog 的信号处理必须先修，否则“可干净停止/重启”这一目标没有达成。
- `teamctl.sh` 的启停语义需要补齐：启动要能接管旧 watcher，停止要返回真实失败状态。
- JSON fallback 应从“静默吞错”改为“不中断主循环但显式记录/暴露错误”。

## 验证

已执行：

```bash
bash -n scripts/task-watcher-watchdog.sh scripts/task-watcher.sh scripts/teamctl.sh
python3 -m unittest discover -s tests
```

结果：

- shell 语法检查通过。
- 单元测试通过：`Ran 64 tests in 4.412s`，`OK`。
- 任务回填核对：59 个 `tasks/*/task.json`，提交后全部 `status=done`、`merge_gate_state=closed`。

## 建议结论

该提交可以作为方向性修复保留，但需要追加修复后再认为 watcher 可靠性已闭环。优先修复顺序：

1. 修正 watchdog `TERM`/`INT` trap，确保收到停止信号后退出。
2. 修正 `teamctl stop_watcher` 返回码，不吞掉停止失败。
3. 修正 `teamctl start_watcher` 对已有 standalone watcher 的接管逻辑。
4. 为 malformed invariant report / patch JSON 增加日志或错误状态。
5. 单独提交或补说明，澄清历史任务回填数量与新增 task.json 的来源。
