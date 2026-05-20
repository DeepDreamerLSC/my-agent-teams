# 任务：建立PDF转Word最终门禁样例清单与分层治理

## 任务类型
质量 / P0 样例治理

## 目标
把 final-gated / variant / debug-or-authoritative 三层样例彻底分开，形成唯一 source→output 配对清单，避免再拿错样例。

## 任务边界
- 本任务以 manifest、分层目录说明、样例口径治理为主，不改后端算法。
- 必须覆盖科学、数学、语文、英语，以及答案区/教师版相关变体。
- 若发现当前 final-output-samples 中样例命名或层级不足，可新增 manifest 与说明文件，不强制迁移大体量历史产物。

## 输入事实
- 架构整改意见（全学科）：`/Users/linsuchang/Desktop/work/my-agent-teams/.runtime/worktrees/chiralium/PDF-Word-205980b6/artifacts/pdf2word/final-archive/reports/PDF转Word视觉门禁全学科整改意见.md`
- 架构整改任务结果：`/Users/linsuchang/Desktop/work/my-agent-teams/tasks/制定PDF转Word视觉门禁整改意见/result.json`
- 当前高优先级问题说明：`/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-archive/reports/PDF转Word-五下科学样例复核与95门禁偏差说明.md`
- 代表样例：原 PDF `/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-output-samples/PDF转Word门禁样例-五下科学-source.pdf`；门禁 DOCX `/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-output-samples/PDF转Word门禁样例-五下科学-hybrid_experimental-output.docx`
- 当前统一前提：**不能只盯科学学科，必须把科学、数学、语文、英语统一纳入门禁与样例口径。**
- 当前已知边界：可以保留 `quality/hybrid_async` 工程门禁通过；不可继续宣称“全学科人工视觉 95% 已达成”。
- 本任务前置依赖：统一PDF转Word95门禁命名与对外口径

## 写入范围
仅允许修改以下路径：
  - `/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-output-samples/final-gated-manifest.json`
  - `/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-output-samples/README.final-gated.md`
  - `/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-archive/reports/PDF转Word样例分层治理说明.md`

## 约束
- 每个 final-gated 样例必须有唯一 source_pdf 与 output_docx 配对。
- variant/debug/authoritative 产物必须显式标注为不可直接用于 95 宣称。
- 输出必须给后续 render pair、rubric、重跑判定直接消费。

## 交付物
1. final-gated-manifest.json。
2. 样例分层 README/说明。
3. 一份说明当前哪些文件能用于最终视觉门禁、哪些只能用于调试的治理文档。

## 验收标准
- PM 不会再把 student/teacher/authoritative 变体误认为 final-gated 样例。
- final-gated 样例清单至少能覆盖科学、数学、语文、英语四类。
- 后续任务可直接引用该 manifest，不需要再次人工口头解释。

## 下游动作
完成后，dev-2 的 render pair 生成器与 qa-1 的人工视觉 rubric 将统一消费该清单。
