# 审查说明：LocalInferenceBackend抽象层（补修后复审）

## 结论

**通过（approve）**。

本次复审只针对上轮指出的两个阻塞问题做核对，结果已修复到位：

1. `CustomHTTPBackend.healthcheck()` 现在只把 **2xx** 视为成功；
2. 当 `GET /health` 返回 **404/405** 时，`CustomHTTPBackend` 会按设计 fallback 到 `POST base_url {}`；
3. `OpenAICompatibleVisionBackend.healthcheck()` 现在只把 `GET /models` 的 **2xx** 视为成功，404/401 等会返回 `ok=False`；
4. 回归测试已补齐，并且我做的手工复核也通过。

## 审查范围

- `tasks/LocalInferenceBackend抽象层/instruction.md`
- `tasks/LocalInferenceBackend抽象层/result.json`
- `backend/app/services/pdf_to_word/parser_adapters/inference/custom_http_backend.py`
- `backend/app/services/pdf_to_word/parser_adapters/inference/openai_vision_backend.py`
- `backend/tests/test_pdf_to_word_inference_backends.py`
- 辅助确认：`backend/app/services/pdf_to_word/parser_adapters/inference/backend.py`
- 辅助确认：`backend/app/services/pdf_to_word/parser_adapters/inference/registry.py`

## 复核结果

### 1) CustomHTTP healthcheck 假阳性

已修复。

当前逻辑是：

- `GET /health` 返回 **2xx**：直接成功；
- `GET /health` 返回 **404/405**：继续 fallback 到 `POST base_url {}`；
- fallback 也必须是 **2xx** 才算成功；
- 其他 4xx/5xx 会返回 `ok=False`。

这与我上一轮 review 的要求一致。

### 2) OpenAI-compatible vision healthcheck 假阳性

已修复。

当前 `OpenAICompatibleVisionBackend.healthcheck()` 对 `/models` 的判定已经收紧为：

- **仅 2xx 为成功**；
- 404/401/403/5xx 都会返回 `ok=False`。

这解决了之前“base_url 配错或鉴权失败却仍被误判为可用”的问题。

### 3) 测试补齐情况

本轮新增/补强了对应回归测试：

- CustomHTTP：`/health=404` 时 fallback 到 POST 成功；
- CustomHTTP：`/health=401` 时返回 not ok；
- OpenAI-compatible vision：`/models=404/401` 时返回 not ok。

我复跑后结果为：`11 passed, 4 warnings`。

## 手工复核

我额外做了两项手工验证：

1. **CustomHTTP 404 fallback**
   - `GET /health -> 404`
   - 请求轨迹确认出现：`[(GET, /health), (POST, /infer_page)]`
   - 最终 `status.ok=True`

2. **OpenAI 404 not ok**
   - `GET /v1/models -> 404`
   - 最终 `status.ok=False`

这说明上轮 review 里指出的两个假阳性问题已经实际消失，不只是测试改了。

## 说明

- 本次是**补修后的复审**，重点只复核了两处 healthcheck 修复及其测试。
- `result.json` 中保留的风险说明仍成立：本任务还没有把 Phase A 的 `registry.py` 占位 `create_backend` 接到新的 backend factory，这属于后续集成任务范围，不阻塞本轮补修通过。

## 下一步

建议进入 QA / 后续集成门禁。

审查时间：2026-05-14T18:35:22+08:00
