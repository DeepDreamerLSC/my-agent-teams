# 任务：实现 Hybrid MVP 图片表格并回链路

## 任务类型
开发

## 目标
打通 hybrid_pipeline 中 mineru_full image/table 候选的完整链路：候选抽取 → 过滤归属 → PageIR 合并 → hybrid_validator，使 enable_enhancement=True 时能稳定产出包含图片/表格候选的 hybrid PageIR。

## 任务边界
- 修改 `hybrid_pipeline.py`，把现有的 skeleton stub 接线到真实子模块
- 只处理 image/table 候选，formula_candidate 保持 audit-only
- 不修改子模块本身（question_region_detector、candidate_extractor 等已有实现）

## 输入事实
- hybrid_pipeline.py 当前 _detect_question_regions/_select_enhancement_pages/_extract_candidates 返回空，_merge 直接返回 baseline pages
- 子模块已实现：question_region_detector、candidate_extractor、candidate_filter、page_ir_merger、hybrid_validator
- e2e 验证已证明测试侧可以接线跑通（ArtifactWiredHybridPipeline），现在需要在生产代码中做同样的事
- mineru_full profile 已在 inference_config.yaml 中配置，候选归属率 64.9%，直接可用率 52.7%

## 约束
- write_scope: `hybrid_pipeline.py`
- apple_baseline 文本块不可被替换，增强只追加 image/table
- validator 失败时整页回退 baseline
- formula_candidate 默认 audit-only，不参与合并
- 前置依赖：`补齐QuestionRegion可判定性与跳过策略` 完成

## 交付物
- 更新后的 hybrid_pipeline.py，enable_enhancement=True 时走真实增强链路
- 用 5 个横评样例验证，result.json 中报告每个样例的 accepted candidates 数和 fallback 情况

## 验收标准
1. `数学试卷`、`英语八年级` 能稳定插入 image/table 候选
2. `语文五年级` 因题号区域不可判定，全部跳过增强
3. exercise_item_count 相比 baseline 不下降
4. validator_fallback_rate 在可判定样例中 <= 50%（Phase 1 初期允许较高）

## 下游动作
完成后解锁 `补齐ExerciseIR和DOCX的图片表格输出` 和 `扩展Hybrid指标与审计产物`。
