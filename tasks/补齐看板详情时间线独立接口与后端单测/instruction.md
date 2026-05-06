# 任务：补齐看板详情时间线独立接口与后端单测

## 任务类型
开发

## 目标
在现有 `/api/tasks/<id>/detail` 基础上，补齐独立的 timeline / communications 查询接口与后端自动化测试，收敛任务详情后端契约。

## 任务边界
- 只负责后端 API / query / tests。
- 不负责前端详情抽屉渲染。
- 不负责分析页。

## 输入事实
- 现有已实现 `/api/tasks/<id>/detail`。
- `design/任务协作看板-任务拆解.md` 中 `PH1-08` / `PH1-08A` 仍有剩余项：
  - timeline 独立接口
  - communications 独立接口
  - 自动化测试
- 现有 communication_events 已能入库。

## 约束
- write_scope:
  - `dashboard/app.py`
  - `dashboard/query.py`
  - `dashboard/ingest.py`
  - `dashboard/db.py`
  - `dashboard/tests`
- read_only: false
- target_environment: dev
- execution_mode: dev
- owner_approval_required: false
- 需要覆盖空 communication、排序稳定性、缺失 review/verify 等场景。

## 交付物
- 新增或补齐接口：
  - `/api/tasks/<id>/timeline`
  - `/api/tasks/<id>/communications`
- 后端测试
- `result.json`

## 验收标准
1. 新接口返回口径稳定，与 `/detail` 一致。
2. timeline / communications 可分别单独拉取。
3. 至少覆盖 query/app 的自动化测试。
4. 不破坏现有 `/api/board`、`/api/gantt`、`/api/tasks/<id>/detail`。

## 下游动作
review
