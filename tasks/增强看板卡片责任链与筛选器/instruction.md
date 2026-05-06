# 任务：增强看板卡片责任链与筛选器

## 任务类型
开发

## 目标
在现有 Kanban 基础上，补齐第一期剩余的责任链信息与筛选器能力，让看板卡片更适合日常 PM 使用。

## 任务边界
- 只负责 dashboard 前端 UI/交互。
- 不负责后端指标分析页。
- 可按需要少量调用既有查询参数，但不要扩写第二期分析能力。

## 输入事实
- 当前卡片已支持基础字段、沟通数、详情抽屉点击。
- `design/任务协作看板-任务拆解.md` 中 `PH1-13` 仍未完成：
  - owner_pm / reviewer / integration_owner
  - 当前状态停留时长
  - priority / target_environment 标记
  - project / domain / assigned_agent / owner_pm / review_level 筛选器

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
- 不要破坏现有详情抽屉与三大 Tab。

## 交付物
- 卡片增强
- 筛选器 UI/交互
- 如有必要的前端辅助逻辑与测试
- `result.json`

## 验收标准
1. Kanban 卡片能显示责任链关键字段与状态停留信息。
2. 至少支持按 project/domain/assigned_agent/owner_pm/review_level 做筛选。
3. 详情抽屉和现有视图不回归。
4. 有对应的前端测试或最小验证说明。

## 下游动作
review
