# 任务：实现表格可编辑结构与区域视觉Veto联合门禁

## 任务类型
development

## 目标
把表格治理升级为“可编辑结构 + 区域视觉Veto”联合门禁，覆盖科学实验页与数学表格页。

## 任务边界
- 重点覆盖五下科学、数学八年级相关表格页。
- 不能只停留在 table block 存在与否，必须考虑单元格、合并关系与关键区域视觉否决。

## 输入事实
- /Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-archive/reports/PDF转Word阶段性生成样例与差异分析报告.md
- /Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-archive/reports/PDF转Word当前阶段与目标差距及优化计划.md
- /Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-acceptance/final_acceptance_summary.json
- /Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-acceptance/final_human_visual_acceptance_report.md
- /Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-archive/profiles/hybrid_experimental/五下科学
- /Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-archive/profiles/hybrid_experimental/数学八年级

## 约束
- write_scope: ['/Users/linsuchang/Desktop/work/chiralium/backend/app/services/pdf_to_word/table_ir.py', '/Users/linsuchang/Desktop/work/chiralium/backend/app/services/pdf_to_word/docx_assembler.py', '/Users/linsuchang/Desktop/work/chiralium/backend/app/services/pdf_to_word/exercise_docx_assembler.py', '/Users/linsuchang/Desktop/work/chiralium/backend/tests/test_pdf_to_word_table_ir_contract.py', '/Users/linsuchang/Desktop/work/chiralium/backend/tests/fixtures/pdf_to_word/table_ir', '/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/table_gate']
- read_only: false
- 依赖上游任务: ['补齐四个正向样例视觉证据链并接入FinalArchive']
- target_environment: dev
- execution_mode: dev
- owner_approval_required: false

## 交付物
1. 表格结构门禁实现与测试。
2. 表格区域视觉 veto 规则与相关产物。

## 验收标准
1. 科学与数学表格页同时具备结构检查与区域视觉 veto。
2. 不能再仅凭 table XML 存在就宣称表格达标。

## 下游动作
完成后解锁 QA 复验与全学科95重跑。
