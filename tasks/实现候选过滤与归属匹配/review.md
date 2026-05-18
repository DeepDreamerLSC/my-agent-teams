# 审查说明：实现候选过滤与归属匹配

## 结论

**通过（approve）**。

这轮实现符合任务边界，只新增了 `candidate_filter.py` 和 `test_candidate_filter.py`，没有改已有组件。实现也不是自造一套接口，而是直接接在现有 `QuestionRegionDetector` 和 `CandidateExtractor` 的真实 dataclass 上，完成了候选过滤、question-bound assignment，以及 `candidates.filtered.jsonl` / `merge-decisions.jsonl` 的输出。

我复跑 `pytest tests/test_candidate_filter.py -q`，结果为 `5 passed, 4 warnings`。另外我抽查了真实 artifacts，得到的统计与 `result.json` 一致：`数学试卷` 的 MinerU 候选有 10 个 accepted；`语文五年级` 的 PaddleOCR-VL 候选 20 个全部因为 `question_region_not_detectable` 被 skipped；`英语 八年级下册` 里的 formula candidate 也按要求被 reject。

## 复核要点

- 规则覆盖对齐设计文档：
  - bbox 非法 / 越界 reject
  - 面积过小 / 过大 reject
  - 高文本重叠 reject
  - 非 `image` / `table` reject
  - `formula_candidate` 默认 `audit_only -> reject`
  - question-region 不可判定页统一 `skipped`
- assignment 规则对齐设计：
  - `0.45 * center_inside_region`
  - `0.25 * bbox_iou_with_region`
  - `0.20 * vertical_distance_score`
  - `0.10 * source_confidence`
  - `>= 0.70 -> assigned`
  - `0.50-0.70 -> ambiguous`
  - `< 0.50 -> unassigned`
- Paddle 特殊策略也落了：
  - `min_area_ratio = 0.003`
  - `max_text_overlap_ratio = 0.20`
  - duplicate 时优先 MinerU

## 非阻塞提示

当前重复候选在已经完成几何归属后，如果又被 duplicate 规则降级为 `rejected`，实现会保留 `assignment_status='assigned'` 和 `assigned_question_id`。这不影响最终 `merge_eligible_count`，但会让 `assignment_counts` 更像“几何归属统计”，不完全等于“最终可合并统计”。如果后续要把这组指标直接拿去做报表，建议先统一口径。

## 建议动作

建议 PM 直接推进下一步 `PageIR merger + validator` 任务。这轮没有发现需要返工的阻塞问题。

审查时间：2026-05-15T19:32:54+08:00
