# 任务：接入 GLM-OCR 适配器到横评框架

## 任务类型
development

## 目标
实现 `glm_ocr` 适配器，接入横评框架的 `ADAPTER_REGISTRY`，使 GLM-OCR 模型可以作为 `--profiles glm_ocr` 在 `model_eval_runner.py` 中运行。

## 任务边界
- 只实现适配器代码，不修改 `model_eval_runner.py` 核心逻辑（注册表更新除外）
- 依赖 GLM-OCR 本地推理环境；如果当前未安装，`is_available()` 返回 False 并提供安装指引
- 不做真实样例跑批（跑批是单独任务）

## 输入事实
- 横评框架：`/Users/linsuchang/Desktop/work/chiralium/backend/app/services/pdf_to_word/model_eval_runner.py`
- 基础接口：`/Users/linsuchang/Desktop/work/chiralium/backend/app/services/pdf_to_word/parser_adapters/base_adapter.py`
- 注册表：`/Users/linsuchang/Desktop/work/chiralium/backend/app/services/pdf_to_word/parser_adapters/__init__.py`
- 参考：`/Users/linsuchang/Desktop/work/chiralium/backend/app/services/pdf_to_word/parser_adapters/apple_baseline_adapter.py`
- 技术方案 Section 0.5：GLM-OCR 定位为 P0 级 OCR 主候选，重点看公式、表格、中文扫描件稳定性
- 技术方案 Section 20.3：GLM-OCR 输入粒度为页图，输出要求为 OCR + bbox + 结构块转 PageIR

## 约束
- write_scope 以 task.json 为准
- 适配器必须继承 `BaseParserAdapter`，实现 `parse()` 和 `is_available()`
- 输出必须符合 `AdapterResult` 规范（PageIR + EvalMetrics + warnings）
- 需要更新 `__init__.py` 中的 `ADAPTER_REGISTRY`

## 交付物

### 1. `parser_adapters/glm_ocr_adapter.py`

关键实现要求：
- 继承 `BaseParserAdapter`，`profile_name = "glm_ocr"`
- `is_available()`: 检查 GLM-OCR 推理环境是否就绪
- `parse()`: 调用 GLM-OCR 模型解析 PDF 页图：
  1. 用 pypdfium2 渲染指定页为图片
  2. 将页图送入 GLM-OCR 获取 OCR + bbox + 结构块
  3. 将结果转为 PageIR / PDFSourceBlock
- GLM-OCR 调用方式：通过 Python SDK 或 HTTP API 调用本地推理服务
- 如果 GLM-OCR 未安装，`parse()` 应抛出明确错误

### 2. `tests/test_glm_ocr_adapter.py`

测试用例：
- `test_is_available_false_when_no_glm_ocr` — 模拟环境缺失时返回 False
- `test_is_available_true_when_installed` — 模拟环境就绪时返回 True
- `test_parse_returns_adapter_result` — mock GLM-OCR 响应，验证输出为合法 AdapterResult
- `test_parse_output_pageir_blocks` — 验证 GLM-OCR 输出正确转换为 PDFSourceBlock
- `test_registry_includes_glm_ocr` — 验证 ADAPTER_REGISTRY 包含 glm_ocr

### 3. 更新 `parser_adapters/__init__.py`

在 `ADAPTER_REGISTRY` 中注册 `glm_ocr`。

## 验收标准
1. `GLMOCRAdapter` 继承 `BaseParserAdapter`，实现 `parse()` 和 `is_available()`
2. `ADAPTER_REGISTRY["glm_ocr"]` 可用
3. `is_available()` 在 GLM-OCR 未安装时返回 False
4. mock 测试全部通过：`cd backend && python -m pytest tests/test_glm_ocr_adapter.py -v`
5. 不修改 `base_adapter.py`、`model_eval_runner.py` 核心逻辑

## 下游动作
完成后可与 apple_baseline 做样例对比跑批，评估 GLM-OCR 是否能替代或增强当前 OCR 链路。
