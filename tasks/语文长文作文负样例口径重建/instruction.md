# 任务：语文长文作文负样例口径重建

## 任务类型
设计 / P1 语文样例口径

## 目标
重建语文长文/作文/负样例的口径，明确哪些只是 negative/document fallback，哪些若要参与 95 宣称需要补充正样例。

## 任务边界
- 本任务以口径、样例分类、后续建议为主，不改后端算法。
- 必须把“语文不应被忽略”写清楚。
- 要与 final-gated manifest 和全学科 rubric 对齐。

## 输入事实
- 架构整改意见（全学科）：`/Users/linsuchang/Desktop/work/my-agent-teams/.runtime/worktrees/chiralium/PDF-Word-205980b6/artifacts/pdf2word/final-archive/reports/PDF转Word视觉门禁全学科整改意见.md`
- 架构整改任务结果：`/Users/linsuchang/Desktop/work/my-agent-teams/tasks/制定PDF转Word视觉门禁整改意见/result.json`
- 当前高优先级问题说明：`/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-archive/reports/PDF转Word-五下科学样例复核与95门禁偏差说明.md`
- 代表样例：原 PDF `/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-output-samples/PDF转Word门禁样例-五下科学-source.pdf`；门禁 DOCX `/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-output-samples/PDF转Word门禁样例-五下科学-hybrid_experimental-output.docx`
- 当前统一前提：**不能只盯科学学科，必须把科学、数学、语文、英语统一纳入门禁与样例口径。**
- 当前已知边界：可以保留 `quality/hybrid_async` 工程门禁通过；不可继续宣称“全学科人工视觉 95% 已达成”。
- 本任务前置依赖：建立PDF转Word最终门禁样例清单与分层治理、建立全学科人工视觉复核Rubric与基线报告

## 写入范围
仅允许修改以下路径：
  - `/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-output-samples/chinese-samples-manifest.json`
  - `/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-archive/reports/PDF转Word语文样例口径重建.md`

## 约束
- negative/document_fallback 不得再被误读为已达 95 的正样例。
- 如当前无合格正样例，必须明确提出补样或延期纳入口径。
- 输出要能被 PM 直接用于对外说明。

## 交付物
1. 语文样例口径重建文档。
2. 语文样例 manifest。
3. 后续是否纳入 95 宣称的建议。

## 验收标准
- 语文样例边界清楚，不再混用 negative 与 final-gated。
- 作文/长文类页型有单独说明。
- PM 能据此统一全学科口径。

## 下游动作
完成后，PM 再决定语文是否进入本轮人工视觉 95 宣称范围。
