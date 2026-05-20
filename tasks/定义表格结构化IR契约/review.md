# review-1 审查结论

- 任务：`定义表格结构化IR契约`
- 结论：`approve`
- 审查时间：`2026-05-19T09:00:00+08:00`

## 审查范围

1. `instruction.md`
2. `result.json`
3. `task.json`
4. 代码与测试：
   - `backend/app/services/pdf_to_word/table_ir.py`
   - `backend/tests/test_pdf_to_word_table_ir_contract.py`
   - `backend/tests/fixtures/pdf_to_word/table_ir/structured_table.json`
   - `backend/tests/fixtures/pdf_to_word/table_ir/image_only_missing_structure.json`

## 审查结论

- `NormalizedTableIR v1` 已冻结核心字段、span 语义、warning 语义与 raw 回溯字段；
- 结构化正样例可通过，image-only 缺结构样例会落入 review，不会被当作表格成功；
- 越界 / 重叠 / 缺字段等失败语义也有覆盖；
- `pytest` 与 `diff --check` 均通过。

## 备注

- 任务目录下暂无 `verify.json`，本次已用本地复跑测试作为补充验证证据。
