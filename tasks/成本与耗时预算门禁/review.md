# 成本与耗时预算门禁 — 审查结论

- **结论**：approve
- **是否可收口**：可以，建议交 PM 收口
- **审查人**：review-1
- **审查时间**：2026-05-20T00:26:30+08:00

## 1. 本轮确认点

1. `visual_gate_budget.py` 已把以下内容收敛到统一 contract：
   - `quality/hybrid_async` 才启预算门禁；default sync 不引入 render/slow-model 成本；
   - 科学 / 数学 / 语文 / 英语四学科缺一即 blocker；
   - render pair / visual similarity / slow-model / document_total 四层预算阈值与降级动作均可机读；
   - 超预算不会伪造通过，而是转为 `manual_review` 或 `skip_slow_model_keep_visual_fail_open`。
2. `test_pdf_to_word_visual_gate_budget.py` 已覆盖默认模式跳过、全学科通过、render_pair 超预算、slow-model 超预算、缺学科 blocker 等核心路径。
3. `PDF转Word视觉门禁成本预算报告.md` 与代码口径一致，阈值、样例、降级策略和适用边界都能对上 instruction。
4. `verify.json` 已存在且 QA 通过，结论与代码/报告一致。

## 2. 我补充做的验证

- `py_compile`：通过
- 定向 pytest：`5 passed, 4 warnings`
  - warnings 为既有 FastAPI `on_event` deprecation warnings，与本任务无关
- reviewer 额外 smoke：
  - `visual_similarity` 超预算时会阻断自动通过，并给出 `manual_review`
  - `document_total` 超预算时会阻断自动通过，并给出 `manual_review`

## 3. 非阻塞建议

当前 pytest 还没有把 `visual_similarity` 与 `document_total` 超预算两条分支固化成显式测试；本次我已人工补跑确认行为正确，因此**不阻塞放行**。若后续该 helper 继续演进，建议把这两条 smoke 断言补成正式 pytest，降低后续回归风险。
