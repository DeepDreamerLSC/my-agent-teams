# 任务：设计 PDF 转 Word 端到端技术链路

## 任务类型
架构设计

## 目标
基于后续技术路线方案，设计从 PDF 输入到 Word 输出的完整端到端技术链路，覆盖各 Phase 的数据流、模块交互、接口契约。

## 任务边界
- 输出设计文档到 `artifacts/pdf2word/final-archive/reports/端到端技术链路.md`
- 不修改代码
- 基于已有的后续技术路线方案和横评报告

## 输入事实
- 后续技术路线：`artifacts/pdf2word/final-archive/reports/后续技术路线.md`（3 Phase 计划）
- 横评最终报告：`artifacts/pdf2word/final-archive/reports/横评最终报告.md`
- 当前架构：apple_baseline → PageIR → ExerciseIR → DOCX
- hybrid_experimental 骨架：question_region_detector → candidate_extractor → candidate_filter → page_ir_merger → hybrid_validator
- 林总工确认的 4 个决策点：hybrid 显式开启、首批 MinerU full、formula 默认关闭、新模型延后

## 约束
- write_scope: `artifacts/pdf2word/final-archive/reports/端到端技术链路.md`
- 保持 PageIR / ExerciseIR / DOCX 分层架构
- 需要覆盖 Phase 1/2/3 的完整数据流

## 交付物
`artifacts/pdf2word/final-archive/reports/端到端技术链路.md`，包含：
1. **Phase 1 端到端数据流图**：PDF → apple_baseline PageIR → question_region → mineru_full 候选 → filter → merge → validate → ExerciseIR → DOCX
2. **模块接口契约**：每个模块的输入/输出 JSON Schema、字段说明
3. **Phase 2/3 扩展点**：review worker 接入点、paddleocr_vl 触发点
4. **错误处理与回退链路**：每个节点的失败行为和回退策略
5. **性能预算**：各节点的耗时/内存预算

## 验收标准
1. 数据流覆盖从 PDF 输入到 DOCX 输出的完整路径
2. 每个模块的接口契约可被 dev 直接实现
3. 回退策略清晰：任何增强失败不影响 baseline 输出
4. 包含 formula 专项的接口预留（Phase 3）

## 下游动作
文档供 dev-1/dev-2 实现 Phase 1 子任务时参考接口契约。
