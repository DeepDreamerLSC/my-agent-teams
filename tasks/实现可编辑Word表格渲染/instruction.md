# 任务：实现可编辑Word表格渲染

## 任务类型
开发实现

## 目标
消费 ExerciseIR 中的表格 payload，输出真实可编辑的 Word 表格 XML（`<w:tbl>` / `<w:tr>` / `<w:tc>`），满足路线文档定义的表格硬门禁，不再把图片 fallback 当作成功形态。

## 任务边界
- 只允许修改 `docx_assembler.py`、`exercise_docx_assembler.py`、`test_pdf_exercise_docx_assembler.py`。
- 本任务只实现 renderer，不改 normalizer、payload 归属、final gate。
- 不引入慢模型，不改变默认同步调度策略。

## 输入事实
- 上游依赖：`打通ExerciseIR表格载荷`。
- 路线文档已明确 renderer 输入优先级：`table_ir.cells` -> `table_rows` -> `table_html` -> `image_path` fallback；只有 fallback 不算通过。
- Phase 1 最低要求包括：基础边框、合并单元格、单元格文本、行列结构；像素级样式还原放到后续质量阶段。

## 约束
- 对结构化表格必须输出真实 `<w:tbl>`，不能只生成图片或提示文本。
- `image_path` fallback 只能作为降级输出，并且要让 gate 可识别。
- 不要趁机改无关文本/题号渲染逻辑。

## 交付物
1. 支持结构化 table payload 的 DOCX renderer 实现。
2. 覆盖正常表格、合并单元格、fallback 场景的自动化测试。
3. 明确证明 renderer 生成了 `<w:tbl>` 的测试断言。

## 验收标准
- 结构化表格能输出真实 `<w:tbl>`，并包含基本行列/单元格内容。
- fallback 场景不会被误判为通过。
- 自动化测试可直接检查 Word XML 关键节点。
- 不越界修改 normalizer / gate / 题号逻辑。

## 下游动作
完成后，PM 将接续表格样例夹具、DOCX gate 和最终 fidelity report 验收。
