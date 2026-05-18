# 审查说明：补充PDF转Word独立API路由

## 结论

**通过（approve）**。实现满足任务目标：新增 `POST /api/pdf-to-word/convert` 与 `GET /api/pdf-to-word/health`，完成 API 模块导出、`main.py` 路由注册，并补充 API 级测试。

## 审查范围

- `backend/app/api/pdf_to_word.py`
- `backend/app/api/__init__.py`
- `backend/app/main.py`
- `backend/tests/test_pdf_to_word_api.py`
- 任务输入：`instruction.md`、`result.json`

## 复核结果

- convert 路由：接收 `UploadFile`，支持 `mode` / `parser_backend` 表单参数，调用 `PDFConversionService.convert()`，返回 DOCX `StreamingResponse` 与 `Content-Disposition`。
- 权限：路由使用 `require_permission("chat.file.upload")`，符合任务中“或复用已有文件权限”的边界说明。
- 错误处理：非 `.pdf` 文件返回 400；服务层已继续校验 PDF header、大小、页数；转换异常返回 500。
- 路由注册：已在 `app.include_router(pdf_to_word.router, prefix="/api", tags=["pdf-to-word"])` 注册。
- 服务层边界：本次审查的声明文件未修改 `backend/app/services/pdf_to_word/`。

## 测试

已复跑：

```bash
TMPDIR=/private/tmp PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/chiralium-pyc backend/.venv/bin/python -m pytest backend/tests/test_pdf_to_word_api.py -q
```

结果：`5 passed, 5 warnings`。warnings 为现有 FastAPI `on_event` 弃用提示和沙箱下 `.pytest_cache` 写入限制，不阻塞本任务。

## 非阻塞建议

1. `health` 当前固定返回 `available=true`，后续如果要作为真实监控信号，可补 parser/worker 探活。
2. 测试已覆盖未登录 401，后续可补“已登录但无权限返回 403”的用例。
3. 审查时工作区存在本任务 write_scope 之外的未提交/未跟踪变更（如 `design/pdf2word`、`.runtime`、`example` 输出），这些不在 dev-1 的 `result.json.modified_files` 中，未纳入本次审查；集成时建议只合入本任务四个声明文件。

## 下一步

建议进入 QA 验证。

审查时间：2026-05-14T11:21:35+08:00
