# 审查说明：接入GLM-OCR适配器到横评框架

## 结论

**通过（approve）**。本次实现已完成：

- `GLMOCRAdapter` 适配器
- `ADAPTER_REGISTRY` 注册 `glm_ocr`
- `tests/test_glm_ocr_adapter.py` mock 测试

未发现阻塞合并的问题。

## 审查范围

- `backend/app/services/pdf_to_word/parser_adapters/glm_ocr_adapter.py`
- `backend/app/services/pdf_to_word/parser_adapters/__init__.py`
- `backend/tests/test_glm_ocr_adapter.py`
- 任务输入：`instruction.md`、`result.json`

## 复核结果

- `GLMOCRAdapter` 已继承 `BaseParserAdapter`，并实现 `parse()` / `is_available()`。
- `parse()` 先渲染页图，再按 HTTP API 或 Python SDK 路径执行单页 OCR，并统一转成 `PageIR / PDFSourceBlock / EvalMetrics`。
- block kind 已对 `formula/equation -> formula_candidate`、`picture/figure -> image` 做别名归一。
- 注册表已包含 `ADAPTER_REGISTRY["glm_ocr"]`。
- mock 测试覆盖了：可用性 true/false、不可用时报错、AdapterResult 输出、PageIR block 转换、注册表注册。

## 测试复核

已复跑：

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/chiralium-pyc backend/.venv/bin/python -m py_compile backend/app/services/pdf_to_word/parser_adapters/glm_ocr_adapter.py backend/app/services/pdf_to_word/parser_adapters/__init__.py backend/tests/test_glm_ocr_adapter.py

TMPDIR=/private/tmp PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/chiralium-pyc PYTEST_ADDOPTS='-p no:cacheprovider' backend/.venv/bin/python -m pytest backend/tests/test_glm_ocr_adapter.py -q
```

结果：`6 passed, 4 warnings`。warnings 为现有 FastAPI `on_event` 弃用提示，不阻塞本任务。

## 非阻塞建议

1. 当配置 `GLM_OCR_API_URL` 时，`is_available()` 当前只检查 URL 是否存在，不会探测服务是否真正在运行；后续可补 health/ping。
2. `__init__.py` 注册表更新不在当前 `task.json.write_scope` 中；`result.json` 已说明这是基于当前对话中的明确授权执行，建议 PM 在任务上下文里补齐该例外记录。
3. 当前仅验证了 mock 契约，真实 GLM-OCR 环境的 HTTP/SDK 返回结构仍需在后续跑批任务中实测确认。

## 下一步

建议进入 QA；通过后可继续执行真实 GLM-OCR 样例跑批。

审查时间：2026-05-14T15:17:48+08:00
