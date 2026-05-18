# 任务：设计 PDF 转 Word 后续技术路线

## 任务类型
架构设计 / 技术规划

## 目标
基于 7 个 profile 横评完整数据，设计 PDF 转 Word 下一阶段技术路线，输出分阶段实施计划。

## 任务边界
- 输出技术路线文档到 `artifacts/pdf2word/final-archive/reports/后续技术路线.md`
- 不修改任何现有代码
- 方案需要 PM 飞书推送林总工确认后才会拆子任务

## 输入事实
1. **横评最终报告**：`artifacts/pdf2word/final-archive/reports/横评最终报告.md`（7 个 profile 完整对比）
2. **当前架构**：
   - 默认路径：apple_baseline → PageIR → ExerciseIR → DOCX
   - hybrid_experimental 管线骨架已实现并通过 e2e 验证
   - 子模块：question_region_detector、candidate_extractor、candidate_filter、page_ir_merger、hybrid_validator
   - VLMReviewAdapter 已实现，支持 OpenAI-compatible vision backend
3. **关键结论**：
   - apple_baseline 5/5 完成，6.92s/页，题号召回 100%，图片/公式/表格候选为 0
   - paddleocr_vl 最有潜力（题号召回 94.9%，图片 48、表格 10），但 243s/页
   - mineru_lite/full 0/5 优于基线，但公式候选有 18 个
   - qwen3_vl_8b 可做 VLM review worker，JSON 有效率待提升
   - glm_46v_flash VLM review JSON 解析 5/5 失败，当前不可用

## 约束
- 不要设计"一个大 VLM 直接 PDF 转 Word"的方案（横评已证明不可行）
- 保持 PageIR / ExerciseIR / DOCX 分层架构
- 所有增强必须可回退到 baseline
- 默认同步路径不能变慢
- 考虑 M5 Max 128G 本地算力限制
- write_scope: 空（只读分析 + 新建文档）

## 交付物
`artifacts/pdf2word/final-archive/reports/后续技术路线.md`，包含：
1. 分阶段实施计划（不超过 3 个 Phase），含目标、模块、依赖、门禁
2. 每 Phase 可量化的验收指标
3. 模型投入优先级（继续/放弃/引入新模型）
4. hybrid_experimental 管线演进路径
5. 建议拆解的子任务列表

## 验收标准
1. 每个 Phase 有明确目标和可量化验收指标
2. 模型取舍有数据支撑
3. 方案可执行（能直接拆成 dev 任务）

## 下游动作
方案完成后 PM 通过飞书推送摘要给林总工确认，确认后拆子任务派发。
