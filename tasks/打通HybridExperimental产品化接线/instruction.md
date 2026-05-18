# 任务：打通 hybrid_experimental 产品化接线

## 任务类型
development

## 目标
让 `parser_backend=hybrid_experimental` 在 API / service / skill 入口下真正走 Hybrid 管线，而不是继续停留在 `parser_client.py` 里的 apple/mocked 占位实现；同时保持默认 `apple` / `auto` 路径 0 回归。

## 任务边界
- 只处理 `hybrid_experimental` 的产品化接线、路由解析、结果 meta 与测试闭环。
- 不改默认 `apple_baseline` 同步链路行为。
- 不新增新的模型 profile，不改 Phase 3/4 已收口的算法策略边界。
- 不做部署，不改 prod 配置，不做新的端到端 parser 横评。

## 输入事实
- 当前 Phase 1/2/3 已完成：Hybrid 管线本体、Paddle 选择性触发、公式 audit-only 基线、局部模型评估都已闭环。
- 但 `backend/app/services/pdf_to_word/parser_client.py` 里的 `hybrid_experimental` 仍是 apple/mocked 占位实现，`parse_with_backend()` 并没有真正进入 `HybridExperimentalPipeline`。
- API 路由在 `backend/app/api/pdf_to_word.py`，service 入口在 `backend/app/services/pdf_to_word/conversion_service.py`。
- 路线文档的稳态目标是：默认 `apple_baseline -> ExerciseIR -> DOCX`；显式开启 `hybrid_experimental` 时才走 selective hybrid enhancement。

## 约束
- write_scope 以 task.json 为准。
- 默认链路 `parser_backend=auto/apple` 行为必须保持不变，不能被 `hybrid_experimental` 反向污染。
- `hybrid_experimental` 只能在显式指定时生效，不能偷偷变成默认 backend。
- 结果必须能被 API / service / route resolve 测试证明，不接受只改文案或只改元数据。
- 若需要补验证产物，只能写入 `artifacts/pdf2word/productization-hybrid/`。

## 交付物
1. 让 `hybrid_experimental` 在 API / service / skill 入口下真正走 Hybrid 管线的实现。
2. 对应测试更新：至少覆盖 backend resolve、service、API、exercise pipeline integration。
3. 如有必要，补一份产品化验证产物到 `artifacts/pdf2word/productization-hybrid/`。
4. result.json：写清真实入口、默认链路不回归证明、仍未覆盖的边界。

## 验收标准
1. 显式 `parser_backend=hybrid_experimental` 时，service / API 不再落到 apple/mocked 占位实现。
2. `parser_backend=auto/apple` 默认链路 0 回归。
3. 指定 pytest 通过，且能从结果 meta 或验证产物中看出 Hybrid 路径已可观测。
4. 不引入新的 profile 选型、部署动作或默认开关反转。

## 下游动作
完成后进入 review-1 审查；审查通过后作为 Hybrid 能力从实验态走向产品调用态的接线结果。
