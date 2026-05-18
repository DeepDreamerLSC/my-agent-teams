# 审查说明：搭建PDF转Word本地模型横评框架

## 结论

**通过（approve）**。本次实现已覆盖任务要求的横评框架骨架：

- `model_eval_runner.py` CLI 入口
- `parser_adapters/base_adapter.py` 基础接口与数据结构
- `parser_adapters/apple_baseline_adapter.py` Apple CLI 基线适配器
- `parser_adapters/__init__.py` 注册表
- `backend/tests/test_model_eval_runner.py` 测试

未发现阻塞合并的问题。

## 审查范围

- `backend/app/services/pdf_to_word/model_eval_runner.py`
- `backend/app/services/pdf_to_word/parser_adapters/__init__.py`
- `backend/app/services/pdf_to_word/parser_adapters/base_adapter.py`
- `backend/app/services/pdf_to_word/parser_adapters/apple_baseline_adapter.py`
- `backend/tests/test_model_eval_runner.py`
- 任务输入：`instruction.md`、`result.json`

## 复核结果

- 框架边界符合要求：未修改 `conversion_service.py`、`parser_client.py` 等现有生产链路文件。
- `BaseParserAdapter` / `AdapterResult` / `PageIR` / `EvalMetrics` 已定义，且具备序列化输出能力。
- `apple_baseline` 适配器复用了现有 Apple Worker CLI 调用链（`render_pdf_pages_for_parser` + `build_parser_request_payload` + `parse_with_backend`），并把结果转成 `PageIR / PDFSourceBlock` 兼容结构。
- `model_eval_runner` 已支持 `--samples-dir`、`--output-dir`、`--profiles`、`--profile`、`--pages` 参数，并能输出 `pages.jsonl`、`metrics.json`、`warnings.json`、`output.docx`。
- 测试覆盖了接口契约、注册表、适配器可用性、CLI 参数解析、Apple 适配器结果转换，以及输出目录结构。

## 测试复核

已复跑：

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/chiralium-pyc backend/.venv/bin/python -m py_compile backend/app/services/pdf_to_word/model_eval_runner.py backend/app/services/pdf_to_word/parser_adapters/__init__.py backend/app/services/pdf_to_word/parser_adapters/base_adapter.py backend/app/services/pdf_to_word/parser_adapters/apple_baseline_adapter.py backend/tests/test_model_eval_runner.py

TMPDIR=/private/tmp PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/chiralium-pyc PYTEST_ADDOPTS='-p no:cacheprovider' backend/.venv/bin/python -m pytest backend/tests/test_model_eval_runner.py -q
```

结果：`7 passed, 4 warnings`。warnings 为现有 FastAPI `on_event` 弃用提示，不阻塞本任务。

## 非阻塞建议

1. 当前 `--pages` 的 0-based / 1-based 兼容是靠“是否包含 0”推断，`--pages 2` 这类输入仍有语义歧义；后续若对外使用，建议显式声明页码基准或增加 `--page-base` 参数。
2. 审查时工作区存在本任务 write_scope 之外的其他未提交/未跟踪内容（如先前 PDF API 相关文件、`.runtime`、`example` 产物），这些未纳入本次审查；集成时建议只合入本任务声明的 5 个文件。

## 下一步

建议进入 QA 验证。

审查时间：2026-05-14T12:56:52+08:00
