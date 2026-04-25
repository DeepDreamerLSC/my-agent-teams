# 任务：修正 DeepSeek 前端能力驱动接入与展示文案

## 背景

上游任务：
- `/Users/lin/Desktop/work/my-agent-teams/tasks/接入DeepSeek固定供应商展示与能力驱动前端`

review-1 已给出 REQUEST CHANGES，阻塞点有两个：
1. `Chat.tsx` 真实接线仍只传旧的 `supportsZhipuTools`，没有把 `supportsThinking` / `supportsWebSearch` 传进 `ChatToolbar`
2. `Models.tsx` 列表展示仍直接显示原始 `provider` 字符串，没有统一展示 `DeepSeek` 文案

此外，当前测试没有覆盖真实 `Chat.tsx -> useChatOptions -> ChatToolbar` 接线路径，因此漏掉了上述问题。

## 你的任务

### 必修 1：修正真实聊天页接线
- 在 `Chat.tsx` 中真正传递：
  - `supportsThinking`
  - `supportsWebSearch`
- 不再让 `supportsZhipuTools` 继续作为聊天页主路径能力判定
- `supportsZhipuTools` 只保留为兼容 fallback

### 必修 2：修正 Models 页的 provider 展示文案
- 列表/卡片展示不要直接显示原始 `provider`
- 优先使用后端返回的 `provider_label`
- 或 fallback 到统一的 provider label helper
- 确保 DeepSeek 在真实展示里显示为 `DeepSeek`

### 必修 3：补真实接线测试
至少补一条组件级测试覆盖：
1. 模型仅支持 thinking、不支持 web_search 时：
   - 深度思考按钮可用
   - 联网搜索按钮禁用
2. 模型仅支持 web_search、不支持 thinking 时：
   - 联网搜索按钮可用
   - 深度思考按钮禁用
3. Models 页 provider 展示文案正确

## write_scope
- `/Users/lin/Desktop/work/chiralium/frontend/src/pages/admin/Models.tsx`
- `/Users/lin/Desktop/work/chiralium/frontend/src/hooks/useChatOptions.ts`
- `/Users/lin/Desktop/work/chiralium/frontend/src/components/ChatToolbar.tsx`
- `/Users/lin/Desktop/work/chiralium/frontend/src/pages/Chat.tsx`
- `/Users/lin/Desktop/work/chiralium/frontend/src/utils/chatThinking.ts`
- `/Users/lin/Desktop/work/chiralium/frontend/src/test`

## 交付物
完成后写：
- `/Users/lin/Desktop/work/my-agent-teams/tasks/修正DeepSeek前端能力驱动接入/result.json`
