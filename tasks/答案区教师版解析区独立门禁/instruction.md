# 任务：答案区教师版解析区独立门禁

## 任务类型
开发 / P1 答案区专项

## 目标
把答案区、教师版、解析区从当前 final fidelity 口径中单独拆出来，建立是否纳入、如何计分、如何 veto 的独立门禁。

## 任务边界
- 本任务不允许继续把 answer_area expected=0 的旧逻辑误读为“已覆盖答案区”。
- 必须兼顾 student / teacher / answer / analysis 变体。
- 与全学科样例分层保持一致。

## 输入事实
- 架构整改意见（全学科）：`/Users/linsuchang/Desktop/work/my-agent-teams/.runtime/worktrees/chiralium/PDF-Word-205980b6/artifacts/pdf2word/final-archive/reports/PDF转Word视觉门禁全学科整改意见.md`
- 架构整改任务结果：`/Users/linsuchang/Desktop/work/my-agent-teams/tasks/制定PDF转Word视觉门禁整改意见/result.json`
- 当前高优先级问题说明：`/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-archive/reports/PDF转Word-五下科学样例复核与95门禁偏差说明.md`
- 代表样例：原 PDF `/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-output-samples/PDF转Word门禁样例-五下科学-source.pdf`；门禁 DOCX `/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-output-samples/PDF转Word门禁样例-五下科学-hybrid_experimental-output.docx`
- 当前统一前提：**不能只盯科学学科，必须把科学、数学、语文、英语统一纳入门禁与样例口径。**
- 当前已知边界：可以保留 `quality/hybrid_async` 工程门禁通过；不可继续宣称“全学科人工视觉 95% 已达成”。
- 本任务前置依赖：建立PDF转Word最终门禁样例清单与分层治理

## 写入范围
仅允许修改以下路径：
  - `/Users/linsuchang/Desktop/work/chiralium/backend/app/services/pdf_to_word/answer_section_gate.py`
  - `/Users/linsuchang/Desktop/work/chiralium/backend/tests/test_pdf_to_word_answer_section_gate.py`
  - `/Users/linsuchang/Desktop/work/chiralium/backend/tests/fixtures/pdf_to_word/answer_section`
  - `/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-archive/reports/PDF转Word答案区教师版解析区独立门禁说明.md`

## 约束
- 要明确哪些场景仍不纳入当前 final fidelity。
- 若纳入专项门禁，必须可产生独立的通过/不通过结论。
- 不能影响当前工程门禁的既有稳定性。

## 交付物
1. answer section gate 代码与测试。
2. 专项说明文档。
3. 与主线门禁的边界说明。

## 验收标准
- student/teacher/answer/analysis 边界清楚。
- 答案区专项结论不再混入主线 final fidelity。
- 结果可被 PM 单独说明。

## 下游动作
完成后，PM 再决定是否把答案区/教师版能力纳入对外能力说明。
