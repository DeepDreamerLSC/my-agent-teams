# 任务：排查生产联网搜索 DeepSeek 可点不可用与 GLM 按钮置灰

## 背景
林总工刚在生产环境验证发现两个关键问题仍然存在：
1. **DeepSeek**：联网按钮能按，但实际联网搜索仍然用不了
2. **GLM**：联网按钮仍然是灰的

这是生产关键功能问题。按当前 PM 规则，先由一个 dev 做事实排查，确认根因后，再由 PM 拆修复任务。

## 你的任务
请先做**只读排查 + 最小必要验证**，不要一开始就大面积改代码。
务必遵守方法论：
- **先看现有正常实现**做参照
- **不要假设，去确认**代码 / 配置 / API 响应 / 日志 / 生产行为

### A. DeepSeek：按钮可点但仍无法联网
至少检查：
- 生产最新代码是否已经走回 `tool_call` 正确链路
- 后端实际是否触发了 web_search tool call
- `CHAT_WEB_SEARCH_BASE_URL / API_KEY / PROVIDER` 等生产配置是否已经齐全且生效
- tool-call runtime 是否拿到了真实搜索结果，还是在某个环节短路/失败
- 是否是后端工具调用逻辑、运行时配置、外部搜索接口、还是提示链路的问题

### B. GLM：按钮仍然置灰
至少检查：
- 先找 **当前系统中正常工作的联网搜索按钮判断逻辑**做参照（DeepSeek / 其他 provider）
- 前端为什么把 GLM 判成不可用：是 capability、provider runtime 状态、还是前端条件分支造成的
- 后端 provider-native 搜索健康探针/状态输出是否已经落地
- 如果后端状态是 unavailable，前端置灰是否符合当前简化策略；如果后端并未明确 unavailable，那就是前端/契约问题

## 输出要求
完成后在 result.json 中明确写：
1. DeepSeek 问题根因判断（代码 / 配置 / 数据 / 外部依赖）
2. GLM 问题根因判断（代码 / 配置 / 数据 / 外部依赖）
3. 每个问题的关键证据（文件、接口、日志、配置项、生产表现）
4. 建议拆给谁修（dev-1 / dev-2 / arch-1）
5. 如果需要，给出最小修复范围

## 交付物
完成后写：
- `/Users/lin/Desktop/work/my-agent-teams/tasks/排查生产联网搜索DeepSeek可点不可用与GLM置灰/ack.json`
- `/Users/lin/Desktop/work/my-agent-teams/tasks/排查生产联网搜索DeepSeek可点不可用与GLM置灰/result.json`
