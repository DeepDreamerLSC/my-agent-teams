# 任务：审计并行度、任务池与甘特图真实性优化方案文档，判断其与现有 control-plane/task-pool 设计及脚本实现是否一致、是否存在遗漏风险，并给出架构审计结论。

## 任务类型
design

## 目标
从架构与控制面一致性角度，审计 `/Users/linsuchang/Desktop/work/my-agent-teams/design/collaboration/parallelism-task-pool-and-gantt-optimization.md` 当前版本，判断其是否与现有 task-pool / watcher / dispatch / dashboard 设计方向一致，是否存在与现状实现冲突、遗漏约束、风险低估或优先级不当的问题，并给出可执行审计结论。

## 任务边界
- 只做审计，不做实现，不改代码
- 可阅读并引用：
  - `/Users/linsuchang/Desktop/work/my-agent-teams/design/collaboration/parallelism-task-pool-and-gantt-optimization.md`
  - `/Users/linsuchang/Desktop/work/my-agent-teams/design/collaboration/control-plane-and-task-pool.md`
  - `/Users/linsuchang/Desktop/work/my-agent-teams/design/collaboration/task-pool-claiming.md`
  - `/Users/linsuchang/Desktop/work/my-agent-teams/scripts/dispatch-task.sh`
  - `/Users/linsuchang/Desktop/work/my-agent-teams/scripts/pool-task.sh`
  - `/Users/linsuchang/Desktop/work/my-agent-teams/scripts/claim-task.sh`
  - `/Users/linsuchang/Desktop/work/my-agent-teams/scripts/task-watcher.sh`
  - `/Users/linsuchang/Desktop/work/my-agent-teams/scripts/task-pool-router.py`
  - `/Users/linsuchang/Desktop/work/my-agent-teams/scripts/task-pool-view.py`
  - `/Users/linsuchang/Desktop/work/my-agent-teams/config.json`
- 不要求你直接修改上述文件；如认为文档仍需修订，请在结果中明确指出具体段落和修改建议

## 输入事实
- PM 已根据一次内部评审，直接修改了 `parallelism-task-pool-and-gantt-optimization.md`
- 本轮 PM 修订重点包括：
  - 增加“根因未明先 diagnosis / design”原则
  - 收紧 pool-first 的适用边界
  - 明确 `dependency_policy` 默认应为 `done_only`
  - 将 `ready_for_merge_ok` 限制在低耦合场景
  - 将 artifact 生成器前移到 Phase 1
  - 将 `reserved` 降为 P2 试点能力
  - 将 review/QA 并行改为分层并行
  - 要求 Gantt 区分 exact / inferred
- 现有系统中已存在 pooled / claim / pool view / pool router / watcher nudge / timeout 等机制，但 watcher 目前并未形成完整自动 claim 闭环
- 当前目标不是立刻实现全部方案，而是先确认这份文档是否作为后续优化依据足够稳妥

## 约束
- write_scope: []
- read_only: true
- 依赖上游任务: 无
- target_environment: dev
- execution_mode: dev
- owner_approval_required: false
- 结论必须基于当前仓库内文档与脚本现状，不要凭抽象流程图泛化判断
- 重点关注“文档与现状是否一致”“优先级是否合理”“是否会诱导 PM 过早并行导致返工”

## 交付物
1. 审计结论：通过 / 有条件通过 / 不建议采用
2. 关键发现清单：
   - 与现有实现一致的点
   - 与现有实现不一致或表述过头的点
   - 仍遗漏的关键风险 / 约束
3. 对 PM 当前修订的评价：哪些改对了，哪些还不够
4. 建议的后续动作：
   - 直接继续修文
   - 先补主文档
   - 先拆实现任务验证
   - 或需要退回重写某些章节

## 验收标准
1. 明确指出该文档当前是否可作为后续优化工作的工作底稿
2. 至少覆盖 task-pool、dispatch、watcher、artifact、Gantt 口径五类一致性检查
3. 至少指出 3 条非显而易见的风险、缺口或边界条件（如果确实存在）
4. 给出明确的 PM 下一步建议，而不是只做笼统评价

## 下游动作
审计完成后由 PM 根据结论决定是否继续修订文档或拆实现任务。
