# 审查说明：实现学生版教师版审校版输出变体

## 结论

**审查通过（approve）。**

## 通过依据

1. 三种输出变体已经接通且职责清晰。

   当前入口是：

   ```python
   PDFConversionService.convert(..., output_variant="student" | "teacher" | "review")
   ```

   `exercise_ir.py` 负责统一规范化，未知值会安全回落到 `student`。

2. `student` 默认输出没有被改坏。

   student 仍然只输出题干、选项、作答区、公式等正文主链路，不额外暴露答案解析或 warning。
   这符合“默认稳定、不回归”的任务要求。

3. `teacher / review` 只消费已有事实，没有编造答案。

   `teacher` 只在已有 `AnswerSection` 存在时追加答案解析段。
   `review` 在 teacher 基础上再追加 `Warnings` 审校提示。
   它们都只使用现有 `AnswerSection / warnings`，没有引入 LLM 生成的新答案文本。

4. 测试覆盖是够的。

   测试已经覆盖：
   - assembler 层：student 不显示答案、teacher 显示答案、review 显示 warnings
   - service 层：`meta.output_variant`、teacher/review 的 Word 呈现
   - exercise pipeline 集成层：默认 student 不回归，teacher 变体可透传到结构化主链路

5. 本地复跑通过。

   我执行了：

   ```bash
   PYTHONDONTWRITEBYTECODE=1 /Users/linsuchang/Desktop/work/chiralium/backend/.venv/bin/pytest /Users/linsuchang/Desktop/work/chiralium/backend/tests/test_pdf_exercise_docx_assembler.py /Users/linsuchang/Desktop/work/chiralium/backend/tests/test_pdf_to_word_service.py /Users/linsuchang/Desktop/work/chiralium/backend/tests/test_pdf_to_word_exercise_pipeline_integration.py -o cache_dir=/private/tmp/chiralium-pytest-answer-variants --basetemp=/private/tmp/chiralium-pytest-answer-variants-tmp
   ```

   结果 `20 passed`，只有 4 条既有 FastAPI deprecation warnings。

## 非阻塞说明

`result.json` 本身写得过于简略，没有把 instruction 要求的“变体入口、teacher/review 呈现规则、student 不回归验证结果”直接结构化写回。实际证据已经体现在代码、测试和 `artifacts/pdf2word/p2-answer-teacher/variants/summary.json` 中，因此不阻塞本轮通过。
