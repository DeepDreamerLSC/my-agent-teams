# 任务：打通ExerciseIR表格载荷

## 任务类型
开发实现

## 目标
把 `NormalizedTableIR` 接入 ExerciseIR / Exercise detector 链路，确保 `ContentBlock(kind="table")` 能携带 v2 table payload、题目/材料归属和 warning 语义，而不是继续退回普通文本或只挂图片。

## 任务边界
- 只允许修改 `exercise_ir.py`、`exercise_detector.py`、`test_pdf_exercise_detector.py`、`test_pdf_to_word_exercise_pipeline_integration.py`。
- 本任务不直接渲染 DOCX 表格，不改 gate，不新增慢模型。
- 不允许把 table block 降级成普通 text block 来规避问题。

## 输入事实
- 上游依赖：`定义表格结构化IR契约`、`实现表格结构归一化器`。
- 路线文档要求：table block 有 `assigned_question_id` 时挂题干；属于公共材料时挂 section materials；归属不明不能静默挂页尾。
- 当前目标是让后续 renderer 能从 payload 中直接读到 table IR。

## 约束
- 必须保留题目归属、区域归属、warning、fallback reason 等关键信息。
- payload 兼容策略要清楚：已有 v1 rows/html 不要无声破坏；新 v2 优先使用 `table_ir`。
- 不要改 DOCX assembler。

## 交付物
1. ExerciseIR / detector 中的 table payload 接线。
2. 至少一组 integration/test，证明 table payload 可从候选并回流到 ExerciseIR。
3. 对归属不明与结构缺失场景的 warning/blocked 行为测试。

## 验收标准
- `ContentBlock(kind="table")` 能承载 `table_ir` 或兼容 payload，不再只剩图片/占位。
- 有归属的表格能挂到对应题目或 materials；归属不明场景不会静默成功。
- 集成测试能覆盖一条 end-to-end payload 流转路径。
- 不越界改 DOCX renderer / final gate。

## 下游动作
完成后，PM 将接续可编辑 Word 表格渲染任务。
