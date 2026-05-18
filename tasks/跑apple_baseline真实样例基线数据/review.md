# 审查说明：跑apple_baseline真实样例基线数据

## 结论

**通过（approve）**。本次任务已按要求完成 5 个真实 PDF 样例的 `apple_baseline` 跑批，且产物完整：

- 每个样例目录均包含 `pages.jsonl`、`metrics.json`、`warnings.json`、`output.docx`
- 已生成 `baseline_summary.json`
- `failed_samples` 为空，5 个样例全部完成

## 审查范围

- `instruction.md`
- `result.json`
- `artifacts/pdf2word/model-eval/20260514-144102/apple_baseline/baseline_summary.json`
- 5 个样例目录下的 `metrics.json / pages.jsonl / warnings.json / output.docx`

## 复核结果

- 运行目录存在且结构符合任务说明。
- `baseline_summary.json` 中包含：
  - `question_sequence`
  - `block_count / image_candidate_count / formula_candidate_count`
  - `total_seconds / per_page_seconds`
  - `failed_samples`
- 5 个样例的 `metrics.json` 与 summary 中对应字段对齐。
- 5 个 `output.docx` 均存在，且可被识别为合法 docx 包。
- `sample_count = 5`，`failed_samples = []`，符合“全部跑完”的验收要求。

## 审查中做的核验

1. 检查 artifacts 目录下 5 个样例子目录均存在且文件齐全。
2. 校验 `baseline_summary.json` 与各样例 `metrics.json` 的 `block_count / page_count / total_seconds` 一致。
3. 校验每个 `output.docx` 均可打开 zip 结构并包含 `word/document.xml`。

## 非阻塞建议

1. 当前 `question_sequence` 字段已成功抽取，但可以看出仍混有明显 OCR/版面噪声（如 `0`、`00`、`66`、`150` 等），建议后续把它作为“题号抽取质量观测项”，而不是直接作为结构化结论。
2. 本次 `total_seconds` 包含首次 PaddleOCR 模型下载/缓存成本，因此更接近冷启动基线；若后续要做性能对比，建议再补一轮热启动复跑数据。

## 下一步

建议进入 QA 验证；之后可继续作为 GLM-OCR / MinerU / 其他适配器横评的基线对照。

审查时间：2026-05-14T14:52:55+08:00
