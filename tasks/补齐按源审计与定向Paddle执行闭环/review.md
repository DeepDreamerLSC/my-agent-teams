# 审查说明：补齐按源审计与定向Paddle执行闭环

## 结论

**审查通过（approve）。**

本轮没有发现阻塞问题。

## 通过依据

1. 按源审计已经接进真实 merge / validator 链路。

   这次不是在报告层再拼一份统计，而是直接在 `HybridExperimentalPipeline` 里基于同一套 `FilteredCandidate` 和 `HybridValidationReport` 生成 `per_source_merge_audit`。现在每次 run 都能按：
   - `sample`
   - `page_type`
   - `candidate_kind`
   - `source_profile`

   输出 `accepted / rejected / ambiguous / skipped / fallback / final_accepted`，同时保留 `merge_reason_counts`、`fallback_reason_counts` 和 `candidate_ids`。

2. `profile_audits` 已经补成可解释的按源事实。

   除了原来的 `page_scope / selected_pages / cache hits/misses`，现在还能直接看到：
   - `accepted_count`
   - `rejected_count`
   - `fallback_count`
   - `final_accepted_count`
   - `latency_seconds`
   - `merge_reasons`
   - `fallback_reasons`
   - `per_source_rows`

   这满足了任务要求里“可审计、可复跑、可解释”的目标。

3. Paddle 仍是 selected pages 定向执行，不是全书默认增强。

   我对照了 runtime 逻辑和 phase3 报告，确认 Paddle 仍受 `source_selection + trigger` 约束。
   这轮样例里总 `selected_pages=21/32`，没有退化成整本同步跑。
   `数学试卷` 虽然是高价值样本，也只在 `[1,3,4,6,8,9,11]` 这些命中页运行。

4. 负样例和公式边界都保住了。

   `语文五年级` 继续是 `baseline_only / document_fallback`，对应 `per-source-merge-audit.rows=[]`，`profile_audits` 里也没有伪造候选事实。
   `formula_candidate` 仍然只记审计事实，不放开正文 merge。

5. phase3 报告能直接支持 QA/PM 判断。

   报告里已经能同时看到：
   - 触发页
   - cache hit/miss
   - latency
   - candidate 数
   - accepted / rejected / fallback / final accepted
   - 样例级解释口径

   这已经足够支撑“Paddle 何时有价值、何时只是噪声被过滤”的后续门禁讨论。

6. 本地复跑通过。

   我执行了：

   ```bash
   PYTHONDONTWRITEBYTECODE=1 /Users/linsuchang/Desktop/work/chiralium/backend/.venv/bin/pytest /Users/linsuchang/Desktop/work/chiralium/backend/tests/test_hybrid_pipeline.py /Users/linsuchang/Desktop/work/chiralium/backend/tests/test_page_ir_merger.py /Users/linsuchang/Desktop/work/chiralium/backend/tests/test_hybrid_e2e.py -o cache_dir=/private/tmp/chiralium-pytest-source-audit --basetemp=/private/tmp/chiralium-pytest-source-audit-tmp
   ```

   结果 `19 passed`，只有 4 条既有 FastAPI deprecation warnings。

## 总结

这次交付已经把“Paddle 为什么被触发、跑了哪些页、出了多少候选、最后被接受/拒绝/回退了多少”沉到运行时事实层，并且 report 产物与测试都能闭环，因此可以通过并进入 `qa`。
