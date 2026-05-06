# 任务：补齐看板沟通详情前端自动化测试

## 任务类型
开发

## 目标
为任务详情抽屉、状态时间线、沟通时间线和空态场景补齐前端自动化测试，完成第一期开发侧测试补强。

## 任务边界
- 只负责前端测试与必要的小修。
- 不负责新增分析图表。

## 输入事实
- 当前详情抽屉、状态流转时间线、沟通时间线已存在。
- `design/任务协作看板-任务拆解.md` 中 `PH1-12A` 尚未完成。

## 约束
- write_scope:
  - `dashboard/static/js`
  - `dashboard/static/css`
  - `dashboard/templates`
  - `dashboard/tests`
- read_only: false
- target_environment: dev
- execution_mode: dev
- owner_approval_required: false
- 覆盖无 communication、缺失阶段耗时、排序、空态等情况。

## 交付物
- 前端自动化测试
- 必要的小修
- `result.json`

## 验收标准
1. 至少覆盖任务详情抽屉打开、状态时间线渲染、沟通时间线渲染、空态 fallback。
2. 时间线排序与展示逻辑有测试兜底。
3. 不引入 UI 回归。

## 下游动作
review
