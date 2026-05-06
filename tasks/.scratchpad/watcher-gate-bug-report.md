# task-watcher Gate 漏推进排查报告

## 排查范围
`~/Desktop/work/my-agent-teams/scripts/task-watcher.sh` 中 `merge_gate_state` 的推进链路

## 现象
当 review.md=APPROVE 且 verify.json.status=pass 后，task-watcher 没有自动把 merge_gate_state 从 `review_pending` 推进到 `qa_pending` 或 `closed`，导致任务卡在 `review_pending` 无法自动收口。

## 相关代码路径

| 功能 | 位置 | 作用 |
|------|------|------|
| gate 归一化 | L1788-1794 | 每轮对 ready_for_merge/blocked 任务推断正确 gate |
| result.json 检测 | L1840-1896 | result.json → ready_for_merge，设初始 gate |
| review.md 检测 | L1914-1954 | review pass → 推进 gate 到 qa_pending/pm_acceptance_pending |
| verify.json 检测 | L1957-1985 | verify pass → auto_close_task → close-task.sh |
| resolve_merge_gate_state | L1116-1217 | Python gate 推断（gate 归一化使用） |
| close-task.sh gate 检查 | close-task.sh:164-176 | 拒绝 review_pending/review_rejected/qa_failed |

## 发现的问题

### 问题 1（HIGH）: resolve_merge_gate_state 不区分 verify 是否已 pass

**位置**: L1209-1210

```python
elif test_required and (not review_required or review_state == 'pass'):
    print('qa_pending')
```

当 review=pass、verify=pass、test_required=true 时，此分支返回 `qa_pending`，**不检查 verify 是否已经 pass**。结果：

- gate 归一化每轮都把 merge_gate_state 设为 `qa_pending`（即使 verify 已 pass）
- gate 永远不会到达 "已全部通过可收口" 的终态
- 自动收口完全依赖 verify 检测代码路径（L1963-1975），如果该路径被跳过，任务永久卡住

**应返回**: 当 review=pass 且 verify=pass 时，应返回可触发自动收口的状态（如 `pm_acceptance_pending` 或直接标记为可 close）。

### 问题 2（HIGH）: close-task.sh 无条件拒绝 review_pending，即使 review.md 已 APPROVE

**位置**: close-task.sh:164-165

```python
if merge_gate_state == 'review_pending':
    fail(f'task merge_gate_state still pending: {merge_gate_state}')
```

与 qa_pending 不同（L169 有 verify pass 豁免），review_pending 没有任何豁免路径。场景：

1. result.json → merge_gate_state=review_pending
2. Reviewer 写入 APPROVE review.md
3. QA 写入 verify.json (pass) — 发生在 watcher 处理 review 之前
4. 如果 gate 归一化因任何原因失败（见问题 3），gate 仍为 review_pending
5. verify 检测 → auto_close_task → close-task.sh → **被 review_pending 直接拒绝**

**建议**: 像 qa_pending 一样，当 review_pending 且 review.md 已 APPROVE 时允许 close。

### 问题 3（HIGH）: resolve_merge_gate_state 错误吞噬所有异常

**位置**: L1789

```bash
inferred_gate_state=$(resolve_merge_gate_state "$task_dir" 2>/dev/null || true)
```

`2>/dev/null || true` 导致：
- verify.json JSON 解析错误 → 脚本崩溃 → 输出空 → gate 归一化静默跳过
- review.md 编码错误 → 同上
- 任何 Python 异常 → 同上

gate 归一化是唯一"每轮必跑"的 gate 推进路径。如果它静默失败，gate 永远停在当前状态。

**建议**: 至少 log 错误，不要完全吞噬异常。

### 问题 4（MEDIUM）: review.md 存在三套不一致的解析器

| 解析器 | 位置 | 扫描范围 | 误判风险 |
|--------|------|----------|---------|
| bash `review_file_state()` | L986-1034 | 先提取结论块(awk)，再 grep | 低 — 限定结论段 |
| python `parse_review_state()` (resolve_merge_gate_state 内) | L1131-1157 | **全文 substring scan** | 高 — body 中的 reject 词会触发 |
| python `classify_review_text()` (close-task.sh 内) | close-task.sh:80-154 | 结论标签后的 snippet | 低 — 类似 awk 逻辑 |

**具体冲突场景**: review.md 结论为 APPROVE，但 body 中提及 `review_rejected`/`qa_failed`/`不通过`（如解释历史驳回原因）：
- resolve_merge_gate_state 的 python 解析器扫描全文 → 找到 reject 词 → 返回 `fail` → gate 归一化设为 `review_rejected`
- bash review_state 提取结论块 → 只看结论段 → 返回 `pass` → review 检测设为 `qa_pending`

**时序冲突**:
1. 第一轮 watcher cycle: gate 归一化设 `review_rejected` → review 检测设 `qa_pending`（覆盖）→ review_key 标记已处理
2. **后续 cycle**: gate 归一化仍返回 `review_rejected` → 设 gate 为 `review_rejected` → 但 review 检测已标记不再触发 → **gate 被永久覆写为 `review_rejected`**
3. verify 检测 → close-task.sh → gate=`review_rejected` → **被拒绝 → 无限重试**

### 问题 5（MEDIUM）: auto_close_task 失败导致无限重试循环

**位置**: L1966-1970

```bash
if ! auto_close_task "$task_dir" "$task_id" "$vsummary"; then
    notify_pm "..."
    continue    # 跳过 mark_notified
fi
```

当 auto_close 失败时：
- `continue` 跳过 `mark_notified "$verify_key"` (L1985) → 下轮重试
- 每轮都发 PM 通知 → **通知刷屏**
- 如果根因是持久性问题（如 gate 被归一化覆写），永不自愈

### 问题 6（LOW）: gate 归一化与 review 检测同 cycle 内互相覆写

**执行顺序**: gate 归一化 (L1788) → ... → review 检测 (L1914) → verify 检测 (L1957)

gate 归一化先跑，设一个 gate 值；review 检测后跑，可能设另一个值。最终值取决于谁后写。这不是严格的时序 bug，但增加了不确定性。

## 最可能的根因组合

**场景 A（review.md body 含 reject 上下文词）**:
1. review.md 结论 APPROVE 但 body 提及 `review_rejected`/`qa_failed`
2. 第一轮: gate 归一化 → `review_rejected`(python 全文扫描) → review 检测 → `qa_pending`(bash 结论块) → review_key 标记
3. 后续轮: gate 归一化 → `review_rejected` → review 检测已标记跳过 → **gate 被永久覆写**
4. verify 检测 → close-task.sh 拒绝 `review_rejected` → 无限重试

**场景 B（resolve_merge_gate_state 静默崩溃）**:
1. verify.json 或 review.md 存在 JSON/编码问题
2. gate 归一化静默跳过 → gate 停留在上一个状态
3. review 检测/verify 检测可能正确推进 gate，但如果两者都被 dedup 跳过，gate 永远不动

**场景 C（close-task.sh 拒绝 review_pending）**:
1. result.json → review_pending
2. Reviewer + QA 都在 watcher cycle 之前完成
3. 某些原因 gate 归一化未能将 review_pending → qa_pending（如场景 B）
4. verify 检测 → close-task.sh → review_pending 被无条件拒绝

## 修复建议

1. **resolve_merge_gate_state 增加 verify=pass 判定**: 当 review=pass 且 verify=pass 时，返回 `pm_acceptance_pending`（而非 `qa_pending`），允许自动收口
2. **统一 review 解析器**: 将 close-task.sh 的 `classify_review_text()` 复用到 resolve_merge_gate_state，消除全文扫描 vs 结论块提取的不一致
3. **close-task.sh 增加 review_pending 豁免**: 当 review_pending 且 review.md 已 APPROVE 时允许 close（类似 qa_pending + verify pass 豁免）
4. **gate 归一化错误处理**: `2>/dev/null || true` 改为至少 log warning，不要静默跳过
5. **auto_close 重试上限**: 加一个 retry count，超过 N 次后标记为 blocked 并通知 PM
