# 任务：实现 PageTypeClassifier 与 SourceSelectionPolicy，收口 Hybrid 候选源运行时策略

## 任务类型
development

## 目标
把 P1 候选源页型策略真正落到运行时，让 `hybrid_experimental` 在一次 run 内可按样例/页输出 `page_type`、`default_source_profile`、`supplemental_source_profile`、`selected_pages_or_crops`，并作为后续 Paddle/MinerU 选择与审计的唯一事实源。

## 任务边界
- 只实现运行时 `PageTypeClassifier / SourceSelectionPolicy` 与配置接线，不重做主 parser 选型。
- 允许修改：`hybrid_pipeline.py`、`parser_client.py`、`inference_config.yaml`、`test_hybrid_pipeline.py`、`test_hybrid_backend_resolve.py`、`test_pdf_to_word_service.py`。
- 不做 per-source merge 明细审计，不重跑 Phase 3 报告；那是下游任务。
- 不放开公式并回，`formula_candidate` 仍保持 `audit-only / merge-disabled`。

## 输入事实
- authoritative 策略文档：`/Users/linsuchang/Desktop/work/chiralium/design/pdf2word/P1候选源页型选择策略.md`
- authoritative 策略 JSON：`/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/p1-source-selection/source_selection_strategy.json`
- 当前代码已具备 `enhancement_pages`、`paddle_trigger`、`profile_audits` 等基础设施，但还没有显式的 `page_type/source_profile` 运行时输出。
- 已确认发布边界继续维持：`apple default + hybrid_experimental quality gray + formula audit-only / merge-disabled`。

## 约束
- `write_scope` 以 `task.json` 为准。
- 默认增强源仍是 `mineru_full`；`paddleocr_vl` 只能作为 `selected pages / crops` 的补充源。
- 负样例 / fallback 场景必须能输出 `baseline_only` 或等价事实，不能为了补图表破坏 `document/page fallback`。
- 运行时输出可以挂在 `last_run`、`profile_audits`、service meta 或等价审计结构上，但不要引入破坏现有默认 API 的强制字段。
- 若需要配置项，优先通过现有 `inference_config.yaml + parser_client` 接线显式表达，不要再写隐式硬编码分叉。

## 交付物
1. `PageTypeClassifier / SourceSelectionPolicy` 运行时实现。
2. 测试覆盖至少包括：`math_exam_image_dense`、`table_heavy`、负样例/`document_fallback`、显式配置覆盖。
3. `result.json`：写明最终页型映射、默认源/补充源规则、仍待下游补齐的审计缺口。

## 验收标准
1. 一次 hybrid run 内可观测到 `page_type`、`default_source_profile`、`supplemental_source_profile`、`selected_pages_or_crops`。
2. 默认规则与 P1 策略文档一致：`mineru_full` 默认、`paddleocr_vl` 定向补充、负样例 baseline-only、公式 audit-only。
3. 指定测试通过，且不回归当前 `hybrid_experimental` 解析/resolve 行为。

## 下游动作
完成后进入 review-1 审查；通过后作为 P1 候选源运行时策略基线，并解锁下游按源审计与定向执行任务。
