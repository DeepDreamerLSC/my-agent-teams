# 审查结论：通过（APPROVE）

## 审查范围
- `/Users/lin/Desktop/work/chiralium/backend/app/services/model_service.py`
- `/Users/lin/Desktop/work/chiralium/backend/app/api/chat.py`
- `/Users/lin/Desktop/work/chiralium/backend/app/services/web_search_service.py`
- `/Users/lin/Desktop/work/chiralium/backend/app/services/chat_tool_runtime_service.py`
- `/Users/lin/Desktop/work/chiralium/backend/tests/test_models.py`
- `/Users/lin/Desktop/work/chiralium/backend/tests/test_chat.py`
- `/Users/lin/Desktop/work/chiralium/backend/tests/test_chat_tool_runtime_service.py`
- `/Users/lin/Desktop/work/chiralium/backend/tests/test_chat_capabilities.py`

## 结论摘要
这次 DeepSeek 聊天链路改动已经达到任务目标：
- thinking / web_search 开关改成基于 capability 判断
- DeepSeek 的 web_search 明确走平台级 `tool_call` runtime，而不是误走智谱原生 `web_search`
- Zhipu 原生 thinking / web_search 请求体没有被破坏
- 相关测试已覆盖 capability gating、DeepSeek tool-call 补轮、以及 Zhipu 回归

综合代码检查和本地复跑结果，我认为该任务可以通过 review。

---

## 通过项

### 1. capability-based thinking / web_search gating 已进入主链路
- **位置**：`backend/app/api/chat.py:309-318`
- **关键实现**：
  - `_resolve_chat_feature_flags()` 不再根据 provider 名硬编码，而是读取 `resolve_model_capabilities(model)`
  - 只有当 capability `supported=true` 时，`thinking_enabled` / `web_search_enabled` 才会生效
- **判断**：
  - 这满足了“capability-based gating”的核心要求
  - 非支持 provider 会自然降级为 `False`

### 2. DeepSeek web_search 已切到平台级 tool_call runtime
- **位置**：
  - `backend/app/services/model_service.py:136-190`
  - `backend/app/api/chat.py:863-938`
- **关键实现**：
  - `build_model_chat_request_body()` 对 `web_search.mode == 'tool_call'` 时：
    - 注入 system prompt
    - 注入 `tool_definitions`
    - 设置 `tool_choice = 'auto'`
  - `_stream_text_model_response()` 在 `web_search_mode == 'tool_call'` 时，直接进入 `chat_tool_runtime_service.run_web_search_tool_call_flow(...)`
- **判断**：
  - DeepSeek 已不再走智谱原生 `web_search` 分支
  - 平台级补轮路径已真实接入主链路

### 3. tool_call runtime 具备补轮与死循环保护
- **位置**：`backend/app/services/chat_tool_runtime_service.py:54-148`
- **关键实现**：
  - 解析 `tool_calls`
  - 执行 `web_search_service.search(query, limit=...)`
  - 将工具结果回填为 `role=tool` 消息继续补轮
  - 通过：
    - `MAX_TOOL_CALL_TURNS = 4`
    - `seen_signatures` 重复签名检测
    来阻止死循环
- **判断**：
  - 这满足了“DeepSeek tool_call web_search runtime”和“死循环保护”要求。

### 4. Zhipu 原生 thinking / web_search 未回归
- **位置**：`backend/app/services/model_service.py:158-190`
- **关键实现**：
  - 当 `web_search_mode == 'native_provider_tool'` 时，仍保留原来的 Zhipu 原生 `tools: [{type: 'web_search', ...}]` 组装路径
  - `thinking.mode == 'native_toggle'` 也仍保留原生 `body['thinking']`
- **测试证据**：
  - `backend/tests/test_models.py` 中原有 Zhipu 请求体测试仍在，并在本地复跑通过
- **判断**：
  - DeepSeek 新能力没有破坏既有 Zhipu 行为。

### 5. 测试覆盖与任务重点匹配
- **证据**：
  - `test_models.py:494-517`：DeepSeek thinking + tool_call web_search 请求体测试
  - `test_chat.py:1584-1675`：主聊天链路 capability gating，验证 DeepSeek 可开、OpenAI 等安全降级
  - `test_chat_tool_runtime_service.py:37-131`：正常补轮返回最终答案 + 重复 tool_call 死循环保护
  - `test_models.py` 其他用例：Zhipu 原生 web_search / thinking 回归验证
- **判断**：
  - 对本任务声明的重点路径，测试覆盖是充分的。

---

## 非阻塞备注
- 当前 `test_chat_tool_runtime_service.py` 没有单独覆盖“tool_call 链路最终返回空正文”的场景；不过 runtime 实现里已显式对空正文抛 502，这属于可后续补强的测试，而不是当前阻塞项。
- `skill-backed` 文本路径虽未单独写一条 DeepSeek 回归测试，但它与主路径共用 `_resolve_chat_feature_flags()` 和 `_stream_text_model_response()`，风险可接受。

## 本次复核证据
- `python3 -m py_compile backend/app/services/model_service.py backend/app/services/web_search_service.py backend/app/services/chat_tool_runtime_service.py backend/app/api/chat.py backend/tests/test_models.py backend/tests/test_chat_tool_runtime_service.py backend/tests/test_chat.py backend/tests/test_chat_capabilities.py` → **通过**
- `pytest backend/tests/test_models.py backend/tests/test_chat_tool_runtime_service.py backend/tests/test_chat.py backend/tests/test_chat_capabilities.py -q` → **66 passed, 4 warnings**

## 最终建议
- **当前结论：通过 / APPROVE**
- 可以进入后续前端接入与集成验证流程。
