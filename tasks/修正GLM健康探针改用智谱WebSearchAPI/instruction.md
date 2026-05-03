# 任务：修正 GLM 健康探针改用智谱 Web Search API

## 背景
生产排查结论：
- `/Users/lin/Desktop/work/my-agent-teams/tasks/排查生产联网搜索DeepSeek可点不可用与GLM置灰/result.json`

林总工要求先看智谱网络搜索官方文档，再对比我们实现哪里有问题并修复。参考官方文档：
- Chat Completions 文档：`https://docs.bigmodel.cn/api-reference/模型-api/对话补全`
- 网络搜索 Tool API 文档：`https://docs.bigmodel.cn/api-reference/工具-api/网络搜索`

## 当前已确认的问题
我们当前的 GLM / zhipu provider-native 健康探针实现有两个风险：
1. **探针方式不对**：当前通过 chat completion + 原生 web_search 工具，让模型回答“今天日期”，再从自然语言结果反推搜索可用性；这高度依赖模型表现，不是稳定健康探针。
2. **探针绑定到具体模型**：当前 provider 级状态依赖某个 active zhipu 模型（生产上实际落到 `GLM-4.7-Flash`），它一旦 429 或 request_failed，就把整个 GLM 按钮置灰；这与智谱文档里独立的 `POST /api/paas/v4/web_search` Tool API 语义不一致。

## 你的任务
请按最小范围修正后端实现：
1. 认真对照智谱官方 Web Search API 文档，确认我们探针与文档契约的偏差
2. 将当前 **provider-native 健康探针** 优先改为基于 `POST /api/paas/v4/web_search` 的结构化探测，而不是依赖模型自然语言回答
3. 保持前端当前消费字段尽量稳定：
   - `provider_web_search_runtime.zhipu`
   - `zhipu_web_search_runtime_status`
4. 避免把某个模型（如 `GLM-4.7-Flash`）的瞬时故障直接扩大成整个 provider 永久 unavailable
5. 补测试，至少覆盖：
   - Tool API 成功 -> healthy
   - 429 / request_failed -> unavailable 或 degraded（按你校准后的规则）
   - chat-capabilities 仍能稳定暴露前端需要的字段

## 方法论要求
- 先以官方文档为参照物，再对比我们实现
- 不要假设，用实际字段和契约对比给出修复
- 不要顺手重写整个 GLM 链路，只修健康探针与状态输出

## 边界
- 只改 `write_scope` 内文件
- 前端暂不动，除非后端字段形状必须变化（尽量避免）
- 不处理 DeepSeek 生产配置问题，那是另一条链路

## 交付物
完成后写：
- `/Users/lin/Desktop/work/my-agent-teams/tasks/修正GLM健康探针改用智谱WebSearchAPI/result.json`

结果中请明确写：
1. 官方文档与我们原实现的差异点
2. 你改成了什么探针方式
3. 前端消费字段是否保持兼容
4. 测试命令与结果
