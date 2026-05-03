# 任务：补齐生产 AI 对话联网搜索配置并部署验证

## 背景
林总工明确要求：把缺失的联网搜索配置补上，并确保每个大模型供应商的联网搜索和深度思考配置都正确对应，不要混用。

相关分析与证据：
- `/Users/lin/Desktop/work/my-agent-teams/tasks/分析AI对话供应商配置与生产一致性/result.json`
- `/Users/lin/Desktop/work/chiralium/design/product/ai-chat-provider-config-analysis.md`
- `/Users/lin/Desktop/work/my-agent-teams/tasks/排查生产联网搜索DeepSeek可点不可用与GLM置灰/result.json`
- `/Users/lin/Desktop/work/my-agent-teams/tasks/合入DeepSeek联网搜索回退修复到集成/result.json`

当前已知：
1. DeepSeek 生产代码已恢复为 `tool_call` 正确链路
2. DeepSeek 当前生产关键缺口是 `CHAT_WEB_SEARCH_BASE_URL`
3. GLM/Zhipu 当前走 `native_provider_tool` + provider-native 健康探针
4. 需要确认并避免不同 provider 的联网搜索 / 深度思考配置被混用

## 你的任务
请直接处理生产配置与部署验证：

### A. 核对并补齐生产联网搜索配置
至少检查并修正：
- `/Users/lin/Desktop/prod/chiralium/backend/.env.prod`
- `CHAT_WEB_SEARCH_PROVIDER`
- `CHAT_WEB_SEARCH_BASE_URL`
- `CHAT_WEB_SEARCH_API_KEY`
- `CHAT_WEB_SEARCH_TIMEOUT_MS`

要求：
- 确认这些变量与 **DeepSeek tool_call + 外部搜索 runtime** 的代码契约一致
- 不要把它们误当成 GLM / Zhipu provider-native 搜索配置

### B. 核对各 provider 配置对应关系，不要混用
请明确并验证：
- DeepSeek：`thinking = native_toggle`，`web_search = tool_call + 外部 runtime`
- GLM / Zhipu：`thinking = native_toggle`，`web_search = native_provider_tool`
- 生产环境中不要出现把 DeepSeek 当成 Zhipu native web_search 去调用，或把 Zhipu provider-native 状态误用于 DeepSeek 的配置/部署结果
- 如生产数据中存在会影响当前链路的 provider/data 混用，请修正；若不影响当前链路，也请在结果中记录

### C. 执行部署与验证
在配置修正后执行生产部署（林总工已明确授权）：
```bash
cd /Users/lin/Desktop/work/chiralium && ./scripts/deploy.sh prod
```

部署后至少验证：
1. DeepSeek：按钮状态、tool_call runtime、真实联网结果
2. GLM：按钮状态是否符合当前策略；若仍 unavailable，要明确是上游退化还是本地问题
3. 后端 / 公网健康检查通过

## 输出要求
完成后写：
- `/Users/lin/Desktop/work/my-agent-teams/tasks/补齐生产AI对话联网搜索配置并部署验证/ack.json`
- `/Users/lin/Desktop/work/my-agent-teams/tasks/补齐生产AI对话联网搜索配置并部署验证/result.json`

结果中请包含：
- 修改了哪些生产配置项
- 最终各 provider 的联网搜索 / 深度思考对应关系
- deployed_commit
- health_check_result
- DeepSeek / GLM 的验证结果
- 若仍有残留问题，明确是代码 / 配置 / 数据 / 外部依赖 哪一类
