# 审查结论：驳回（REQUEST CHANGES）

## 审查范围
- `/Users/lin/Desktop/work/chiralium/frontend/src/pages/admin/Models.tsx`
- `/Users/lin/Desktop/work/chiralium/frontend/src/components/ChatToolbar.tsx`
- `/Users/lin/Desktop/work/chiralium/frontend/src/hooks/useChatOptions.ts`
- `/Users/lin/Desktop/work/chiralium/frontend/src/pages/Chat.tsx`
- `/Users/lin/Desktop/work/chiralium/frontend/src/test/deepseekWebSearchVisibility.test.tsx`
- `/Users/lin/Desktop/work/chiralium/frontend/src/test/deepSeekComponentWiring.test.tsx`

## 结论摘要
这次改动在聊天工具栏提示文案和 runtime 状态接线上做了不少正确工作，但**Models 页的 capability 可视化当前会误报**，同时“前向兼容接线”和“Models 页真实渲染”的测试覆盖仍然不够扎实，因此我不能给通过结论。

最核心的问题是：`Models.tsx` 没有消费后端真实返回的 `capabilities`，而是前端本地硬编码了一张 `PROVIDER_CAPABILITIES` 映射表；这张表已经和后端 registry 发生漂移，导致 UI 能力标签会显示错误。

---

## 阻塞问题

### 1. [HIGH] Models 页 capability 可视化未使用后端真实 `capabilities`，且已出现实际误报
- **证据**：
  - `frontend/src/pages/admin/Models.tsx:18-29` 的 `ModelConfig` 接口里没有 `capabilities`
  - `frontend/src/pages/admin/Models.tsx:38-49` 本地写死了 `PROVIDER_CAPABILITIES`
  - `frontend/src/pages/admin/Models.tsx:205-210` 和 `:294-300` 都通过 `getExpectedCapabilities(record.provider)` 渲染“深度思考 / 联网搜索”标签
- **具体误报**：
  - 前端把 `anthropic` 写成了 `thinking: true`（`Models.tsx:42`）
  - 但后端 provider registry 中 `anthropic` 的 `thinking` 是 `false`
- **为什么阻塞**：
  - 任务要求是“provider/capability/配置异常可视化是否清晰且**不误报**”
  - 当前前端能力标签不是来自后端契约，而是来自一份已经漂移的前端硬编码表；这会让管理员看到错误能力信息。
- **修复建议**：
  - `Models.tsx` 直接消费 `/api/admin/models` 返回的 `capabilities`
  - 前端可以保留 provider anomaly 检测作为辅助提示，但能力标签必须以后端真实能力为准

### 2. [HIGH] Models 相关测试没有覆盖“真实 Models 页面接线”，只能证明测试文件里的局部拼装逻辑
- **证据**：
  - `frontend/src/test/deepseekWebSearchVisibility.test.tsx:127-148` 中的 `renderCapabilityColumn()` 是在测试里临时拼装一组 `columns`
  - 它没有 render `Models` 页面组件本身，也没有经过真实的 `desktopColumns/mobileColumns`
- **为什么阻塞**：
  - 当前阻塞点就在 `Models.tsx` 真正使用了错误的能力数据源；但测试没有 render 真实 `Models.tsx`，因此完全没能发现这个问题。
  - 这与任务要求的“真实组件级测试优先”不符。
- **修复建议**：
  - 至少补一条真实 `Models` 组件测试：mock `/admin/models` 返回带 `provider/capabilities` 的数据，断言页面真实渲染出的标签与异常提示

---

## 非阻塞问题

### 3. [MEDIUM] `/meta/chat-capabilities` 的前向兼容测试仍偏弱，未真正覆盖 hook 接线
- **证据**：
  - `useChatOptions.ts:155-179` 的实现本身是合理的：只接受 `available/unavailable/degraded/unknown`，缺失字段时保留默认 `available`
  - 但 `deepseekWebSearchVisibility.test.tsx:403-418` 只是对字符串数组做静态判断，没有 render hook，也没有 mock `/meta/chat-capabilities`
- **影响**：
  - 代码接线本身我认为是稳妥的，但当前测试还不足以证明“后端新增字段后前端会正确接住，非法值会被忽略”。
- **建议**：
  - 增加一条 `useChatOptions` 级测试，mock `/meta/chat-capabilities` 返回：
    - `web_search_runtime_status='degraded'`
    - 一个非法值
  - 断言 hook 最终导出的 `webSearchRuntimeStatus`

### 4. [LOW] ChatToolbar 提示测试以 `title` 精确字符串断言为主，后续文案微调会较脆
- **证据**：`deepseekWebSearchVisibility.test.tsx:226-310`
- **影响**：
  - 这些测试目前是有效的，也是真实组件级测试；只是未来若文案做非语义变更，失败概率会偏高。
- **建议**：
  - 可保留核心精确断言，同时对部分提示改成包含关键语义词的断言，降低维护成本。

---

## 已完成且认可的部分
- `ChatToolbar.tsx` 已正确区分：
  - 不支持 capability
  - runtime unavailable
  - degraded
  这三类状态，提示语义是清晰的（`ChatToolbar.tsx:212-228`）
- `useChatOptions.ts` 对 `web_search_runtime_status` 的前向兼容接线思路是正确的（`useChatOptions.ts:155-179`）
- `deepseekWebSearchVisibility.test.tsx` 对 `ChatToolbar` 的真实组件级 DOM 断言是有效的（`226-395`）

## 本次复核证据
- `npx vitest run src/test/deepseekWebSearchVisibility.test.tsx src/test/deepSeekComponentWiring.test.tsx` → **2 files, 41 tests passed**
- `npx tsc --noEmit` → **通过**
- 结论说明：测试虽然全绿，但未覆盖真实 `Models.tsx` 接线，而且当前 `Models.tsx` 本身已存在能力误报。

## 最终建议
- **当前结论：驳回 / REQUEST CHANGES**
- 优先修复：
  1. `Models.tsx` 改为消费后端返回的真实 `capabilities`
  2. 补真实 `Models` 组件测试
  3. 补 `useChatOptions` 的真实前向兼容 hook 测试
