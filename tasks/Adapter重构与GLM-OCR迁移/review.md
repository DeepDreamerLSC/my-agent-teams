# Review - Adapter重构与GLM-OCR迁移

## 结论
- 结果：`approve`
- 说明：上轮阻塞问题已修复，当前可以过审。

## 本轮确认通过的点

### 1) 包级导出已接到真实 DocumentOCRAdapter
`backend/app/services/pdf_to_word/parser_adapters/__init__.py`

当前包级导出的 `DocumentOCRAdapter` 已直接来自真实实现文件：
- `from .document_ocr_adapter import DocumentOCRAdapter`
- `ADAPTER_REGISTRY['paddleocr_vl'] = DocumentOCRAdapter`

不再是之前 `inference.registry` 里的占位类。

### 2) registry / factory 已接到真实 document_ocr 实现
`backend/app/services/pdf_to_word/parser_adapters/inference/registry.py`

当前：
- `ADAPTER_CLASS_REGISTRY['document_ocr']` 已指向真实 `DocumentOCRAdapter`
- `create_adapter()` 对非 Apple / 非 GLM 的 `document_ocr` profile 会注入：
  - `profile`
  - `backend=create_backend(...)`
  - `normalizer=_maybe_create_normalizer(profile)`

这已经把公开 factory 接到本轮 Phase C 的真实基础设施上。

### 3) 回归测试覆盖了上轮遗漏的 public wiring
`backend/tests/test_pdf_to_word_inference_config.py`

新增测试覆盖了：
- `parser_adapters.DocumentOCRAdapter is RealDocumentOCRAdapter`
- `ADAPTER_CLASS_REGISTRY['document_ocr'] is RealDocumentOCRAdapter`
- `create_adapter('glm_ocr')` 返回 `GLMOCRAdapter`，且是 `RealDocumentOCRAdapter` 子类
- `create_adapter('paddleocr_vl')` 返回真实 `DocumentOCRAdapter`

这正好补上了上轮 review 指出的测试缺口。

## 验证结果
- `py_compile`：通过
- `pytest tests/test_pdf_to_word_inference_config.py tests/test_pdf_to_word_document_ocr_adapter.py tests/test_glm_ocr_adapter.py -q`：`30 passed`
- 内联类型校验：通过
  - `exported_is_real=True`
  - `registry_document_ocr_is_real=True`
  - `glm_is_real_doc_ocr=True`
  - `glm_is_glm_wrapper=True`

## 非阻塞观察

### 1) GLM normalizer 仍未对缺失 confidence 记 warning
`backend/app/services/pdf_to_word/parser_adapters/normalizers/glm_ocr.py`

当前仍是静默补 `confidence=1.0`。这不影响本轮通过，但和设计文档里“补默认值并记 warning”的要求还有一点差距。

### 2) Paddle normalizer 仍待后续任务接入
当前 `paddleocr_vl` 已返回真实 `DocumentOCRAdapter`，但专属 normalizer 尚未落地，所以还不是完整可跑形态。这个风险已在 `result.json` 里写明，属于后续任务范围。
