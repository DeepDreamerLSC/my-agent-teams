# 审查说明：实现页型分类与候选源运行时策略

## 结论

**审查通过（approve）。**

本轮没有发现阻塞问题。

## 通过依据

1. runtime 事实层已经接通。

   `HybridExperimentalPipeline` 现在不只是“有候选 profile 配置”，而是会生成统一的 `source_selection` 事实，并在一次 run 内输出：
   - `document/page page_type`
   - `default_source_profile`
   - `supplemental_source_profile`
   - `selected_pages_or_crops`

   这些信息同时进入 `last_run`、`profile_audits`，并经 `parser_client.py` 透传到 `meta.hybrid_pipeline.source_selection`。

2. 候选源执行策略和 P1 口径一致。

   我对照了 `P1候选源页型选择策略.md`、`source_selection_strategy.json`、`inference_config.yaml` 和 `hybrid_pipeline.py`，确认这轮实现维持了正确边界：
   - `mineru_full` 仍是默认增强源
   - `paddleocr_vl` 只在命中的 selected pages / crops 上补充执行
   - 负样例会输出 `baseline_only` 并跳过 Paddle
   - `formula_candidate` 继续 `audit-only / merge-disabled`

3. 点名场景已有测试覆盖。

   测试里已经覆盖：
   - `math_exam_image_dense`
   - `table_heavy`
   - 负样例 / `document_fallback`
   - 显式 `source_selection` 配置覆盖
   - parser_client / service 的 runtime meta 透传

4. 本地复跑通过。

   我执行了：

   ```bash
   PYTHONDONTWRITEBYTECODE=1 /Users/linsuchang/Desktop/work/chiralium/backend/.venv/bin/pytest /Users/linsuchang/Desktop/work/chiralium/backend/tests/test_hybrid_pipeline.py /Users/linsuchang/Desktop/work/chiralium/backend/tests/test_hybrid_backend_resolve.py /Users/linsuchang/Desktop/work/chiralium/backend/tests/test_pdf_to_word_service.py -o cache_dir=/private/tmp/chiralium-pytest-source-selection --basetemp=/private/tmp/chiralium-pytest-source-selection-tmp
   ```

   结果为 `21 passed`，只有 4 条既有 FastAPI deprecation warnings。

## 残余边界

当前实现的主要目标是把 P1 五样例的页型/候选源策略收口到 runtime 事实层。更细的按源 accepted/rejected/fallback 明细审计，以及更泛化的页型判定扩展，仍是下游任务，不构成本轮阻塞。
