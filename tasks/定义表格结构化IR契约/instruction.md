# 任务：定义表格结构化IR契约

## 任务类型
架构契约冻结 / 代码协议落盘

## 目标
把 2026-05-18 路线文档里定义的 `NormalizedTableIR` 落成一份可被代码和测试直接消费的契约：字段、最小约束、span 语义、warning 语义、raw 输入回溯字段都要冻结，供后续 normalizer / ExerciseIR / DOCX renderer 共用。

## 任务边界
- 只允许修改 `backend/app/services/pdf_to_word/table_ir.py`、`backend/tests/test_pdf_to_word_table_ir_contract.py`、`backend/tests/fixtures/pdf_to_word/table_ir/`。
- 本任务只做契约/fixture/contract test，不实现 normalizer、payload 并回或 DOCX 表格渲染。
- 不修改默认同步调用链与任何慢模型触发逻辑。

## 输入事实
- 主要输入：
  - `/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-archive/reports/95还原度与Word表格验收路线.md`
  - `/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-archive/reports/端到端技术链路.md`
- 路线已明确：表格必须从 candidate -> normalized table IR -> ExerciseIR -> DOCX table renderer 闭环；仅图片 fallback 不算通过。
- 契约至少要覆盖：table_id、source_candidate_id、assigned_question_id / assigned_region_id、row_count / column_count、cells、row_span / column_span、text、runs/style、bbox、metrics、warnings、raw.image_path/html/markdown。

## 约束
- 契约要兼容后续 v2 payload，但不要直接改 ExerciseIR dataclass。
- `row_count/column_count` 与 cells 推导结果必须能被测试校验。
- 允许保留 raw 回溯字段，但 raw 字段不能充当通过条件。
- 任何字段设计都不能暗示“只有图片也算表格通过”。

## 交付物
1. `table_ir.py`：定义 NormalizedTableIR 及相关最小结构。
2. `backend/tests/fixtures/pdf_to_word/table_ir/` 下至少一份正样例与一份结构缺失样例 fixture。
3. `backend/tests/test_pdf_to_word_table_ir_contract.py`：验证字段完备性、span 规则、结构一致性与 warning 语义。

## 验收标准
- 契约可明确表达路线文档中的核心字段和失败语义。
- contract test 能区分“结构化表格可通过”和“只有图片/缺结构只能 fail/review”。
- 本任务不越界实现 normalizer / renderer / gate。
- 后续 dev/qa 任务可直接以该契约为输入继续开发。

## 下游动作
完成后，PM 将放行表格归一化器、ExerciseIR 表格载荷与 DOCX 表格渲染任务。
