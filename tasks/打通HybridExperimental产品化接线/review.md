# 审查说明：打通HybridExperimental产品化接线

## 结论

**审查通过（approve）。**

## 通过依据

1. `hybrid_experimental` 已经真正接到生产 Hybrid 管线。

   `parser_client.parse_with_backend()` 在显式 `parser_backend=hybrid_experimental` 时会进入 `_run_hybrid_pipeline()`，读取 `source_pdf`、`render.dpi`，构造 `HybridExperimentalPipeline` 并执行 `pipeline.parse(...)`，不再回退到 apple/mock 占位实现。

2. API / service / adapter 三个入口都已经收口到同一条真实路径。

   - API 路由会把 `parser_backend=hybrid_experimental` 原样透传给 service。
   - `conversion_service._resolve_parser_backend()` 允许显式 hybrid，同时保留 `auto -> apple/mock` 的原有默认解析逻辑。
   - `HybridExperimentalAdapter.parse()` 也已改为直接构造并调用 Hybrid pipeline，避免 adapter 侧继续沿用 apple baseline 行为。

3. Hybrid 可观测性已经进入 service result meta。

   `parser_client` 会在 `meta.hybrid_pipeline` 中回填 `path`、`candidate_profiles`、`review_profile`、`enhancement_page_count`、`candidate_count`、`filtered_candidate_count`、`fallback_page_count`、`review_metrics`、`profile_audits`；`conversion_service.build_result_meta()` 又把关键字段抬升为 `hybrid_path`、`hybrid_candidate_profiles`、`hybrid_enhancement_page_count` 等 service 级指标，满足“结果可观测”的验收要求。

4. 默认链路没有被反向污染。

   `resolve_effective_parser_backend()` 与 `conversion_service._resolve_parser_backend()` 都保持：只有显式传入 `hybrid_experimental` 时才走 Hybrid；`auto` 仍然根据 apple worker 可用性解析为 `apple` 或 `mock`。相关回归测试也覆盖了这一点。

5. pytest 证据与任务声明一致。

   我复跑了两组结果中声明的测试：

   - `test_hybrid_backend_resolve.py`、`test_pdf_to_word_service.py`、`test_pdf_to_word_api.py`、`test_pdf_to_word_exercise_pipeline_integration.py`：`18 passed`
   - `test_hybrid_backend_resolve.py`、`test_hybrid_pipeline.py -k 'hybrid_experimental or create_adapter_hybrid_experimental_returns_dedicated_adapter_and_identity'`：`3 passed, 5 deselected`

   这覆盖了 backend resolve、service、API、exercise pipeline integration 以及 adapter identity / hybrid pipeline 入口。

## 非阻塞观察

- 本轮没有新增真实模型在线 smoke 或新的端到端 PDF 样本产物。当前结论主要建立在代码接线审阅与定向 pytest 上。对“产品化接线是否完成”的任务目标来说这已足够，但如果后续要作为长期稳定能力维护，仍建议补一条最小真实样本 smoke 或固化验证产物。

## 总结

这次交付完成了任务要求的核心接线：显式 `hybrid_experimental` 已能从产品入口进入真实 Hybrid pipeline，结果 meta 具备观测性，默认 `auto/apple` 链路未回归，相关定向 pytest 也全部通过，因此可以通过。
