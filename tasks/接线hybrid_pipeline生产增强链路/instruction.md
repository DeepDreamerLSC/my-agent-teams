# 任务：接线 hybrid_pipeline.py 生产增强链路

## 任务类型
development

## 目标
将 `hybrid_pipeline.py` 中 6 个 skeleton stub 方法接线到已有的子模块，使 `enable_enhancement=True` 时能走真实增强链路：baseline → question region → candidate extraction → filter → merge → validate。

需要接线的 stub 方法（当前全部返回空或透传）：

1. `_detect_question_regions(pages)` → 调用 `QuestionRegionDetector`
2. `_select_enhancement_pages(pages, question_regions)` → 基于可判定性选择需要增强的页
3. `_extract_candidates(pdf_path, ...)` → 调用 `CandidateExtractor`，从 `candidate_profiles` 配置的模型抽取候选
4. `_filter_and_attach(candidates, question_regions, baseline_pages)` → 调用 `CandidateFilter`，过滤并归属匹配
5. `_merge(baseline_pages, candidates)` → 调用 `PageIRMerger`，将 accepted 候选合并到 baseline PageIR
6. `_validate_or_fallback(baseline_pages, merged_pages)` → 调用 `HybridValidator`，页级校验与回退

已有子模块位置：
- `question_region_detector.py` — QuestionRegionDetector
- `candidate_extractor.py` — CandidateExtractor
- `candidate_filter.py` — CandidateFilter
- `page_ir_merger.py` — PageIRMerger
- `hybrid_validator.py` — HybridValidator
- `review_integrator.py` — ReviewIntegrator（已接线，无需改动）

## 任务边界
- **在范围内**：修改 `hybrid_pipeline.py` 的 6 个 stub 方法，使其调用对应子模块
- **不在范围内**：不修改子模块本身、不修改 normalizer、不修改 inference_config、不写新测试文件

## 输入事实
- `hybrid_pipeline.py` 当前 6 个 stub 返回空列表或直接透传 baseline
- 所有子模块已实现且通过各自单元测试
- `HybridPipelineConfig` 已有 `candidate_profiles`、`merge_policy`、`filters` 等配置字段
- `_review_ambiguous` 已接线 ReviewIntegrator，不需要改动
- `_filter_and_attach` 当前返回 `list(candidates)`，需要改为调用 `CandidateFilter`
- 现有 `test_hybrid_pipeline.py` 和 `test_hybrid_validator.py` 需要继续通过

## 约束
- write_scope: `hybrid_pipeline.py`
- target_environment: dev
- enable_enhancement=False 时行为必须与当前完全一致（baseline pass-through）
- 新增 import 只能引用同目录下已有的子模块
- 不引入新的外部依赖

## 交付物
1. `hybrid_pipeline.py` — 6 个 stub 方法已接线到真实子模块
2. `result.json` 标准格式

## 验收标准
1. `pytest tests/test_hybrid_pipeline.py tests/test_hybrid_validator.py -q` 全部通过
2. `enable_enhancement=False` 时输出与当前 baseline pass-through 完全一致
3. `enable_enhancement=True` 时 `_detect_question_regions` 返回非空（对有题号的页面）
4. `_extract_candidates` 根据 `candidate_profiles` 配置调用对应 adapter 抽取候选
5. `_merge` 将 accepted 候选追加到 baseline PageIR 的 blocks 中
6. `_validate_or_fallback` 在合并后 PageIR 校验失败时回退到 baseline

## 下游动作
接线完成后，端到端验证任务可以重新跑真实管线验证
