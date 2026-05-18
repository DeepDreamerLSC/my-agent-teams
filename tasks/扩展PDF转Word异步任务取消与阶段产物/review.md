# 审查说明：扩展PDF转Word异步任务取消与阶段产物

## 结论

**通过（approve）**。这次实现把最关键的产品化边界讲清楚了：取消不是“看起来取消了”，而是区分 `queued -> cancelled` 和 `running -> cancel_requested -> cancelled/succeeded/failed` 两类语义；如果 worker 不响应取消，也会把 `cancellation.outcome` 和历史保留下来，而不是伪装成已经中断。

## 复核结果

- 状态机诚实：
  - 新增 `cancel_requested` 与 `cancelled`。
  - `queued` 阶段取消会直接完成并落盘。
  - `running` 阶段只承诺 best-effort；worker 接受取消时转 `cancelled`，否则最终仍可能 `succeeded/failed`。
- 阶段产物边界清楚：
  - `job.json` 记录完整状态、stage、cancellation、history 和 artifact 路径。
  - `stage.json` 提供当前阶段快照。
  - `history.jsonl` 保留阶段事件与流转轨迹。
  - 成功才有最终 `output.docx`，真正取消生效时不会伪造输出。
- API 口径一致：
  - `POST /api/pdf-to-word/jobs/{job_id}/cancel`
  - 查询返回 `status_url` 和 `cancel_url`
  - 已完成 job 返回 409，未知 job 返回 404

## 测试

我复跑了任务里声明的 pytest：

```bash
PYTHONDONTWRITEBYTECODE=1 /Users/linsuchang/Desktop/work/chiralium/backend/.venv/bin/python -m pytest /Users/linsuchang/Desktop/work/chiralium/backend/tests/test_pdf_to_word_api.py /Users/linsuchang/Desktop/work/chiralium/backend/tests/test_pdf_to_word_async_jobs.py -o cache_dir=/private/tmp/chiralium-pytest-pdf-job-cancel-cache --basetemp=/private/tmp/chiralium-pytest-pdf-job-cancel-tmp -q
```

结果：`17 passed, 4 warnings in 0.19s`。

## 非阻塞提示

当前测试已经覆盖 queued cancel、running cancel、worker ignore cancel 和 completed job 409，但没有单独覆盖“已 cancelled 再次取消幂等返回当前状态”的回归用例。代码分支本身是清楚的，不构成驳回；后续可以补一个小测试，把这个状态机边角也锁住。

## 下一步

建议进入 QA / verify。

审查时间：2026-05-18T14:21:07+08:00
