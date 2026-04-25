# 任务：实现 ready_for_merge 任务收口脚本

## 背景

当前 `my-agent-teams` 中存在大量 `ready_for_merge` 任务。PM 需要一种统一、可审计的方式把“责任链已闭环”的任务从 `ready_for_merge` 收口到 `done`。

林总工已明确要求：
1. 编写 `scripts/close-task.sh`
2. 脚本应至少支持：
   - 校验任务当前状态必须是 `ready_for_merge`
   - 将 `task.json.status` 更新为 `done`
   - 写回 `task.json.updated_at`
   - 写回/补充 `task.json.result_summary`
   - 追加 `transitions.jsonl`

## write_scope
- `/Users/lin/Desktop/work/my-agent-teams/scripts/close-task.sh`

## 要求
- 先做单任务关闭能力
- 建议支持：
  - `--task-dir`
  - `--summary`
  - `--reason`
  - `--dry-run`
- 脚本报错信息要清楚
- 不要直接扫描批量任务；批量执行由 PM 后续任务负责

## 验收标准
- 非 `ready_for_merge` 状态时拒绝关闭
- 正常关闭时：
  - `task.json.status=done`
  - `task.json.updated_at` 更新
  - `task.json.result_summary` 可写入
  - `transitions.jsonl` 追加 `ready_for_merge -> done`
- `--dry-run` 不落盘

## 交付物
完成后写 `/Users/lin/Desktop/work/my-agent-teams/tasks/实现任务收口脚本/result.json`，说明：
- 脚本参数
- dry-run 示例
- 实测命令和结果
