# 审查说明：建立Hybrid更大样本收益分布回归与抽检清单

## 结论

**通过（approve）**。这份收益分布回归报告的核心优点不是“数字很多”，而是边界讲得很清楚：它明确说明当前仍只有 5 个真实归档样例，当前产物只是把现有五样例按页型、来源组合和触发原因展开成更可操作的分布视图，不是新增大样本文档集的覆盖证明。

## 复核结果

- 结论诚实：
  - `covered_real_samples=5`
  - `is_strict_large_corpus=false`
  - `scope_note` / `scope_statement` / `Boundary` 段都反复强调当前不是“大样本已充分覆盖”
- 收益分布不是空泛重复总数：
  - 明确指出 `math_exam_image_dense / 数学试卷` 是当前最高收益带
  - `math_exercise_with_sparse_image_and_table` 属于“final accepted 为正，但 candidate gain 为负”的特殊观察
  - `language_exercise_sparse_media_with_fallback_pages` 被诚实归为 trigger 命中但当前无 Paddle 最终收益的优先补样空白
  - `negative_non_exercise_or_question_region_unresolvable` 继续只承担 baseline-only 边界保护
- 抽检/补样清单可直接复用：
  - `sampling_checklist.json` 已按 `P0 / P1 / P2` 排出优先级
  - 每项都写了 why now、目标样本数和验收关注点，足够直接转成下一轮执行任务

## 交叉核对

我把这份 summary 的关键字段直接和上游 artifacts 对了一遍：

- `accepted_candidate_total=35` 对回 `current-five-sample-baseline/regression_summary.json`
- `paddle_final_accepted_total=50`、`selected_pages_total=21`、`selected_scope_pages_total=32`、`selected_ratio=0.6562` 对回 `phase3-paddle-quality/report.json`
- 样例 ranking 中的 `candidate_gain_vs_mineru`、`paddle_final_accepted_count`、`selected_ratio` 也都能逐样例对回 phase3 报告

没有发现把现有事实放大包装的情况。

## 非阻塞提示

当前 manifest 仍缺 `source_pdf` / 采样来源，这一点报告本身已经诚实披露了，所以不构成驳回；但后续如果真的进入扩样执行，最好把来源、教材版本和人工抽检结论一起补进去，否则它更像导航清单，而不是完整 provenance 报告。

## 下一步

建议交 PM 作为下一轮补样/抽检任务底稿继续拆分。

审查时间：2026-05-18T14:21:07+08:00
