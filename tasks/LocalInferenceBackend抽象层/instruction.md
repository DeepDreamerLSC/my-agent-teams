# 任务：LocalInferenceBackend 抽象层（Phase B）

## 任务类型
development

## 目标
实现 `LocalInferenceBackend` Protocol 及四种 backend 实现（PythonSDK、CustomHTTP、OpenAICompatibleVision、CLI），为所有模型提供统一推理调用接口。

## 任务边界
- 只实现 backend 抽象和四种实现
- 不修改 adapter 逻辑（Phase C 负责）
- 不实现真实模型调用（用 fake/mock 验证接口）
- 依赖 Phase A 的 `inference/config.py` 和 `inference/registry.py`

## 输入事实
- 架构方案：`/Users/linsuchang/Desktop/work/chiralium/design/pdf2word/PDF转Word本地模型横评推理架构落地方案.md` Section 6、11
- Phase A 产出：
  - `inference/config.py` — BackendConfig、ProfileConfig
  - `inference/registry.py` — create_backend 占位
- 现有代码：`parser_adapters/base_adapter.py`

## 约束
- write_scope 以 task.json 为准
- 所有 backend 必须实现 `LocalInferenceBackend` Protocol
- 不在 backend 内启动重模型服务
- healthcheck 第一阶段只检查可用性，不自动拉起

## 交付物

### 1. `inference/schemas.py`
按架构方案 Section 6 定义：
- `PageInferenceRequest`（profile, source_pdf, page_index, image_path, render_dpi, pixel_width/height, width/height_points, prompt, output_schema, meta）
- `DocumentInferenceRequest`（profile, source_pdf, pages, meta）
- `InferenceResponse`（backend_id, profile, raw, text, warnings, model_load_seconds, inference_seconds）
- `BackendCapabilities`（supports_page_image, supports_pdf, supports_openai_vision, supports_bbox, supports_formula, supports_table）
- `BackendStatus`（backend_id, ok, kind, model, latency_ms, message, details）

### 2. `inference/backend.py`
- `LocalInferenceBackend` Protocol：`backend_id`、`healthcheck()` → BackendStatus、`infer_page()` → InferenceResponse、`infer_document()` → InferenceResponse
- `create_backend(config: BackendConfig) -> LocalInferenceBackend`：根据 kind 分发到具体实现

### 3. `inference/python_sdk_backend.py`
- 根据 `BackendConfig.module` / `class_path` / `entrypoint` 动态 import 并调用
- healthcheck：检查 module import 成功
- 用于：GLM-OCR SDK、PaddleOCR-VL pipeline

### 4. `inference/custom_http_backend.py`
- POST 请求到 `BackendConfig.base_url`
- healthcheck：GET `/health` 或 POST 空请求
- 用于：GLM-OCR HTTP、PaddleOCR-VL HTTP

### 5. `inference/openai_vision_backend.py`
- OpenAI-compatible chat/completions API + vision（base64 image）
- healthcheck：GET `/models`
- 用于：Qwen3-VL、GLM-4.6V-Flash

### 6. `inference/cli_backend.py`
- 执行 `BackendConfig.command` 子进程
- healthcheck：检查 command 文件存在 + `--help` 或版本
- 用于：apple_baseline CLI

### 7. 测试 `test_pdf_to_word_inference_backends.py`
每种 backend 的测试：
- PythonSDKBackend：fake module → infer_page 返回 InferenceResponse
- CustomHTTPBackend：mock httpx/aiohttp → healthcheck + infer_page
- OpenAICompatibleVisionBackend：mock OpenAI client → healthcheck + vision call
- CLIBackend：mock subprocess → healthcheck + infer_page
- create_backend 按 kind 正确分发
- backend 不可用时 healthcheck 返回 ok=False
- 超时行为

## 验收标准
1. `LocalInferenceBackend` Protocol 定义完整（healthcheck, infer_page, infer_document）
2. 四种 backend 实现均能通过 mock 测试
3. `create_backend()` 根据 kind 正确分发
4. healthcheck 在后端不可用时返回 ok=False，不抛异常
5. 所有测试通过：`cd backend && python -m pytest tests/test_pdf_to_word_inference_backends.py -v`

## 下游动作
完成后为 Phase C（Adapter 重构）提供统一 backend 调用接口。
