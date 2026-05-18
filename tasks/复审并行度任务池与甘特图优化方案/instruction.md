# 任务：复审并行度、任务池与甘特图真实性优化方案文档修订版，确认是否已吸收上一轮架构审计意见，并判断当前版本是否可作为后续优化实施的工作底稿。

## 任务类型
design

## 目标
对 `/Users/linsuchang/Desktop/work/my-agent-teams/design/collaboration/parallelism-task-pool-and-gantt-optimization.md` 的最新修订版做一次复审，确认其是否已吸收上一轮架构审计中指出的关键问题，尤其是：artifact status 契约、Pool Gate 只读任务例外、现状能力与目标能力分层标注；并判断当前版本是否已经足够稳妥，可作为后续优化实施与任务拆解的工作底稿。

## 任务边界
- 只做复审，不做实现，不改代码
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
  - `/Users/linsuchang/Desktop/work/my-agent-teams/scripts/lib/task_artifacts.py`
  - `/Users/linsuchang/Desktop/work/my-agent-teams/dashboard/query.py`
  - `/Users/linsuchang/Desktop/work/my-agent-teams/config.json`
- 不要求你直接修改上述文件；如仍需修文，请指出具体段落和修改建议

## 输入事实
- 上一轮架构审计结论为“有条件通过”
- 上一轮明确指出的主要问题包括：
  - artifact 示例仍写 `success`
  - Pool Gate 把 `write_scope` 非空写成统一前提，未覆盖只读 design/审计任务
  - `reserved`、`pool_starvation`、Gantt exact/inferred 等目标能力与现状能力混写
  - watcher 已有局部 pooled/续推能力，但文档容易让人误读为“当前几乎没有”或“当前已经完整具备”
- PM 已按上述意见修订了文档最新版本
- 当前希望确认：该文档是否已从“有条件通过但不适合直接拆任务”提升为“可作为后续实现拆解工作底稿”

## 约束
- write_scope: []
- read_only: true
- 依赖上游任务: 无
- target_environment: dev
- execution_mode: dev
- owner_approval_required: false
- 结论必须基于当前仓库内文档与脚本现状，不要只评价文字是否好看
- 请特别关注是否还存在“会误导 PM 按错误系统能力拆任务”的表述

## 交付物
1. 复审结论：
   - 通过
   - 有条件通过
   - 仍不建议作为实施底稿
2. 对上一轮关键问题的逐项确认：
   - 是否已修正
   - 是否仍有残留
3. 当前版本是否可作为后续实现任务拆解依据
4. 如果还要修，只指出最少必要修订项，不要泛泛而谈

## 验收标准
1. 必须逐项回应上一轮的关键审计意见是否已吸收
2. 必须明确回答“当前是否可以进入实现拆解阶段”
3. 若仍不建议直接实施，必须指出最少必要修订项（不超过 5 条）
4. 结论应可直接供 PM 做下一步决策

## 下游动作
复审完成后由 PM 决定是否继续微调文档或进入实现拆解。
