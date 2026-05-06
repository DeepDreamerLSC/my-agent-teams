# 任务：实现看板只读聚合视图

## 任务类型
开发

## 目标
实现第二期的只读聚合视图，让 PM 可按 owner_pm/domain/task_level/parent_task_id/root_request_id 观察任务树与拥塞点。

## 任务边界
- 只负责聚合查询与必要的脚本/接口。
- 不负责前端分析页。

## 输入事实
- 方案与任务拆解中明确要求“先做只读聚合视图，不急着上分层 PM runtime”。
- 当前 tasks 表已具备 owner_pm、domain、task_level、parent/root 字段。

## 约束
- write_scope:
  - `dashboard/query.py`
  - `dashboard/app.py`
  - `scripts/task-aggregate.py`
  - `dashboard/metrics.py`
- read_only: false
- target_environment: dev
- execution_mode: dev
- owner_approval_required: false
- 输出应保持只读，不改变 task 事实源。

## 交付物
- 聚合查询/API/脚本
- `result.json`

## 验收标准
1. 至少支持按 owner_pm/domain/task_level/parent_task_id/root_request_id 汇总。
2. PM 可通过脚本或 API 获得只读摘要。
3. 不把聚合视图误当成状态事实源。

## 下游动作
review
