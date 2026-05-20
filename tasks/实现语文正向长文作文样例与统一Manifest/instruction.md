# 任务：实现语文正向长文作文样例与统一Manifest

## 任务类型
development

## 目标
按架构方案真正落地语文正向样例，并把 unified manifest 接到当前样例体系，使语文学科拥有可参与全学科95复验的 positive_candidate。

## 任务边界
- 不得改写 chinese_grade5 negative_guard 的身份。
- 新增的语文正向样例必须可被后续 human visual 复验链路消费。
- 如需新增 sample_key、manifest 字段或夹具，必须与方案文档保持一致。

## 输入事实
- /Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-archive/reports/PDF转Word阶段性生成样例与差异分析报告.md
- /Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-archive/reports/PDF转Word当前阶段与目标差距及优化计划.md
- /Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-acceptance/final_acceptance_summary.json
- /Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-acceptance/final_human_visual_acceptance_report.md
- /Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-archive/reports/语文正向样例与统一Manifest方案.md

## 约束
- write_scope: ['/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-output-samples', '/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-archive/profiles/hybrid_experimental/语文正向样例', '/Users/linsuchang/Desktop/work/chiralium/backend/tests/fixtures/pdf_to_word/chinese_positive']
- read_only: false
- 依赖上游任务: ['设计语文正向样例与统一Manifest方案']
- target_environment: dev
- execution_mode: dev
- owner_approval_required: false

## 交付物
1. 语文正向样例相关 artifacts / fixtures / manifest 变更。
2. result.json 中明确新增样例 key、角色、资格字段与使用路径。

## 验收标准
1. 至少一个语文正向样例进入 positive_candidate 体系。
2. negative_guard 与 positive_candidate 在 manifest 中有清晰区分。
3. 后续任务可直接用该样例进入全学科95复验。

## 下游动作
完成后解锁语文正向样例复验与 FinalAcceptance 强依赖升级。
