# 审查说明：实现Hybrid题号顺序与阅读顺序校验器

## 结论

**审查通过（approve）。**

## 通过依据

- `order_resolver.py` 已移除过去的 silent renumber 行为，`resolve_block_order()` 现在只做阅读顺序排序；顺序回退改由 `analyze_question_number_sequence()` 产出诊断。
- `QuestionRegionDetector` 已把顺序问题收口成可审计的页级字段：`order_verdict`、`order_reasons`、`question_sequence_numbers`、`question_sequence_issue_count`、`question_anchor_conflict_count`。顺序异常页会直接返回 `wrong_order` 并 `skip_enhancement=true`。
- `HybridValidator` 已把 `wrong_order`、`question_sequence_regression`、`question_anchor_conflict`、`reading_order_invalid` 纳入 fallback gate；调用方未透传 `question_region_results` 时也会在 validator 内部兜底重算，确保当前生产路径可生效。
- 我复跑了任务要求的命令：
  `PYTHONDONTWRITEBYTECODE=1 /Users/linsuchang/Desktop/work/chiralium/backend/.venv/bin/pytest /Users/linsuchang/Desktop/work/chiralium/backend/tests/test_question_region_detector.py /Users/linsuchang/Desktop/work/chiralium/backend/tests/test_hybrid_validator.py /Users/linsuchang/Desktop/work/chiralium/backend/tests/test_pdf_to_word_exercise_pipeline_integration.py -o cache_dir=/private/tmp/chiralium-pytest-hybrid-order-review --basetemp=/private/tmp/chiralium-pytest-hybrid-order-review-tmp`
  结果为 `15 passed, 4 warnings`。warnings 为既有 FastAPI `on_event` 弃用告警，不是本任务新增问题。
- 我额外抽检了真实 baseline 样例：
  - `数学试卷`：`12/12` 页 resolvable，`order_verdict` 全为 `ok`
  - `英语 八年级下册`：`8` 页 `ok`，`2` 页 `wrong_order` / `question_sequence_regression`，`2` 页 `question_region_not_detectable`
  - `语文五年级`：`13/13` 页保持 `question_region_not_detectable`，`order_verdict=not_applicable`

## 非阻塞观察

- 当前 validator 会在未显式传入 `question_region_results` 时自行调用 detector。这是合理兜底，但后续若允许改 `hybrid_pipeline.py`，建议改成显式透传，减少重复计算和隐式耦合。

## 总结

本轮实现满足任务目标与验收标准，没有发现阻塞性问题，可以进入 `qa-1` 回归验证。
