# 任务：重跑全学科人工视觉95判定

## 任务类型
质量 / P0 最终复验

## 目标
在 render pair、真实 visual artifact、reporter veto、人工 rubric 全部就位后，给出全学科人工视觉 95 的新 go/no-go。

## 任务边界
- 本任务以复验与结论为主，不补代码。
- 结论必须同时呈现工程门禁分、人工视觉分、veto 列表。
- 必须覆盖科学、数学、语文、英语，不允许以单学科替代全结论。

## 输入事实
- 架构整改意见（全学科）：`/Users/linsuchang/Desktop/work/my-agent-teams/.runtime/worktrees/chiralium/PDF-Word-205980b6/artifacts/pdf2word/final-archive/reports/PDF转Word视觉门禁全学科整改意见.md`
- 架构整改任务结果：`/Users/linsuchang/Desktop/work/my-agent-teams/tasks/制定PDF转Word视觉门禁整改意见/result.json`
- 当前高优先级问题说明：`/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-archive/reports/PDF转Word-五下科学样例复核与95门禁偏差说明.md`
- 代表样例：原 PDF `/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-output-samples/PDF转Word门禁样例-五下科学-source.pdf`；门禁 DOCX `/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-output-samples/PDF转Word门禁样例-五下科学-hybrid_experimental-output.docx`
- 当前统一前提：**不能只盯科学学科，必须把科学、数学、语文、英语统一纳入门禁与样例口径。**
- 当前已知边界：可以保留 `quality/hybrid_async` 工程门禁通过；不可继续宣称“全学科人工视觉 95% 已达成”。
- 本任务前置依赖：升级visual_similarity为真实渲染对视觉证据、在最终Fidelity报告加入页级与区域级Veto、建立全学科人工视觉复核Rubric与基线报告

## 写入范围
仅允许修改以下路径：
  - `/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-acceptance/final_human_visual_acceptance_report.md`
  - `/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-acceptance/final_human_visual_acceptance.json`
  - `/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-archive/reports/PDF转Word全样本人工视觉95判定结论.md`

## 约束
- 不放宽 threshold=95。
- 如任一 P0 veto 触发，必须明确 no-go。
- 若答案区/教师版不在本轮口径内，必须写清楚不纳入口径。

## 交付物
1. 最终人工视觉 95 判定报告。
2. 结构化结论 JSON。
3. PM 可直接用于收口或继续整改的话术建议。

## 验收标准
- 结论清楚说明 go/no-go。
- 报告包含学科覆盖、页级/区域级低分与 veto 原因。
- PM 可直接据此决定是否恢复“人工视觉 95”宣称。

## 下游动作
完成后，PM 将根据新结论决定 PDF→Word 是否恢复人工视觉 95 收口声明。
