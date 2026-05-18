# 审查说明：归档横评样例到artifacts目录

## 结论

**通过（approved）。**

这轮交付满足任务目标和边界：

- `artifacts/pdf2word/final-archive/` 已创建完成
- 目录结构包含 `profiles/`、`reports/`、`README.md`、`archive_manifest.json`
- 6 个 profile 已归档，`glm_46v_flash` 以 blocked 形式占位
- 样例命名已统一为：
  - `五下科学`
  - `数学八年级`
  - `数学试卷`
  - `英语八年级`
  - `语文五年级`

我核对了归档实物、README 和 manifest，整体是自洽的。

## 验收核对

验收标准 1：**6 个 profile 的数据均已归档**

- `apple_baseline`
- `mineru_lite`
- `mineru_full`
- `glm_ocr`
- `paddleocr_vl`
- `qwen3_vl_8b`

都已在 `profiles/` 下落盘。

验收标准 2：**目录结构一致**

- 各 profile 都有 `profile_manifest.json`
- 各样例目录都有 `source_manifest.json`
- 完整样例包含 `output.docx / metrics.json / pages.jsonl / warnings.json`

验收标准 3：**报告文档已收录**

已看到：

- `横评最终报告.md`
- `候选增强可行性报告.md`
- `hybrid管线设计.md`
- 可用的 `*_comparison_report.json`

验收标准 4：**README 有完整说明**

README 已明确说明：

- 归档来源
- 只复制不修改原始数据
- PaddleOCR-VL 缺“数学试卷”
- MinerU full 缺 5/5 `output.docx`
- GLM-4.6V 当前 blocked

## 说明

这轮有数据缺口，但它们都来自**源数据本身**，不是归档任务遗漏：

- `mineru_full` 原始 run 缺 5/5 `output.docx`
- `paddleocr_vl` 原始 run 缺“数学试卷”
- `glm_46v_flash` 当前无可归档产物

归档侧已经按 instruction 要求保留空目录、manifest 和说明，没有伪造文件，这点是对的。

另外，`example/扫描件 /docx横评对比/` 下的手工 DOCX 本轮没有额外复制进 `final-archive`，但 README 已解释本次优先以 `model-eval` 原始 runner 产物为归档基线。按当前任务描述，这不构成阻塞问题。

审查时间：2026-05-15T21:51:42+08:00
