# 任务：复验语文正向样例进入全学科95分母

## 任务类型
verification

## 目标
确认语文学科已有至少一个合格 positive_candidate，且 negative_guard 没有被错误计入全学科95正向分母。

## 任务边界
- 只做 read-only 复验与结论记录。
- 若 manifest 角色、资格字段或 sample_key 仍混乱，必须直接阻塞。

## 输入事实
- /Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-archive/reports/PDF转Word阶段性生成样例与差异分析报告.md
- /Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-archive/reports/PDF转Word当前阶段与目标差距及优化计划.md
- /Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-acceptance/final_acceptance_summary.json
- /Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-acceptance/final_human_visual_acceptance_report.md
- /Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-archive/reports/语文正向样例与统一Manifest方案.md

## 约束
- write_scope: []
- read_only: true
- 依赖上游任务: ['实现语文正向长文作文样例与统一Manifest']
- target_environment: dev
- execution_mode: dev
- owner_approval_required: false

## 交付物
1. result.json 中给出语文样例角色与95资格复验结论。

## 验收标准
1. 至少一个语文样例 eligible_for_human_visual_95=true。
2. chinese_grade5 仍保持 negative_guard，不计入正向分母。

## 下游动作
完成后作为全学科95重跑前置输入。
