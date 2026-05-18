# 审查说明：推进公式裁块失败归因与对比专项

## 结论

**审查通过（approve）。**

## 通过依据

1. 失败归因已经接进现有评测框架。

   这次不是额外拼接离线脚本，而是在 `model_eval_runner.py` 里补齐了公式 crop 失败分桶、profile 对比、P1 摘要生成和 Markdown/JSON 产物写出。任务边界要求“优先在现有框架内补齐诊断”，这一点已经满足。

2. P1 产物与真实 run `20260517-174500` 对得上。

   我对照了上游 `formula_crop_eval_report.json` 与输出的 `formula_crop_failure_summary.json/.md`，关键数字一致：
   - `unmaterialized_candidate_count=1`
   - `blocked_profile_count=3`
   - `selected_profiles`: `alignment_failed=26`、`format_failed=3`、`empty=2`、`blocked=51`、`success=3`
   - `runnable_profiles`: `alignment_failed=26`、`format_failed=3`、`empty=2`、`blocked=0`、`success=3`

3. 失败类型和下一轮 A/B 拆法符合任务目标。

   产物已经把问题拆成：
   - `crop/materialization`
   - `cleanup/conversion`
   - `model capability`

   这满足 instruction 里“区分数据/裁块问题、格式转换问题、模型识别问题，并形成下一轮可执行输入”的要求。

4. `merge-disabled` 结论是站得住的。

   当前最佳 runnable profile 是 `qwen3_vl_8b`，但 exact success 只有 `2/17 (11.8%)`，同时仍有 `12` 个 `alignment failed` 和 `3` 个 `format failed`；再加上仍有 `1` 个 candidate 未 materialize、`3` 个 selected profile blocked，继续保持默认公式 `audit-only / merge-disabled` 是合理结论，没有被偷偷放开。

5. 测试证据成立。

   我本地执行：

   ```bash
   PYTHONDONTWRITEBYTECODE=1 backend/.venv/bin/pytest -o cache_dir=/private/tmp/pytest-review-1 backend/tests/test_model_eval_runner.py
   ```

   结果 `14 passed`，只有 4 条既有 FastAPI `on_event` deprecation warnings，与本任务无关。

## 总结

这次交付已经把“公式 crop 目前为什么还不能放开 merge”解释成可复核的结构化证据，而不是只报总成功率；任务目标已完成，建议进入 `qa` 复核公式专项口径与产物。
