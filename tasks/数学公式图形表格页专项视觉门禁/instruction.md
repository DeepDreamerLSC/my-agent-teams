# 任务：数学公式图形表格页专项视觉门禁

## 任务类型
开发 / P0 数学专项

## 目标
针对数学公式、图形、表格、题块顺序建立专项视觉门禁，避免 formula audit-only 或 media 数量掩盖真实视觉问题。

## 任务边界
- 本任务只做数学专项关键区域，不替代共性 visual_similarity。
- 必须同时考虑公式/图形/表格/题块顺序。
- 不把某套试卷的绝对坐标写死为规则。

## 输入事实
- 架构整改意见（全学科）：`/Users/linsuchang/Desktop/work/my-agent-teams/.runtime/worktrees/chiralium/PDF-Word-205980b6/artifacts/pdf2word/final-archive/reports/PDF转Word视觉门禁全学科整改意见.md`
- 架构整改任务结果：`/Users/linsuchang/Desktop/work/my-agent-teams/tasks/制定PDF转Word视觉门禁整改意见/result.json`
- 当前高优先级问题说明：`/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-archive/reports/PDF转Word-五下科学样例复核与95门禁偏差说明.md`
- 代表样例：原 PDF `/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-output-samples/PDF转Word门禁样例-五下科学-source.pdf`；门禁 DOCX `/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-output-samples/PDF转Word门禁样例-五下科学-hybrid_experimental-output.docx`
- 当前统一前提：**不能只盯科学学科，必须把科学、数学、语文、英语统一纳入门禁与样例口径。**
- 当前已知边界：可以保留 `quality/hybrid_async` 工程门禁通过；不可继续宣称“全学科人工视觉 95% 已达成”。
- 本任务前置依赖：实现PDF与DOCX渲染对生成器、升级visual_similarity为真实渲染对视觉证据

## 写入范围
仅允许修改以下路径：
  - `/Users/linsuchang/Desktop/work/chiralium/backend/app/services/pdf_to_word/math_visual_gate.py`
  - `/Users/linsuchang/Desktop/work/chiralium/backend/tests/test_pdf_to_word_math_visual_gate.py`
  - `/Users/linsuchang/Desktop/work/chiralium/backend/tests/fixtures/pdf_to_word/visual_similarity/math`

## 约束
- formula audit-only 不能再替代视觉分。
- 图形与题干绑定、题块顺序错误要能显式暴露。
- 关键区域低分或失败要能回传给最终 veto。

## 交付物
1. math 专项视觉 gate。
2. fixture 与测试。
3. 与共性 visual_similarity/veto 的接入说明。

## 验收标准
- 数学八年级/数学试卷类样例可识别公式图形关键失真。
- 题块顺序与图文绑定异常不会被总分掩盖。
- 实现可被后续 QA 直接复验。

## 下游动作
完成后，qa-1 将把数学专项结果并入全学科人工视觉复验。
