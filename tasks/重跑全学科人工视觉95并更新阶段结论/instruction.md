# 任务：重跑全学科人工视觉95并更新阶段结论

## 任务类型
verification

## 目标
在 P0/P1 关键整改完成后，按统一 Rubric 重跑全学科人工视觉95，并更新当前阶段结论，明确是否仍为 NO-GO。

## 任务边界
- 必须以新的 final acceptance / human visual artifacts 为准。
- 若任一学科、样例、关键页或关键区域仍有证据缺口或 P0 veto，必须维持 NO-GO。
- 本任务负责更新阶段结论，不负责额外开新功能。

## 输入事实
- /Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-archive/reports/PDF转Word阶段性生成样例与差异分析报告.md
- /Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-archive/reports/PDF转Word当前阶段与目标差距及优化计划.md
- /Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-acceptance/final_acceptance_summary.json
- /Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-acceptance/final_human_visual_acceptance_report.md
- /Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-acceptance/final_human_visual_acceptance.json

## 约束
- write_scope: ['/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-acceptance/final_acceptance_summary.json', '/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-acceptance/final_acceptance_report.md', '/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-acceptance/final_human_visual_acceptance.json', '/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-acceptance/final_human_visual_acceptance_report.md', '/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-archive/reports/PDF转Word当前阶段与目标差距及优化计划.md']
- read_only: false
- 依赖上游任务: ['复验正向样例视觉证据链与FinalArchive门禁', '复验语文正向样例进入全学科95分母', '升级FinalAcceptance为HumanVisual强依赖门禁', '复验表格可编辑结构与区域视觉Veto门禁', '复验英语Fallback页事实与阅读顺序', '建立HybridAsync成本预算与慢模型灰度门禁']
- target_environment: dev
- execution_mode: dev
- owner_approval_required: false

## 交付物
1. 重跑后的 final_acceptance_summary / report。
2. 重跑后的 final_human_visual_acceptance / report。
3. result.json 中明确 GO/NO-GO 结论与阻塞项。

## 验收标准
1. 结论必须可追溯到样例、页级和区域级证据。
2. 没有完整证据链时，不允许把阶段结论升级为 GO。

## 下游动作
完成后由 PM 依据结果决定是否继续收口或再拆下一轮整改。
