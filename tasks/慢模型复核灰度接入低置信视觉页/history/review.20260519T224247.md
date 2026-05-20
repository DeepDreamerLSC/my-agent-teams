# 审查结论：request_changes

本轮**不建议放行**。

## 阻塞问题
- `visual_similarity_slow_review.py` 的 `_collect_low_confidence_reasons()` 把 near-threshold 条件写成了：
  - `page_render_similarity < page_threshold + review_band`
  - `region_similarity < region_threshold + review_band`
- 这里**缺少 `>= threshold` 下界**，导致明显低于阈值的 hard-fail 页/区域，也会被误记为 `near_threshold_*`，并进入 slow review / fallback 路径。
- 这与 instruction 的核心约束 **“仅允许 low-confidence pages 触发 qwen3_vl_8b”** 不一致；当前实现实际上会让 hard-fail 页面也消耗灰度预算。

## 复现证据
我本地复现了一个最小例子：
- page threshold = `0.92`，实际 `page_render_similarity = 0.50`
- region threshold = `0.90`，实际 `region_similarity = 0.40`
- `gate_enabled=True`、`artifact_ready_for_scoring=True`

当前返回结果仍然是：
- `triggered=True`
- `decision_reason=slow_review_worker_not_configured`
- `trigger_reasons` 包含：
  - `near_threshold_page_render_similarity`
  - `near_threshold_key_region_similarity:math:p1:table-01`

这说明 hard-fail 页面已经被误送进 slow review 选择逻辑。

## 返修口径（最小）
1. 把页级与区域级 near-threshold 判定都收紧为：`[threshold, threshold + review_band)`。
2. 或直接复用上游 `page_scores` / `key_regions` 已产出的 near-threshold `review_reasons`，不要在 slow-review helper 里重新放宽判定。
3. 补回归测试：
   - 明显低于页阈值的 page 不得 `triggered=true`
   - 明显低于区域阈值的 region 不得单独把页面送入 slow review
   - gate 侧补一条 hard-fail 页面不会出现 `slow_review_triggered:*` 的回归

## 其他说明
- 我复跑了现有测试：`13 passed, 4 warnings`。
- 任务目录当前没有 `verify.json`，本轮主要依据代码静态审阅 + 本地复现给出结论。
