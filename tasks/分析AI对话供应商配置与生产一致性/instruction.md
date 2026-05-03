# 任务：分析 AI 对话供应商配置与生产一致性

## 背景
需要对 chiralium 项目当前 AI 对话功能做一次供应商配置与生产一致性分析。

## 你的任务
请做**只读技术分析**，重点关注以下三类问题：

### 1. 不同大模型供应商的 API 配置差异
请梳理：
- 智谱 / GLM
- DeepSeek
- 其他当前代码中支持的 provider（如有）

重点说明：
- 模型 API key / base_url / model_name 是怎么配置的
- 深度思考（thinking）是怎么开关/配置的
- 联网搜索（web_search）是怎么开关/配置的
- 哪些走 provider-native，哪些走 tool_call，哪些依赖平台级 runtime

### 2. 是否存在不同供应商配置混用
重点排查：
- 是否存在把 DeepSeek 当成 GLM/Zhipu native web_search 去调用的场景
- 是否存在把 GLM 的 provider-native 状态误用于 DeepSeek 的场景
- 是否存在全局 runtime 状态和 provider-specific 状态语义混淆
- 是否存在 env / 代码 / 数据库模型配置之间混用或错配

### 3. 检查生产环境配置是否与代码逻辑一致
至少检查：
- `/Users/lin/Desktop/prod/chiralium/backend/.env.prod`
- 当前生产代码逻辑
- 模型管理 / provider registry / meta 接口 / runtime 检测逻辑

要明确指出：
- 代码逻辑要求哪些环境变量
- 生产当前是否已经配置
- 缺了哪些、错了哪些、冗余了哪些
- 哪些问题是代码问题，哪些是配置问题，哪些是数据问题

## 输出要求
请在以下路径输出分析文档：
- `/Users/lin/Desktop/work/chiralium/design/product/ai-chat-provider-config-analysis.md`

文档至少包含：
1. 当前 AI 对话架构简述
2. 各 provider 配置方式对比表
3. thinking / web_search 差异说明
4. 发现的混用/错配场景
5. 生产配置与代码逻辑一致性检查
6. 明确结论与建议

## 交付物
完成后写：
- `/Users/lin/Desktop/work/my-agent-teams/tasks/分析AI对话供应商配置与生产一致性/result.json`

结果中请包含：
- 文档路径
- 核心结论摘要
- 是否发现配置混用
- 是否发现生产配置缺失/不一致
