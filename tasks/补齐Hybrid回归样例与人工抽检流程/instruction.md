# 任务：补齐 Hybrid 回归样例与人工抽检流程

## 任务类型
verification

## 目标
把当前 Hybrid 的回归验证从“有 e2e 报告但缺少固定抽检口径”提升为“有固定正负样例、固定验收指标、固定人工抽检模板”的可复用质量基线，支撑后续 Phase 2/3 持续收口。

## 任务边界
- 基于现有 `hybrid-e2e-validation` 产物，整理正样例/负样例名单、必检指标、抽检步骤与报告模板
- 可补充测试说明或回归脚本引用，但不改生产代码
- 可在 `artifacts/pdf2word/final-archive/reports/` 中补充 QA 口径文档，或更新 `hybrid-e2e-validation/report.json` 的说明字段
- 不负责实现新的 parser / review / merge 逻辑

## 输入事实
- 当前 `artifacts/pdf2word/hybrid-e2e-validation/report.json` 已覆盖 5 个样例，但重点还是技术验证，缺少 QA 可复用的人工抽检口径
- `数学试卷`、`英语八年级` 已验证 visual blocks 能进入 ExerciseIR / DOCX，适合作为正样例
- `语文五年级` 是不可判定页跳过增强的负样例
- Phase 2/3 后续还要继续做顺序校验、review worker、Paddle 选择性触发，需要一套固定回归基线防止反复人工摸索

## 依赖上游任务
- `实现Hybrid题号顺序与阅读顺序校验器` 完成后，回归口径需补入顺序/题号类验收点
- `收口Qwen3VL审查Worker严格JSON闭环` 完成后，回归口径需补入 review_mode / json_valid_rate / review_acceptance_rate 抽检项

## 约束
- write_scope 以 task.json 为准
- 不修改生产代码
- 输出必须能被 PM / review-1 / qa-1 后续重复使用
- 抽检口径必须同时覆盖：PageIR 级差异、ExerciseIR 挂接、DOCX 可视输出、fallback 行为

## 交付物
1. 一份 Hybrid 回归与人工抽检口径文档（写入 `artifacts/pdf2word/final-archive/reports/`）
2. 对 `hybrid-e2e-validation` 现有报告的补充说明或附录
3. 明确的样例分组：正样例、负样例、重点抽检页
4. result.json：列出后续每轮必须检查的核心指标与建议命令

## 验收标准
1. 至少覆盖正样例（数学试卷/英语八年级）与负样例（语文五年级）
2. 明确列出必须检查的指标：candidate_count、accepted/rejected、fallback、media_count、has_drawing/has_table_xml、review_mode/json_valid_rate（如适用）
3. 能指导 qa-1 独立完成一轮 Hybrid 回归，不依赖开发口头解释
4. review-1 审查后可作为 Phase 2/3 通用质量基线

## 下游动作
完成后进入 review-1 审查，确认回归口径后作为后续 Phase 2/3 的质量基线。

## PM 补充处理指令（2026-05-17）
- 上游任务《收口Qwen3VL审查Worker严格JSON闭环》已于 2026-05-17 09:09:05+08:00 自动收口；当前 `report.json` 顶层 `review_mode=online_review`，`online_review_probe` 指标为 `json_valid_rate=1.0`、`review_acceptance_rate=1.0`、`service_available=true`。
- 预整理任务《预整理Hybrid回归抽检模板》已产出可复用骨架文档：`artifacts/pdf2word/final-archive/reports/hybrid回归抽检模板.md`。请**直接复用该文档结构**，但必须先修正其中被 review-1 指出的过期事实：不得再写“全部 fallback”或“review_mode=skipped_no_review_worker”。
- 本正式任务不需要重做结构设计，重点是：
  1. 吸收并修正预整理模板；
  2. 补齐当前真实 online review worker 指标与口径；
  3. 固化正样例/负样例/重点抽检页；
  4. 形成可重复执行的一轮完整 Hybrid 回归与人工抽检说明。
- 若需要补充 `hybrid-e2e-validation/report.json` 说明字段或测试说明，可在既有 write_scope 内完成；但不要扩展到生产代码逻辑。

## PM 仲裁与返工要求（2026-05-17 review round 1）
- PM 接受 review-1 的驳回结论。本轮不需要重做结构，**只做最小补修**。
- 必修项 1：在正式 QA 基线文档中补齐验收标准点名的缺失指标：`media_count`、`has_drawing`、`has_table_xml`。
  - 这些指标必须同时出现在：
    1. 必检指标一览；
    2. 对应检查步骤/判定方式；
    3. checklist 或报告模板中的可执行检查位。
  - 即使当前主要依赖 DOCX / 产物层人工确认，也要明确“从哪里取值、如何判定通过/异常”。
- 必修项 2：把 Step 7 与相关模板中的 `reviewed_rejected_count` 统一修正为真实字段名 `review_rejected_count`，并写明其来源是 `report.json -> online_review_probe.metrics`。
- 保留当前已经修正好的内容：
  - 不要回退 `online_review`、`json_valid_rate=1.0`、`review_acceptance_rate=1.0`、`service_available=true` 等真实事实；
  - 不要恢复“全部 fallback”或 `skipped_no_review_worker` 之类过期描述。
- 本轮是文档型返工，原则上不需要扩展到生产代码；如需补充说明字段或执行命令，请在既有 write_scope 内最小处理。
- result.json 重提时请明确写出：
  1. 新增了哪些缺失指标；
  2. 这些指标在文档中的位置；
  3. `review_rejected_count` 字段名已与真实报告对齐。

