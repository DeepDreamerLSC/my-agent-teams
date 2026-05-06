# Code Review - 补齐看板 Schema 迁移与回填策略

## 结论
- **审查结论：通过（APPROVE）**
- 依据：`instruction.md`、`result.json`、`design/任务协作看板-迁移策略.md`、`design/任务协作看板优化方案.md`、`design/任务协作看板-任务拆解.md` 审查。
- 说明：任务目录当前 **无 `verify.json`**；本次结论基于文档与现有实现口径审查给出。

## 通过项

### 1. schema version 语义已明确
- 新文档已区分：
  - 代码期望版本（`dashboard/db.py` 中的 `SCHEMA_VERSION`）
  - 数据库实际版本（`metadata.schema_version`）
- 并定义了数据库不存在、版本相等、低于代码版本、高于代码版本四类处理语义。

### 2. migrate / backfill / rebuild-all 边界已清晰
- 已明确区分四类动作：
  - `initialize`
  - `migrate`
  - `backfill`
  - `rebuild-all`
- 也明确了：
  - 开发/本地库默认 `rebuild-first`
  - 共享库默认 `migrate-first`
  - 哪些变更可自动 migrate，哪些场景优先 rebuild

### 3. 与现有看板/Chat Hub 事件模型兼容
- 文档已明确：
  - `communication_events` 继续复用 Chat Hub 协议边界
  - `sync-task / sync-chat / rebuild-metrics` 不承担 schema 决策
- 这与现有架构审查结论和当前 `dashboard/db.py` 扩表方向不冲突。

### 4. 已能直接指导后续 dev-2 实现
- 文档不仅给原则，也给了后续实现时的明确约束和推荐顺序：
  - 先 version check
  - 再 limited migrate
  - 再 rebuild-all / full backfill
- 能满足“后续实现无需再自行补规则”的验收标准。

## 非阻塞备注
- 当前代码工作树里 `dashboard/db.py` 已先行出现更高 `SCHEMA_VERSION` 与扩表实现；本任务文档没有和该方向冲突，但后续合入时仍应注意代码与文档版本号同步更新。

## 最终意见
本次设计任务已经把看板 schema migration / rebuild / backfill 的关键边界补齐，且能直接为后续实现提供统一规则。建议通过。
