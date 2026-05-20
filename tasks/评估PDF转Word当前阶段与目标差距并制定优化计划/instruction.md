# 任务：评估PDF转Word当前阶段与目标差距并制定优化计划

## 任务类型
design

## 目标
- 站在**全学科统一目标**视角，明确当前 PDF转Word 实际阶段能力，与目标阶段能力之间的具体差距。
- 输出一份可直接指导下一波实施拆分的优化计划，覆盖技术、指标、证据链、门禁、成本与推进节奏。
- 明确哪些差距是必须优先补齐的，哪些适合分阶段治理，避免继续出现“局部场景收口，但整体口径仍不成立”的情况。

## 任务边界
- 本任务只做架构评估、差距分析和优化计划设计，不直接修改生产代码。
- 必须覆盖**全部学科**，不能只聚焦科学/数学或单一高风险页型。
- 需要同时考虑：工程门禁、人工视觉结论、对外口径、成本性能、运行链路与可观测性。
- 需要正面回答：为什么当前仍然会出现“工程门禁 PASS，但人工视觉 95 仍 NO-GO”的断层，以及如何收敛。

## 输入事实
- 阶段性样例差异报告：`/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-archive/reports/PDF转Word阶段性生成样例与差异分析报告.md`
- 阶段性样例差异 JSON：`/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-archive/reports/PDF转Word阶段性生成样例与差异分析报告.json`
- 横评最终报告：`/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-archive/reports/横评最终报告.md`
- 后续技术路线：`/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-archive/reports/后续技术路线.md`
- 最终验收摘要：`/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-acceptance/final_acceptance_summary.json`
- 最终人工视觉报告：`/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-acceptance/final_human_visual_acceptance_report.md`
- 当前共识基线：
  - 默认同步主 parser 仍是 `apple_baseline`
  - 质量增强主线仍是 `hybrid_experimental / quality/hybrid_async`
  - `PaddleOCR-VL` 仅适合 selected-page supplemental source
  - 公式链路仍是 `audit-only`
  - 截至 2026-05-19，全学科人工视觉 95 仍为 `NO-GO`
- 林总工强调：**不止科学学科，其他所有学科都要统一看待**，不能用单学科收口替代全局达标。

## 约束
- write_scope: ['/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-archive/reports/PDF转Word当前阶段与目标差距及优化计划.md', '/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-archive/reports/PDF转Word当前阶段与目标差距及优化计划.json']
- read_only: false
- 依赖上游任务: 无
- target_environment: dev
- execution_mode: dev
- owner_approval_required: false

## 交付物
1. Markdown 报告：`/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-archive/reports/PDF转Word当前阶段与目标差距及优化计划.md`
2. JSON 摘要：`/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-archive/reports/PDF转Word当前阶段与目标差距及优化计划.json`
3. result.json 中至少要回写：
   - `current_stage_summary`
   - `target_definition`
   - `gap_matrix`
   - `priority_actions`
   - `recommended_next_tasks`
   - `risks_and_dependencies`

## 验收标准
1. 必须清晰定义“当前阶段”与“目标阶段”，且目标必须可验证、可落地、可被 PM 继续拆任务。
2. 必须给出结构化 gap matrix，至少覆盖以下维度：
   - 全学科覆盖度
   - 人工视觉 fidelity / 页级与区域级 veto
   - 表格可编辑性与结构完整性
   - 公式/符号链路成熟度
   - 视觉门禁证据链完整性
   - 性能/成本/慢模型灰度边界
   - 对外命名与对外口径
   - 运行链路与可观测性
3. 必须给出优化计划，至少分为：短期（立即/72h）、中期（1周）、阶段性目标（2周+）。
4. 必须明确：
   - 哪些问题是恢复全学科目标前的**必修项**
   - 哪些问题可以在灰度阶段继续演进
   - 哪些目标本身需要拆成分阶段目标，而不是一次性宣称完成
5. 必须覆盖全学科，不得用局部样例或单学科结果代替整体判断。

## 下游动作
完成后在 result.json 回写差距结论与优化计划，供 PM 继续拆分实施任务与派发。
