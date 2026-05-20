# 任务：在最终Fidelity报告加入页级与区域级Veto

## 任务类型
开发 / P0 no-go Veto 框架

## 目标
把“总体分高但关键页/关键区域明显失败仍应 no-go”的规则落到最终 reporter，使工程门禁与人工视觉门禁边界真正可执行。

## 任务边界
- 本任务聚焦 final fidelity reporter 的 veto 消费与 no-go 语义，不负责生成 render pair。
- 允许先行冻结 reporter 所需消费 contract、失败 taxonomy、测试骨架；等 C-04 完成后补齐最终接线。
- 必须覆盖科学/数学/语文/英语共性 veto，而不是只为科学样例打补丁。

## 输入事实
- 架构整改意见（全学科）：`/Users/linsuchang/Desktop/work/my-agent-teams/.runtime/worktrees/chiralium/PDF-Word-205980b6/artifacts/pdf2word/final-archive/reports/PDF转Word视觉门禁全学科整改意见.md`
- 架构整改任务结果：`/Users/linsuchang/Desktop/work/my-agent-teams/tasks/制定PDF转Word视觉门禁整改意见/result.json`
- 当前高优先级问题说明：`/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-archive/reports/PDF转Word-五下科学样例复核与95门禁偏差说明.md`
- 代表样例：原 PDF `/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-output-samples/PDF转Word门禁样例-五下科学-source.pdf`；门禁 DOCX `/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-output-samples/PDF转Word门禁样例-五下科学-hybrid_experimental-output.docx`
- 当前统一前提：**不能只盯科学学科，必须把科学、数学、语文、英语统一纳入门禁与样例口径。**
- 当前已知边界：可以保留 `quality/hybrid_async` 工程门禁通过；不可继续宣称“全学科人工视觉 95% 已达成”。
- 本任务前置依赖：升级visual_similarity为真实渲染对视觉证据

## 写入范围
仅允许修改以下路径：
  - `/Users/linsuchang/Desktop/work/chiralium/backend/app/services/pdf_to_word/model_eval_runner.py`
  - `/Users/linsuchang/Desktop/work/chiralium/backend/app/services/pdf_to_word/fidelity_veto.py`
  - `/Users/linsuchang/Desktop/work/chiralium/backend/tests/test_pdf_to_word_fidelity_report.py`
  - `/Users/linsuchang/Desktop/work/chiralium/backend/tests/fixtures/pdf_to_word/fidelity/veto`

## 约束
- 任一 P0 veto 触发时，即使 overall_score >= 95 也必须 no-go。
- 至少覆盖：关键页读序崩坏、表格视觉邻接严重错位、公式/图形区关键失真、英语阅读/选项区关键失真、关键页 fallback 无法接近原 PDF。
- 不能放宽 default sync 与既有工程结构门禁。

## 交付物
1. reporter veto 消费逻辑。
2. 失败 taxonomy / fixture / 测试。
3. result.json 中写清楚后续 QA 如何观察 no-go 原因。

## 验收标准
- P0 veto 能让 final report 明确 no-go。
- 测试可证明“总分高但关键页失败”时不会误通过。
- 设计与实现都面向全学科，不局限于单一 science 页。

## 下游动作
完成后，qa-1 将基于新 reporter 与 visual_similarity artifact 重跑全学科人工视觉 95 判定。
