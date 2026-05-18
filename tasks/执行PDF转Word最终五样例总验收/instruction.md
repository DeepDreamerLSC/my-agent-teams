# 任务：执行 PDF 转 Word 最终五样例总验收

## 任务类型
verification

## 目标
对当前 PDF 转 Word 的**阶段性最终链路**做一次五样例总验收，输出自动化结果、人工抽检结论、已知缺口与默认发布建议，回答：当前是否可以把 PDF 转 Word 视为“阶段性端到端完成并可继续灰度/默认发布”。

## 任务边界
- 只做验收、抽检、结论归纳与报告落盘，不改主链代码。
- 输出统一写入 `artifacts/pdf2word/final-acceptance/`。
- 允许引用现有产物：`final-archive/`、`hybrid-e2e-validation/`、`phase3-paddle-quality/`、`phase4-formula-crop-eval/`、相关测试结果与人工抽检模板。
- 如果某个下游实验任务（如公式 OCR 实验）仍在进行中，可以把它记为 in-flight gap，但不能因此空等。

## 输入事实
- Hybrid 主链已打通：question-region、candidate extract/filter、merge、review、validator、ExerciseIR、DOCX 都已有闭环与回归。
- 当前默认候选已收口为 `mineru_full`，`paddleocr_vl` 不再默认常驻；formula 仍是 `audit-only / shadow-only`。
- 仍有 1 个已知非主功能 blocker：`数学试卷` Paddle 归档 provenance 契约待收口；它影响证据强度，但不等于主链功能不可运行。
- 公式专项已补齐 baseline/crop 资产，但真实 OCR 实验可能仍在并行进行。

## 约束
- write_scope 以 task.json 为准。
- 验收必须覆盖 5 个真实样例，并同时给出“自动化回归”与“人工抽检”两部分结论。
- 结论必须明确区分：
  1. 已可视为阶段性完成的能力
  2. 仍是 known gap 但不阻塞当前链路的事项
  3. 仍阻塞“整体收口/默认发布”的事项
- 最终必须给出清晰建议：
  - 可否认定 PDF 转 Word 阶段性端到端完成
  - 默认发布建议（例如继续 `apple` 默认 / `hybrid_experimental` 仅 quality 灰度 / 可否放开更广）

## 交付物
1. `final-acceptance/` 下的一份总验收报告（md 或 json，建议同时给 summary + checklist）。
2. 自动化回归记录：引用/复跑关键测试与产物检查。
3. 人工抽检结论：对 5 个样例的题号顺序、阅读顺序、图片/表格保留、公式现状、答案/作答区处理给出结论。
4. result.json：写明总体验收结论、阻塞项、建议 PM/owner 下一步如何处理。

## 验收标准
1. 报告能直接回答“距离整体端到端完成还差什么、当前是否可阶段性收口”。
2. 五样例自动化 + 人工抽检结论完整，且 known gap / blocker 分层清楚。
3. 输出明确的默认发布建议，而不是只罗列问题。
4. 不改主链代码，只沉淀验收产物。

## 下游动作
完成后进入 review-1 审查；通过后作为 PDF 转 Word 阶段性收口、默认发布建议与后续 PM 排期的直接输入。
