# Review Note - 审查 task-watcher 空闲补推与收口链路修复

## 审查范围
本次按任务要求审查以下 13 个文件：
1. `scripts/task-watcher.sh`
2. `scripts/close-task.sh`
3. `scripts/create-task.sh`
4. `tasks/task.schema.json`
5. `dashboard/db.py`
6. `dashboard/ingest.py`
7. `dashboard/query.py`
8. `dashboard/templates/index.html`
9. `dashboard/static/js/dashboard.js`
10. `dashboard/static/js/helpers.js`
11. `dashboard/static/js/test/helpers.test.js`
12. `dashboard/static/css/style.css`
13. `dashboard/tests/test_task_detail_endpoints.py`

## 结论
**REQUEST CHANGES**

## 通过项
- `result.json(status=done)` 进入 `ready_for_merge` 后，已不再发送“任务完成/部署完成”类飞书通知，而是只推进到下游 review / QA / PM 验收队列。
- review fail 会自动回退为 `blocked + review_rejected`，QA fail 会自动回退为 `blocked + qa_failed`，并同步写回 `merge_gate_state / rework_reason / last_gate_actor / last_gate_decision_at`。
- review / QA 空闲补推逻辑已经具备：基于 `review_pending / qa_pending` 队列状态和 idle agent 判断做续推。
- 看板后端字段链路已经补齐：`integration_owner / target_environment / review_level / merge_gate_state / rework_reason / last_gate_actor / last_gate_decision_at / auto_close_policy` 已从 task.json → SQLite → query → 前端展示贯通。
- dashboard 前端已补 `merge_gate_state` 的筛选与展示，详情接口测试覆盖了关键新字段。

## 阻塞项
### 1. 最终完成类飞书通知没有覆盖所有进入 `done` 的合法收口路径
当前实现把“【任务完成】/【部署完成】”通知只放在 `task-watcher.sh` 的 `auto_close_task()` 里，即 **只有 QA 通过并由 watcher 自动调用 `close-task.sh`** 的路径才会发送最终完成类飞书。

但系统仍存在其他合法进入 `done` 的路径，例如：
- PM / integrator 手工执行 `close-task.sh`
- 无 QA 任务在 review 通过后由 PM 手工收口

这些路径会把任务状态更新为 `done`，但 watcher 在 `done` 分支只做同步与后续续推，不会补发最终完成类飞书，因此会出现“真正 done 了，但没有最终完成通知”的遗漏。

这与需求“**只有进入 `done` 终态后，才发送最终完成类通知，且该通知必须保留**”不完全一致。

## 建议修复
- 把最终完成类飞书通知从“QA 自动收口专属逻辑”提升为“任意任务真实进入 `done` 终态时统一触发”的机制；
- 同时保留当前对 `ready_for_merge` 阶段不再误报完成的修正；
- 建议补一条针对“手工 close-task.sh 收口后 watcher 是否补发最终完成通知”的回归验证。
