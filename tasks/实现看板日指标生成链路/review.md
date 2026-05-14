# Code Review - 实现看板日指标生成链路

审查结论：APPROVE

## 审查范围
- `dashboard/metrics.py`
- `dashboard/tests/test_dashboard_metrics.py`
- `task.json`
- `result.json`
- 相关验证命令输出

## 复审结论
本轮复审通过。此前 `REQUEST CHANGES` 的唯一阻塞项是新增测试文件 `dashboard/tests/test_dashboard_metrics.py` 不在 `write_scope` 内；当前 `task.json.write_scope` 已明确补入该文件，流程阻塞已解除。`transitions.jsonl` 也记录了 PM 的扩 scope 仲裁。

## 通过项

### 1. `--project` 重建不再污染 `__all__` 全局口径
- `rebuild_daily_metrics()` 现在仅在全量重建（`project is None`）时插入 `__all__`；指定 `project` 时只重建该项目自身指标。
- 关键实现：`dashboard/metrics.py:253-257`、`261-275`。
- 这直接修复了上一轮驳回的核心问题：单项目重建不再把缩窄后的任务集写回默认 API 读取的全局聚合行。

### 2. 新增回归测试与修复点对齐
- `test_project_rebuild_does_not_overwrite_all_aggregate_rows()` 验证全量重建后再做单项目重建，`task_metrics_daily.project='__all__'` 统计保持不变。
- `test_api_metrics_default_query_keeps_all_scope_after_project_rebuild()` 验证 `/api/metrics/daily` 默认查询仍返回真实 `__all__` 口径。
- 见 `dashboard/tests/test_dashboard_metrics.py:78-119`。

### 3. 授权范围现已匹配实际改动
- 当前 `task.json.write_scope` 已包含：
  - `dashboard/tests/test_dashboard_metrics.py`
- 因此上一轮唯一的 scope 越界阻塞已经被正式解除，本次没有新的越界问题。

## 验证证据
已复跑：

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/tmp/taskboard-pyc python3 -m py_compile \
  /Users/linsuchang/Desktop/work/my-agent-teams/dashboard/metrics.py \
  /Users/linsuchang/Desktop/work/my-agent-teams/dashboard/tests/test_dashboard_metrics.py

python3 -m unittest /Users/linsuchang/Desktop/work/my-agent-teams/dashboard/tests/test_dashboard_metrics.py -v

python3 -m unittest discover -s /Users/linsuchang/Desktop/work/my-agent-teams/dashboard/tests -p 'test_*.py' -v
```

结果：
- `py_compile` 通过
- 指标专项测试 `2 tests OK`
- dashboard 全量测试 `10 tests OK`

## 非阻塞备注
- 当前任务目录仍无新的 `verify.json`；本次结论基于代码与本地回归验证给出。
- 本次补修仍严格收敛在上一轮 review 阻塞点，没有观察到对 `/api/board`、`/api/gantt`、任务详情接口的回归。

## 最终意见
此前唯一阻塞已经通过 PM 扩容 `write_scope` 正式解除；功能修复正确、回归测试充分、当前代码可合入。审查通过：**APPROVE**。
