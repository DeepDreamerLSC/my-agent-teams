# 任务：修正任务看板前端接口契约与五列状态映射

## 背景

PM 在验收 `任务看板前端可视化实现` 时发现两个阻塞问题：

### 阻塞 1：前端调用的 API 与架构/后端实现不一致
- 架构方案规定 API：
  - `/api/health`
  - `/api/board`
  - `/api/gantt`
  - `/api/agents`
- 后端当前实现也是这组 API：
  - `/Users/lin/Desktop/work/my-agent-teams/dashboard/app.py:42-79`
- 但前端当前代码仍在请求：
  - `/api/tasks`
  - `/api/tasks/gantt`
  - `/api/agents/stats`
  见：`/Users/lin/Desktop/work/my-agent-teams/dashboard/static/js/dashboard.js:29-57`

### 阻塞 2：看板列数与方案不一致
- 架构方案要求只有五列：
  - `pending / working / ready_for_merge / blocked / done`
  - 且 `dispatched -> pending`
  见：`/Users/lin/Desktop/work/my-agent-teams/design/任务看板系统方案.md` 中 board_status 设计
- 但当前前端使用了 6 列，把 `dispatched` 独立成一列：
  - `dashboard/static/js/dashboard.js:2-14`

## 你的任务

修正前端看板页面，使其真正对齐：
1. **后端 API contract**
2. **五列状态映射**
3. **后端返回的 payload shape**

## 必改要求

### A. API 对齐
将前端数据请求改为消费后端实际实现：
- `/api/board`
- `/api/gantt`
- `/api/agents`

### B. 五列状态
前端看板必须只保留：
- pending
- working
- ready_for_merge
- blocked
- done

`dispatched` 不能独立成一列，而应通过：
- `board_status=pending`
- `current_status=dispatched` badge
来表达。

### C. payload shape 对齐
不要再假设后端直接返回“tasks 数组 / gantt 数组 / stats 数组”的裸数据。
请按实际 API contract 消费后端 payload。

### D. 保持现有 UI 目标
保留三视图目标：
- 看板
- 甘特图
- Agent 统计

## write_scope

仅允许修改：
- `/Users/lin/Desktop/work/my-agent-teams/dashboard/templates`
- `/Users/lin/Desktop/work/my-agent-teams/dashboard/static`

## 测试要求

至少补充/更新：
- 状态列映射测试
- API 响应 shape 兼容测试 / 数据转换测试

## 交付物

完成后请写：
- `/Users/lin/Desktop/work/my-agent-teams/tasks/修正任务看板前端接口契约/result.json`
