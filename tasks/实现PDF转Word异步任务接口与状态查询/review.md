# 审查说明：实现PDF转Word异步任务接口与状态查询

## 结论

**通过（approve）**。本次实现满足任务目标：新增 `POST /api/pdf-to-word/jobs` 与 `GET /api/pdf-to-word/jobs/{job_id}`，补齐最小本地异步 job 执行骨架，状态覆盖 `queued / running / succeeded / failed`，成功后可定位输出 DOCX，失败时可返回错误信息；同步 `POST /api/pdf-to-word/convert` 路径未回归。

## 审查范围

- `backend/app/api/pdf_to_word.py`
- `backend/app/services/pdf_to_word/job_service.py`
- `backend/app/services/pdf_to_word/settings.py`
- `backend/tests/test_pdf_to_word_api.py`
- `backend/tests/test_pdf_to_word_async_jobs.py`
- `artifacts/pdf2word/p2-productization/async_job_api_summary.md`
- 任务输入：`instruction.md`、`result.json`、`task.json`

## 复核结果

- 接口形态符合任务要求：
  - `POST /api/pdf-to-word/jobs` 返回 `202 Accepted`，创建后给出 `job_id`、`status=queued`、`status_url` 与 artifact 路径。
  - `GET /api/pdf-to-word/jobs/{job_id}` 能返回当前状态与结果/错误信息，未知 job 返回 404。
- 异步执行骨架符合“最小可运行、本地可回放”边界：
  - job 创建时落盘 `input/<source>.pdf` 与 `job.json`。
  - 后台通过 `asyncio.create_task()` 启动，运行后复制最终 DOCX 到 `output/`。
  - 成功和失败都会把状态、时间戳、history、result/error 写回 manifest。
- 发布边界未被绕开：
  - job service 仍通过现有 `normalize_conversion_mode` / `resolve_released_parser_backend` 收敛生效 mode 与 parser backend。
  - `hybrid_experimental` 仍只在 `quality` 模式下放行，和当前发布约束一致。
- 同步接口未回归：
  - `POST /api/pdf-to-word/convert` 代码路径保持原有同步语义，API 测试继续覆盖下载流、默认参数、hybrid 参数透传、非 PDF 拒绝与未登录 401。

## 测试

已复跑：

```bash
PYTHONDONTWRITEBYTECODE=1 /Users/linsuchang/Desktop/work/chiralium/backend/.venv/bin/python -m pytest /Users/linsuchang/Desktop/work/chiralium/backend/tests/test_pdf_to_word_api.py /Users/linsuchang/Desktop/work/chiralium/backend/tests/test_pdf_to_word_async_jobs.py -o cache_dir=/private/tmp/chiralium-pytest-pdf-job-cache --basetemp=/private/tmp/chiralium-pytest-pdf-job-tmp -q
```

结果：`12 passed, 4 warnings in 0.16s`。warnings 为现有 FastAPI `on_event` 弃用提示，不阻塞本任务。

## 非阻塞提示

当前实现是单进程内 `asyncio.create_task()` + 本地磁盘落盘骨架；进程在 `queued/running` 阶段退出后不会自动重放未完成 job。该限制已经在 `result.json` 与 `async_job_api_summary.md` 中明确披露，符合本任务“首轮最小可运行骨架”的边界，不构成驳回条件；后续若要把该能力作为更稳健的长任务接口，需要补外部队列或重启后的 reconcile/replay 机制。

## 下一步

建议进入 QA 验证。

审查时间：2026-05-18T09:10:41+08:00
