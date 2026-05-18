# 任务：搭建 GLM-OCR 本地推理环境

## 任务类型
development（环境搭建）

## 目标
在 M5 Max 128GB Apple Silicon 上搭建 GLM-OCR 本地推理服务，使现有 `glm_ocr_adapter.py` 的 `is_available()` 返回 True，`parse()` 能成功调用本地推理。

## 任务边界
- 只搭建推理环境和更新适配器配置，不修改框架核心逻辑
- 优先走 MLX 后端（Apple Silicon 原生加速），如果 MLX 不支持则走 vLLM 或 llama.cpp
- 不做样例跑批（跑批是单独任务）

## 输入事实
- 硬件：M5 Max 128GB，Apple Silicon
- 现有适配器：`/Users/linsuchang/Desktop/work/chiralium/backend/app/services/pdf_to_word/parser_adapters/glm_ocr_adapter.py`
- 适配器当前检测逻辑：检查 `zhipuai` SDK 或 `GLM_OCR_API_URL` 环境变量
- 后端 venv：`/Users/linsuchang/Desktop/work/chiralium/backend/.venv/`
- 当前 `is_available()` 返回 False

## 约束
- write_scope 以 task.json 为准
- 推理服务必须在本机启动，不依赖云端 API
- 模型下载后应缓存到本地，不要每次重新下载
- 需要评估模型显存/内存占用，确保 128GB 内存足够
- 如果需要修改适配器的调用方式（从 HTTP API 改为本地推理调用），可以在 write_scope 内修改 `glm_ocr_adapter.py`

## 交付物

### 1. GLM-OCR 模型部署
- 确认 GLM-OCR 的具体模型名称和来源（HuggingFace / ModelScope）
- 下载模型权重到本地缓存目录（建议 `.runtime/models/glm-ocr/` 或类似位置）
- 选择合适的推理后端：
  - 首选：MLX（Apple Silicon 原生加速）
  - 备选：vLLM、llama.cpp、transformers + torch.mps
- 启动推理服务（HTTP API 或 Python 直接调用均可）
- 记录：模型大小、首次加载耗时、推理延迟

### 2. 适配器配置更新
- 更新 `glm_ocr_adapter.py` 的调用方式以适配本地推理
- 如果使用 HTTP API：设置 `GLM_OCR_API_URL`（如 `http://localhost:8000/v1/ocr`）到 `.env`
- 如果使用 Python 直接调用：更新 `is_available()` 和 `parse()` 使用本地推理 SDK
- 确保 `is_available()` 在环境就绪后返回 True

### 3. 环境验证
- 运行 `is_available()` 确认返回 True
- 用一张简单页图调用 `parse()` 确认返回合法 `AdapterResult`
- 记录单页推理耗时

## 验收标准
1. GLM-OCR 模型权重已下载并缓存在本地
2. 推理服务可正常启动（HTTP API 或 Python 调用）
3. `is_available()` 返回 True
4. `parse()` 对单页测试图片返回合法 `AdapterResult`（非 mock）
5. 单页推理耗时记录在案
6. 内存/显存占用评估完成，确认 128GB 足够

## 下游动作
完成后可创建"跑 glm_ocr 样例对比"任务，用同样 5 个样例与 apple_baseline 对比。同时此环境搭建经验可为 PaddleOCR-VL、Qwen3-VL 等后续模型提供参考。
