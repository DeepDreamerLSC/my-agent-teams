# 任务：复审 Hybrid 候选源页型选择，输出 MinerU 与 Paddle 执行策略

## 任务类型
design

## 目标
基于现有 `final-archive`、`hybrid-e2e-validation`、`model-eval` 与已收口报告，输出 **P1 可执行的候选源页型选择策略**，明确 MinerU 与 PaddleOCR-VL 在不同页型、候选类型、触发条件下的职责分工，为后续开发与 QA 提供统一口径。

## 任务边界
- 这是候选源策略复审任务，不是重新做主 parser 选型。
- 不放宽默认发布边界，不修改线上默认配置。
- 优先复用已有 artifacts / reports / gate 结果；如果无需改代码，不要为了分析而改代码。
- 公式仍保持 `audit-only / merge-disabled`，本任务不讨论放开公式合并。

## 输入事实
- 当前正式口径是：`apple default + hybrid_experimental quality gray + formula audit-only / merge-disabled`。
- 一页摘要与增强管线设计已把 P1 第一项明确为“候选源 A/B 与页型选择”。
- 现有 evidence 已表明：
  - `mineru_full` 当前更适合作为默认本地增强候选源；
  - `paddleocr_vl` 有补图表潜力，但只适合 `selected pages / crops`；
  - 当前仍缺“按页型、按候选类型、按 source 的 accepted / rejected / fallback 解释口径”。
- 可复用证据源包括但不限于：
  - `artifacts/pdf2word/final-archive/`
  - `artifacts/pdf2word/hybrid-e2e-validation/`
  - `artifacts/pdf2word/model-eval/`
  - `design/pdf2word/` 下三份已校准文档

## 约束
- `write_scope` 以 `task.json` 为准。
- 输出必须至少覆盖：`sample / page_type / candidate_kind / source_profile` 四个维度。
- 必须给出 `selected pages / crops` 的触发建议，不能只停留在“Paddle 慢但有潜力”。
- 负样例与 fallback 场景要诚实保留，不能为得出结论而忽略失败页。

## 交付物
1. 一份策略报告，写入 write_scope（建议同时产出结构化 JSON 摘要 + Markdown 结论）。
2. 报告中必须明确：
   - 哪些页型默认优先 MinerU；
   - 哪些页型/信号值得补 Paddle；
   - 哪些场景只保留 baseline / fallback；
   - 后续可直接拆给开发的 execution 任务建议。
3. 如能无侵入形成结构化统计，请附 `accepted / rejected / fallback` 明细或汇总表。

## 验收标准
1. 形成按页型的 source selection 结论，不再只有总量判断。
2. `per-source accepted / rejected / fallback` 口径可解释，可被后续开发/QA直接引用。
3. 结论不与当前正式发布边界冲突。
4. 输出可直接作为后续 P1 开发任务的拆分依据。

## 下游动作
完成后进入 review-1 审查；通过后作为 P1 候选源执行依据，供后续开发/QA 复用。
