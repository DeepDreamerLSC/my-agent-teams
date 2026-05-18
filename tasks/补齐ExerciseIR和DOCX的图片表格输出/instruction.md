# 任务：补齐 ExerciseIR 和 DOCX 的图片表格输出

## 任务类型
开发

## 目标
确保 hybrid pipeline 产出的 accepted image/table candidates 能正确进入 ExerciseIR 和最终 Word 文档，实现从候选到可见输出的闭环。

## 任务边界
- 修改 `exercise_ir.py`：处理 hybrid PageIR 中的 image/table block
- 修改 `docx_assembler.py`：将 image/table block 渲染到 Word 文档
- 不修改 hybrid_pipeline.py

## 输入事实
- 当前 ExerciseIR 和 DOCX assembler 只处理 baseline 文本 block
- hybrid pipeline 的 accepted candidates 包含：image（带 bbox 和 source path）、table（带行列结构）
- 图片插入需要：从候选的 source 路径读取图片，按 bbox 位置插入到对应题号区域
- 表格插入需要：将候选的表格结构转为 Word table

## 约束
- write_scope: `exercise_ir.py`、`docx_assembler.py`
- 前置依赖：`实现HybridMVP图片表格并回链路` 完成
- 图片插入位置必须与题号归属一致，不能插入到错误题目下
- 表格必须可编辑（不能是截图）

## 交付物
- 更新后的 exercise_ir.py 和 docx_assembler.py
- 用 5 个横评样例生成 Word 文档，验证图片和表格可见且位置正确

## 验收标准
1. accepted image 候选在 Word 中可见，插入位置在对应题号区域内
2. accepted table 候选在 Word 中可编辑
3. 纯 baseline 样例（无增强）的 Word 输出不变
4. `数学试卷`、`英语八年级` 的 Word 中能看到插入的图片/表格

## 下游动作
完成后 Phase 1 最小闭环落地，进入验收和指标统计阶段。
