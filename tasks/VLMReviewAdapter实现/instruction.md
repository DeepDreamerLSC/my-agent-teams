# 任务：VLMReviewAdapter 实现（Phase D）

## 任务类型
development

## 目标
实现 `VLMReviewAdapter`，使 Qwen3-VL、GLM-4.6V-Flash 等通用 VLM 可作为低置信页 review / 结构修复 worker 接入横评框架。

## 任务边界
- 实现 `VLMReviewAdapter`、prompt templates、strict JSON normalizer
- VLM 定位为 review worker，不是整页 OCR 主 parser
- 不实现模型部署（模型部署是独立任务）
- 依赖 Phase A（配置）、Phase B（backend）、Phase C（adapter 基础）

## 输入事实
- 架构方案：`/Users/linsuchang/Desktop/work/chiralium/design/pdf2word/PDF转Word本地模型横评推理架构落地方案.md` Section 8.4、9
- Phase A/B/C 产出：config、backend 抽象、DocumentOCRAdapter + normalizer 模式
- 推荐推理栈：OpenAI-compatible vision API（MLX / llama.cpp / Ollama 提供）
- VLM 角色：低置信页复核、答案区识别、图片/材料归属判断

## 约束
- write_scope 以 task.json 为准
- VLM 不直接整本 PDF 生成 Word
- 输出可以是 `PDFSourceBlock` 或 `review_suggestion` meta
- JSON 解析失败必须进入 warnings，不允许静默忽略
- prompt 必须强制 VLM 输出严格 JSON schema

## 交付物

### 1. `vlm_review_adapter.py`
```text
parse():
  -> render pages
  -> for each page: build vision prompt (image + template)
  -> backend.infer_page(request) -> response
  -> normalizer.to_page_ir(response, rendered_page) -> PageIR or review_suggestions
  -> collect AdapterResult
```
特点：
- 支持传入 prompt_template（从 profile 配置获取）
- 支持传入 output_schema（强制 JSON 输出格式）
- 输出可以是 PageIR（结构修复）或 review suggestions（低置信标注）

### 2. `prompts/qwen3_vl_page_review.md`
Qwen3-VL 页面 review prompt：
- 输入：页图
- 要求输出 JSON：题目编号、文本纠正建议、图片/公式位置、答案区标注、confidence
- 强调不要编造内容、不要猜测不确定信息

### 3. `prompts/glm_vl_page_review.md`
GLM-4.6V-Flash 页面 review prompt：
- 类似 qwen3_vl 但适配 GLM 视觉模型特性
- 同样要求严格 JSON 输出

### 4. `normalizers/vlm_review_json.py`
VLM review JSON → PageIR / review_suggestions：
- 解析 VLM 输出的 JSON
- 校验 schema：必要字段存在、类型正确
- JSON 解析失败 → warning，返回空结果（不抛异常）
- 将 review suggestions 映射为 PDFSourceBlock 或 meta

### 5. 测试 `test_pdf_to_word_vlm_review_adapter.py`
- VLMReviewAdapter + mock OpenAI vision backend → 完整流程
- qwen3_vl_8b、qwen3_vl_32b、glm_46v_flash 共享同一个 adapter
- prompt template 加载正确
- JSON schema 校验：合法 JSON → 正确 PageIR，非法 JSON → warnings
- normalizer 对缺失字段、类型错误、空响应的处理
- `ADAPTER_CLASS_REGISTRY["vlm_review"]` 注册正确

## 验收标准
1. `VLMReviewAdapter` 通过 OpenAI-compatible vision backend 调用 VLM
2. qwen3_vl_8b、qwen3_vl_32b、glm_46v_flash 三个 profile 共享同一个 adapter class
3. prompt templates 要求严格 JSON 输出
4. JSON 解析失败进入 warnings，不静默忽略
5. 所有测试通过：`cd backend && python -m pytest tests/test_pdf_to_word_vlm_review_adapter.py -v`
6. 不修改 `DocumentOCRAdapter`、`base_adapter.py` 核心逻辑

## 下游动作
完成后四个 Phase 全部就绪，可以：
1. 部署具体模型（GLM-OCR 本地推理、Qwen3-VL 本地推理等）
2. 用 `model_eval_runner` 跑所有 profiles 的样例对比
3. 汇总横评报告，决定 parser 替换/增强策略
