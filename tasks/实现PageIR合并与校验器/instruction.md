# 任务：实现 PageIR 合并与校验器

## 任务类型
development

## 目标
将 accepted image/table 候选追加到 baseline PageIR，保留 baseline 正文文本，实现页级 fallback 和校验。

## 任务边界
- 新增 page_ir_merger.py 和 hybrid_validator.py
- 依赖：HybridExperimentalPipeline（B，已完成）、CandidateFilter（E，已完成）
- 不修改现有 adapter

## 输入事实
- HybridExperimentalPipeline 骨架已实现，有扩展点
- CandidateFilter 已实现过滤和归属
- 设计文档：design/pdf2word/hybrid_experimental增强管线设计.md（Section 9-11）
- 核心原则：baseline 文本是主干，增强不能覆盖 baseline blocks
- 页级 fallback：任何增强失败只影响单页

## 约束
- write_scope 以 task.json 为准
- baseline 正文 blocks 不能被覆盖或删除
- 新增 block 必须带来源标记（source_profile、confidence）
- 校验失败时整页回退到 baseline
- 输出审计日志

## 交付物
1. page_ir_merger.py：PageIRMerger 类
2. hybrid_validator.py：HybridValidator 类
3. 测试文件：test_page_ir_merger.py、test_hybrid_validator.py
4. result.json 包含合并测试结果

## 验收标准
1. accepted image/table 候选正确追加到 baseline PageIR
2. baseline 正文 blocks 不受影响
3. 新增 block 带来源标记
4. validator 校验失败时回退到 baseline
5. 输出 hybrid-pages.jsonl 和 validator-report.json
6. 测试通过

## 下游动作
完成后接入 HybridExperimentalPipeline，形成完整 hybrid 增强链路。
