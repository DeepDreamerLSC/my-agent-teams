# 任务：审查 task-watcher 空闲补推与收口链路修复

## 任务类型
验证

## 目标
由 review-1 对本轮 `task-watcher` 收口链路治理 + 空闲补推 + 看板 gate 数据链路改动做一次完整代码审查，覆盖下列 13 个文件，并明确给出 **APPROVE / REQUEST CHANGES** 结论。

## 任务边界
- 这是 **只读审查任务**，不直接改业务代码。
- 重点审查状态机正确性、通知时机、review/QA 补推逻辑、收口 gate 字段一致性、看板后端字段链路是否闭环。
- 不审查与本轮改动无关的历史脏 diff。
- 如发现阻塞问题，需写清文件、风险、复现/推导依据。

## 输入事实
- 当前改动集中在以下 13 个文件：
  - /Users/lin/Desktop/work/my-agent-teams/scripts/task-watcher.sh
  - /Users/lin/Desktop/work/my-agent-teams/scripts/close-task.sh
  - /Users/lin/Desktop/work/my-agent-teams/scripts/create-task.sh
  - /Users/lin/Desktop/work/my-agent-teams/tasks/task.schema.json
  - /Users/lin/Desktop/work/my-agent-teams/dashboard/db.py
  - /Users/lin/Desktop/work/my-agent-teams/dashboard/ingest.py
  - /Users/lin/Desktop/work/my-agent-teams/dashboard/query.py
  - /Users/lin/Desktop/work/my-agent-teams/dashboard/templates/index.html
  - /Users/lin/Desktop/work/my-agent-teams/dashboard/static/js/dashboard.js
  - /Users/lin/Desktop/work/my-agent-teams/dashboard/static/js/helpers.js
  - /Users/lin/Desktop/work/my-agent-teams/dashboard/static/js/test/helpers.test.js
  - /Users/lin/Desktop/work/my-agent-teams/dashboard/static/css/style.css
  - /Users/lin/Desktop/work/my-agent-teams/dashboard/tests/test_task_detail_endpoints.py
- 本轮目标包括：
  1. review fail 自动回退为 blocked + review_rejected；
  2. QA fail 自动回退为 blocked + qa_failed；
  3. 最终完成类通知仅在 done 终态发送；
  4. review/QA 支持空闲补推；
  5. 看板后端补齐 integration_owner / target_environment / review_level / merge_gate_state 等字段链路。
- 已执行过的本地验证命令：
  - `bash -n scripts/task-watcher.sh scripts/close-task.sh scripts/create-task.sh`
  - `python3 -m unittest dashboard.tests.test_task_detail_endpoints dashboard.tests.test_dashboard_metrics dashboard.tests.test_dashboard_frontend_timeline`
  - `node dashboard/static/js/test/helpers.test.js`

## 约束
- write_scope: []
- read_only: true
- 依赖上游任务: 无
- target_environment: dev
- execution_mode: dev
- owner_approval_required: false

## 交付物
1. `result.json`
   - `status` 固定为 `done`（若完成审查）或 `blocked`（若发现无法继续的阻塞）
   - `summary` 首句必须明确：`APPROVE` 或 `REQUEST CHANGES`
2. `review-note.md`
   - 列出审查范围
   - 结论
   - 通过项
   - 阻塞项（如有）
   - 建议修复项（如有）

## 验收标准
1. 13 个目标文件全部覆盖到，不漏审。
2. 对 `task-watcher.sh` / `close-task.sh` 的状态机与通知时机给出明确结论。
3. 对看板字段链路（尤其 `integration_owner / target_environment / review_level / merge_gate_state`）给出明确结论。
4. 若驳回，必须给出可执行的阻塞点；若通过，必须说明无阻塞残留。

## 下游动作
若审查通过，我会立即派发 `验证taskwatcher空闲补推与收口链路修复` 给 qa-1 做功能验证与 watcher 实战观察。
