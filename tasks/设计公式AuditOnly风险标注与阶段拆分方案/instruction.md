# 任务：设计公式AuditOnly风险标注与阶段拆分方案

## 任务类型
design

## 目标
明确公式/符号链路在当前阶段继续维持 audit-only 的风险标注方式，并拆出后续“可编辑公式”阶段目标。

## 任务边界
- 本任务不把公式纳入当前全学科95恢复主目标。
- 必须明确什么条件下才允许进入下一阶段的可编辑公式实现。

## 输入事实
- /Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-archive/reports/PDF转Word阶段性生成样例与差异分析报告.md
- /Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-archive/reports/PDF转Word当前阶段与目标差距及优化计划.md
- /Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-acceptance/final_acceptance_summary.json
- /Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-acceptance/final_human_visual_acceptance_report.md
- /Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/phase4-formula-baseline/summary.json
- /Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/p1-formula-crop/formula_crop_failure_summary.md

## 约束
- write_scope: ['/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-archive/reports/公式AuditOnly风险标注与阶段拆分方案.md', '/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-archive/reports/公式AuditOnly风险标注与阶段拆分方案.json']
- read_only: false
- 依赖上游任务: 无
- target_environment: dev
- execution_mode: dev
- owner_approval_required: false

## 交付物
1. 公式 audit-only 风险标注与阶段拆分方案文档。
2. JSON 摘要，列出进入下一阶段的门禁条件。

## 验收标准
1. 明确当前阶段为什么不能把公式计入恢复95主口径。
2. 明确后续可编辑公式阶段的输入、门禁和退出条件。

## 下游动作
完成后解锁公式实验任务，但不阻塞当前95恢复主线。
