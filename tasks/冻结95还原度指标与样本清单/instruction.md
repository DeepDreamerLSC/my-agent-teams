# 任务：冻结95还原度指标与样本清单

## 任务类型
质量/验证基线冻结

## 目标
基于 2026-05-18 晚间更新的三份路线文档，冻结一版可机读的 95% 还原度评分维度、权重和样本清单，作为后续 DOCX gate、表格 gate、最终 fidelity report 的共同事实源。

## 任务边界
- 只允许修改 `backend/tests/fixtures/pdf_to_word/fidelity/` 与 `backend/tests/test_pdf_to_word_fidelity_manifest.py`。
- 本任务只冻结 manifest / schema / fixture / baseline 说明，不改生产转换链路。
- 不要新增“现状已经达到 95%”之类结论；只能把已有事实结构化落盘。

## 输入事实
- 主要输入：
  - `/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-archive/reports/95还原度与Word表格验收路线.md`
  - `/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-archive/reports/后续技术路线.md`
  - `/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-archive/reports/端到端技术链路.md`
- 现阶段路线明确：95% 是 quality/hybrid_async 模式下的最终验收口径，不是默认同步 SLA。
- 样本至少要覆盖：数学试卷、英语八年级、五下科学、语文五年级负样例，以及表格/答案区/图片归属扩展位。

## 约束
- 权重与维度必须与路线文档保持一致，不得自行增删主维度。
- manifest 里要明确区分：当前样本、负样例、后续待补的 table-heavy / multi-column / answer-area 样本。
- 产物必须可被后续测试/脚本直接消费；不要只写自然语言说明。

## 交付物
1. 一份可机读的 fidelity manifest / schema fixture（写入 `backend/tests/fixtures/pdf_to_word/fidelity/`）。
2. 一份针对 manifest 结构与关键样本字段的测试文件（`backend/tests/test_pdf_to_word_fidelity_manifest.py`）。
3. 在测试或 fixture 中明确当前各维度权重、P0 阻断项和样本类别。

## 验收标准
- fixture 能表达 95% 八个主维度、权重、P0 阻断项与样本类别。
- 至少覆盖现有 4 个正/混合样例 + 1 个负样例，且字段不自相矛盾。
- 测试能验证 manifest 基本结构、权重总和、关键样本标签和负样例标记。
- 不越界修改生产代码。

## 下游动作
完成后，PM 将基于该 manifest 推进 DOCX 表格门禁、表格夹具与最终 fidelity report 任务。
