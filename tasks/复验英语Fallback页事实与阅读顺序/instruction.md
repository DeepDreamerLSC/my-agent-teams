# 任务：复验英语Fallback页事实与阅读顺序

## 任务类型
verification

## 目标
复验英语八年级 fallback 页事实是否统一，阅读段落、选项区和题号顺序是否满足当前人工复核要求。

## 任务边界
- 只做 read-only 复验。
- 若事实口径仍不一致，必须直接阻塞最终全学科95重跑。

## 输入事实
- /Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-archive/reports/PDF转Word阶段性生成样例与差异分析报告.md
- /Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-archive/reports/PDF转Word当前阶段与目标差距及优化计划.md
- /Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-acceptance/final_acceptance_summary.json
- /Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-acceptance/final_human_visual_acceptance_report.md

## 约束
- write_scope: []
- read_only: true
- 依赖上游任务: ['修正英语Fallback页事实并复核阅读顺序']
- target_environment: dev
- execution_mode: dev
- owner_approval_required: false

## 交付物
1. result.json 中给出英语样例事实一致性与阅读顺序复验结论。

## 验收标准
1. fallback facts 一致。
2. 阅读顺序问题不存在未解释的残留偏差。

## 下游动作
完成后作为全学科95重跑前置输入。
