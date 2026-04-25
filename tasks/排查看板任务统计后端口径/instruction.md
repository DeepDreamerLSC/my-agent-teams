# 任务：排查并修复看板任务统计后端口径

## 背景

用户反馈：任务看板的“任务统计”tab 与实际任务状态不一致。

用户给出的当前真实状态口径（以任务事实源为准）：
- pending：3
- blocked：2
- ready_for_merge：6
- done：25

你的任务是检查**后端 API 数据口径**是否正确，若不正确则修复。

## 重点检查

1. SQLite 中 tasks 表的 `current_status` / `board_status` 统计口径
2. `/api/agents`、`/api/board`、`/api/health` 等接口返回的统计是否一致
3. `task-watcher.sh` / `task-board-sync.py` / `dashboard/ingest.py` 是否把任务状态写错或漏写
4. 是否存在旧任务状态残留、blocked→ready_for_merge 或 ready_for_merge→done 收口后未同步的问题

## 目标

- 找出“任务统计 tab 与实际状态不一致”的后端根因
- 若是后端口径问题，直接修复
- 在结果中给出修复前后口径

## write_scope
- `/Users/lin/Desktop/work/my-agent-teams/dashboard/query.py`
- `/Users/lin/Desktop/work/my-agent-teams/dashboard/db.py`
- `/Users/lin/Desktop/work/my-agent-teams/dashboard/ingest.py`
- `/Users/lin/Desktop/work/my-agent-teams/dashboard/app.py`
- `/Users/lin/Desktop/work/my-agent-teams/scripts/task-board-sync.py`
- `/Users/lin/Desktop/work/my-agent-teams/scripts/task-watcher.sh`

## 交付物
请写 `/Users/lin/Desktop/work/my-agent-teams/tasks/排查看板任务统计后端口径/result.json`，说明：
- 根因
- 修改文件
- 修复后后端口径
- 测试/验证命令与结果
