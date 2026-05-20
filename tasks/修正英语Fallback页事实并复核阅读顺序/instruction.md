# 任务：修正英语Fallback页事实并复核阅读顺序

## 任务类型
development

## 目标
统一英语八年级 fallback 页事实，并复核阅读段落、选项区与题号顺序，避免不同报告对同一样例出现冲突描述。

## 任务边界
- 聚焦英语八年级样例，不扩展到其他学科。
- 必须统一 authoritative archive、final acceptance summary 与 visual evidence 的事实口径。

## 输入事实
- /Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-archive/reports/PDF转Word阶段性生成样例与差异分析报告.md
- /Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-archive/reports/PDF转Word当前阶段与目标差距及优化计划.md
- /Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-acceptance/final_acceptance_summary.json
- /Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-acceptance/final_human_visual_acceptance_report.md
- /Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-archive/profiles/hybrid_experimental/英语八年级

## 约束
- write_scope: ['/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-archive/profiles/hybrid_experimental/英语八年级', '/Users/linsuchang/Desktop/work/chiralium/backend/tests/fixtures/pdf_to_word/visual_similarity/english', '/Users/linsuchang/Desktop/work/chiralium/backend/app/services/pdf_to_word/english_visual_gate.py']
- read_only: false
- 依赖上游任务: ['补齐四个正向样例视觉证据链并接入FinalArchive', '升级FinalAcceptance为HumanVisual强依赖门禁']
- target_environment: dev
- execution_mode: dev
- owner_approval_required: false

## 交付物
1. 英语样例 fallback 事实与阅读顺序修正。
2. 相关夹具/规则更新。

## 验收标准
1. fallback pages 在不同 summary/report 中口径一致。
2. 阅读段落、选项区与题号顺序的复核依据明确可追溯。

## 下游动作
完成后解锁英语专项复验与最终全学科95重跑。
