# 任务：补齐 DeepSeek 前端真实组件接线测试

## 背景

上游任务：
- `/Users/lin/Desktop/work/my-agent-teams/tasks/修正DeepSeek前端能力驱动接入`

review-1 已明确指出：
- Chat.tsx 真实接线已修好
- Models.tsx provider 展示文案已修好
- 但当前测试仍只是文件内模拟函数，没有覆盖真实组件路径

因此本轮修复任务只聚焦：**补真实组件级接线测试**。

## 必做要求

### 1. 聊天工具栏真实接线测试
至少覆盖：
- render `Chat` / `ChatWorkspace` / `ChatToolbar` 的真实组件路径之一
- 模型仅支持 `thinking`、不支持 `web_search` 时：
  - 深度思考按钮可用
  - 联网搜索按钮禁用
- 模型仅支持 `web_search`、不支持 `thinking` 时：
  - 联网搜索按钮可用
  - 深度思考按钮禁用

### 2. Models 页展示测试
至少覆盖：
- mock provider=`deepseek`
- 页面真实渲染后显示 `DeepSeek`
- 不再显示裸字符串 `deepseek`

## write_scope
- `/Users/lin/Desktop/work/chiralium/frontend/src/pages/Chat.tsx`
- `/Users/lin/Desktop/work/chiralium/frontend/src/pages/admin/Models.tsx`
- `/Users/lin/Desktop/work/chiralium/frontend/src/components/ChatToolbar.tsx`
- `/Users/lin/Desktop/work/chiralium/frontend/src/test`

## 注意
- 这轮优先补测试，不要大改逻辑
- 如果确需顺手改少量接线细节，可以改，但必须围绕“让真实组件测试成立”

## 交付物
完成后写：
- `/Users/lin/Desktop/work/my-agent-teams/tasks/补齐DeepSeek前端真实组件接线测试/result.json`
