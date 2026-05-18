# 任务：推理配置与 registry 基础设施（Phase A）

## 任务类型
development

## 目标
搭建统一推理配置和 registry 基础设施，使后续所有模型适配器通过 YAML 配置 + profile 注册接入，不再散落环境变量和硬编码。

## 任务边界
- 实现 `inference_config.yaml`、`inference/config.py`、`inference/registry.py`
- 改造 `model_eval_runner.py` 支持 `--config`、`--list-profiles`、`--dry-run`
- 更新 `__init__.py` 的导出
- 不实现具体 backend 调用逻辑（Phase B）
- 不修改现有 adapter 行为（apple_baseline 仍正常工作）

## 输入事实
- 架构方案：`/Users/linsuchang/Desktop/work/chiralium/design/pdf2word/PDF转Word本地模型横评推理架构落地方案.md`
- 现有代码：
  - `parser_adapters/base_adapter.py` — BaseParserAdapter、AdapterResult、PageIR、EvalMetrics
  - `parser_adapters/__init__.py` — ADAPTER_REGISTRY
  - `parser_adapters/apple_baseline_adapter.py` — 现有基线适配器
  - `parser_adapters/glm_ocr_adapter.py` — 现有 GLM-OCR 适配器（将被 Phase C 重构）
  - `model_eval_runner.py` — 现有评估入口

## 约束
- write_scope 以 task.json 为准
- 必须保持 `apple_baseline` 现有行为不破坏
- `inference_config.yaml` 必须包含架构方案 Section 7.1 中的所有 backends 和 profiles
- 配置加载支持环境变量覆盖：`PDF_TO_WORD_INFERENCE_CONFIG` 指向本地配置文件

## 交付物

### 1. `inference_config.yaml`
按架构方案 Section 7.1 编写完整配置，包含：
- `defaults`: render_dpi, timeout_seconds, max_concurrency 等
- `backends`: apple_cli, glm_ocr_sdk, glm_ocr_http, paddleocr_vl_sdk, qwen3_vl_8b_local, qwen3_vl_32b_local, glm_46v_flash_local
- `profiles`: apple_baseline, glm_ocr, paddleocr_vl, qwen3_vl_8b, qwen3_vl_32b, glm_46v_flash

### 2. `inference/config.py`
- `BackendConfig` dataclass（id, kind, model, base_url, module, class_path, command, device, timeout_seconds, max_concurrency, extra）
- `ProfileConfig` dataclass（name, adapter, backend, input_mode, normalizer, prompt_template, output_schema, enabled）
- `InferenceConfig` 类：加载 YAML、支持环境变量覆盖、提供 `get_profile()` / `get_backend()` / `list_profiles()` 方法

### 3. `inference/registry.py`
- `create_adapter(profile_name, *, config=None) -> BaseParserAdapter`：从配置创建 adapter
- `ADAPTER_CLASS_REGISTRY`：按类型注册（apple_baseline → AppleBaselineAdapter, document_ocr → DocumentOCRAdapter 占位, vlm_review → VLMReviewAdapter 占位）
- `create_backend(backend_config) -> LocalInferenceBackend`：占位，Phase B 实现

### 4. 改造 `model_eval_runner.py`
新增 CLI 参数：
- `--config`：指定 inference_config.yaml 路径
- `--list-profiles`：打印所有 profile 及其 adapter/backend/enabled 状态
- `--dry-run`：校验配置和样例路径，不调用模型
- `--healthcheck`：占位，Phase B 实现
- `--raw-output`：占位，Phase B 实现
- `--no-docx`：只产出 JSON artifacts

### 5. 测试 `test_pdf_to_word_inference_config.py`
- YAML 加载和解析正确性
- Profile/Backend 查找
- 环境变量覆盖
- `--list-profiles` 输出格式
- `--dry-run` 校验逻辑
- 配置错误时明确错误信息
- apple_baseline 行为不变

## 验收标准
1. `inference_config.yaml` 包含所有 7 个 backends 和 6 个 profiles
2. `InferenceConfig` 能正确加载 YAML 并支持环境变量覆盖
3. `create_adapter("apple_baseline", config=...)` 能创建正常工作的 AppleBaselineAdapter
4. `model_eval_runner --list-profiles` 输出所有 profiles 状态
5. `model_eval_runner --dry-run` 校验配置不调用模型
6. 现有 apple_baseline 跑批行为不破坏
7. 所有测试通过：`cd backend && python -m pytest tests/test_pdf_to_word_inference_config.py -v`

## 下游动作
完成后为 Phase B（LocalInferenceBackend 抽象层）提供配置和 registry 基础。
