# 任务：升级FinalAcceptance为HumanVisual强依赖门禁

## 任务类型
development

## 目标
把 FinalAcceptance 升级为 HumanVisual 强依赖门禁：缺任一 canonical artifact、缺语文正向样例、或 subject/sample manifest 不一致时，必须明确输出 NO-GO。

## 任务边界
- 不要放宽默认同步边界，也不要把工程 PASS 误升格为人工95 PASS。
- 必须统一 final_acceptance_summary 与 final_human_visual_acceptance 的 manifest 口径。

## 输入事实
- /Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-archive/reports/PDF转Word阶段性生成样例与差异分析报告.md
- /Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-archive/reports/PDF转Word当前阶段与目标差距及优化计划.md
- /Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-acceptance/final_acceptance_summary.json
- /Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-acceptance/final_human_visual_acceptance_report.md
- /Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-archive/reports/PDF转Word当前阶段与目标差距及优化计划.md

## 约束
- write_scope: ['/Users/linsuchang/Desktop/work/chiralium/backend/app/services/pdf_to_word/model_eval_runner.py', '/Users/linsuchang/Desktop/work/chiralium/backend/tests/test_pdf_to_word_fidelity_report.py', '/Users/linsuchang/Desktop/work/chiralium/backend/tests/test_pdf_to_word_fidelity_manifest.py', '/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-acceptance']
- read_only: false
- 依赖上游任务: ['补齐四个正向样例视觉证据链并接入FinalArchive', '实现语文正向长文作文样例与统一Manifest']
- target_environment: dev
- execution_mode: dev
- owner_approval_required: false

## 交付物
1. FinalAcceptance / HumanVisual 汇总逻辑与报告口径更新。
2. result.json 中写明 PASS/NO-GO 双口径的触发条件。

## 验收标准
1. 缺 artifact 或缺语文正向样例时，FinalAcceptance 不能再给出可恢复95的误导性结论。
2. final_acceptance_summary 与 human_visual_acceptance 的 sample/subject 口径一致。

## 下游动作
完成后解锁英语事实统一与最终全学科95重跑。
