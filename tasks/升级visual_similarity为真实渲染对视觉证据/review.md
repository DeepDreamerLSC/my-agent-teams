# Review - 升级visual_similarity为真实渲染对视觉证据

## 结论
- **审查结果：approve**
- **recommended_next_action：qa**
- **当前是否可直接收口：否**

代码审查本身通过；但当前 `qa_gate_state` 仍是 `pending`，任务还需要继续走 QA。

## 我核对后的结论
这轮实现已经达到本任务的核心目标：

1. **visual_similarity 已从 contract-only 升级为真实 render-pair 视觉证据入口**
   - report 会输出 `render_pairs`、`page_scores`、`key_regions`、`vetoes`、`subject_page_type`、`human_review_required`、`evidence_paths`；
   - `quality_ready_contract.json` + `quality_ready_render_pair.json` 组合证明它可以追溯到真实 render pair artifact；
   - `visual_similarity_contract.json` 则冻结了旧 contract-only 路径，确保它不会再被误算为可计分视觉证据。

2. **状态区分已经清楚**
   - `ready`：真实 render pair 就绪且无 blocking veto；
   - `failed`：真实证据就绪，但页级/区域级 veto 触发；
   - `artifact_not_ready`：contract-only、render pair 缺失、render pair 状态异常或评分载荷不完整。

3. **default_sync 与 quality/hybrid_async 的边界是清楚的**
   - `default_sync` 不会把 visual similarity 17 分计入 95 分路线；
   - `quality/hybrid_async` 只有在真实 render-pair 就绪且无 blocking veto 时才会 award 17 分；
   - 因此 contract-only 路径不会再被误判为“人工视觉通过”。

4. **页级 / 区域级 / veto 语义是完整的**
   - 页级：`page_render_similarity`、layout/text/image coverage delta、critical/regular threshold；
   - 区域级：`region_similarity`、`bbox_iou`、required 区域 veto；
   - 汇总级：`blocking_failures`、`gate_passed`、`artifact_ready_for_scoring`、`human_review_reasons`。

5. **下游消费口径已经冻结**
   - 从当前实现与 `result.json` 看，后续 reporter / QA 应基于：
     - `artifact_ready_for_scoring`
     - `vetoes[]`
     - `human_review_required`
     - `score_contract`
   - 这满足了“字段命名稳定，供 C-05/C-07/S-01/S-02/S-03 继续消费”的目标。

## 我补跑的证据
我额外复核了：
- `py_compile`
- `pytest`
- `git diff --check`
- 静态代码 / fixture / contract 复核

其中定向 pytest 为：
- `backend/tests/test_pdf_to_word_visual_similarity_gate.py`

结果：
- `8 passed, 4 warnings`
- warnings 为既有 FastAPI `on_event` deprecation warnings，不阻塞本任务结论。

## 非阻塞说明
- 当前任务目录还没有 `verify.json`；
- `task.json` 中 `qa_gate_state` 仍为 `pending`。

所以我的结论是：
- **review 可以 approve**；
- 但**不能视为已经最终收口**，下一步应进入 QA。

## 建议
建议 **approve** 并交给 QA：
- 用真实 render-pair / visual_similarity artifact 再做一轮下游 reporter 与人工复验链路验证；
- 重点确认后续消费者对 `artifact_ready_for_scoring`、`vetoes[]`、`human_review_required` 的消费口径与本轮 contract 保持一致。
