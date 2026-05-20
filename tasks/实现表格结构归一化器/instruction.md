# 任务：实现表格结构归一化器

## 任务类型
开发实现

## 目标
基于已冻结的 `NormalizedTableIR` 契约，实现表格结构归一化器，把 `table_html`、`table_rows`、markdown 表格、cell boxes + OCR 文本等输入统一整理成结构化 TableIR，并对“只有图片/缺结构”的情况产出明确 warning / fail reason。

## 任务边界
- 只允许修改 `backend/app/services/pdf_to_word/parser_adapters/table_structure_normalizer.py` 与 `backend/tests/test_pdf_to_word_table_structure_normalizer.py`。
- 本任务不改 ExerciseIR 并回，不改 DOCX 渲染，不改默认同步调度。
- 不接入新模型；只处理已有候选原始结构的归一化。

## 输入事实
- 上游依赖：`定义表格结构化IR契约`。
- 路线文档已明确支持的输入优先级：`table_html` -> `table_rows` -> markdown -> `cell_boxes + OCR` -> image only fail。
- 当前真实缺口是 table candidate 常常只有 bbox/image，导致无法稳定渲染 `<w:tbl>`。

## 约束
- 归一化结果必须严格落到 `NormalizedTableIR`，不能自定义旁路结构。
- 对 image-only / grid inconsistent 场景必须输出清晰 warning/reason，不得伪造结构化通过。
- 不要触碰题号、答案区、图片归属其他链路。

## 交付物
1. `table_structure_normalizer.py` 实现。
2. 覆盖 html / rows / markdown / image-only 的自动化测试。
3. 测试中至少包含一个“结构缺失只能 fail/review”的负样例。

## 验收标准
- 正常输入可稳定生成 `NormalizedTableIR`。
- image-only 或结构冲突场景能稳定输出 fail/warning，而不是假成功。
- 测试覆盖至少 4 类输入源。
- 不越界修改 payload、renderer 与 gate。

## 下游动作
完成后，PM 将接续 ExerciseIR 表格载荷与 DOCX 表格渲染任务。
