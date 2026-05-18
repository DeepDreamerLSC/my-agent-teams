# 审查说明：提取图片公式候选并验证增强可行性

## 结论

**通过（approve）**。

这份可行性报告已经完成了任务要求的主线交付：覆盖 5 个样例整体分析，给出了量化的归属匹配统计、逐样例判断、增强模拟结论，以及可以直接给 arch-1 使用的合并策略建议。核心结论也和上游 artifacts 基本一致：

- `MinerU full` 是当前更稳的候选源
- 图片/表格候选增强可行，但必须先判定题号区域并做过滤
- `formula_candidate` 暂不适合直接并回
- `语文五年级` 这类无法稳定提取题号区域的样例应直接跳过 question-bound merge

## 复核要点

- 报告结构和 instruction.md 对齐：
  - 候选统计
  - 归属匹配结果
  - 增强模拟结论
  - 合并策略建议
- 总体统计不是拍脑袋：
  - MinerU full 的候选总数 74，与上游 48 image + 8 table + 18 formula_candidate 对得上
  - PaddleOCR-VL 的候选总数 58，与上游 48 image + 10 table 对得上
- 对 PaddleOCR-VL 缺失“数学试卷” artifacts 的限制有明确说明，没有把 4/5 数据伪装成完整覆盖

## 非阻塞提示

1. `task.json.write_scope` 为空，但 instruction 又要求产出 `design/pdf2word/` 下的报告，这属于任务定义本身的治理不一致。
2. `result.json` 已记录 `report_path` / `output_files`，但 `modified_files` 仍为空数组，审计口径略有不一致。

这两点不影响本轮报告内容质量，但建议 PM 后续把同类 investigation 任务的 design 文档路径写进 write_scope，并让 result.json 的文件清单保持一致。

## 建议动作

建议 PM 直接把这份报告交给 arch-1 用于 hybrid_experimental 管线设计，不需要因为 reviewer 发现新的内容问题而返工。

审查时间：2026-05-15T17:59:14+08:00
