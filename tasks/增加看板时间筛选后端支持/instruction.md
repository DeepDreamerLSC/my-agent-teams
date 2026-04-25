# 任务：为任务看板增加时间范围筛选后端支持

## 背景

用户需要在看板上增加时间尺度筛选，支持：
- 24小时内
- 近3天
- 近7天
- 近1个月

## 你的任务
为后端 API 增加时间筛选能力，供前端界面使用。

## 范围
- `/Users/lin/Desktop/work/my-agent-teams/dashboard/app.py`
- `/Users/lin/Desktop/work/my-agent-teams/dashboard/query.py`

## 要求
- 至少支持 query 参数（如 `range=24h|3d|7d|30d`）
- 看板、甘特图、Agent 统计三类接口都要有一致口径
- 需说明筛选基于哪个时间字段（建议 `current_status_at` 或等价口径）

## 交付物
完成后写 `/Users/lin/Desktop/work/my-agent-teams/tasks/增加看板时间筛选后端支持/result.json`
