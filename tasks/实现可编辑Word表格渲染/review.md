# review-1 审查结论

- 任务：`实现可编辑Word表格渲染`
- 结论：`approve`
- 审查时间：`2026-05-19T12:36:33+08:00`
- 收口判断：**审查侧可收口；建议继续按下游样例夹具 / gate / final fidelity report 做集成回归**

## 审查范围

1. `instruction.md`
2. `result.json`
3. `task.json`（确认 `write_scope` / workspace 信息）
4. 实现文件：
   - `backend/app/services/pdf_to_word/docx_assembler.py`
   - `backend/app/services/pdf_to_word/exercise_docx_assembler.py`
5. 测试与夹具：
   - `backend/tests/test_pdf_exercise_docx_assembler.py`
   - `backend/tests/fixtures/pdf_to_word/table_ir/structured_table.json`
   - `backend/tests/fixtures/pdf_to_word/table_ir/image_only_missing_structure.json`

## 重点结论

- `exercise_docx_assembler.py` 仍通过 `word_paragraph_xml()` 消费 table block，因此本次能力升级集中在 `docx_assembler.py` 即可生效，未越界碰题号、答案区或其它无关渲染逻辑。
- `add_table_xml()` 已按任务要求执行渲染优先级：
  1. `table_ir.cells`
  2. `table_rows`
  3. `table_html`
  4. `image_path` fallback
- 对 `NormalizedTableIR` 路径：
  - 先做 `validate_normalized_table_ir()` 校验；
  - 仅在存在 structured cells 且 `row_count/column_count` 合法时输出真实 `<w:tbl>`；
  - 合并单元格会生成 `w:gridSpan` / `w:vMerge`，满足本任务对基础结构与 merge 的要求。
- 对 HTML fallback 路径：
  - 新 parser 能识别 `rowspan` / `colspan`；
  - 测试已验证会输出真实 `<w:tbl>`，而不是纯文本占位。
- 对降级路径：
  - 结构缺失时不会误产出 `<w:tbl>`；
  - 当前测试已稳定断言 fallback 场景只有降级输出，没有 table XML 假阳性。

## 补充验证

我额外复跑了以下检查：

```bash
PYTHONPYCACHEPREFIX=/private/tmp/pycache-word-table-review python3 -m py_compile   /Users/linsuchang/Desktop/work/my-agent-teams/.runtime/worktrees/chiralium/Word-c8800428/backend/app/services/pdf_to_word/docx_assembler.py   /Users/linsuchang/Desktop/work/my-agent-teams/.runtime/worktrees/chiralium/Word-c8800428/backend/app/services/pdf_to_word/exercise_docx_assembler.py   /Users/linsuchang/Desktop/work/my-agent-teams/.runtime/worktrees/chiralium/Word-c8800428/backend/tests/test_pdf_exercise_docx_assembler.py

git -C /Users/linsuchang/Desktop/work/my-agent-teams/.runtime/worktrees/chiralium/Word-c8800428 diff --check --   backend/app/services/pdf_to_word/docx_assembler.py   backend/app/services/pdf_to_word/exercise_docx_assembler.py   backend/tests/test_pdf_exercise_docx_assembler.py

PYTHONPATH=/Users/linsuchang/Desktop/work/my-agent-teams/.runtime/worktrees/chiralium/Word-c8800428/backend PYTHONPYCACHEPREFIX=/private/tmp/pycache-word-table-review /Users/linsuchang/Desktop/work/chiralium/backend/.venv/bin/python -m pytest   /Users/linsuchang/Desktop/work/my-agent-teams/.runtime/worktrees/chiralium/Word-c8800428/backend/tests/test_pdf_exercise_docx_assembler.py   -q -o cache_dir=/private/tmp/chiralium-pytest-cache-word-table-review   --basetemp=/private/tmp/chiralium-pytest-temp-word-table-review
```

结果：`7 passed, 4 warnings`

warnings 为既有 FastAPI `on_event` deprecation warnings，不构成阻塞。

## 非阻塞备注

1. 当前任务目录下暂无 `verify.json`；建议后续 QA / watcher 门禁补写，以便流程留痕。
2. 当前回归主要基于结构化 fixture、兼容 payload 与 fallback 文本断言；进入 integration 后，建议再补一次真实 ExerciseIR→DOCX 端到端样例，并带上图片 fallback 资产路径验证。

## 结论

本任务以 reviewer 视角可 `approve`，当前没有需要返修的阻塞项；可流转到 `qa` / PM 后续流程。
