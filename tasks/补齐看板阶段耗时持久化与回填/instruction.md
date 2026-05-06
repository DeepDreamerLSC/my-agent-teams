# 任务：补齐看板阶段耗时持久化与回填

## 任务类型
开发

## 目标
把当前任务详情页里临时计算的阶段耗时，收敛为 SQLite 中可回填、可复用的持久化数据层，至少支持对现有任务做全量回填，并为后续分析页复用。

## 任务边界
- 只负责阶段耗时持久化与回填链路。
- 不负责前端图表改造。
- 不负责 metrics 聚合表。

## 输入事实
- 当前 `dashboard/query.py` 会在任务详情 API 中临时计算 durations。
- `design/任务协作看板优化方案.md` 中建议新增 `task_stage_durations`。
- `design/任务协作看板-任务拆解.md` 中 `PH1-06` 尚未完成。

## 约束
- write_scope:
  - `dashboard/db.py`
  - `dashboard/ingest.py`
  - `scripts/task-board-sync.py`
  - `dashboard/query.py`
- read_only: false
- target_environment: dev
- execution_mode: dev
- owner_approval_required: false
- 需兼容现有任务数据缺阶段的情况，允许 null。
- 需支持 backfill/rebuild 现有任务目录。

## 交付物
- `task_stage_durations` 落库实现
- 回填入口（可复用 task-board-sync）
- 相关代码改动
- `result.json`

## 验收标准
1. SQLite 中存在阶段耗时持久化表或等价持久化结构。
2. 能对至少已有任务做全量回填。
3. 缺失 review/verify 等阶段时不会报错。
4. 查询层可直接读取持久化阶段耗时，而不是只依赖临时计算。

## 下游动作
review
