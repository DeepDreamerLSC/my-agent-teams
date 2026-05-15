# One API 接入 agent 团队方案（面向 Codex / Responses API）

> 生成日期：2026-05-14  
> 修订日期：2026-05-15  
> 结论先行：**经典版 One API 目前不适合直接作为 Codex `wire_api=responses` 的上游。**  
> 原因不是“负载均衡/账号池”能力不够，而是**协议面不兼容**：Codex 这条链路只能使用 Responses 协议，需要上游按 OpenAI Responses 语义处理 `POST /v1/responses`。One API 当前标准 OpenAI 兼容路由仍以 `/v1/chat/completions` 等传统入口为主，没有标准 `/v1/responses` relay；仓库里存在 `/v1/oneapi/proxy/:channelid/*target` 这种通用代理路由，但它不是 Codex 可直接配置的 OpenAI-compatible base URL，必须实测认证、路径改写、流式透传和策略旁路后才能考虑。

---

## 1. 本仓库里找到的相关资料

本次先在 `design/`、`README.md`、`config.json`、`tasks/` 下做了检索。**没有找到现成的 One API 接入 Codex 方案文档**，但找到了几类强相关资料，可作为方案约束来源：

### 1.1 agent 团队当前对 Codex 的接入方式
- `README.md`
  - 说明团队通过 `CODEX_CMD` / `CLAUDE_CMD` 覆盖 agent 启动命令。
- `scripts/teamctl.sh`
  - 已支持用环境变量统一替换 Codex 启动命令，适合后续把 `CODEX_CMD` 包成带自定义 `~/.codex/config.toml` 的启动器。

### 1.2 现有“供应商配置 / 能力分流 / 运行时故障切换”经验
- `tasks/分析AI对话供应商配置与生产一致性/result.json`
  - 结论强调：**不要混淆“聊天模型供应商”与“外部 runtime 供应商”**。
- `tasks/补齐生产AI对话联网搜索配置并部署验证/result.json`
  - 结论强调：缺少明确 endpoint 时，不要硬写配置；要先确认真实兼容契约。
- `tasks/实现DeepSeek固定供应商注册表与能力输出/result.json`
  - 已形成 provider registry / capability 输出思路，说明项目更适合“显式能力声明”，不适合黑盒式隐式路由。
- `tasks/实现DeepSeek聊天链路思考与联网搜索支持/result.json`
  - 已有 capability-based gating、tool-call runtime、多轮补偿、防死循环保护经验。
- `tasks/修复智谱联网搜索健康探针生产失效/result.json`
  - 已形成 `healthy / degraded / unavailable` 分级健康探针思路，适合复用到账号池故障切换。

### 1.3 对本方案的直接启示
1. **Codex provider** 与 **账号池 / relay runtime** 必须分层命名，避免再出现“provider 字段语义混用”。
2. 接入必须先验证**真实协议兼容性**，不能只看“OpenAI-compatible”宣传语。
3. 多账号故障切换不能只做“盲重试”，要有**健康状态、降级状态、熔断窗口、会话粘性**。

---

## 2. 外部兼容性结论

### 2.1 Codex 这条链路要的是什么

OpenAI 官方资料显示：
- Codex 的自定义 `model_providers` 配置支持 `base_url`、`env_key`、`wire_api`；当前配置参考明确说明 `wire_api` 只支持 `responses`。
- 对非 OpenAI 官方上游，Codex 配置还要求显式写 `requires_openai_auth = false`，避免把 OpenAI 官方鉴权语义错误套到自建网关或第三方代理上。
- OpenAI 官方 `Responses API` 的真实入口是 `POST /v1/responses`，并且协议不只是简单文本补全，还包含：
  - streaming 事件流
  - function/tool calling
  - reasoning 参数
  - 更丰富的 output item 结构

这意味着：**只要上游不能按 OpenAI Responses 语义稳定处理 `/v1/responses`，哪怕它支持 `/v1/chat/completions`，也不能视为可直接兼容 Codex。**

### 2.2 One API 现在有什么

One API 官方 README 明确写了：
- 支持“通过负载均衡的方式访问多个渠道”；
- 不指定渠道时会用多个渠道负载均衡；
- 可通过 `Authorization: Bearer ONE_API_KEY-CHANNEL_ID` 指定渠道；
- 可作为 OpenAI API Base 使用。

这些能力说明：**One API 很适合做账号池 / 渠道路由层。**

但是，One API 当前 `router/relay.go` 的标准 OpenAI 兼容 relay 暴露的是：
- `/v1/completions`
- `/v1/chat/completions`
- `/v1/embeddings`
- `/v1/audio/*`
- `/v1/images/generations`
- 等传统路由

**标准 relay 中没有 `/v1/responses` 路由。**

同时要避免另一个误判：`router/relay.go` 还存在 `/v1/oneapi/proxy/:channelid/*target` 通用代理路由。它看起来可以把目标路径拼到下游，但它不是“对 Codex 提供一个标准 OpenAI-compatible `/v1` base URL”的证据，因为至少还缺少以下验证：

1. Codex 发到 `base_url + /responses` 时能否自然命中该 proxy 路由，还是必须把 base URL 写成带 channel id 的特殊路径；
2. One API token、渠道 token 和下游 OpenAI token 的鉴权语义是否会冲突；
3. Responses streaming 事件是否逐字节透传，不被 One API 的 relay 兼容层改写；
4. One API 的模型映射、渠道分发、日志计费、错误包装是否会改变 Responses 请求/响应体。

在这些验证完成前，不能把 proxy 路由等同为“已支持 Codex Responses”。

### 2.3 兼容性最终判断

#### 结论 A：One API 经典版 **不兼容** Codex `wire_api=responses` 标准直连
- 不是“可能不兼容”，而是当前标准 OpenAI 兼容 relay 层面就**缺少 `/v1/responses`**。
- 因此 `base_url = "https://one-api.example.com/v1" + wire_api = "responses"` 这条路径，当前不可直接成立。
- `/v1/oneapi/proxy/:channelid/*target` 只能列为“待验证 raw proxy 旁路”，不能作为生产方案默认前提。

#### 结论 B：One API 的“多账号负载均衡 / 渠道路由”能力本身 **有价值**
- 但只能在以下两类前提下使用：
  1. **One API 先补齐 `/v1/responses` 协议支持**；或
  2. **在 One API 前面再加一层 Responses Gateway**，由这层 Gateway 对 Codex 说 `/v1/responses`，对下游再决定怎么转发。

#### 结论 C：把 Responses API 简单翻译成 Chat Completions **不建议作为一期方案**
原因是 Responses API 不是 Chat Completions 的薄皮：
- tool / function call item 结构不同；
- streaming 事件格式不同；
- `previous_response_id` 等状态字段不同；
- reasoning / output item / built-in tools 能力面更宽；
- One API README 还提示：对某些非原生兼容渠道，One API 可能会“中继并修改请求体和返回体”。

所以：**“Codex -> `/v1/responses` shim -> `/v1/chat/completions`” 属于高风险翻译层，不适合作为首选落地。**

---

## 3. 可选方案对比

| 方案 | 描述 | 是否能满足 `wire_api=responses` | 是否支持多账号故障切换 | 风险 | 结论 |
|---|---|---:|---:|---|---|
| A | Codex 用标准 `base_url=https://one-api.example.com/v1` 直连 One API 经典版 | 否 | 部分有，但用不上 | 标准 relay 缺 `/v1/responses` | 淘汰 |
| A2 | Codex 把 `base_url` 指到 One API `/v1/oneapi/proxy/:channelid` 旁路 | 未验证 | 可能绕过或削弱 One API 分发 | 路径/鉴权/streaming/计费语义均未验证 | 只可做 POC，不进一期 |
| B | Fork One API，原生新增标准 `/v1/responses` relay | 可以（做完后） | 可以，复用渠道/分发 | 开发与兼容验证成本高 | 可做中期 |
| C | 新增独立 Responses Gateway，Codex 只连它 | 可以 | 可以，Gateway 自己做 key pool / health / failover | 实现最可控 | **推荐** |
| D | Gateway 把 Responses 翻译成 Chat Completions 后再走 One API | 理论可做 | 可复用 One API 池子 | 协议翻译高风险 | 不推荐一期 |

---

## 4. 推荐方案：Responses Gateway 与 One API 分层

### 4.1 总体思路

建议把“Codex 接入层”和“One API 账号池层”拆开：

```text
Codex agents
  -> custom model_provider (wire_api=responses)
  -> Responses Gateway
      -> 优先：直连 OpenAI / Azure OpenAI / 已验证支持 Responses 的上游
      -> 可选：未来接 One API（前提是 One API 原生支持 /v1/responses）
```

### 为什么这样拆
1. **先解决协议兼容**：Codex 只认 `/v1/responses` 语义，Gateway 最容易对齐。
2. **再解决多账号可用性**：账号池、熔断、重试、健康探针放 Gateway 做最清晰。
3. **避免语义混用**：
   - `model_provider = codex-gateway`
   - `upstream_account_pool = openai-prod-pool`
   - `fallback_policy = sticky_failover`

---

### 4.2 Gateway 的职责边界

#### 对上（面向 Codex）
必须实现：
- `POST /v1/responses`
- Responses API streaming（至少覆盖 Codex 实际使用的 event 流）
- function/tool calling 所需字段透传
- reasoning 字段透传
- model 名称白名单 / 映射

#### 对下（面向账号池）
必须实现：
- 多 API key / 多 deployment / 多 region 池化
- 健康检查
- 失败分级：`healthy / degraded / unavailable`
- 限流 / 429 退避
- 熔断与半开恢复
- 会话粘性（避免同一长会话频繁跨账号）

#### 不建议一期就做的事情
- 把 Responses 完整翻译成 Chat Completions
- 把 Codex 全部 built-in tools 重新抽象一遍
- 在 One API 里直接魔改所有 provider 适配器

---

## 5. 多账号故障切换设计

### 5.1 账号池对象模型

建议至少抽象到这一级：

```yaml
pool:
  name: openai-prod-pool
  strategy: weighted-sticky-failover
  members:
    - id: openai-key-a
      endpoint: https://api.openai.com/v1
      auth_env: OPENAI_KEY_A
      weight: 5
      model_allowlist: [gpt-5.4, gpt-5.5, gpt-5.4-mini]
    - id: openai-key-b
      endpoint: https://api.openai.com/v1
      auth_env: OPENAI_KEY_B
      weight: 3
    - id: azure-eastus-a
      endpoint: https://xxx.openai.azure.com/openai
      auth_env: AZURE_OPENAI_API_KEY_A
      query_params:
        api-version: 2025-04-01-preview
      weight: 2
```

### 5.2 路由策略

建议：**加权 + 会话粘性 + 故障切换**

1. 新会话：按权重选一个健康成员。
2. 会话内：优先 stick 在同一成员，减少上下文行为漂移。
3. 失败时：
   - 网络错误 / 5xx / upstream timeout -> 切下一个 `healthy` 成员；
   - 429 -> 标记 `degraded`，短时间降权，不立刻永久摘除；
   - 401/403/invalid_request -> 视为配置类错误，直接标记该成员 `unavailable`；
4. 熔断恢复：经过冷却窗口后做半开探测。

### 5.3 健康状态建议

延续仓库内已有的 runtime 探针分级思路：

- `healthy`：最近探针与真实请求都稳定
- `degraded`：可连通，但有 429 / 高延迟 / 偶发 5xx
- `unavailable`：鉴权失败、协议错误、持续超时、明确 4xx 配置错误

### 5.4 重试原则

- **幂等前提下** 才自动重试
- streaming 已经向客户端吐出有效内容后，不要静默切账号重放
- 对同一请求最多一次跨账号 failover，避免放大成本和双写风险

---

## 6. Codex 侧接入方式

建议不要改 `my-agent-teams` 主逻辑，而是通过 `CODEX_CMD` 注入一套专用 profile。

### 6.1 推荐配置形态

`~/.codex/config.toml` 示例（概念性）：

```toml
[model_providers.codex-gateway]
name = "Codex Gateway"
base_url = "https://codex-gateway.example.com/v1"
wire_api = "responses"
env_key = "CODEX_GATEWAY_API_KEY"
requires_openai_auth = false

[profiles.pm-team]
model_provider = "codex-gateway"
model = "gpt-5.4"
model_reasoning_effort = "high"
```

然后在团队启动时：

```bash
export CODEX_CMD='codex -p pm-team'
```

或者给不同 agent 配不同 profile：
- PM / arch：高配模型，高 reasoning
- dev：标准模型
- review：高 reasoning

### 6.2 为什么不用直接改 repo 内 config.json

因为当前仓库的 `config.json` 管的是**agent runtime = codex / claude** 与工作目录，不是 Codex 自身 provider 协议细节。  
更稳妥的做法是：
- 仓库仍只管“启动哪个命令”；
- Codex provider 细节由 `CODEX_CMD` + `~/.codex/config.toml` 管。

---

## 7. 如果坚持复用 One API，最低可行中期方案

如果目标是“最终仍由 One API 承担账号池”，建议优先走 **Fork One API 增量补齐标准 `/v1/responses` relay**，而不是 Responses->Chat 的翻译层。`/v1/oneapi/proxy/:channelid/*target` 可以作为只读/灰度 POC 对象，但不能替代标准 relay 方案。

### 需要补的最小能力
1. 标准 relay 路由层新增 `/v1/responses`（不是只依赖 `/v1/oneapi/proxy/:channelid/*target`）
2. relay controller 支持 Responses 请求体与响应体透传
3. streaming event 逐字节/事件级透传验证
4. tool/function call 字段透传验证
5. reasoning、`previous_response_id`、output item 等 Responses 字段不丢失
6. 禁止对 Codex 流量启用会重写请求体的模型映射/兼容转换
7. 验证渠道分发、指定渠道、健康检查、计费和日志能力在 Responses 路径上仍成立

### 这一方案的主要风险
- One API 现有很多能力建立在 Chat Completions 兼容语义上；
- Responses API 字段更多，后续升级频率也更高；
- 一旦做了请求体重构，容易再次踩到“新字段丢失 / 事件流变形”。

所以这条路**可以做，但不适合本周直接落地到 agent 团队生产使用**。

---

## 8. 分阶段落地建议

### Phase 0：验证阶段（1~2 天）
目标：确认 Codex 走自定义 `model_provider` 没问题，并把 One API proxy 误判风险排除掉。

- 先做一个最小 Responses Gateway：
  - 单账号
  - 只转发 `/v1/responses`
  - 支持非 streaming + streaming
- 可选做一个 One API proxy POC，但只回答“能否透明转发 Responses”，不进入生产默认路径：
  - `base_url` 是否能配置到 proxy 路径；
  - streaming 是否完整；
  - tool/reasoning 字段是否原样保留；
  - One API 渠道分发/计费是否仍有效。
- 用一个 agent profile 接入验证：
  - 能启动
  - 能对话
  - 能流式返回
  - 能跑至少一次工具调用相关任务

验收：Codex 在自定义 `base_url + wire_api=responses` 下稳定工作。

### Phase 1：可用性阶段（2~4 天）
目标：把 Gateway 升级成可生产试用。

- 加账号池
- 加健康探针与状态面板
- 加 429 / 5xx failover
- 加会话粘性
- 加请求日志与 request-id 贯通

验收：单账号失效时，新会话自动切走；老会话按策略降级或重试。

### Phase 2：团队接入阶段（1~2 天）
目标：让 `my-agent-teams` 用起来。

- 为 pm / arch / dev / review 定义 Codex profiles
- 在启动脚本层通过 `CODEX_CMD` 指向对应 profile
- 小范围灰度：先 1~2 个 agent，再全队切换

验收：团队 agent 能稳定跑任务，且日志能定位具体上游账号。

### Phase 3：是否收编 One API（后续决策）
目标：决定 One API 是不是要成为这套链路的统一账号池。

- 若 One API 官方 / fork 已支持标准 `/v1/responses` relay，再评估是否把 Gateway 下游切到 One API
- 否则保持“Codex 走独立 Responses Gateway；其他 OpenAI-compatible 客户端继续走 One API” 的双轨结构

---

## 9. 最终建议

### 推荐结论

**短期不要让 Codex 直接连 One API 经典版。**  
最稳妥的落地方式是：

1. **Codex 独立走 Responses Gateway**；
2. Gateway 原生实现 `/v1/responses`；
3. Gateway 自己做多账号健康探针、降权、熔断、failover；
4. One API 暂时继续服务于其他 Chat Completions / OpenAI-compatible 客户端；
5. 等 One API 原生支持标准 `/v1/responses` relay 后，再考虑是否合并成单层架构。

### 是否能实现“多账号故障切换”

**能。** 但结论分两层：

- **One API 自身有账号池/负载均衡/渠道分发能力**；
- **然而在 Codex `wire_api=responses` 这条链路上，当前不能通过标准 OpenAI-compatible base URL 直接利用这些能力**，因为标准 `/v1/responses` relay 入口还没打通。

所以正确表述是：

> **“多账号故障切换可以实现，但建议先在 Responses Gateway 层实现；One API 经典版当前不能通过标准 `/v1` base URL 直接承担 Codex Responses 上游。”**

---

## 10. 参考资料

### 仓库内资料
- `README.md`
- `scripts/teamctl.sh`
- `tasks/分析AI对话供应商配置与生产一致性/result.json`
- `tasks/补齐生产AI对话联网搜索配置并部署验证/result.json`
- `tasks/实现DeepSeek固定供应商注册表与能力输出/result.json`
- `tasks/实现DeepSeek聊天链路思考与联网搜索支持/result.json`
- `tasks/修复智谱联网搜索健康探针生产失效/result.json`

### 外部资料（调研时核对）
- OpenAI Codex config reference  
  `https://developers.openai.com/codex/config-reference/`
- OpenAI Responses API Reference  
  `https://developers.openai.com/api/reference/resources/responses/methods/create`
- OpenAI Codex responses proxy README  
  `https://github.com/openai/codex/blob/main/codex-rs/responses-api-proxy/README.md`
- One API README  
  `https://github.com/songquanpeng/one-api`
- One API relay router  
  `https://github.com/songquanpeng/one-api/blob/main/router/relay.go`

