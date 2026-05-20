# review-1 审查结论

- 任务：`打通ExerciseIR表格载荷`
- 结论：`approve`
- 审查时间：`2026-05-19T09:35:00+08:00`

## 审查范围

1. `instruction.md`
2. `result.json`
3. 实现文件：
   - `backend/app/services/pdf_to_word/exercise_ir.py`
   - `backend/app/services/pdf_to_word/exercise_detector.py`
4. 测试文件：
   - `backend/tests/test_pdf_exercise_detector.py`
   - `backend/tests/test_pdf_to_word_exercise_pipeline_integration.py`

## 审查结论

本次实现符合任务目标与边界：

- `ContentBlock(kind="table")` 已能承载 v2 table payload；
- payload 保留了 `table_ir`、`table_rows/table_html` 兼容策略、题目/区域归属、assignment 状态、reason、warnings 等关键信息；
- detector 已覆盖：
  - 有归属的表格挂到对应题目
  - 明确 material 路由的表格进入 `section.materials`
  - answer-area-like 表格可回退为 answer area
  - 无题目时不会静默成功，而会给出 unresolved warning
- integration test 已覆盖一条 end-to-end payload 流转路径；
- 未越界改 DOCX renderer / final gate。

## 补充验证

我额外在当前 backend 契约上叠加 worktree 修改复跑了：

```bash
PYTHONPATH=<temp-staged-backend> /Users/linsuchang/Desktop/work/chiralium/backend/.venv/bin/python -m pytest <temp-staged-backend>/tests/test_pdf_exercise_detector.py <temp-staged-backend>/tests/test_pdf_to_word_exercise_pipeline_integration.py -q -o cache_dir=/private/tmp/chiralium-pytest-cache-exerciseir-table-review --basetemp=/private/tmp/chiralium-pytest-temp-exerciseir-table-review
```

结果：`22 passed, 4 warnings`

warnings 为既有 FastAPI `on_event` deprecation warnings，不构成阻塞。

## 非阻塞备注

1. 任务目录下暂无 `verify.json`，建议后续 QA 门禁补写以便流程留痕。
2. 当前联调主要使用 `meta.table_ir` / 兼容 payload 模拟 normalizer 输出；进入 integration 后建议再补一次与真实 `table_structure_normalizer.py` 产物的联调回归。

## 下一步建议

- 建议进入 `qa`，再由下游 `可编辑 Word 表格渲染` 任务继续消费。
