# 任务：扩展 PDF 转 Word 异步任务取消与阶段产物暴露，补齐后台任务产品化

## 任务类型
development

## 目标
在现有 `create job + get status` 基础上，补齐 PDF→Word 异步任务的**取消能力**与**阶段产物可追踪能力**，让 quality/hybrid 后台任务具备更接近产品可用态的 job 管控能力。

## 任务边界
- 只做后端 job API / job service / 测试 / 运行摘要，不做前端页面。
- 本轮重点是：取消语义、状态流转、阶段产物暴露；不做多机调度、队列系统替换、复杂租户隔离。
- 保持现有同步 `/api/pdf-to-word/convert` 路径可用，不因 job 扩展而回归。

## 输入事实
- 当前异步 job 已支持：创建、查询、`queued / running / succeeded / failed`。
- 当前尚无明确 cancel 能力；阶段产物也主要停留在基础 input/output/manifest 级别。
- 下一阶段产品化重点明确要求：后台任务需要更完整的状态机与 artifact 可追踪性。

## 约束
- `write_scope` 以 `task.json` 为准。
- 取消语义必须诚实：`queued` 可直接取消；`running` 可采用 best-effort 的 `cancel_requested / cancelled` 语义，但不要伪装成已中断却实际继续跑完。
- 阶段产物至少要能追踪：job_dir、manifest、输入文件、输出文件、阶段事件/history；如已有字段足够可在现有结构上补充，不必另造复杂 schema。
- 若实现中发现必须引入更重基础设施，先收敛最小版本并在 `result.json` 说明，而不是无边界扩张。

## 交付物
1. job cancel API / service 逻辑与状态枚举更新。
2. 阶段产物暴露增强：状态查询返回更完整的 artifacts / history / stage 信息。
3. 测试更新，至少覆盖：
   - queued job 取消
   - running job 取消或 cancel_requested 语义
   - 已完成 job 的幂等/拒绝取消行为
   - 同步 convert 路径不回归
4. `artifacts/pdf2word/p2-productization/` 下的运行摘要，说明当前状态机与 artifacts 结构。
5. `result.json`：说明 cancel 语义、状态流转、已知限制与下一步产品化建议。

## 验收标准
1. API 层可对 job 发起取消，并能查询到诚实的状态结果。
2. 阶段产物/历史信息足够支撑排查，不再只有最终 output 路径。
3. 同步 `/convert` 不回归，现有 create/status 用例不被破坏。
4. 测试通过，并对暂未覆盖的复杂场景明确列出边界。

## 下游动作
完成后进入 review-1 审查；通过后作为异步产品化主链路基础，再决定是否继续拆取消超时治理、任务清理与前端状态透出。
