# 审查说明：MinerU本地Adapter接入PDF转Word（补修后复审）

## 结论

**通过（approve）**。

本次复审只针对上轮指出的两个阻塞问题做核对，结果两项都已修复，且对应回归测试已补齐并通过：

1. `settings.py` 已改为优先从 `app.core.config.settings` / `ENV_FILE` 透传 `PDF_TO_WORD_PARSE_BACKEND` 与 `MINERU_*` 配置；
2. `mineru_client.py` 读取输出文件时已统一使用 `source_pdf.stem`，不再依赖 `source_name`，因此 API / skill 常见的“临时上传文件名与原始文件名不同”场景已被覆盖。

## 审查范围

- `tasks/MinerU本地Adapter接入PDF转Word/instruction.md`
- `tasks/MinerU本地Adapter接入PDF转Word/result.json`
- `backend/app/services/pdf_to_word/settings.py`
- `backend/app/services/pdf_to_word/mineru_client.py`
- `backend/tests/test_pdf_to_word_mineru_client.py`
- 受影响回归路径：`backend/app/services/pdf_to_word/conversion_service.py`、`backend/tests/test_pdf_to_word_service.py`

## 复核结果

### 1) 配置透传问题

已修复。

当前 `get_pdf_to_word_settings()` 会优先读取：

- `app_settings.PDF_TO_WORD_PARSE_BACKEND`
- `app_settings.MINERU_CLI_PATH`
- `app_settings.MINERU_PYTHON_BIN`
- `app_settings.MINERU_MODEL_DIR`
- `app_settings.MINERU_WORKDIR`
- `app_settings.MINERU_TIMEOUT_SECONDS`
- `app_settings.MINERU_PARSE_MODE`

补充的回归测试 `test_pdf_to_word_settings_reads_mineru_config_from_env_file()` 通过 `ENV_FILE` 重新加载配置模块，确认：

- `parse_backend == local_mineru_cli`
- `mineru_cli_path == /tmp/magic-pdf`
- `mineru_timeout_seconds == 456`
- `mineru_parse_mode == txt`

这正是上轮 review 要求验证的点。

### 2) 输出文件 stem 不一致问题

已修复。

当前 `parse_with_mineru()` 以 `source_pdf.stem` 计算实际输出目录，`load_mineru_outputs()` 也统一以 `resolved_source_pdf.stem` 读取：

- `<stem>_content_list.json`
- `<stem>_middle.json`
- `<stem>.md`

补充的服务级回归测试 `test_pdf_conversion_service_reads_mineru_outputs_by_temp_pdf_stem()` 已覆盖：

- 临时文件名：`upload_tmp_abc123.pdf`
- 原始文件名：`原始文件名.pdf`

在该场景下，转换仍能成功完成并返回 `原始文件名.docx`，说明此前的读取失败路径已经被消除。

## 测试复核

已复跑：

```bash
cd /Users/linsuchang/Desktop/work/chiralium/backend
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/chiralium-pyc   .venv/bin/python -m py_compile   app/services/pdf_to_word/settings.py   app/services/pdf_to_word/mineru_client.py   tests/test_pdf_to_word_mineru_client.py

TMPDIR=/private/tmp PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/chiralium-pyc PYTEST_ADDOPTS='-p no:cacheprovider'   .venv/bin/python -m pytest   tests/test_pdf_to_word_mineru_client.py   tests/test_pdf_to_word_service.py -q
```

结果：`10 passed, 4 warnings`。

warnings 为现有 FastAPI `on_event` 弃用提示，不阻塞本任务。

## 说明

- 本次是**补修后的复审**，只复核了上轮阻塞点及其受影响回归路径。
- task write_scope 中未改动的其他文件，本轮未重新逐项展开审查。

## 下一步

建议进入 QA / 集成门禁。

审查时间：2026-05-14T17:03:41+08:00
