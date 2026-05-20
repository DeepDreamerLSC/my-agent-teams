# 任务：复验正向样例视觉证据链与FinalArchive门禁

## 任务类型
verification

## 目标
复验 4 个正向样例的 canonical visual evidence 是否已完整落盘，并确认 FinalArchive 不会在证据缺失时误判可恢复95。

## 任务边界
- 只做 read-only 复验与结论记录，不修改业务代码。
- 若发现缺 artifact、命名不一致、样例漏挂，必须直接判失败/阻塞。

## 输入事实
- /Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-archive/reports/PDF转Word阶段性生成样例与差异分析报告.md
- /Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-archive/reports/PDF转Word当前阶段与目标差距及优化计划.md
- /Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-acceptance/final_acceptance_summary.json
- /Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-acceptance/final_human_visual_acceptance_report.md

## 约束
- write_scope: []
- read_only: true
- 依赖上游任务: ['补齐四个正向样例视觉证据链并接入FinalArchive']
- target_environment: dev
- execution_mode: dev
- owner_approval_required: false

## 交付物
1. result.json 中逐样例列出 artifact presence 结论。
2. 明确记录 FinalArchive / final_human_visual_acceptance 对缺失 artifact 的处理结果。

## 验收标准
1. 4 个 positive_candidate 的 evidence presence 结果可追溯。
2. 任何样例缺任一 canonical artifact 时，结论必须是 NO-GO 或 blocked，不能给出模糊通过。

## 下游动作
完成后作为全学科95重跑的前置验证输入。
