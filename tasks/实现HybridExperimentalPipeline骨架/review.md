# 审查说明：实现HybridExperimentalPipeline骨架

## 结论

**通过（approve）**。

这轮实现符合任务边界：只新增了 `hybrid_pipeline.py` 和 `test_hybrid_pipeline.py`，没有去改现有 adapter。作为 Phase 1 骨架，`HybridExperimentalPipeline` 已经具备了 baseline pass-through 主链路，并预留了 question-region、候选抽取、过滤归属、review、merge、validate 这些后续增强步骤的方法入口。

关闭增强时，pipeline 会直接复用 baseline 结果，并保留原始 `pages`、`metrics`、`warnings`、`error`，仅把返回 `profile` 改成 `hybrid_experimental`。这和任务要求的“baseline-only hybrid result”一致。相关测试我复跑后为 `15 passed, 4 warnings`。

## 复核要点

- 在 write_scope 内完成：
  - 新增 `HybridExperimentalPipeline`
  - 新增 `HybridPipelineConfig / Context / Run`
  - 新增扩展阶段 stub methods
  - 新增 pass-through 回归测试
- baseline pass-through 行为对齐任务要求：
  - 默认 `baseline_profile='apple_baseline'`
  - 关闭增强时不做额外候选、review 或 merge
  - 最终结果仅重标 `profile='hybrid_experimental'`
- 扩展点齐全：
  - `_detect_question_regions`
  - `_select_enhancement_pages`
  - `_extract_candidates`
  - `_filter_and_attach`
  - `_review_ambiguous`
  - `_merge`
  - `_validate_or_fallback`

## 非阻塞提示

当前这份 pipeline 还是一个独立骨架类，尚未真正接入现有 `HybridExperimentalAdapter` / service 运行入口。我本地打桩验证过，`create_adapter('hybrid_experimental').parse()` 目前不会落到这个新 pipeline 上。所以这轮代码更像是后续任务的开发基座，而不是已经切换运行链路的完成态。

另外，骨架里自定义的 `QuestionRegion`、`EnhancementCandidate`、`MergeDecision` 和当前仓库里 `question_region_detector.py`、`candidate_extractor.py`、`candidate_filter.py` 的真实 dataclass 存在字段命名差异。现在因为都是 stub，不影响收口；但后续接线时最好尽早统一类型或增加明确的转换层，否则还会再改一轮方法签名。

## 建议动作

建议 PM 直接推进后续任务，但最好尽快补一轮“接线任务”，把 `hybrid_experimental` 真实入口绑定到 `HybridExperimentalPipeline`，同时统一 pipeline 骨架与 detector/extractor/filter 的接口形状。

审查时间：2026-05-15T19:26:26+08:00
