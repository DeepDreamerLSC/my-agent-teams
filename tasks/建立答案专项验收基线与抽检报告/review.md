# 审查说明：建立答案专项验收基线与抽检报告

## 结论

**通过（approve）**。这份 QA 报告基本满足任务要求：它基于真实五样例、答案识别摘要和输出变体摘要，量化了 `answer_area / answer_section / matched / unmatched`，逐样例保留了命中与未命中事实，也明确说明当前只能作为 `teacher/review` 路线的阶段性验收基线，不能外推成“答案专项已全面收口”。

## 审查范围

- `tasks/建立答案专项验收基线与抽检报告/{instruction.md,result.json,verify.json,task.json}`
- `artifacts/pdf2word/p2-answer-teacher/qa/{summary.json,report.md}`
- `artifacts/pdf2word/p2-answer-teacher/detection/summary.json`
- `artifacts/pdf2word/p2-answer-teacher/variants/summary.json`
- 相关测试证据：
  - `backend/tests/test_pdf_exercise_detector.py`
  - `backend/tests/test_pdf_exercise_docx_assembler.py`
  - `backend/tests/test_pdf_to_word_exercise_pipeline_integration.py`
  - `backend/tests/test_pdf_to_word_service.py`

## 复核结果

- 五样例事实没有被夸大：
  - aggregate 明确写出 `answer_section_sample_count=2`、`answer_area_sample_count=1`、`matched_answer_item_count=2`、`warning_count=6`。
  - 逐样例保留了 `五下科学=partial_hit`、`英语八年级=miss`、`语文五年级=miss`、`数学八年级=hit`、`数学试卷=hit_with_warnings`。
  - `英语八年级`、`语文五年级` 的 miss 原因和 `数学试卷` 的 `visual_assignment_unresolved` warnings 都被保留下来，没有成功化表述。
- teacher/review 路线的阶段性基线表述是克制的：
  - `teacher` 只展示已有 `AnswerSection / AnswerItem`，不生成新答案。
  - `review` 在 teacher 基础上保留 unmatched/warning 事实，用于抽检和审校。
  - phase conclusion 明确写了 `can_continue_teacher_route=true`，但 `can_continue_formula_route=false`，并且不改变默认发布边界。
- student 默认链路未被宣称回归：
  - variants 摘要与 QA 报告都保持 `default_variant=student`。
  - report 中关于正文顺序、题号顺序、noisy OCR guard、analysis heading 边界的说法，能被相关测试断言支撑。

## 非阻塞提示

`qa/summary.json` 的 `ordering_checks.evidence` 对题号顺序证据做了文字转述，但没有直接写真实测试函数名。当前我已核到相应断言确实存在于 integration 测试中，所以不构成驳回；后续如果再迭代这类收口报告，建议直接引用测试函数名或更精确的断言位置。

## 下一步

建议交 PM 收口。

审查时间：2026-05-18T12:47:40+08:00
