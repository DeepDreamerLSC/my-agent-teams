# 审查说明：建立PDF转Word更大样本回归入口与样例清单

## 结论

**通过（approve）**。本次实现满足任务目标：在 `model_eval_runner.py` 中新增 `--regression-summary` / `--regression-manifest` / `--hybrid-e2e-root` 入口，支持从 manifest 或当前 authoritative 五样例基线出发，统一汇总 archive + hybrid e2e 事实，输出可扩展的 `regression_manifest.json`、`regression_summary.json` 和 `regression_summary.md`。

## 审查范围

- `backend/app/services/pdf_to_word/model_eval_runner.py`
- `backend/tests/test_model_eval_runner.py`
- `artifacts/pdf2word/p2-regression/current-five-sample-baseline/regression_manifest.json`
- `artifacts/pdf2word/p2-regression/current-five-sample-baseline/regression_summary.json`
- `artifacts/pdf2word/p2-regression/current-five-sample-baseline/regression_summary.md`
- 任务输入：`instruction.md`、`result.json`、`task.json`

## 复核结果

- 入口设计符合任务边界：
  - `--regression-summary` 负责统一构建 larger-sample regression summary。
  - `--regression-manifest` 支持外部补充/覆盖 manifest，同时保留 bootstrap 基线字段。
  - `--hybrid-e2e-root` 与 `--archive-root` 共同作为现有事实来源，没有另起割裂脚本。
- manifest/schema 具备扩展位：
  - `manifest_version = pdf2word_regression_manifest/v1`
  - 保留了 `sample_name / source_pdf / subject / grade_or_stage / page_type / current_baseline_source / authoritative / artifact_paths / notes / tags`
  - 既区分 `coverage_tier=current_five_sample_baseline`，又显式写出 `future_expansion_fields` 与 `known_limitations`。
- 摘要生成不是手工拼报告：
  - summary 会从 authoritative report、hybrid e2e report、source manifest、validator report 和 final DOCX gate source facts 聚合出 `aggregate / golden_summary / meta_summary / samples`。
  - 当前五样例产物中，`sample_count=5`、`current_baseline_ready_sample_count=5`、`docx_openable_sample_count=5`、`document_fallback_sample_count=1`、`accepted_candidate_total=35` 等字段均已自动生成。
- 现有边界陈述诚实：
  - 产物明确说明当前仍锚定现有五样例 authoritative/archive/e2e 基线。
  - `missing_source_pdf_count=5`、`source_pdf` 大量缺失、不会自动发现新的真实 PDF 样本，都在 manifest/summary 中公开暴露，没有夸大“更大样本已覆盖”。

## 测试

已复跑：

```bash
PYTHONDONTWRITEBYTECODE=1 /Users/linsuchang/Desktop/work/chiralium/backend/.venv/bin/python -m pytest /Users/linsuchang/Desktop/work/chiralium/backend/tests/test_model_eval_runner.py -o cache_dir=/private/tmp/chiralium-pytest-regression-cache --basetemp=/private/tmp/chiralium-pytest-regression-tmp -q
```

结果：`16 passed, 4 warnings in 0.18s`。

同时复跑了真实入口命令。由于 reviewer 沙箱不能写 `chiralium/artifacts`，我把 `--output-dir` 改到 `/private/tmp` 做等价验证：

```bash
PYTHONDONTWRITEBYTECODE=1 /Users/linsuchang/Desktop/work/chiralium/backend/.venv/bin/python -m app.services.pdf_to_word.model_eval_runner --regression-summary --archive-root /Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-archive --hybrid-e2e-root /Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/hybrid-e2e-validation --output-dir /private/tmp/chiralium-p2-regression-review --run-label current-five-sample-baseline-review
```

结果：成功生成 `/private/tmp/chiralium-p2-regression-review/current-five-sample-baseline-review`，说明入口逻辑可复现。

## 非阻塞提示

当前入口是“统一摘要层”，不是“自动采样层”。它已经把 manifest schema、golden/meta 聚合和五样例基线入口搭好，但不会自动引入新的真实 PDF 样本；后续要扩大样本，仍需 QA/owner 在同一 schema 下补充 `source_pdf`、采样来源和人工抽检结论。

## 下一步

建议进入 QA 验证。

审查时间：2026-05-18T09:46:05+08:00
