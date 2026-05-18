# 审查说明：改造 Qwen3-VL 为严格 review worker

## 结论

**驳回并请求补修（request_changes）**。

上一轮缺失的两项证据这次已经补齐了：`result.json` 现在包含真实 5 样例在线验证和 old/new prompt 对比数据，strict `page_review` 路径在代码和本地 smoke test 里也能跑通。问题不再是“没有证据”，而是**证据已经明确表明当前结果没有达到任务写死的验收门槛**。

## 阻塞点

当前唯一阻塞点是：

- instruction 把 `5 样例验证：json_valid_rate ≥ 80%` 同时写进了交付物和验收标准。
- 但本轮真实线上实测结果是：
  - `new_prompt_json_valid_rate = 0.4`
  - `new_prompt_valid_json_count = 2/5`
  - `strict_page_review_rate = 0.4`
- old/new 对比也没有证明提升：
  - valid JSON 数仍然是 `2 -> 2`
  - warning 总数从 `2 -> 3`

这说明“strict review worker 方向是对的”，但“当前版本已经达到首轮验收目标”这个结论不成立。

## 我复核到的真实状态

- prompt 已经改成只输出 `page_review` 严格 JSON，不再要求正文 blocks。
- `vlm_review_json.py` 里也已经有 strict schema 和 `issues -> review_issue` 的解析路径。
- 本地 `pytest tests/test_pdf_to_word_vlm_review_adapter.py -q` 通过，结果是 `9 passed, 4 warnings`。
- 本地 smoke test 也确认了 strict `page_review.issues` 可以被转成 `kind=note`、`meta.review_issue` 完整的 block。
- 但真实 5 样例在线验证只有 `40%`，离任务要求的 `80%` 还差一倍。

## 非阻塞建议

1. 后续补修时优先处理导致 JSON 截断的问题。从这轮样例看，`detail` 字段容易写得过长，导致返回被截断，直接拖低 `json_valid_rate`。
2. 当前 pytest 仍主要覆盖 legacy `blocks/review_suggestions` 兼容路径。建议补 2-3 条 strict 主路径专项测试，例如：
   - 合法 `page_review.issues` 输入
   - 非法 `issue_type` / `suggested_action`
   - 非法 `confidence_summary.layout_quality`

## 建议动作

建议 PM 将该任务继续留在补修链路，不要按当前验收标准直接放行。除非 PM 明确接受“方向验证通过但 80% 门槛未达成”的阶段性结果，并同步调整验收口径，否则这轮仍应继续改 prompt 或增加后处理/重试策略后再审。

审查时间：2026-05-15T18:19:10+08:00
