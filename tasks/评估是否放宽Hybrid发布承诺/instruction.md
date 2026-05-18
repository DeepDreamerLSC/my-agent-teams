# 任务：评估是否放宽 Hybrid 发布承诺，给出 owner/PM 决策条件

## 任务类型
design

## 目标
基于当前已经收口的 `final-acceptance`、authoritative hybrid final DOCX archive，以及三份最新设计文档，输出一份面向 owner/PM 的发布承诺评估：明确当前**能放宽什么、不能放宽什么、还缺哪些前置条件**，避免把“证据 blocker 已闭合”误写成“默认发布边界可以自动扩大”。

## 任务边界
- 只做评估与决策文档，不改代码、不改运行配置、不改 final-archive/final-acceptance 产物。
- 结论必须基于已存在证据，不能主观放大。
- 文档应支持 owner/PM 直接做后续排期和决策，不要只重复技术事实。

## 输入事实
- 当前正式口径已经统一：
  - `apple default`
  - `hybrid_experimental quality gray`
  - `formula audit-only / merge-disabled`
- 已闭合事项：
  - hybrid 主链路 e2e 已完成
  - authoritative hybrid final DOCX archive 已补齐
  - `5/5` hybrid `output.docx` 可打开
  - `4/5` 样例进入 `word/media`
  - `2/5` 样例含 table XML
- 当前仍存在的限制：
  - `answer_area / answer_section = 0/5`
  - `语文五年级 = document fallback baseline only`
  - formula 仍只属于 supplementary evidence
  - 更大样本回归与异步产品化尚未完成
- 参考文档：
  - `/Users/linsuchang/Desktop/work/chiralium/design/pdf2word/PDF转Word当前阶段一页摘要与后续任务清单.md`
  - `/Users/linsuchang/Desktop/work/chiralium/design/pdf2word/PDF习题转Word当前可用性差距分析.md`
  - `/Users/linsuchang/Desktop/work/chiralium/design/pdf2word/hybrid_experimental增强管线设计.md`
  - `/Users/linsuchang/Desktop/work/chiralium/design/pdf2word/PDF转Word本地模型横评最终报告.md`
  - `/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-acceptance/final_acceptance_report.md`
  - `/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-archive/reports/hybrid_experimental_authoritative_archive_report.json`

## 约束
- write_scope: [`/Users/linsuchang/Desktop/work/chiralium/design/pdf2word/是否放宽Hybrid发布承诺评估.md`]
- read_only: false
- 依赖上游任务: 无
- target_environment: dev
- execution_mode: dev
- owner_approval_required: false
- 必须显式区分：
  1. 已可对外承诺的能力
  2. 仅限灰度/内测的能力
  3. 仍不能承诺的能力
- 必须给出建议的发布措辞，而不只是“建议谨慎”。

## 交付物
1. `/Users/linsuchang/Desktop/work/chiralium/design/pdf2word/是否放宽Hybrid发布承诺评估.md`
2. 文档至少包含：
   - 当前是否建议放宽 hybrid 发布承诺
   - 若不建议，最关键的 3 个原因
   - 若未来要放宽，必须先满足的前置条件
   - 建议 owner/PM 采用的发布措辞（内部灰度 / 限定场景 / 默认发布）
   - 建议下一步创建哪些任务
3. `result.json`：概括评估结论和建议的后续 PM 动作。

## 验收标准
1. 文档能直接回答“现在能不能放宽 hybrid 发布承诺”。
2. 结论与现有 final-acceptance/final-archive 证据不冲突。
3. 文档不是泛泛讨论，而是能作为 owner/PM 的决策输入。
4. 不改主链代码，只输出决策评估文档。

## 下游动作
完成后进入 review-1 审查；通过后作为 owner/PM 是否放宽 hybrid 发布承诺的直接输入。
