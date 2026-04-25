# 任务：接入 DeepSeek 固定供应商展示与能力驱动前端

## 背景

上游方案任务：
- `/Users/lin/Desktop/work/my-agent-teams/tasks/设计DeepSeek供应商与能力支持方案`
- 方案文档：`/Users/lin/Desktop/work/chiralium/design/product/deepseek-provider-capability-support-plan.md`

本任务对应方案中的 execution 子任务 C。

## 前置依赖
- `实现DeepSeek固定供应商注册表与能力输出`

## 目标

完成前端两类改造：
1. 模型管理页能正确展示 DeepSeek 作为固定 provider
2. 聊天页“深度思考 / 联网搜索”按钮不再写死为 zhipu，而是基于后端 capability 驱动

## 建议实现范围
- `/Users/lin/Desktop/work/chiralium/frontend/src/pages/admin/Models.tsx`
- `/Users/lin/Desktop/work/chiralium/frontend/src/hooks/useChatOptions.ts`
- `/Users/lin/Desktop/work/chiralium/frontend/src/components/ChatToolbar.tsx`
- `/Users/lin/Desktop/work/chiralium/frontend/src/utils/chatThinking.ts`
- `/Users/lin/Desktop/work/chiralium/frontend/src/test`

## 验收标准
1. 管理后台 provider 列表能出现 DeepSeek
2. DeepSeek provider 的展示文案正确
3. 聊天工具栏的 thinking / web_search 开关基于 capability 控制
4. 不再使用 `provider === 'zhipu'` 作为唯一能力判断依据
5. 现有其他 provider UI 不回归

## 测试要点
- provider 展示
- capability 驱动按钮状态
- 非 DeepSeek provider 的兼容性

## 交付物
完成后写：
- `/Users/lin/Desktop/work/my-agent-teams/tasks/接入DeepSeek固定供应商展示与能力驱动前端/result.json`
