# Code Review - 补齐看板阶段耗时持久化与回填

## 结论
- **审查结论：通过（APPROVE）**
- 依据：`instruction.md`、`result.json`、`dashboard/db.py`、`dashboard/ingest.py`、`dashboard/query.py`、`scripts/task-board-sync.py` 代码审查。
- 说明：任务目录当前 **无 `verify.json`**；本次结论基于代码与工件审查给出，未自行执行功能测试。

## 通过项

### 1. 阶段耗时持久化表已补齐
- `dashboard/db.py` 已新增 `task_stage_durations` 表与对应 upsert 入口：
  - `/Users/lin/Desktop/work/my-agent-teams/dashboard/db.py:91-99,254-264,385-388`
- 字段覆盖了设计里要求的 7 段耗时与 `updated_at`。

### 2. ingest / backfill 主链路已打通
- `dashboard.ingest` 已新增阶段耗时计算与 `task_stage_durations` 落库：
  - `/Users/lin/Desktop/work/my-agent-teams/dashboard/ingest.py:413-440,471-503`
- `task-board-sync.py backfill` 继续复用现有 `sync_task_dir()`，因此对现有任务目录做全量回填时会自动写入阶段耗时，不需要另造命令。

### 3. 查询层已优先消费持久化阶段耗时
- `dashboard.query` 现在会 `LEFT JOIN task_stage_durations`：
  - `/Users/lin/Desktop/work/my-agent-teams/dashboard/query.py:154-167,192-196`
- 详情页 durations 已改为“优先读持久化值，缺失时回退到现有临时计算”：
  - `/Users/lin/Desktop/work/my-agent-teams/dashboard/query.py:253-272`
- 这与任务目标“查询层可直接读取持久化阶段耗时，而不是只做临时计算”一致。

### 4. 缺失阶段场景保持兼容
- `_seconds_between()` 对任一端缺失时返回 `None`，不会因为 review/verify 缺失报错：
  - `/Users/lin/Desktop/work/my-agent-teams/dashboard/ingest.py:421-428`
- 各阶段字段允许为 `null`，符合任务约束。

## 非阻塞备注
- 本次任务主要依赖 py_compile + backfill/query 运行验证，未在自身任务范围内补专门的自动化测试文件；后续可考虑补 dashboard 层单测加强回归保障。
- 当前工作区里 `dashboard/db.py` / `dashboard/query.py` 还夹带了后续“日指标”相关未提交改动，但不影响本次 `task_stage_durations` 持久化与回填闭环的审查结论。

## 最终意见
当前实现满足任务目标：**阶段耗时已经从 query 层临时计算收敛到 SQLite 可持久化、可回填、可复用的数据层，且对缺失阶段保持兼容。** 建议通过。
