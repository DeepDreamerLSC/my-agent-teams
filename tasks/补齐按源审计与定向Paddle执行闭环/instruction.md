# 任务：补齐 per-source merge audit 与 Paddle 定向页执行闭环

## 任务类型
development

## 目标
在上游运行时策略落地后，把 Hybrid 的按源事实补齐到“可审计、可复跑、可解释”：每次 run 都能输出按 `sample/page_type/candidate_kind/source_profile` 拆分的 accepted / rejected / fallback 明细，同时把 `paddleocr_vl` 收口为真正的 `selected pages / crops` 定向执行器，记录 cache、耗时、候选量与最终 accepted。

## 任务边界
- 允许修改：`hybrid_pipeline.py`、`page_ir_merger.py`、`candidate_filter.py`、`test_hybrid_pipeline.py`、`test_hybrid_e2e.py`、`test_page_ir_merger.py`。
- 允许更新 `artifacts/pdf2word/phase3-paddle-quality/` 作为本轮专项报告产物。
- 不改默认 `apple_baseline` 发布边界，不把 Paddle 升级为默认全量增强源。
- 不放开 `formula_candidate` merge，公式仍只保留 audit 事实。

## 输入事实
- 上游任务将产出 `page_type / default_source_profile / selected_pages_or_crops` 运行时策略事实。
- 当前 `profile_audits` 只有 `page_scope / selected_pages / candidate_count / cache hits/misses` 等粗粒度信息，缺少 accepted / rejected / fallback 的按源拆分。
- 当前 Paddle 已具备部分按页触发与缓存能力，但还未形成与 P1 策略矩阵完全一致的按源审计闭环。
- P1 口径明确：Paddle 候选多但 `final accepted=0` 时应解释为噪声被过滤成功，而不是提升默认优先级的证据。

## 约束
- `write_scope` 以 `task.json` 为准。
- 必须复用上游 `page_type/source_selection` 输出，不再各写一套局部判定逻辑。
- Paddle 只能在 `table_heavy / image_dense / mineru shortfall / low confidence / allowlist` 的 selected pages/crops 上运行，不能整本同步跑。
- 需要保留 `source_profile`、`candidate_kind`、`merge_reason`、`fallback_reason` 等事实，便于 QA 后续按策略矩阵核对。
- 协作环境下不要回滚他人无关修改；如果上游任务已触达相同文件，只做本任务职责范围内的增量收口。

## 交付物
1. 按 `sample/page_type/candidate_kind/source_profile` 的 per-source merge audit 实现。
2. Paddle 定向页/crop 执行与缓存审计收口，至少记录：`cache hit/miss`、`latency`、`candidate_count`、`accepted_count`。
3. 更新后的 `phase3-paddle-quality` 报告产物，说明触发页、候选增益、accepted/fallback 事实。
4. `result.json`：写明 audit 字段新增项、Paddle 最终触发口径、仍残留的风险。

## 验收标准
1. 每次 hybrid run 都能输出按源 accepted / rejected / fallback 明细，而不是只有总量。
2. `paddleocr_vl` 只在 selected pages/crops 运行，且 cache / latency / candidate / accepted 指标可观测。
3. `phase3-paddle-quality` 报告能支撑 QA/PM 判断“Paddle 何时有价值、何时只是噪声”。
4. 指定测试通过，且不回归现有 Hybrid 合并与 page fallback 行为。

## 下游动作
完成后进入 review-1 审查；通过后作为 Hybrid 按源审计、Paddle 定向增强与 QA 门禁的事实输入。
