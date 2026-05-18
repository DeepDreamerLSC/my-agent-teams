# 审查说明：补齐Hybrid回归样例与人工抽检流程

## 结论

**驳回并请求补修（request_changes）。**

## 为什么驳回

这轮正式版已经比预整理版好很多，关键改进我都确认到了：

- 过期事实基本修掉了，不再写“全部 fallback”或“review_mode=skipped_no_review_worker”
- 当前 `online_review` 指标已经补入
- 有正样例 / 负样例 / 重点抽检页
- 有 7 步检查流程
- 有执行命令、JSON 模板和 checklist

问题在于，它还**没有完全满足任务验收标准里点名的指标集合**。

任务要求必须明确列出这些指标：

- `candidate_count`
- `accepted/rejected`
- `fallback`
- `media_count`
- `has_drawing / has_table_xml`
- `review_mode / json_valid_rate`

当前正式文档虽然已经覆盖了：

- `candidate_count`
- `fallback`
- `review_mode`
- `json_valid_rate`
- `review_acceptance_rate`

但仍然漏了：

- `media_count`
- `has_drawing`
- `has_table_xml`

此外还有一个字段名错误：

- Step 7 里写成了 `reviewed_rejected_count`
- 真实 `report.json` / `online_review_probe.metrics` 使用的是 `review_rejected_count`

这两点会直接影响它作为“固定 QA 基线”的可执行性，所以这轮还不能过。

## 建议怎么修

只需要小范围补齐，不需要重做结构：

1. 在“必检指标一览”里补上 `media_count`、`has_drawing`、`has_table_xml`。
2. 在检查步骤或人工抽检步骤里明确这些指标怎么取值、从哪里取、怎么判定。
3. 把 `reviewed_rejected_count` 改成真实字段名 `review_rejected_count`。

## 已确认正确的部分

- 当前真实状态已对齐到文档：
  - `review_mode=online_review`
  - `json_valid_rate=1.0`
  - `review_acceptance_rate=1.0`
  - `service_available=true`
  - `fallback_triggered_sample_count=3`
- 预整理版里被指出的旧事实残留已基本清掉

## 总结

正式基线已经接近完成，阻塞点只剩“验收指标缺项”和“一处 review 指标字段名错误”。补齐这两点后，就可以作为 Phase 2/3 通用 QA 基线通过。
