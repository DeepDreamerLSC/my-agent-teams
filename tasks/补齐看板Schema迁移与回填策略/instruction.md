# 任务：补齐看板 Schema 迁移与回填策略

## 任务类型
设计

## 目标
补齐任务协作看板的 schema migration / rebuild / backfill 策略，把现有 SQLite 从“可创建 schema”升级为“有明确演进路径”的方案文档，为后续新增 communication_events、task_stage_durations、metrics 表继续扩表打基础。

## 任务边界
- 只负责文档与策略设计，不直接修改 dashboard 运行时代码。
- 重点关注：schema version、增表/加索引、幂等 rebuild、全量 backfill、老库兼容语义。
- 不负责实现 SQL migration runner。

## 输入事实
- 当前 `dashboard/db.py` 已有 `SCHEMA_VERSION` 与 `CREATE TABLE IF NOT EXISTS`，但没有显式 migration 机制。
- `design/任务协作看板优化方案.md` 已补充“迁移 / 回填策略必须先补”的原则。
- `design/任务协作看板-任务拆解.md` 中已有 `PH1-02A` 任务定义。
- 当前 SQLite 路径：`.omx/task-board/task-board.sqlite3`。

## 约束
- write_scope:
  - `design/任务协作看板优化方案.md`
  - `design/任务协作看板-任务拆解.md`
  - `design/任务协作看板-迁移策略.md`
- read_only: false
- target_environment: dev
- execution_mode: dev
- owner_approval_required: false
- 方案必须明确哪些场景可直接 rebuild，哪些场景必须保守迁移。

## 交付物
- 更新后的：
  - `design/任务协作看板优化方案.md`
  - `design/任务协作看板-任务拆解.md`
- 如有必要新增：
  - `design/任务协作看板-迁移策略.md`
- `result.json`

## 验收标准
1. 文档中明确 schema version 升级策略。
2. 文档中明确 full rebuild 与 incremental/backfill 的边界。
3. 后续 dev-2 能据此直接实现迁移/重建逻辑，无需自行补规则。
4. 不与现有 Chat Hub / dashboard 事件模型设计冲突。

## 下游动作
review
