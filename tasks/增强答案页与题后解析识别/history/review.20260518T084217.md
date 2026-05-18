**结论**
`request_changes`

上一轮指出的 `assigned visual block` 误吞问题已经修掉了。现在视觉块会先按 `assigned_region_id / assigned_question_id` 回挂题目，新增的回归测试也覆盖到了“inline answer cue 后开始新题，新题带 assigned visual”的场景，这部分是成立的。

**新的阻塞点**
当前又把 `document_fallback` 负样例 [`语文五年级`](</Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-archive/profiles/hybrid_experimental/语文五年级/validator-report.json:1>) 从基线 `miss` 推成了 `hit`。但 authoritative archive 对这个样例的口径仍然是：
- `document_fallback=true`
- `accepted_candidate_total=0`
- `answer_section_not_materialized`

对应证据见 [hybrid_experimental_authoritative_archive_report.json](/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-archive/reports/hybrid_experimental_authoritative_archive_report.json:102) 和 [p1-answer-sections/summary.json](/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/p1-answer-sections/summary.json:186)。

我直接回放了当前 authoritative pages 到 `detect_exercise_document()`，实际结果是：
- `answer_section_count = 1`
- `source_type = analysis_heading`
- `number = 3`
- 后续第 4 页开始的大量普通正文块也被继续挂进这个答案项

这说明 [`exercise_detector.py`](/Users/linsuchang/Desktop/work/chiralium/backend/app/services/pdf_to_word/exercise_detector.py:165) 的 `analysis_heading` 路径在 fallback 样例里仍然过宽，会把缺乏稳定题号上下文的“解题思路”强行物化成答案段，并把后续正文整页吸进去。这个行为仍然违反任务边界里“document_fallback 场景继续保守，不能给语文五年级这类样例伪造答案结构”。

**对专项产物的影响**
[`summary.json`](/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/p2-answer-teacher/detection/summary.json:49) 当前把 `语文五年级` 记成 `hit`，并写了 `analysis_heading: p3 -> 3`。这条统计在现口径下不可信，修掉 fallback 守卫后必须重新 replay 五样例，再决定它是继续 `miss` 还是单列 failure bucket。

**验证证据**
- `tests/test_pdf_exercise_detector.py`：`7 passed, 4 warnings`
- `tests/test_pdf_to_word_exercise_pipeline_integration.py` + `tests/test_pdf_exercise_docx_assembler.py`：`8 passed, 4 warnings`
- 最小复现确认上一轮的 assigned visual route 问题已修复
- 直接回放 `语文五年级` authoritative pages 仍能复现新的 fallback 误命中问题
