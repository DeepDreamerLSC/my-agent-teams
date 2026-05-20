# 任务：统一PDF转Word95门禁命名与对外口径

## 任务类型
设计 / P0 口径纠偏

## 目标
把“工程 95”与“人工视觉 95”彻底拆开命名，落到最终报告、summary 与对外展示口径中，避免再出现把工程分误读成人工视觉分的情况。

## 任务边界
- 本任务只改命名、注释、口径和最终说明文档，不改算法、不重跑样本。
- 必须覆盖科学、数学、语文、英语全学科，不能只围绕五下科学样例。
- 需要把可继续宣称与暂不可宣称的话术写成可直接复用的结论。

## 输入事实
- 架构整改意见（全学科）：`/Users/linsuchang/Desktop/work/my-agent-teams/.runtime/worktrees/chiralium/PDF-Word-205980b6/artifacts/pdf2word/final-archive/reports/PDF转Word视觉门禁全学科整改意见.md`
- 架构整改任务结果：`/Users/linsuchang/Desktop/work/my-agent-teams/tasks/制定PDF转Word视觉门禁整改意见/result.json`
- 当前高优先级问题说明：`/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-archive/reports/PDF转Word-五下科学样例复核与95门禁偏差说明.md`
- 代表样例：原 PDF `/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-output-samples/PDF转Word门禁样例-五下科学-source.pdf`；门禁 DOCX `/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-output-samples/PDF转Word门禁样例-五下科学-hybrid_experimental-output.docx`
- 当前统一前提：**不能只盯科学学科，必须把科学、数学、语文、英语统一纳入门禁与样例口径。**
- 当前已知边界：可以保留 `quality/hybrid_async` 工程门禁通过；不可继续宣称“全学科人工视觉 95% 已达成”。
- 本任务前置依赖：制定PDF转Word视觉门禁整改意见

## 写入范围
仅允许修改以下路径：
  - `/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-archive/reports/PDF转Word95门禁口径与对外说明.md`
  - `/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-acceptance/final_acceptance_report.md`
  - `/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-acceptance/final_acceptance_summary.json`

## 约束
- 必须明确保留：quality/hybrid_async 工程门禁当前通过。
- 必须明确暂停：全学科人工逐页视觉 95% 已达成的宣称。
- 不得用模糊表述替代结论，必须给出一句话版和完整说明版两套口径。

## 交付物
1. 一份正式口径说明文档。
2. 对 final_acceptance_report.md / final_acceptance_summary.json 的命名与说明修订建议或直接修订。
3. 可供 PM/QA/架构师复用的对外答复模板。

## 验收标准
- 读者能一眼区分工程门禁 95 与人工视觉 95。
- 五下科学、数学、语文、英语都被纳入口径边界，不再只以单学科举例。
- 后续 QA 重跑时，最终报告不会再把工程分写成人工视觉最终结论。

## 下游动作
完成后，qa-1 与 PM 将基于新口径继续推进样例治理与真实视觉门禁实施。
