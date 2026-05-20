# 任务：实验公式AuditOnly风险标注与可编辑公式阶段拆分

## 任务类型
development

## 目标
按方案做最小实验，验证公式 audit-only 风险标注和下一阶段拆分是否可落地，但不把公式链路并入当前95恢复主线。

## 任务边界
- 保持公式链路 audit-only / merge-disabled。
- 只做风险标注与阶段拆分实验，不把公式能力对外升级为已可用。

## 输入事实
- /Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-archive/reports/PDF转Word阶段性生成样例与差异分析报告.md
- /Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-archive/reports/PDF转Word当前阶段与目标差距及优化计划.md
- /Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-acceptance/final_acceptance_summary.json
- /Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-acceptance/final_human_visual_acceptance_report.md
- /Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-archive/reports/公式AuditOnly风险标注与阶段拆分方案.md

## 约束
- write_scope: ['/Users/linsuchang/Desktop/work/chiralium/backend/app/services/pdf_to_word/formula_pipeline.py', '/Users/linsuchang/Desktop/work/chiralium/backend/tests/test_pdf_formula_pipeline.py', '/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/formula']
- read_only: false
- 依赖上游任务: ['设计公式AuditOnly风险标注与阶段拆分方案']
- target_environment: dev
- execution_mode: dev
- owner_approval_required: false

## 交付物
1. 公式风险标注/阶段拆分相关实验产物。
2. result.json 中说明哪些能力可以进入下一阶段，哪些仍不可放开。

## 验收标准
1. 当前阶段仍明确保持 audit-only。
2. 对下一阶段需要新增的素材化、清理、可编辑输出门禁有可执行结论。

## 下游动作
作为后续公式专项路线输入，不阻塞当前95恢复主线。
