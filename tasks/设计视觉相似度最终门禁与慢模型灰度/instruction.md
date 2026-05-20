# 任务：设计视觉相似度最终门禁与慢模型灰度

## 任务类型
架构设计 / 质量模式规划

## 目标
基于 95% 路线文档，设计视觉相似度最终门禁与慢模型灰度接入边界：哪些能力只进 `quality/hybrid_async`，哪些产物需要结构化输出，怎样在不拖慢默认同步的前提下纳入最终评分。

## 任务边界
- 只允许修改 `backend/app/services/pdf_to_word/visual_similarity_gate.py`、`backend/tests/test_pdf_to_word_visual_similarity_gate.py`、`backend/tests/fixtures/pdf_to_word/visual_similarity/`。
- 本任务以方案/契约/基础测试夹具为主，不要求接入完整视觉相似度实现。
- 不改默认同步路径，不引入分钟级耗时逻辑到 auto/apple。

## 输入事实
- 上游依赖：`冻结95还原度指标与样本清单`、`补齐表格样例与验收夹具`。
- 路线文档已明确：视觉相似度和慢模型增强属于后续 quality/hybrid_async 阶段，不能破坏默认同步约 6.92s/页级别。
- 后续需要回答：render 对比、关键区域阈值、慢模型选择性触发、artifact 结构和阻断条件。

## 约束
- 方案必须明确默认同步 vs quality/hybrid_async 的边界。
- 如果本轮只落基础 contract/fixture，也要把缺口写清楚，不能伪装成已接入完整能力。
- 不要顺手改表格 renderer 或 final report 主逻辑。

## 交付物
1. 一份视觉相似度 gate 的最小 contract / stub / fixture。
2. 一组基础测试，证明关键字段、模式边界和失败语义已冻结。
3. 明确慢模型灰度策略与 artifact 输出约定。

## 验收标准
- 能清楚回答视觉相似度分项如何进入 95% 总分。
- 能清楚回答慢模型为何只进 quality/hybrid_async，不进默认同步。
- 方案/fixture/stub 与 2026-05-18 路线文档一致，不夸大现状。
- 不越界改现有默认同步主链路。

## 下游动作
完成后，PM 将据此决定视觉相似度与慢模型能力的后续实现顺序。
