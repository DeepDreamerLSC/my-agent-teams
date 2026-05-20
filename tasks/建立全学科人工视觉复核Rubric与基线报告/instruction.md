# 任务：建立全学科人工视觉复核Rubric与基线报告

## 任务类型
质量 / P0 人工视觉标尺

## 目标
建立科学、数学、语文、英语统一可复核的人工视觉评分表与基线报告，给“人工视觉 95”一个真实、可重复的人审标尺。

## 任务边界
- 本任务不改后端代码，以 rubric、评分表、基线报告为主。
- 可以先完成 rubric 与基线模板；如 C-03 产物稍后落地，再在同一任务内补齐页级/区域级对照示例。
- 必须显式覆盖答案区/教师版是否纳入、负样例如何标注。

## 输入事实
- 架构整改意见（全学科）：`/Users/linsuchang/Desktop/work/my-agent-teams/.runtime/worktrees/chiralium/PDF-Word-205980b6/artifacts/pdf2word/final-archive/reports/PDF转Word视觉门禁全学科整改意见.md`
- 架构整改任务结果：`/Users/linsuchang/Desktop/work/my-agent-teams/tasks/制定PDF转Word视觉门禁整改意见/result.json`
- 当前高优先级问题说明：`/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-archive/reports/PDF转Word-五下科学样例复核与95门禁偏差说明.md`
- 代表样例：原 PDF `/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-output-samples/PDF转Word门禁样例-五下科学-source.pdf`；门禁 DOCX `/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-output-samples/PDF转Word门禁样例-五下科学-hybrid_experimental-output.docx`
- 当前统一前提：**不能只盯科学学科，必须把科学、数学、语文、英语统一纳入门禁与样例口径。**
- 当前已知边界：可以保留 `quality/hybrid_async` 工程门禁通过；不可继续宣称“全学科人工视觉 95% 已达成”。
- 本任务前置依赖：建立PDF转Word最终门禁样例清单与分层治理、实现PDF与DOCX渲染对生成器

## 写入范围
仅允许修改以下路径：
  - `/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-archive/reports/PDF转Word全学科人工视觉复核Rubric.md`
  - `/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-archive/reports/PDF转Word全学科视觉基线报告.md`

## 约束
- 评分维度至少包含页级视觉、表格区、图片区、题干区、选项区、作答区/阅读区/公式图形区。
- 必须区分工程通过与人工视觉通过，不得混分。
- 不能只做单学科 rubric。

## 交付物
1. 全学科人工视觉复核 Rubric。
2. 基线报告模板或首版报告。
3. 低置信页/需慢模型或人工复核页的判定规则。

## 验收标准
- rubric 可直接被后续 QA 重跑使用。
- 科学、数学、语文、英语都各有明确评分要点。
- PM 能据此解释“为什么工程分过了但人工视觉还不能收口”。

## 下游动作
完成后，qa-1 将重跑全样本人工视觉 95 判定，并给 PM 新 go/no-go。
