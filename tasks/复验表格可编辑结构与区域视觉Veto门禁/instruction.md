# 任务：复验表格可编辑结构与区域视觉Veto门禁

## 任务类型
verification

## 目标
复验五下科学与数学八年级表格页是否同时通过结构、编辑性与关键区域视觉 veto。

## 任务边界
- 只做 read-only 复验，不改业务代码。
- 若存在结构通过但视觉不通过，必须明确判定为未达标。

## 输入事实
- /Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-archive/reports/PDF转Word阶段性生成样例与差异分析报告.md
- /Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-archive/reports/PDF转Word当前阶段与目标差距及优化计划.md
- /Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-acceptance/final_acceptance_summary.json
- /Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-acceptance/final_human_visual_acceptance_report.md

## 约束
- write_scope: []
- read_only: true
- 依赖上游任务: ['实现表格可编辑结构与区域视觉Veto联合门禁']
- target_environment: dev
- execution_mode: dev
- owner_approval_required: false

## 交付物
1. result.json 中给出科学/数学表格页联合门禁复验结论。

## 验收标准
1. 科学与数学表格页结论可追溯到结构与视觉两个维度。
2. 任何一个维度不通过都不能算表格达标。

## 下游动作
完成后作为全学科95重跑前置输入。
