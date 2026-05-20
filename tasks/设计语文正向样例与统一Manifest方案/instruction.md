# 任务：设计语文正向样例与统一Manifest方案

## 任务类型
design

## 目标
给出语文学科正向样例的选样、sample_key、positive/negative 角色划分与 unified manifest 方案，确保不再用 negative_guard 替代语文正向95分母。

## 任务边界
- 必须保留 chinese_grade5 作为 negative_guard，不得直接改造成正向样例。
- 需要新增至少一个语文正向长文/作文/阅读样例设计，并给出进入 positive_candidate 的标准。
- 方案需兼容全学科 manifest，不只解决单一样例命名。

## 输入事实
- /Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-archive/reports/PDF转Word阶段性生成样例与差异分析报告.md
- /Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-archive/reports/PDF转Word当前阶段与目标差距及优化计划.md
- /Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-acceptance/final_acceptance_summary.json
- /Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-acceptance/final_human_visual_acceptance_report.md
- /Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-archive/profiles/apple_baseline/语文五年级
- /Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-archive/profiles/hybrid_experimental/语文五年级

## 约束
- write_scope: ['/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-archive/reports/语文正向样例与统一Manifest方案.md', '/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-archive/reports/语文正向样例与统一Manifest方案.json']
- read_only: false
- 依赖上游任务: 无
- target_environment: dev
- execution_mode: dev
- owner_approval_required: false

## 交付物
1. 语文正向样例与统一Manifest方案 Markdown。
2. JSON 摘要，包含 sample_key、角色、资格字段、迁移策略与风险。

## 验收标准
1. 明确至少一个语文正向样例候选与其 positive_candidate 判定依据。
2. 明确 chinese_grade5 仍为 negative_guard，不能混入正向95分母。
3. 统一 manifest 字段能被后续实现任务直接采用。

## 下游动作
完成后解锁语文正向样例实现与 FinalAcceptance 门禁升级。
