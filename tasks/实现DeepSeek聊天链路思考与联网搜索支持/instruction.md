# 任务：实现 DeepSeek 聊天链路思考与联网搜索支持

## 背景

上游方案任务：
- `/Users/lin/Desktop/work/my-agent-teams/tasks/设计DeepSeek供应商与能力支持方案`
- 方案文档：`/Users/lin/Desktop/work/chiralium/design/product/deepseek-provider-capability-support-plan.md`

本任务对应方案中的 execution 子任务 B。

## 前置依赖
- `实现DeepSeek固定供应商注册表与能力输出`

## 目标

在聊天主链路中支持：
1. DeepSeek thinking
2. DeepSeek web_search（通过平台级 tool-call 路径，而不是智谱 native web_search）

## 依据方案（必须阅读）
- `/Users/lin/Desktop/work/chiralium/design/product/deepseek-provider-capability-support-plan.md`
- 重点章节：DeepSeek thinking 支持、DeepSeek 联网搜索、tool-call runtime、风险评估

## 建议实现范围
- `/Users/lin/Desktop/work/chiralium/backend/app/services/model_service.py`
- `/Users/lin/Desktop/work/chiralium/backend/app/api/chat.py`
- `/Users/lin/Desktop/work/chiralium/backend/app/services/web_search_service.py`（新增）
- `/Users/lin/Desktop/work/chiralium/backend/app/services/chat_tool_runtime_service.py`（新增）
- `/Users/lin/Desktop/work/chiralium/backend/tests`

## 验收标准
1. DeepSeek 开启 thinking 时，后端能正确组装请求体
2. DeepSeek 开启联网搜索时，不再走智谱 native `web_search` 分支
3. DeepSeek tool-call web_search 路径可以正确补轮并返回最终回答
4. Zhipu 现有 thinking / web_search 不回归
5. 非支持 provider 仍保持禁用或安全降级

## 测试要点
- thinking 参数组装
- tool-call 多轮补偿
- 搜索结果回填
- Zhipu 回归
- 空响应/死循环保护

## 注意
- 本任务复杂度高，请严格按方案实现
- 如 execution 中发现方案需要调整，请在 result.json 中明确回报给 PM

## 交付物
完成后写：
- `/Users/lin/Desktop/work/my-agent-teams/tasks/实现DeepSeek聊天链路思考与联网搜索支持/result.json`
