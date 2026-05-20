# review-1 审查结论

- 任务：`设计预热任务独占预留机制`
- 结论：`request_changes`
- 审查时间：`2026-05-19T12:48:46+08:00`
- 收口判断：**不可收口，需返修设计文档后再审**

## 审查范围

1. `instruction.md`
2. `result.json`
3. `task.json`
4. 交付文档：
   - `design/collaboration/预热任务独占预留机制.md`
5. 兼容性对照：
   - `scripts/task-pool-view.py`
   - `scripts/task-watcher.sh`
   - `scripts/claim-task.sh`

## 结论摘要

这份设计文档的大方向是对的，覆盖面也比较完整：

- 明确选择了新增 `pre_reserved_*`，没有模糊停留在“复用还是新增”；
- 把 pending / pooled / dependency_wait / dispatched / working 的规则都展开了；
- 也给了 `reserve-task.sh`、watcher、router、view、claim 的实现入口和兼容约束；
- 事故复盘与防复发断言也写得比较清楚。

但我这里不能直接 approve，原因是文档里**容量语义存在关键冲突**，会直接影响下游实现是否能跑通。

## 阻塞问题

### 1. `pre-reserve` 与 `reserved slot` 的关系前后冲突，可能导致任务自锁

文档当前同时给出了三条规则：

1. 第 5.2 节写明：**预热锁计入 reserved slot**（第 223 行）；
2. 第 6.3 节写明：`reserved_count` 应包含 active `pre_reserved_by`（第 289-291 行）；
3. 第 6.4 节又写明：依赖解锁后，只有当目标 agent **“有 reserved slot”** 时才派发（第 303-306 行）。

这三条合在一起，与当前脚本的 capacity gate 会发生冲突。

当前实现里：

- `task-pool-view.py:192-198` 用 `reserved_count >= reserved_limit` 判定 agent 是否还能接 reserved；
- `task-watcher.sh:1450-1457`、`1634-1639` 也用同样逻辑判断是否还能 auto-continue / auto-reserve；
- `claim-task.sh:182-227` 一样会在 `reserved_count >= reserved_limit` 时拒绝。

也就是说，如果默认 `default_reserved_limit=1`：

- PM 先给 `dev-2` 写一个 `pre_reserved_*`；
- 按文档，`reserved_count` 立刻 +1；
- 等依赖解锁时，watcher 再检查“dev-2 是否还有 reserved slot”；
- 结论会变成：**没有**，因为这个 pre-reserve 自己已经把 slot 占满了；
- 于是任务会卡在 `pooled + pre_reserved`，永远无法继承到 `dispatched`。

这与文档目标“把预热变成可执行的排他契约”冲突，也不满足 instruction 里“文档能直接指导 dev-2 落地实现，无关键语义空白”的验收标准。

## 返修建议

请把容量语义收敛成**单一、无歧义**的一种，并在文档里显式写死。至少二选一：

### 方案 A：pre-reserve 占用 reserved slot，但 dispatch 继承复用同一 slot

即：

- `pre_reserved_*` 从写入那一刻开始就算一个 reserved slot；
- 但 `dependency_wait/pooled -> dispatched` 是**同一 slot 的状态转换**；
- watcher 在把预热任务派发给同一 agent 时，**不能再额外要求 spare reserved slot**。

如果采用这个方案，文档需要同步改掉“dev-2 有 reserved slot 时才能派发”的表述，改成“允许把当前 pre-reserve 转换为 dispatched reservation”。

### 方案 B：pre-reserve 单独计数，不纳入 reserved_limit

即：

- `pre_reserved_count` 单独统计；
- `reserved_count` 仍只统计 dispatched 未 ack；
- 只有真正 dispatch 时才占用 reserved slot。

如果采用这个方案，则要同步修改：

- 第 223 行“预热锁计入 reserved slot”；
- 第 289-291 行 `reserved_count` 统计口径；
- watcher / claim / view 的 capacity 兼容描述。

## 非阻塞备注

1. 任务目录下暂无 `verify.json`；本次审查主要依据文档静态复核与现有脚本兼容性比对。
2. 除上述容量冲突外，文档的字段契约、状态覆盖、事故断言和操作入口整体是完整的，修完该点后大概率可快速通过复审。

## 结论

当前结论为：`request_changes`

请先修正文档中 **pre-reserve 是否占用 reserved slot，以及 dispatch 继承时是否还要额外校验剩余 slot** 的口径冲突；修完后我可以再做一轮快速复审。
