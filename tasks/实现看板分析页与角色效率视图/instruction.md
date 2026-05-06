# 任务：实现看板分析页与角色效率视图

## 任务类型
开发

## 目标
实现第二期的前端分析页与角色效率视图，把完成率、平均耗时、角色负载、owner_pm/domain 聚合等结果展示出来。

## 任务边界
- 只负责前端展示层。
- 不负责后端指标计算逻辑。

## 输入事实
- 第二期目标是让看板回答效率与瓶颈问题。
- 后端将补日指标与只读聚合视图。

## 约束
- write_scope:
  - `dashboard/templates/index.html`
  - `dashboard/static/js/dashboard.js`
  - `dashboard/static/css/style.css`
  - `dashboard/static/js/helpers.js`
- read_only: false
- target_environment: dev
- execution_mode: dev
- owner_approval_required: false
- 不破坏现有看板 / 甘特图 / 详情抽屉。

## 交付物
- 分析页 / 角色效率视图
- `result.json`

## 验收标准
1. 看板能展示完成率、平均耗时、角色负载等基础分析。
2. 至少能展示 owner_pm / domain 聚合摘要。
3. 现有视图不回归。

## 下游动作
review
