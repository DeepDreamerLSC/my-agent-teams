# 任务：Adapter 重构与 GLM-OCR 迁移（Phase C）

## 任务类型
development

## 目标
重构 adapter 为 `DocumentOCRAdapter + Normalizer` 模式，将 GLM-OCR 从独立适配器迁移到新架构，消除 adapter 内的模型专属调用逻辑。

## 任务边界
- 重构 `base_adapter.py` 支持配置注入
- 新增 `adapter_utils.py` 抽取公共逻辑
- 新增 `DocumentOCRAdapter` 和 `normalizers/` 模块
- 迁移 GLM-OCR 为新架构首个实例
- 保留 `apple_baseline_adapter.py` 不变（暂不迁移）
- 依赖 Phase A（配置）和 Phase B（backend）

## 输入事实
- 架构方案：`/Users/linsuchang/Desktop/work/chiralium/design/pdf2word/PDF转Word本地模型横评推理架构落地方案.md` Section 8、9
- Phase A 产出：`inference/config.py`、`inference/registry.py`
- Phase B 产出：`inference/backend.py`、`inference/schemas.py`、四种 backend
- 现有 `glm_ocr_adapter.py`：包含 HTTP/SDK 调用、block coercion、render 逻辑混合
- 现有 `apple_baseline_adapter.py`：作为参照

## 约束
- write_scope 以 task.json 为准
- `apple_baseline_adapter.py` 行为不破坏
- 新增 `DocumentOCRAdapter` 必须是通用类，不包含 GLM-OCR 专属逻辑
- GLM-OCR 专属逻辑全部迁移到 `normalizers/glm_ocr.py`
- 删除旧的 `GLM_OCR_API_URL` / `GLM_OCR_SDK_MODULE` 散落配置，改走 YAML

## 交付物

### 1. `adapter_utils.py`
从现有 adapter 抽取公共工具：
- `_select_rendered_pages` — 页选择逻辑
- `_normalize_requested_pages` — 页码归一化
- `_coerce_source_block` — block kind 强制转换
- `_normalize_block_kind` — kind 别名归一（formula→formula_candidate, picture→image 等）
- `_block_sort_key` — block 排序
- `_build_metrics` — metrics 构建
- `_current_peak_memory_mb` — 内存测量

### 2. `base_adapter.py` 改造
- 保留 `BaseParserAdapter.parse()` 抽象方法签名不变
- 新增可选配置注入：`__init__(self, *, profile=None, backend=None, normalizer=None)`
- 保持向后兼容：不传配置时行为不变

### 3. `document_ocr_adapter.py`
通用文档 OCR adapter：
```text
parse():
  -> render pages (pypdfium2)
  -> for each page: backend.infer_page(request) -> response
  -> normalizer.to_page_ir(response, rendered_page) -> PageIR
  -> collect AdapterResult
```
不含任何模型专属逻辑，所有模型差异通过 backend + normalizer 消化。

### 4. `normalizers/` 模块
- `normalizers/__init__.py` — `create_normalizer(name) -> ParserOutputNormalizer` 工厂
- `normalizers/base.py` — `ParserOutputNormalizer` Protocol（name, to_page_ir）
- `normalizers/glm_ocr.py` — GLM-OCR raw output → PageIR 转换
  - bbox 坐标归一化为 PDF points
  - block kind 归一化
  - JSON 解析失败进入 warnings
  - 从旧 `glm_ocr_adapter.py` 迁移 block coercion 逻辑

### 5. `glm_ocr_adapter.py` 改造
- 改为薄封装：继承或委托 `DocumentOCRAdapter`，不再包含 HTTP/SDK 调用逻辑
- 或者直接删除，由 registry 通过 `document_ocr + glm_ocr_blocks normalizer` 创建

### 6. 测试 `test_pdf_to_word_document_ocr_adapter.py`
- `DocumentOCRAdapter` + fake backend + fake normalizer → 完整 parse 流程
- GLM-OCR normalizer：mock 响应 → 正确 PageIR / PDFSourceBlock
- block kind 归一化覆盖所有别名
- JSON 解析失败 → warnings，不静默忽略
- adapter_utils 各工具函数单元测试

## 验收标准
1. `DocumentOCRAdapter` 不含任何 GLM-OCR 专属逻辑
2. GLM-OCR 通过 `document_ocr + glm_ocr_blocks normalizer` 工作正常
3. `adapter_utils.py` 抽取了所有公共逻辑
4. `ParserOutputNormalizer` Protocol 定义完整
5. 旧 `GLM_OCR_API_URL` / `GLM_OCR_SDK_MODULE` 环境变量不再使用
6. 所有测试通过：`cd backend && python -m pytest tests/test_pdf_to_word_document_ocr_adapter.py -v`
7. `apple_baseline` 行为不破坏

## 下游动作
完成后为 Phase D（VLMReviewAdapter）提供 adapter 基础设施。PaddleOCR-VL 后续只需新增 normalizer + YAML profile 即可接入。
