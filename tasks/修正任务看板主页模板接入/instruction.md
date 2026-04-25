# 任务：修正任务看板 Flask 根路由与模板接入

## 背景

PM 在验收时发现：
- 当前 `dashboard/app.py` 的 `/` 路由返回的是 API JSON 列表，而不是任务看板页面
  见：`/Users/lin/Desktop/work/my-agent-teams/dashboard/app.py:34-40`

而该需求要求的是：
- Flask + ECharts 单页 dashboard
- 页面应可通过 Flask 直接访问

也就是说，虽然 API 已存在，但**前端模板还未真正被 Flask 应用接入**。

## 你的任务

把任务看板主页真正接入 Flask：
1. `/` 返回任务看板页面模板，而不是 API JSON
2. 仍保留 JSON API：
   - `/api/health`
   - `/api/board`
   - `/api/gantt`
   - `/api/agents`
3. 保证 Flask static/template 路由工作正常

## write_scope

仅允许修改：
- `/Users/lin/Desktop/work/my-agent-teams/dashboard/app.py`
- `/Users/lin/Desktop/work/my-agent-teams/dashboard/__init__.py`

## 测试要求

至少补：
- `GET /` 返回 HTML 页面而不是 JSON
- 现有 `/api/*` 路由不回归

## 交付物

完成后请写：
- `/Users/lin/Desktop/work/my-agent-teams/tasks/修正任务看板主页模板接入/result.json`
