# 任务：收口 Qwen3-VL 审查 Worker 严格 JSON 闭环

## 任务类型
development

## 目标
把 Qwen3-VL review worker 从“已接线但在线链路未真正收口”推进到“真实 online review 可运行、JSON 失败可重试/可丢弃、指标可观测”的可用状态，并重新生成一份带真实 review 结果的 hybrid e2e 验证报告。

## 任务边界
- 可修改 Qwen3-VL review prompt、JSON normalizer、review_integrator、hybrid_pipeline 相关接线
- 可补充 `test_pdf_to_word_vlm_review_adapter.py`、`test_review_integrator.py`、`test_hybrid_e2e.py`
- 可重生成 `artifacts/pdf2word/hybrid-e2e-validation/` 报告
- 不修改 QuestionRegion / candidate_filter / ExerciseIR / DOCX 主逻辑

## 输入事实
- 既有任务 `改造Qwen3-VL为严格review_worker` 已证明 strict JSON 方向成立，但 2026-05-15 的 5 样例实测 `json_valid_rate=0.4`
- 既有任务 `集成Qwen3-VL-review到hybrid管线` 已把 `ReviewIntegrator` 接入 `HybridExperimentalPipeline._review_ambiguous()`，但 `端到端验证hybrid_experimental管线` 的最新报告仍显示 `review_mode=skipped_no_review_worker`
- 当前 Phase 2 目标不是让 VLM 生成正文，而是只处理 ambiguous / low-confidence / 顺序冲突页的审查决策
- `artifacts/pdf2word/hybrid-e2e-validation/report.json` 目前没有真实 online review 指标，无法说明 review 路径的真实可用性
- Qwen3-VL 本地服务地址与模型路径以现有工程配置为准；若服务不可用，需要优雅降级并把原因写入指标/报告

## 约束
- write_scope 以 task.json 为准
- review worker 只能输出结构化审查结果，不能生成正文 blocks
- JSON 无效时允许重试；仍失败时只能 drop / skip candidate，不能拖垮整页
- 必须保留 `service_available`、`json_valid_rate`、`review_acceptance_rate` 等指标
- 不允许让 baseline 文本主干退化

## 交付物
1. prompt / normalizer / integrator / pipeline 的收口修改
2. 带真实 review 路径的测试与验证脚本
3. 重生成 `artifacts/pdf2word/hybrid-e2e-validation/report.json`（要求能区分 skipped / online_review / service_unavailable）
4. result.json：给出本轮真实 json_valid_rate、review_acceptance_rate、是否仍有 blocker

## 验收标准
1. 当本地 Qwen3-VL 服务可用时，hybrid e2e 报告不再固定为 `skipped_no_review_worker`
2. ambiguous candidate 能进入真实 review 路径；JSON 失败时不会导致整页崩溃
3. `pytest backend/tests/test_pdf_to_word_vlm_review_adapter.py backend/tests/test_review_integrator.py backend/tests/test_hybrid_e2e.py` 通过
4. 相比 2026-05-15 的 0.4 基线，json_valid_rate 不得回退；若未达到 0.6+，必须在 result.json 中明确 blocker 与下一步建议
5. 产出可供后续 Phase 2/3 决策复用的真实在线指标

## 下游动作
完成后进入 review-1 审查，审查通过后由 qa-1 做在线/离线混合验证，最终 PM 收口。

## PM 补充处理指令（2026-05-17）
- 当前 dev-2 已完成代码收口、测试与报告重生成，pytest 结果为 19 passed / 4 warnings；本轮 blocker 已收敛为 **本地 Qwen3-VL review 服务不可用**，而不是主链路代码未接通。
- 现有代码修改应视为输入事实，**不要回退 dev-2 已完成改动**；优先在当前工作树基础上继续处理。
- 第一优先级：恢复 `http://127.0.0.1:18111/v1` 对应的本地 Qwen3-VL review 服务可用性，并确认 `healthcheck` 不再失败。
- 第二优先级：重跑 `build_hybrid_e2e_report()` 或 `backend/tests/test_hybrid_e2e.py` 中的 `online_review_probe`，拿到真实 `json_valid_rate / review_acceptance_rate`。
- 第三优先级：将真实在线指标与 **2026-05-15 的 0.4 基线**直接对比；若低于基线或仍有 JSON 截断问题，再做最小范围 prompt / integrator / normalizer 修复。
- 如仍被阻塞，result.json 必须明确写出：服务状态、已验证证据、是否属于环境问题、下一步建议。

## PM 仲裁与返工要求（2026-05-17 review round 1）
- PM 接受 review-1 的 **major finding**：当前证据只能证明 `18111` 上有可用在线 VLM 服务，**不能证明** `qwen3_vl_8b` 实际命中了真实 Qwen3-VL。
- `strict JSON / retry / drop / metrics / report` 这部分代码闭环视为 **已基本成立**，不要回退已有实现；本轮返工重点只放在 **模型身份与配置/服务映射一致性**。
- 已追加写权限到 `backend/app/services/pdf_to_word/parser_adapters/inference_config.yaml`；如确有必要，可以修正 `qwen3_vl_8b_local` 的 `base_url / model` 映射。
- 返工验收的关键新增事实：
  1. `create_adapter('qwen3_vl_8b')` 实际命中的 backend 与 `inference_config.yaml` 一致；
  2. 对应 `GET /v1/models` 返回值能够证明该端口上的模型确实是 Qwen3-VL（或至少与任务目标一致）；
  3. 在此基础上重跑 `online_review_probe` / `report.json`，再提交真实 `json_valid_rate / review_acceptance_rate`。
- `result.json` 本轮必须补充：
  - 实际命中的 `base_url`
  - `GET /v1/models` 原始返回或明确的模型 ID
  - 若修改了 `inference_config.yaml`，说明修改前后差异
  - 为什么这些证据足以证明“Qwen3-VL 审查 Worker 已真实收口”
- 如果最终确认当前产品决定其实是改用 GLM 作为 review worker，**不要继续以 Qwen3-VL 名义硬交付**；请在 `result.json` 中明确写成阻塞/待决策，由 PM 重新定目标。

## Owner 决策补充（2026-05-17）
- 林总工已明确确认：**本任务的验收方向调整为“在线 review worker 收口即可”，不再锁死必须由 Qwen3-VL 提供在线 review。**
- 因此，本轮验收重点改为：
  1. online review 路径真实可用；
  2. `report.json` 已生成真实在线指标；
  3. `json_valid_rate / review_acceptance_rate / service_available` 可观测；
  4. strict JSON / retry / drop / metrics 闭环成立；
  5. pytest 验证通过。
- **不要再为证明“必须是 Qwen3-VL”继续扩展排查范围。** 如果当前证据已经证明在线 review worker 收口成立，请直接整理结果并提交 `result.json`。
- 对 reviewer 的复审口径也同步调整为：检查“在线 review worker 是否收口”，而不是追究具体模型家族是否必须为 Qwen3-VL。

