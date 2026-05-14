# Code Review - 实现看板只读聚合视图

## 结论
- **审查结论：通过（APPROVE）**
- 依据：`instruction.md`、`result.json`、`dashboard/query.py`、`dashboard/app.py`、`scripts/task-aggregate.py` 与现有 dashboard 数据模型代码审查。
- 说明：任务目录当前 **无 `verify.json`**；本次结论基于代码与工件审查给出，未自行执行功能测试。

## 通过项

### 1. 只读聚合视图主链路已补齐
- 新增聚合 payload 构造：
  - `/Users/linsuchang/Desktop/work/my-agent-teams/dashboard/query.py:575-651`
- 新增 API：
  - `/Users/linsuchang/Desktop/work/my-agent-teams/dashboard/app.py:131-144`
- 新增 CLI：
  - `/Users/linsuchang/Desktop/work/my-agent-teams/scripts/task-aggregate.py:1-78`
- 三者共同构成了“query → API → 脚本”的只读聚合闭环。

### 2. 聚合维度符合任务要求
- 已覆盖：
  - `owner_pm`
  - `domain`
  - `task_level`
  - `parent_task_id`
  - `root_request_id`
- 相关实现：
  - 维度常量：`/Users/linsuchang/Desktop/work/my-agent-teams/dashboard/query.py:11-18`
  - 分组构造：`/Users/linsuchang/Desktop/work/my-agent-teams/dashboard/query.py:518-547`
  - request tree drill-down：`/Users/linsuchang/Desktop/work/my-agent-teams/dashboard/query.py:550-651`

### 3. `task_level` 的 task.json 回退策略合理，能兼容当前 SQLite 快照缺口
- 聚合前会按 `task_json_path` 回退读取 task.json 元数据：
  - `/Users/linsuchang/Desktop/work/my-agent-teams/dashboard/query.py:449-468`
- `task_level` / `parent_task_id` / `root_request_id` 等字段都通过 `_coalesce_task_field()` 做补齐：
  - `/Users/linsuchang/Desktop/work/my-agent-teams/dashboard/query.py:471-500`
- 这与 `result.json` 的说明一致，也避免了当前 read model 未持久化 `task_level` 时的聚合失真。

### 4. 明确声明“只读派生视图”，没有把聚合结果当事实源
- payload 中已显式给出：
  - `read_only: true`
  - `source.note: derived for inspection only`
- 位置：
  - `/Users/linsuchang/Desktop/work/my-agent-teams/dashboard/query.py:630-642`
- 这符合任务“不要把聚合视图误当状态事实源”的边界要求。

## 非阻塞备注
- 本任务主要通过 query / API / CLI 实现只读聚合，未在本次改动里新增专门的 dashboard 自动化测试文件；后续若继续扩展聚合能力，建议补一组针对 `build_task_aggregate_payload()` 与 `/api/tasks/aggregate` 的回归测试。
- 当前工作区里 `dashboard/app.py` / `dashboard/query.py` 还混有 timeline / metrics 等其他未收口改动，但本任务新增的聚合视图逻辑与其不冲突。

## 最终意见
当前实现满足任务目标：**PM 已可通过 API 或 CLI 读取 owner_pm/domain/task_level/parent_task_id/root_request_id 维度的只读聚合摘要、request tree drill-down 与拥塞分布，同时不会把派生结果误当成状态事实源。** 建议通过。
