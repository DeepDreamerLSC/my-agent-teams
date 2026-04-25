# 任务：排查并修复看板任务统计前端展示

## 背景

用户反馈：任务看板的“任务统计”tab 与实际任务状态不一致。

用户给出的当前真实状态口径（以任务事实源为准）：
- pending：3
- blocked：2
- ready_for_merge：6
- done：25

你的任务是检查**前端展示层**是否正确消费和渲染后端返回数据，若不正确则修复。

## 重点检查

1. 任务统计 tab 使用的是哪个 API
2. 前端是否把字段名映射错（例如 `completed_count` / `completed_task_count` 等）
3. 前端是否有额外过滤、聚合或把 board_status/current_status 混用
4. 前端统计文案/颜色/图例是否误导用户

## 目标

- 找出前端展示层是否存在统计口径问题
- 若是前端展示问题，直接修复
- 在结果中给出修复前后展示差异

## 注意
如果排查后确认前端只是如实展示了后端错误数据，也请在 result.json 中明确说明“前端未修改，根因在后端”。

## write_scope
- `/Users/lin/Desktop/work/my-agent-teams/dashboard/static`
- `/Users/lin/Desktop/work/my-agent-teams/dashboard/templates`

## 交付物
请写 `/Users/lin/Desktop/work/my-agent-teams/tasks/排查看板任务统计前端展示/result.json`，说明：
- 根因是否在前端
- 修改文件（如有）
- 修复后展示口径
- 测试/验证命令与结果
