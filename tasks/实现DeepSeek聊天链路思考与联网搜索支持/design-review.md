# 设计审查结论：通过（APPROVE, with follow-up notes）

## 审查范围
- 任务：`/Users/lin/Desktop/work/my-agent-teams/tasks/实现DeepSeek聊天链路思考与联网搜索支持`
- 上游方案：`/Users/lin/Desktop/work/chiralium/design/product/deepseek-provider-capability-support-plan.md`
- 本次重点核对：
  - DeepSeek thinking 是否按方案接入
  - DeepSeek web_search 是否走平台级 tool-call 路径，而不是智谱 native `web_search`
  - capability gating 是否从 `provider == 'zhipu'` 改为 capability-driven
  - tool-call runtime 是否具备基本死循环保护与安全降级

## 结论摘要
本次实现**总体符合**上游方案定义的核心设计：

1. **DeepSeek thinking** 已按 capability-driven 方式接入，不再写死为智谱专属。
2. **DeepSeek web_search** 已切到平台级 tool-call 路径，没有复用智谱 native `web_search` 分支。
3. 聊天主链路与 skill-backed model 路径都已改为消费 `resolve_model_capabilities(model)`，与方案要求一致。
4. 已新增平台级 `web_search_service.py` 与 `chat_tool_runtime_service.py`，架构边界基本符合方案。
5. 我本地复跑了相关后端测试：
   - `PYTHONDONTWRITEBYTECODE=1 PYTEST_ADDOPTS='-p no:cacheprovider' /Users/lin/Desktop/work/chiralium/backend/.venv/bin/pytest /Users/lin/Desktop/work/chiralium/backend/tests/test_models.py /Users/lin/Desktop/work/chiralium/backend/tests/test_chat_tool_runtime_service.py /Users/lin/Desktop/work/chiralium/backend/tests/test_chat.py -q`
   - 结果：`64 passed, 4 warnings`

基于以上，我的**设计审查结论为通过 / APPROVE**。

---

## 对齐方案的正向证据

### 1. DeepSeek thinking 已按方案接入
- `backend/app/services/model_service.py:157-162`
  - `build_model_chat_request_body()` 不再只认 `zhipu`，而是通过 `resolve_model_capabilities(model)` 决定 `thinking` 是否可用。
- `backend/app/api/chat.py:309-318`
  - 新增 `_resolve_chat_feature_flags()`，主聊天链路不再使用 `provider == 'zhipu'` 硬编码。
- `backend/app/api/chat.py:1365-1369, 1612-1616`
  - skill-backed model 路径与普通文本聊天路径都改成 capability-driven gating。

这与方案中“删除前后端所有 `provider == 'zhipu'` 的 capability 判定写死”的要求一致。

### 2. DeepSeek web_search 已走 tool-call，而不是智谱 native provider tool
- `backend/app/services/model_service.py:164-200`
  - `web_search_mode == 'native_provider_tool'` 时仍走智谱现有 `tools: [{type: 'web_search'}]`。
  - `web_search_mode == 'tool_call'` 时改为注入函数工具定义 + `tool_choice='auto'`。
- `backend/app/api/chat.py:863-938`
  - `_stream_text_model_response()` 在 `web_search_mode == 'tool_call'` 时切到 `chat_tool_runtime_service.run_web_search_tool_call_flow()`。
- `backend/app/services/chat_tool_runtime_service.py:83-149`
  - 实现了 `assistant -> tool -> assistant` 的补轮流程。
- `backend/app/services/web_search_service.py`
  - 新增平台级搜索适配层，输出统一 `{query, results, provider}` 结构。

这与方案中“DeepSeek 的联网搜索不走 provider-native search，而走平台自有 `web_search` tool-call 链路”的要求一致。

### 3. 风险约束已有基本落地
- `backend/app/services/chat_tool_runtime_service.py:15`
  - `MAX_TOOL_CALL_TURNS = 4`
- `backend/app/services/chat_tool_runtime_service.py:118-121`
  - 已有重复调用保护
- `backend/app/services/chat_tool_runtime_service.py:132-148`
  - 最终正文为空或补轮超限时，会抛出明确错误而不是静默成功
- `backend/app/services/web_search_service.py:56-59, 62-64, 78-81`
  - 未配置 provider / base_url / 搜索失败时，安全返回空结果，不把搜索服务故障升级为致命崩溃

这与方案中“空响应/死循环保护”“safe degrade to disabled/empty result”的总体方向一致。

---

## 非阻塞建议（建议后续补强，但不构成这轮设计 gate 阻塞）

### 1. [MEDIUM] 重复 tool-call 保护当前把 `tool_call_id` 也纳入 signature，导致“同语义重复调用”识别偏弱
- **位置**：`backend/app/services/chat_tool_runtime_service.py:117-121`
- **当前实现**：
  - `signature = f"{tool_call_id}:{tool_name}:{arguments}"`
- **问题**：
  - 如果模型每轮都生成新的 `tool_call_id`，即便 query/limit 完全相同，也不会命中这层“重复 signature”保护。
  - 当前仍有 `MAX_TOOL_CALL_TURNS=4` 兜底，所以不会无限循环；但“重复调用的早停保护”比方案意图弱。
- **建议**：
  - 把 signature 改成基于 `tool_name + 规范化后的 arguments`（例如 query/limit 的 JSON canonical form），不要依赖 `tool_call_id`。

### 2. [MEDIUM] `limit` 参数解析缺少显式容错，模型返回异常值时可能抛 `ValueError`
- **位置**：`backend/app/services/chat_tool_runtime_service.py:125-128`
- **当前实现**：
  - `limit = int(arguments.get("limit") or web_search_service.DEFAULT_SEARCH_LIMIT)`
- **问题**：
  - 如果模型给出非整数值（例如非法字符串），这里会直接抛 `ValueError`。
  - 当前外层会记录失败，但不是一个清晰的、面向模型协议的 502 错误。
- **建议**：
  - 对 `limit` 做安全解析与 clamp；解析失败时回退默认值，或抛出明确的 `HTTPException(502)`。

---

## 设计层面的总体判断

从**方案符合性**看，这次实现已经满足本任务最关键的三条：

1. DeepSeek thinking 已接入；
2. DeepSeek web_search 已改为平台级 tool-call runtime；
3. Zhipu 原生 thinking/web_search 路径没有被误伤，且相关回归测试通过。

因此我建议：
- **当前设计审查：通过 / APPROVE**
- 进入后续 reviewer / integration 流程时，可把上面的两条 MEDIUM 建议作为 follow-up cleanup 或小修项处理；如果 review-1 认为 merge 前必须收紧死循环语义，也可以把第 1 条升级为修改项。
