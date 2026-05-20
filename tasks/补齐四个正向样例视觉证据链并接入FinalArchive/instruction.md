# 任务：补齐四个正向样例视觉证据链并接入FinalArchive

## 任务类型
development

## 目标
为当前 4 个 positive_candidate 样例补齐并落盘 canonical visual evidence artifacts：render_pair、visual_similarity、fidelity_veto、human_review_report，并把 final-archive 采集链路接到这批终态证据。

## 任务边界
- 只处理当前 4 个正向样例：五下科学、数学八年级、数学试卷、英语八年级。
- 不要改写语文五年级 negative_guard 的角色定义，也不要把公式链路放开到生产。
- 本任务重点是 evidence materialization 与 final-archive 接线，不负责最终对外 GO 口径。

## 输入事实
- /Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-archive/reports/PDF转Word阶段性生成样例与差异分析报告.md
- /Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-archive/reports/PDF转Word当前阶段与目标差距及优化计划.md
- /Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-acceptance/final_acceptance_summary.json
- /Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-acceptance/final_human_visual_acceptance_report.md
- /Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-archive/profiles/hybrid_experimental/五下科学
- /Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-archive/profiles/hybrid_experimental/数学八年级
- /Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-archive/profiles/hybrid_experimental/数学试卷
- /Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-archive/profiles/hybrid_experimental/英语八年级

## 约束
- write_scope: ['/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-archive/profiles/hybrid_experimental/五下科学', '/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-archive/profiles/hybrid_experimental/数学八年级', '/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-archive/profiles/hybrid_experimental/数学试卷', '/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-archive/profiles/hybrid_experimental/英语八年级', '/Users/linsuchang/Desktop/work/chiralium/backend/app/services/pdf_to_word/page_renderer.py', '/Users/linsuchang/Desktop/work/chiralium/backend/app/services/pdf_to_word/conversion_service.py', '/Users/linsuchang/Desktop/work/chiralium/backend/app/services/pdf_to_word/workspace.py', '/Users/linsuchang/Desktop/work/chiralium/backend/app/services/pdf_to_word/visual_similarity_gate.py', '/Users/linsuchang/Desktop/work/chiralium/backend/app/services/pdf_to_word/fidelity_veto.py', '/Users/linsuchang/Desktop/work/chiralium/backend/tests/fixtures/pdf_to_word/visual_similarity', '/Users/linsuchang/Desktop/work/chiralium/backend/tests/fixtures/pdf_to_word/fidelity']
- read_only: false
- 依赖上游任务: 无
- target_environment: dev
- execution_mode: dev
- owner_approval_required: false

## 交付物
1. 4 个正向样例目录下落盘 canonical render_pair.json / visual_similarity.json / fidelity_veto.json / human_review_report.json。
2. final-archive 相关代码与夹具更新，能识别并汇总上述证据。
3. result.json 中列出已补齐的样例、产物路径和仍存在的缺口。

## 验收标准
1. 四个正向样例全部具备四类 canonical artifacts。
2. final-archive 汇总链路能识别 artifact presence，不再只看口头专项结论。
3. 任务结果明确说明每个样例已补齐到什么程度，缺口不能静默吞掉。

## 下游动作
完成后解锁 QA 复验与 FinalAcceptance 强依赖门禁升级任务。
