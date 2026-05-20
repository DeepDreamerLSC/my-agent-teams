# 任务：设计预热任务独占预留机制

## 任务类型
架构设计

## 目标
把“预热”从单纯提醒升级为可机读的独占预留语义，冻结状态字段、状态机、超时回退与 watcher 自动续推规则，避免任务在预热给某个 agent 后仍被其他 agent 抢认领。

## 任务边界
- 只允许修改 `design/collaboration/预热任务独占预留机制.md`。
- 本任务输出设计契约，不直接改 watcher / claim / pool 代码。
- 不扩展到与本次问题无关的任务池大重构。

## 输入事实
- 本次事故：`实现可编辑Word表格渲染` 在我预热给 `dev-2` 后，因为预热只发消息不落状态，依赖解锁后被 `dev-1` 的 auto-continue 抢认领。
- 现状里 `claim.json` / `claimed_by` / `reserved_by` 只在 claim / dispatched 后提供独占能力，预热阶段没有排他语义。
- 业务要求：预热角色应视为“接下下一条任务”，在锁有效期内不能再被其他角色认领；若超时未 ack，任务才可回池。

## 约束
- 必须明确回答：复用 `reserved_by` 还是新增 `pre_reserved_*` 字段；不要给模糊建议。
- 必须定义：pending / pooled / dependency_wait / dispatched / working 各状态下，预热锁的写入、继承、清理、超时与释放规则。
- 必须给出 PM/脚本侧的操作入口建议（例如新增 `reserve-task.sh` 或等价能力），不能依赖人工改 JSON。
- 方案必须兼容现有 `claim-task.sh`、`task-watcher.sh`、`task-pool-view.py`、`task-pool-router.py` 的任务池逻辑。

## 交付物
1. 一份独占预留机制设计文档。
2. 字段契约、状态迁移图/表、超时回退策略、与现有 `claim/reserved/dispatched` 的兼容说明。
3. 对实现层的明确约束：谁能 claim、何时只能派给预留 agent、何时回池、如何通知。

## 验收标准
- 文档能直接指导 `dev-2` 落地实现，无关键语义空白。
- 明确覆盖本次事故复现场景，并给出防复发规则。
- 明确说明“预热不是通知，而是带 TTL 的独占预留”。
- 不越界改生产代码。

## 下游动作
完成后，PM 继续推进 `实现预热任务独占预留锁`，按冻结契约落地脚本与回归测试。
