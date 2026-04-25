# 审查结论：驳回（REQUEST CHANGES）

## 审查范围
- `/Users/lin/Desktop/work/chiralium/frontend/src/pages/Chat.tsx`
- `/Users/lin/Desktop/work/chiralium/frontend/src/pages/admin/Models.tsx`
- `/Users/lin/Desktop/work/chiralium/frontend/src/test/capabilityDrivenToolbar.test.tsx`

## 结论摘要
这次修正把上轮两个代码层阻塞点都修掉了：
- `Chat.tsx` 已真实传递 `supportsThinking` / `supportsWebSearch`
- `Models.tsx` 已统一通过 `getProviderLabel()` 展示 provider 文案

但本任务要求的第三点——**“补真实接线测试”**——仍然没有达成。当前 `capabilityDrivenToolbar.test.tsx` 依然只是测试文件内部自定义的模拟函数，没有 render `Chat.tsx` / `ChatToolbar` / `Models.tsx` 的真实组件路径，因此我仍然不能给通过结论。

---

## 已修复项

### 1. `Chat.tsx` 已真实传递 `supportsThinking` / `supportsWebSearch`
- **证据**：
  - `frontend/src/pages/Chat.tsx:57-59` 已从 `useChatOptions()` 解构：
    - `supportsThinking`
    - `supportsWebSearch`
  - `frontend/src/pages/Chat.tsx:295-297` 已把它们传进 `toolbarProps`
- **判断**：
  - 这消除了上轮“只传 `supportsZhipuTools`，导致单能力模型被误判为双能力”的真实接线问题。

### 2. `Models.tsx` 已统一用 `getProviderLabel()` 展示 DeepSeek 文案
- **证据**：
  - `frontend/src/pages/admin/Models.tsx:6` 导入 `getProviderLabel`
  - `frontend/src/pages/admin/Models.tsx:170` 桌面列表列 render 使用 `getProviderLabel(v)`
  - `frontend/src/pages/admin/Models.tsx:246` 移动端卡片也使用 `getProviderLabel(record.provider)`
- **判断**：
  - DeepSeek 在真实展示里已不再裸显示为 `deepseek`，这一点我认可已经修复。

---

## 阻塞问题

### 1. [HIGH] `capabilityDrivenToolbar.test.tsx` 仍未覆盖真实接线路径，只是在测试里“模拟逻辑”
- **证据**：
  - `capabilityDrivenToolbar.test.tsx:35-49` 自己定义了 `resolveCapabilities()`，只是复制了 `useChatOptions` 的计算逻辑
  - `capabilityDrivenToolbar.test.tsx:130-141` 又自己定义了 `resolveToolbarProps()`，只是复制了 `ChatToolbar` 的 prop fallback 逻辑
  - 全文件没有：
    - `render(<Chat />)`
    - `render(<ChatToolbar />)`
    - `render(<Models />)`
    - 也没有任何 DOM 断言去验证按钮 disabled / enabled 或 provider 文案实际出现在页面上
- **为什么阻塞**：
  - 任务 `instruction.md` 明确要求的是：
    1. 模型仅支持 thinking 时，真实页面里“深度思考可用 / 联网搜索禁用”
    2. 模型仅支持 web_search 时，真实页面里“联网搜索可用 / 深度思考禁用”
    3. Models 页 provider 展示文案正确
  - 当前测试验证的是“测试文件里自己写的两段模拟函数”，不是运行中的组件树。
  - 也就是说：**它证明不了真实接线已被保护住**。
- **修复建议**：
  - 至少新增 2 类真实组件测试：
    1. **聊天工具栏真实接线测试**
       - render `ChatToolbar`（更好是 render `Chat`/`ChatWorkspace`）
       - 传入 `supportsThinking=true, supportsWebSearch=false`
       - 断言“深度思考”按钮可用、“联网搜索”按钮禁用
       - 再做反向场景
    2. **Models 页展示测试**
       - render `Models` 或最小抽取视图
       - mock 返回 `provider='deepseek'`
       - 断言页面显示 `DeepSeek` 而不是 `deepseek`

---

## 本次复核证据
- 本地验证：
  - `npx vitest run src/test/capabilityDrivenToolbar.test.tsx src/test/chatOptions.test.tsx src/test/chatStreaming.test.tsx src/test/chatThinking.test.ts src/test/adminConfigNavigation.test.tsx` → **5 files, 33 tests passed**
  - `npx tsc --noEmit` → **通过**
- 结论说明：
  - 现有测试全绿，但它们没有覆盖本任务要求的真实组件接线路径，因此不足以解除 review gate。

## 最终建议
- **当前结论：驳回 / REQUEST CHANGES**
- 当前代码修复已基本到位；请再补真实组件级测试后重新提交审查。
