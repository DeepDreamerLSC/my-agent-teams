# 任务：建立公式专项实验开关与评测基线

## 任务类型
development

## 目标
把公式专项从“默认 audit-only 的隐式行为”收口为**可显式说明的实验开关 + 可重复评测基线**：保持 `formula_candidate` 默认不并回，但要把默认关闭逻辑、审计指标和评测样例基线整理清楚，为后续公式 OCR / crop lane 做准备。

## 任务边界
- 仅处理公式专项的 experiment flag / audit baseline / 相关测试与基线产物
- 可修改 `candidate_extractor.py`、`candidate_filter.py`、对应测试
- 可新增/重生成 `artifacts/pdf2word/phase4-formula-baseline/` 基线产物
- 不实现公式正式 merge，不改默认 DOCX 正文链路，不与 Paddle 选择性触发任务抢同一文件

## 输入事实
- 当前 `formula_candidate` 在 Hybrid 路线中默认 audit-only，这是 owner 已接受的方向
- Phase 4 之前，接口必须预留，但公式仍不能默认并回正文
- 现有 `candidate_extractor / candidate_filter` 已有 `formula_candidate` 与 `formula_candidate_rejected_audit_only` 行为，可在此基础上做显式开关与基线整理
- 后续需要明确：哪些样例/页面是公式专项重点页，当前审计指标是什么，未来从 audit-only 转向可编辑链路时以什么基线对照

## 约束
- write_scope 以 task.json 为准
- 默认行为必须继续保持：`formula_candidate` 不直接并回正文
- 本轮重点是“显式开关 + 指标基线 + 测试收口”，不是公式识别准确率冲刺
- 产出必须能被后续公式 OCR / crop 实验直接复用

## 交付物
1. 公式专项实验开关的代码/测试收口（默认关闭）
2. 一份公式专项评测基线产物（写入 `artifacts/pdf2word/phase4-formula-baseline/`），至少包含：样例页、公式候选计数、audit-only 原因、后续可扩展字段占位（latex/omml/image_path）
3. result.json：写明默认关闭策略、实验开关位置、基线样例与后续建议

## 验收标准
1. 默认行为仍是 `formula_candidate` audit-only，不会进入正文 merge
2. 代码/测试能明确表达“实验开关存在但默认关闭”
3. 评测基线产物可供后续公式专项直接复用，不依赖口头解释
4. 不与默认同步链路或已完成的 image/table/review 闭环相冲突

## 下游动作
完成后进入 review-1 审查；审查通过后作为 Phase 4 公式专项的默认关闭开关与评测基线，不直接进入正式 merge。
