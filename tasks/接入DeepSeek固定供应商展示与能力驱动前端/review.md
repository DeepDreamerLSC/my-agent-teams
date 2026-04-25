# 审查结论：驳回（REQUEST CHANGES）

## 审查范围
- `/Users/lin/Desktop/work/chiralium/frontend/src/pages/admin/Models.tsx`
- `/Users/lin/Desktop/work/chiralium/frontend/src/hooks/useChatOptions.ts`
- `/Users/lin/Desktop/work/chiralium/frontend/src/components/ChatToolbar.tsx`
- `/Users/lin/Desktop/work/chiralium/frontend/src/utils/chatThinking.ts`
- `/Users/lin/Desktop/work/chiralium/frontend/src/test/capabilityDrivenToolbar.test.tsx`

## 结论摘要
本次改动只完成了**一半**：
- `useChatOptions` 已经算出了 `supportsThinking` / `supportsWebSearch`
- `ChatToolbar` 也已经支持按两个独立 prop 做能力判断

但真实聊天页 `Chat.tsx` 仍然只把旧的 `supportsZhipuTools` 传给 `ChatToolbar`，没有把新的两个 granular capability 传进去。因此在真实页面里，这次“capability-driven” 逻辑并没有真正接通：**只要任一能力为 true，两个按钮都会一起被当作支持**。

另外，`Models.tsx` 只把 DeepSeek 加进了编辑表单下拉，但列表/卡片展示仍直接渲染原始 `provider` 字符串，没有使用统一文案映射，因此“DeepSeek 固定 provider 展示文案正确”这一点也没有完全落地。

因此当前不能通过 review。

---

## 阻塞问题

### 1. [HIGH] 聊天页真实接线仍是旧的 `supportsZhipuTools`，独立能力没有传到 `ChatToolbar`
- **证据**：
  - `useChatOptions.ts:231-237` 已计算：
    - `supportsThinking`
    - `supportsWebSearch`
  - `useChatOptions.ts:324-329` 也已返回这两个字段
  - `ChatToolbar.tsx:25-27, 66-68` 支持优先使用：
    - `supportsThinking?`
    - `supportsWebSearch?`
    - 仅在未传时才 fallback 到 `supportsZhipuTools`
  - 但 `Chat.tsx:47-69, 274-299` 实际只从 hook 里取了 `supportsZhipuTools`，并且只把 `supportsZhipuTools` 传进 `toolbarProps`
- **结果**：
  - 若模型 `thinking=true`、`web_search=false`，则：
    - hook 内部：`supportsThinking=true`，`supportsWebSearch=false`
    - 但传到 `ChatToolbar` 的只有 `supportsZhipuTools = true`
    - `ChatToolbar` fallback 后会得到：
      - `supportsThinking = true`
      - `supportsWebSearch = true`
  - 即：**一个能力支持会把另一个不支持的能力也误打开**。
- **为什么阻塞**：
  - 任务要求是 “thinking / web_search 开关基于 capability 控制”，且是**各自独立**的 capability 控制；当前真实页面达不到这个要求。
- **修复建议**：
  - 在 `Chat.tsx` 中同时解构并传递：
    - `supportsThinking`
    - `supportsWebSearch`
  - `supportsZhipuTools` 只保留给旧调用方兼容，不应继续作为当前聊天页主路径。

### 2. [HIGH] Models 页列表展示仍是原始 provider 值，DeepSeek 文案未在实际列表里正确展示
- **证据**：
  - `Models.tsx:169` 桌面列直接 `dataIndex: 'provider'`
  - `Models.tsx:245` 移动端摘要直接渲染 `${record.provider} · ${record.model_name}`
  - 只有 `Models.tsx:386-397` 的编辑表单 provider 下拉新增了 `{ label: 'DeepSeek', value: 'deepseek' }`
- **结果**：
  - 实际后台模型列表若返回 `provider='deepseek'`，页面展示大概率仍是小写 `deepseek`，不是用户可读的 `DeepSeek`
- **为什么阻塞**：
  - 验收标准明确写了：
    - “模型管理页能正确展示 DeepSeek 作为固定 provider”
    - “DeepSeek provider 的展示文案正确”
  - 当前只修了“可选项”，没修“实际展示”。
- **修复建议**：
  - Models 页展示统一改成使用 `provider_label`（若后端已返回）或 `getProviderLabel(record.provider)`。

---

## 测试覆盖问题

### 3. [MEDIUM] `capabilityDrivenToolbar.test.tsx` 没有覆盖真实集成路径，直接漏掉了本次 HIGH 问题
- **证据**：
  - `capabilityDrivenToolbar.test.tsx:36-48` 在测试里自己定义了 `resolveCapabilities()`，只是“模拟 useChatOptions 的逻辑”
  - 它没有 render `ChatToolbar`
  - 也没有经过 `Chat.tsx -> useChatOptions -> ChatToolbar` 这条真实链路
- **结果**：
  - 测试验证的是“本地复制的一段逻辑”，不是线上真正执行的组件组合
  - 所以 `Chat.tsx` 少传两个新 prop 这种接线问题，测试完全发现不了
- **修复建议**：
  - 至少补 1 条组件级测试，覆盖：
    - model 仅支持 `thinking`
    - `Chat.tsx` / `ChatWorkspace` / `ChatToolbar` 实际渲染后
    - “深度思考”可用，但“联网搜索”禁用
  - 再补反向场景：仅 `web_search` 支持时，thinking 禁用、search 可用。

---

## 本次复核证据
- 代码检查：已核对 `Models.tsx`、`useChatOptions.ts`、`ChatToolbar.tsx`、`chatThinking.ts`、`capabilityDrivenToolbar.test.tsx`
- 本地验证：
  - `npx vitest run src/test/capabilityDrivenToolbar.test.tsx src/test/chatOptions.test.tsx src/test/chatStreaming.test.tsx src/test/chatThinking.test.ts` → **4 files, 26 tests passed**
  - `npx tsc --noEmit` → **通过**
- 结论说明：
  - 当前测试虽然全绿，但没有覆盖真实接线路径，因此不能证明任务已满足验收标准。

## 最终建议
- **当前结论：驳回 / REQUEST CHANGES**
- 先修复：
  1. `Chat.tsx` 传递 `supportsThinking` / `supportsWebSearch`
  2. `Models.tsx` 列表展示使用正确的 provider 文案
  3. 补组件级集成测试覆盖真实能力驱动路径
