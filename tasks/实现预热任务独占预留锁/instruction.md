# 任务：实现预热任务独占预留锁

## 任务类型
开发实现

## 目标
把 PM/系统的“预热”正式做成独占预留锁：任务在预热给某个 agent 后，即使依赖尚未解锁，也应在锁有效期内只允许该 agent 接手；其他 agent 不能再 claim 或被 auto-continue 抢走。

## 任务边界
- 只允许修改：
  - `scripts/claim-task.sh`
  - `scripts/task-watcher.sh`
  - `scripts/task-pool-view.py`
  - `scripts/task-pool-router.py`
  - `scripts/reassign-task.sh`
  - `scripts/reserve-task.sh`（可新增）
  - `scripts/lib/task_state_invariants.py`
  - `tests/test_claim_task_reserved.py`
  - `tests/test_task_pool_and_queue_router.py`
  - `tests/test_reassign_task.py`
  - `tests/test_task_watcher_push_reliability.py`
- 本任务只修复预热/预留/认领/续推链路，不改 ChatHub、任务看板或其他无关派发逻辑。
- 不要把问题绕回“统一改成直接派发”，要在任务池语义内修复。

## 输入事实
- 当前事故复现路径：任务先预热给 `dev-2`，但只发了提醒；依赖一解锁，`dev-1` 因 auto-continue 先写入 `claim.json`，任务被 watcher 正式派发给 `dev-1`。
- 现有系统已在 `claim.json` / `claimed_by` / `reserved_by` 阶段具备独占能力，但预热阶段没有状态位。
- 用户要求：预热角色应视为“接下下一条任务”，在锁超时前不能再被其他角色认领。

## 约束
- 需要提供 PM/系统可调用的正式入口，不能靠人工编辑 `task.json` 预留。
- 预热锁不能无限期占坑：必须有 TTL / 超时回退 / 清理逻辑。
- 依赖未 ready 时也要能预留；依赖 ready 后，watcher 只能把任务正式 dispatch 给被预留的 agent。
- 若被预留 agent 超时未 ack、主动释放或被 PM 改派，锁必须正确回收，任务才能重新开放给其他 agent。
- 不得破坏现有 claim / reserved / dispatched / working 的状态不变量。

## 交付物
1. 预热独占预留的脚本入口与状态字段落地。
2. `claim-task` / `task-watcher` / pool router 对他人 claim 与 auto-continue 抢占的拦截逻辑。
3. 覆盖本次事故的自动化回归测试：
   - 预热给 `dev-2` 后，`dev-1` 不能 claim；
   - 依赖 ready 后只能派给被预留 agent；
   - 超时未 ack 后会清锁并重新开放。

## 验收标准
- 能稳定复现并修复本次“预热后仍被其他 agent 抢走”的问题。
- 有至少一条测试覆盖真实事故路径，而不只是单点字段断言。
- 预热锁有效期内，pool/router/view/watcher 对外表现一致，不出现 UI/路由与真实 claim 规则不一致。
- review / QA 可直接根据脚本与测试判断机制是否生效。

## 下游动作
完成后进入 review-1 审查与 qa-1 复验；PM 将用修复后的机制重新约束后续关键任务的预热与派发。
