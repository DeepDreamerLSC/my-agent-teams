# 任务：建立HybridAsync成本预算与慢模型灰度门禁

## 任务类型
development

## 目标
补齐 quality/hybrid_async 的成本、时延与慢模型灰度边界，使其继续保持灰度定位而不是被误用为默认同步链路。

## 任务边界
- 不放宽 apple_baseline 默认同步边界。
- 重点明确 Paddle/Qwen 调用成本、触发页比例、缓存命中与超时熔断。

## 输入事实
- /Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-archive/reports/PDF转Word阶段性生成样例与差异分析报告.md
- /Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-archive/reports/PDF转Word当前阶段与目标差距及优化计划.md
- /Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-acceptance/final_acceptance_summary.json
- /Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-acceptance/final_human_visual_acceptance_report.md
- /Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-archive/reports/PDF转Word视觉门禁成本预算报告.md

## 约束
- write_scope: ['/Users/linsuchang/Desktop/work/chiralium/backend/app/services/pdf_to_word/parser_adapters/hybrid_pipeline.py', '/Users/linsuchang/Desktop/work/chiralium/backend/app/services/pdf_to_word/visual_gate_budget.py', '/Users/linsuchang/Desktop/work/chiralium/backend/tests/test_hybrid_pipeline.py', '/Users/linsuchang/Desktop/work/chiralium/backend/tests/test_pdf_to_word_visual_gate_budget.py', '/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-archive/reports/PDF转Word视觉门禁成本预算报告.md']
- read_only: false
- 依赖上游任务: 无
- target_environment: dev
- execution_mode: dev
- owner_approval_required: false

## 交付物
1. HybridAsync 成本预算门禁代码/测试更新。
2. 预算报告与关键阈值回写。

## 验收标准
1. 默认同步 0 回归。
2. quality/hybrid_async 的成本边界与慢模型灰度规则可观测、可解释。

## 下游动作
完成后作为全学科95重跑的成本边界输入。
