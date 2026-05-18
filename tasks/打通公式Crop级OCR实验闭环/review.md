# 审查说明：打通公式Crop级OCR实验闭环

## 结论

**通过（approve）。**

## 通过依据

- 公式 crop 实验入口已经真正接通，而不是只刷新报告：[model_eval_runner.py](/Users/linsuchang/Desktop/work/chiralium/backend/app/services/pdf_to_word/model_eval_runner.py:64) 增加了 `--formula-crop-eval` CLI；[model_eval_runner.py](/Users/linsuchang/Desktop/work/chiralium/backend/app/services/pdf_to_word/model_eval_runner.py:2020) 到 [model_eval_runner.py](/Users/linsuchang/Desktop/work/chiralium/backend/app/services/pdf_to_word/model_eval_runner.py:2033) 会在该模式下构建 summary、执行 OCR 实验并落盘产物。
- profile 选择没有锁死到单一模型名：[model_eval_runner.py](/Users/linsuchang/Desktop/work/chiralium/backend/app/services/pdf_to_word/model_eval_runner.py:1113) 到 [model_eval_runner.py](/Users/linsuchang/Desktop/work/chiralium/backend/app/services/pdf_to_word/model_eval_runner.py:1133) 通过 `config.list_profiles(include_disabled=True)` 统一收集 `input_mode=page_image` 的 profile；[model_eval_runner.py](/Users/linsuchang/Desktop/work/chiralium/backend/app/services/pdf_to_word/model_eval_runner.py:1597) 到 [model_eval_runner.py](/Users/linsuchang/Desktop/work/chiralium/backend/app/services/pdf_to_word/model_eval_runner.py:1603) 还会把 disabled / healthcheck failed / capability 不支持等 blocked 原因分开标记。
- 逐 crop 真实结果落盘已成立：[model_eval_runner.py](/Users/linsuchang/Desktop/work/chiralium/backend/app/services/pdf_to_word/model_eval_runner.py:1605) 到 [model_eval_runner.py](/Users/linsuchang/Desktop/work/chiralium/backend/app/services/pdf_to_word/model_eval_runner.py:1645) 会对每个 crop 写出结果 JSON；[model_eval_runner.py](/Users/linsuchang/Desktop/work/chiralium/backend/app/services/pdf_to_word/model_eval_runner.py:1782) 到 [model_eval_runner.py](/Users/linsuchang/Desktop/work/chiralium/backend/app/services/pdf_to_word/model_eval_runner.py:1802) 会把 report、inputs、missing-assets、expected-crops 和 `ocr-results/` 一并落到 run 目录。
- 状态分类满足任务要求：[model_eval_runner.py](/Users/linsuchang/Desktop/work/chiralium/backend/app/services/pdf_to_word/model_eval_runner.py:36) 到 [model_eval_runner.py](/Users/linsuchang/Desktop/work/chiralium/backend/app/services/pdf_to_word/model_eval_runner.py:43) 定义了 `success / needs_manual_review / baseline_alignment_failed / format_failed / empty / blocked` 六类状态；[model_eval_runner.py](/Users/linsuchang/Desktop/work/chiralium/backend/app/services/pdf_to_word/model_eval_runner.py:1313) 到 [model_eval_runner.py](/Users/linsuchang/Desktop/work/chiralium/backend/app/services/pdf_to_word/model_eval_runner.py:1398) 负责把真实响应归类到这些状态。
- formula 默认 `audit-only / merge-disabled` 行为没有被放开：本轮报告在 [formula_crop_eval_report.json](/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/phase4-formula-crop-eval/20260517-174500/formula_crop_eval_report.json:12) 到 [formula_crop_eval_report.json](/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/phase4-formula-crop-eval/20260517-174500/formula_crop_eval_report.json:21) 明确写回 `default_enabled=false`、`default_mode=disabled_audit_only`、`merge_enabled_by_default=false`；页级统计也持续保留 `formula_merge_enabled=false`。
- 真实实验产物已生成并可复核：`20260517-174500` 目录下存在 `expected-crops/`、`formula_crop_inputs.jsonl`、`formula_crop_eval_report.{json,md}` 和 `ocr-results/`；我本地核对 `ocr-results/` 文件数为 `85`，与报告中的 5 个 profile × 17 个 crop 相符。示例上，[crop-01.json](</Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/phase4-formula-crop-eval/20260517-174500/ocr-results/glm_ocr/mineru_full/数学 八年级下册pdf/page-001/crop-01.json:1>) 如实记录了 `glm_ocr` 的 healthcheck 502 blocked 结果，而 [crop-01.json](</Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/phase4-formula-crop-eval/20260517-174500/ocr-results/qwen3_vl_8b/mineru_full/数学 八年级下册pdf/page-001/crop-01.json:1>) 则保留了实际响应、比较结果和失败原因。
- 测试覆盖与实现对齐：[test_model_eval_runner.py](/Users/linsuchang/Desktop/work/chiralium/backend/tests/test_model_eval_runner.py:471) 到 [test_model_eval_runner.py](/Users/linsuchang/Desktop/work/chiralium/backend/tests/test_model_eval_runner.py:835) 覆盖了 CLI 解析、summary 生成、`ocr-results/` 落盘、状态分类和 blocked profile；[test_pdf_formula_pipeline.py](/Users/linsuchang/Desktop/work/chiralium/backend/tests/test_pdf_formula_pipeline.py:22) 到 [test_pdf_formula_pipeline.py](/Users/linsuchang/Desktop/work/chiralium/backend/tests/test_pdf_formula_pipeline.py:26) 还补了 plain-text formula-like 内容到 OMML fallback 的回归用例。

## 验证

- `PYTHONPYCACHEPREFIX=/private/tmp/chiralium-pyc-review-model /Users/linsuchang/Desktop/work/chiralium/backend/.venv/bin/pytest /Users/linsuchang/Desktop/work/chiralium/backend/tests/test_model_eval_runner.py -q`
  结果：`12 passed, 4 warnings`
- `PYTHONPYCACHEPREFIX=/private/tmp/chiralium-pyc-review-formula /Users/linsuchang/Desktop/work/chiralium/backend/.venv/bin/pytest /Users/linsuchang/Desktop/work/chiralium/backend/tests/test_pdf_formula_pipeline.py -q`
  结果：`4 passed, 4 warnings`

## 说明

本轮通过代表“实验闭环已打通、产物可复跑、blocked 原因可读”，不代表公式能力已经达到可接主链路水平。当前报告里 exact success 仍然很低，`baseline_alignment_failed` 占比也高，因此后续仍应按报告建议继续做 crop 级 A/B 和失败归因，并保持 formula 默认 `audit-only / merge-disabled`。
