# 任务：实现 HybridExperimentalPipeline 骨架

## 任务类型
development

## 目标
实现 HybridExperimentalPipeline orchestrator，调用 apple_baseline adapter，输出 baseline-only hybrid result。不开增强时与 apple 等价。

## 任务边界
- 新增 hybrid_pipeline.py
- 复用 HybridExperimentalAdapter（已由任务 A 创建）
- Phase 1 只做 baseline pass-through，不接入增强模型
- 不修改现有 adapter

## 输入事实
- HybridExperimentalAdapter 已注册，profile_name='hybrid_experimental'
- 设计文档：design/pdf2word/hybrid_experimental增强管线设计.md（Section 3-5）
- apple_baseline adapter 可直接调用
- 不开增强时应与 apple 输出完全等价

## 约束
- write_scope 以 task.json 为准
- Phase 1 只做 pass-through，不接入增强模型
- 必须保留扩展点（后续接入 QuestionRegion、候选、review）
- 不修改 apple_baseline adapter

## 交付物
1. hybrid_pipeline.py：HybridExperimentalPipeline 类
2. 测试文件：test_hybrid_pipeline.py
3. result.json 包含等价性测试结果

## 验收标准
1. create_adapter('hybrid_experimental') 返回 HybridExperimentalAdapter
2. 不开增强时输出与 apple_baseline 等价
3. 有扩展点接入后续增强步骤
4. 测试通过

## 下游动作
完成后接入候选过滤、PageIR merger、Qwen3-VL review。
