# 任务：实现看板日指标生成链路

## 任务类型
开发

## 目标
实现第二期的日指标生成链路，为任务完成率、平均耗时、阻塞率、角色负载等分析提供稳定数据源。

## 任务边界
- 只负责后端指标生成与存储/查询基础。
- 不负责前端分析页展示。

## 输入事实
- `design/任务协作看板优化方案.md` 中第二期需要 `task_metrics_daily / agent_metrics_daily` 或等价实现。
- 当前已有 chat-metrics.py，但还不是 dashboard 级日指标链路。

## 约束
- write_scope:
  - `dashboard/metrics.py`
  - `scripts/dashboard-metrics.py`
  - `dashboard/db.py`
  - `dashboard/query.py`
  - `dashboard/app.py`
- read_only: false
- target_environment: dev
- execution_mode: dev
- owner_approval_required: false
- 设计时避免过早泛化成难维护的 EAV 实现。

## 交付物
- 日指标生成模块/脚本
- 相关数据结构与查询
- `result.json`

## 验收标准
1. 可生成完成率、平均耗时、阻塞率、角色负载等核心日指标。
2. 支持指定日期范围重建。
3. 不破坏现有 dashboard API。

## 下游动作
review
