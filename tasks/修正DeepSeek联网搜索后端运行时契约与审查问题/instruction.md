# 任务：修正 DeepSeek 联网搜索后端运行时契约与审查问题

## 背景
原任务：
- `/Users/lin/Desktop/work/my-agent-teams/tasks/修复DeepSeek联网搜索后端守卫与可观测性/instruction.md`
- `/Users/lin/Desktop/work/my-agent-teams/tasks/修复DeepSeek联网搜索后端守卫与可观测性/result.json`

当前状态：complex review 未通过，本次为 review 驳回后的补修任务。

现有已知风险点：
1. 前端 `useChatOptions` 当前消费 `/api/meta/chat-capabilities` 中的 `web_search_runtime_status`
2. 后端当前实现向 `/api/meta/chat-capabilities` 注入的是 `web_search_runtime` 对象，且内部状态值使用 `ready/disabled/misconfigured`
3. 这会导致前后端运行时契约不一致，可能是本轮 complex review 的核心阻塞点之一

## 你的任务
请在后端侧完成“审查问题修复 + 契约对齐”，不要扩散范围：

### 1. 对齐 chat-capabilities 运行时契约
- 检查并修正 `/api/meta/chat-capabilities` 暴露给前端的联网搜索运行时字段
- 目标：让前端无需猜测或二次硬编码即可稳定消费
- 要求尽量**向后兼容**：
  - 可以保留已有 `web_search_runtime` 对象
  - 但需补足前端当前实际消费所需的稳定字段（例如 `web_search_runtime_status`），或给出同等清晰且可直接消费的兼容方案
- 如果保留对象，需保证状态枚举与前端语义可直接映射，不要再出现 `ready/disabled/misconfigured` 与 `available/unavailable/degraded/unknown` 脱节的问题

### 2. 保持可观测性能力不回退
- 不要回退原任务已完成的这些能力：
  - DeepSeek/provider drift 守卫
  - `/api/admin/models/diagnostics`
  - `/api/meta/web-search-runtime`
  - runtime 缺配显式 warning / degraded 日志

### 3. 补测试
至少补/修以下测试：
- `/api/meta/chat-capabilities` 返回给前端的运行时字段契约测试
- 不同 runtime 状态的枚举映射测试
- 向后兼容测试（已有对象结构仍可用 / 或新字段不会破坏既有调用方）

### 4. 若收到新增 reviewer 阻塞点，也一并纳入本任务处理
- 目前任务目录内可能还未完整落盘所有 complex review 反馈
- 若你从已有上下文或后续 review 文件中看到新增阻塞点，请在本任务内一并修掉，但不要扩散到无关重构

## 边界
- 只改 `write_scope` 内文件
- 不直接改生产环境
- 不回退原任务已通过的 drift guard / diagnostics / logging 能力

## 交付物
完成后写：
- `/Users/lin/Desktop/work/my-agent-teams/tasks/修正DeepSeek联网搜索后端运行时契约与审查问题/result.json`

请在 `result.json` 中包含：
- 修改文件列表
- 运行时契约如何对齐（旧字段 / 新字段 / 状态枚举）
- 为什么这次修改能解决审查问题
- 测试命令与结果
