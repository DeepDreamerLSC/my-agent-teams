# 审查说明：补齐 QuestionRegion 可判定性与跳过策略

## 结论

**通过（approve）**。

这次实现已经完成任务要求的主线交付：`question_region_detector.py` 新增了页级和文档级的可判定性/跳过增强信号，并把“题号不够 distinct”“只有 anchor、无正文 region”收进不可判定门槛。复跑测试和真实样例后，`语文五年级` 会被稳定判成不可判定并跳过增强，其他 4 个样例仍能通过文档级可判定门槛。

## 复核要点

- 与 instruction.md 对齐：
  - 只修改了 `question_region_detector.py`
  - 不可判定页明确走跳过增强路径
  - 不再向下游暴露可 merge 的无效 question regions
- 与现有消费方兼容：
  - `candidate_filter` 和 `hybrid_pipeline` 仍按 `resolvable + regions` 工作
  - 这次新增字段不会破坏现有调用方
- 与真实样例结果一致：
  - 数学八年级 `7/8`
  - 数学试卷 `12/12`
  - 英语八年级 `10/12`
  - 五下科学 `6/6`
  - 语文五年级 `0/13`，整本 `document_skip_enhancement=true`

## 非阻塞提示

当前测试已经覆盖真实样例主路径和 candidate_filter 联动，但还没有把这次新增的 `determinable / skip_enhancement` 字段，以及 `question_anchor_not_distinct_enough`、`question_region_indeterminate` 两条新失败路径单独固化成回归断言。建议后续补 1-2 条精确单测，把这次新语义锁住。

## 建议动作

建议 PM 继续推进后续 hybrid MVP 相关任务；当前审查没有发现需要退回返工的阻塞问题。

审查时间：2026-05-16T14:59:06+08:00
