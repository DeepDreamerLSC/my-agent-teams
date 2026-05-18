# 任务：排查 Hybrid 输出到 ExerciseIR 数据流转断裂

## 任务类型
排查 + 修复

## 目标
定位并修复 hybrid_pipeline 产出的 accepted image/table candidates 没有流转到 exercise_ir 和 docx_assembler 的根因。

## 任务边界
- 可修改 hybrid_pipeline.py、exercise_ir.py、exercise_detector.py
- 同时补齐 docx_assembler.py（如果需要在消费侧适配）
- 排查完成后直接修复，不需要另外拆任务

## 输入事实
- hybrid_pipeline.py 的 enhance 流程已跑通：数学试卷 21 个 accepted visual candidates、英语八年级 2 个
- 但生成的 DOCX 中 media_count=0、has_table_xml=false、has_drawing=false
- dev-2 已证明 docx_assembler.py 的渲染能力具备（合成 payload 可以渲染），但真实 hybrid 数据没有流转过来
- hybrid 审计产物在 artifacts/pdf2word/hybrid-phase1/ 下

## 约束
- write_scope: hybrid_pipeline.py、exercise_ir.py、exercise_detector.py
- 可同时修改 docx_assembler.py
- apple_baseline 路径的 DOCX 输出不能退化

## 交付物
1. 根因分析：哪个环节丢掉了 image/table candidates
2. 修复代码
3. 用数学试卷和英语八年级验证 DOCX 中 media_count>0

## 验收标准
1. 数学试卷 DOCX 中能看到插入的 image/table（media_count>0）
2. 英语八年级 DOCX 中能看到插入的 image/table
3. 纯 baseline 样例的 Word 输出不变

## 下游动作
修复完成后，`补齐ExerciseIR和DOCX的图片表格输出` 任务将取消（本任务已覆盖其 scope）。
