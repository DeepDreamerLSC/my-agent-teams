# 任务：实现 PaddleOCR-VL 选择性触发与缓存

## 任务类型
development

## 目标
在不影响默认同步路径的前提下，把 `paddleocr_vl` 收口为 `quality / hybrid_experimental` 模式下的**按页选择性增强器**：只对高价值页触发，支持缓存与资源控制，并输出可审计的触发报告。

## 任务边界
- 仅处理 Phase 3 的 `paddleocr_vl` 选择性触发、页级缓存与相关审计/测试
- 可修改 `hybrid_pipeline.py`、`inference_config.yaml`、`test_hybrid_pipeline.py`、`test_hybrid_e2e.py`
- 可新增/重生成 `artifacts/pdf2word/phase3-paddle-quality/` 报告产物
- 不修改默认 `apple_baseline` 同步链路，不实现公式 merge，不改 review worker 逻辑

## 输入事实
- Phase 1/2 已完成：image/table 回链路、题号顺序/阅读顺序校验、在线 review worker 收口、Hybrid QA 基线均已闭环
- 路线文档要求 Phase 3 只在 `quality` / `hybrid_experimental` 下按页触发 `paddleocr_vl`，不能整本同步跑
- 当前 `hybrid_pipeline.py` 已具备 `candidate_profiles=(mineru_full, paddleocr_vl)` 的能力，但还缺少“只对高价值页触发 Paddle”的独立策略与专门缓存/报告
- 目标门禁：`paddleocr_vl` 仅在 `table-heavy / image-dense / baseline low-confidence` 页触发；触发页比例应可观测且默认同步路径 0 回归

## 约束
- write_scope 以 task.json 为准
- 默认同步 API 仍然走 `apple_baseline`
- `paddleocr_vl` 只能用于 selected pages / crops，不能整本同步跑
- 与 `mineru_full` 冲突时优先 `mineru_full`，除非你能用现有指标证明 Paddle 表格结构更优
- 需要输出触发页、缓存命中、fallback/merge 结果等审计信息，便于后续评估

## 交付物
1. `paddleocr_vl` 选择性触发与缓存实现
2. 对应测试（至少覆盖：仅选中页触发、默认链路不回归、缓存可复用）
3. 一份 Phase 3 触发报告（写入 `artifacts/pdf2word/phase3-paddle-quality/`），至少包含：触发页列表、触发比例、候选增益、fallback 情况
4. result.json：写明本轮触发策略、缓存策略、关键指标与剩余风险

## 验收标准
1. `paddleocr_vl` 只在 selected pages / crops 触发，不出现整本同步跑
2. `quality` 模式触发页比例可观测，且在 5 样例上有明确审计结果
3. 默认同步路径不回归；指定测试通过
4. 触发报告能支撑后续“局部能力模型替代 Paddle 或补公式”的评估输入

## 下游动作
完成后进入 review-1 审查；审查通过后作为 Phase 3 主能力输入，供后续局部模型评估与公式专项基线复用。
