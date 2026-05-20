# 任务：科学实验页表格与图片区关键区域视觉门禁

## 任务类型
开发 / P0 科学专项

## 目标
针对科学实验混合页，建立表格区、图片区、题干邻接关系的关键区域视觉门禁，解决“五下科学看着不像 95% 但总分过线”的核心问题。

## 任务边界
- 本任务只做科学实验页专项，不替代全学科共性 render pair / veto。
- 必须兼容后续更大样本，不把规则写死为某一页坐标。
- 聚焦关键区域分与 veto，不另起新的总分体系。

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
  - `/Users/linsuchang/Desktop/work/chiralium/backend/app/services/pdf_to_word/science_visual_gate.py`
  - `/Users/linsuchang/Desktop/work/chiralium/backend/tests/test_pdf_to_word_science_visual_gate.py`
  - `/Users/linsuchang/Desktop/work/chiralium/backend/tests/fixtures/pdf_to_word/visual_similarity/science`

## 约束
- 必须覆盖表格外框/行列观感、图片与题干绑定、实验记录区邻接关系。
- 关键区域失败时能返回明确 veto 或低分原因。
- 不能只看 w:tbl 或 media 是否存在。

## 交付物
1. science 专项视觉 gate。
2. 对应 fixture 与测试。
3. result.json 中说明如何对接公共 visual_similarity / veto 链路。

## 验收标准
- 五下科学类样例可产出关键区域分。
- 实验表格/图片区关键失败会被识别。
- 实现可复用于更多科学页型。

## 下游动作
完成后，qa-1 将把科学实验页纳入最终人工视觉复验的关键样例。
