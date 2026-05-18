# 审查说明：固化最终DOCX按源门禁

## 结论

**审查通过（approve）。**

本轮没有发现阻塞问题。

## 通过依据

1. final DOCX gate 已经变成按源感知门禁。

   这次不是只统计 DOCX 能否打开，而是把 final archive、P1 策略矩阵和 phase3 Paddle 审计一起拉进 gate。
   每个样例现在都会显式校验：
   - `page_type`
   - `default_source_profile`
   - `supplemental_source_profile`
   - `selected_pages_or_crops`
   - `fallback_pages`
   - 负样例 `baseline_only`
   - 公式 `audit-only / merge-disabled`

2. 负样例和公式边界被正确保护。

   `语文五年级` 继续被识别为 `baseline_only / document_fallback`，不会因为存在候选事实就被误记为增强成功。
   公式侧也仍然只是审计事实，`formula_candidate` 没有被 gate 误当成缺陷性回归。

3. 报告产物已经能直接作为常态化底稿。

   顶层 `final_acceptance_summary.json` 和 `final_acceptance_report.md` 给出汇总口径，运行目录 `20260518-072100/final_docx_gate_report.json/.md` 给出逐样例 source-aware gate 事实，已经足够给 QA / PM 直接使用。

4. 当前发布边界没有被放宽。

   报告明确保持：
   `apple default + hybrid_experimental quality gray + formula audit-only / merge-disabled`

   这和任务边界一致，没有借着 gate 升级顺手改发布结论。

5. 本地复跑通过。

   我执行了：

   ```bash
   .venv/bin/python -m pytest tests/test_model_eval_runner.py tests/test_hybrid_e2e.py -o cache_dir=/private/tmp/chiralium-pytest-final-docx-gate --basetemp=/private/tmp/chiralium-pytest-final-docx-gate-tmp -q
   ```

   结果 `21 passed`，只有 4 条既有 FastAPI deprecation warnings。

## 总结

这次交付已经把 final DOCX 常态化验收从“文档能打开”提升为“按策略矩阵解释最终 Word 质量”，并且负样例、fallback 和公式边界都被显式固化，可以通过。
