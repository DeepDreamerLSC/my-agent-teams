# 任务：为任务看板增加时间范围筛选界面与交互

## 背景

用户需要在看板上增加时间尺度筛选，支持：
- 24小时内
- 近3天
- 近7天
- 近1个月

## 前置依赖
- 后端先完成时间筛选 API 支持
- 甘特图状态颜色/标注一致性问题先修复，避免同时修改同一前端文件冲突

## 你的任务
在 dashboard 页面增加时间筛选 UI，并驱动：
- 看板视图
- 甘特图
- Agent 统计
三视图按所选时间范围刷新。

## write_scope
- `/Users/lin/Desktop/work/my-agent-teams/dashboard/static`
- `/Users/lin/Desktop/work/my-agent-teams/dashboard/templates`

## 验收标准
- 4 个时间选项可见且可切换
- 切换后会重新请求后端并刷新图表/卡片
- 默认值明确
- 不破坏现有 tab 切换

## 交付物
完成后写 `/Users/lin/Desktop/work/my-agent-teams/tasks/增加看板时间筛选前端界面/result.json`
