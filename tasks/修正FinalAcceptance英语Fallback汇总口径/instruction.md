# 任务：修正FinalAcceptance英语Fallback汇总口径

## 任务类型
development

## 目标
修正 FinalAcceptance 中英语八年级样例的 fallback 页口径，使其与 authoritative archive 的事实一致，并同步更新 human visual acceptance 报告中的对应描述。

## 任务边界
- 只处理 FinalAcceptance 汇总与报告中的英语八年级 fallback 口径，不改动其他学科样例结论。
- 以 authoritative archive 的现有事实为准，不重新推翻已核验结论。
- 仅在 write_scope 内修改指定文件。

## 输入事实
- /Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-archive/profiles/hybrid_experimental/英语八年级/validator-report.json
- /Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-archive/profiles/hybrid_experimental/英语八年级/warnings.json
- /Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-archive/profiles/hybrid_experimental/英语八年级/visual_similarity.json
- /Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-acceptance/final_acceptance_summary.json
- /Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-acceptance/final_human_visual_acceptance_report.md

## 约束
- write_scope: ['/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-acceptance/final_acceptance_summary.json', '/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-acceptance/final_human_visual_acceptance_report.md']
- read_only: false
- 依赖上游任务: 无
- target_environment: dev
- execution_mode: dev
- owner_approval_required: false

## 交付物
1. 修正后的 FinalAcceptance 英语八年级 fallback 口径。
2. 同步后的 human visual acceptance 报告说明。
3. 结果说明中明确记录修改点与依据。

## 验收标准
1. final_acceptance_summary.json 中英语样例的 fallback 页码与 authoritative archive 一致。
2. final_human_visual_acceptance_report.md 中对英语样例的描述与汇总口径一致。
3. 不引入其他学科的口径变更。

## 下游动作
完成后解锁英语专项复验与最终全学科95重跑。
