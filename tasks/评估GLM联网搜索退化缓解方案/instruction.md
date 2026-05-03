# 任务：评估 GLM 联网搜索退化缓解方案

## 背景
只读排查任务结论：
- `/Users/lin/Desktop/work/my-agent-teams/tasks/排查DeepSeek模型不可用与GLM联网搜索丢失/result.json`

当前 GLM 问题没有发现本地 capability / UI / 链路回退证据。
更像是：
- 模型侧 / provider-native web_search 退化
- 配额 / 上游行为变化
- 外部依赖不稳定

## 你的任务
请作为架构/策略任务处理，先出技术方案，不直接写代码。重点回答：
1. 继续依赖 GLM 原生联网搜索是否可接受
2. 是否需要增加健康探针 / 降级策略 / 用户提示
3. 当 GLM provider-native search 不稳定时，最小可行缓解方案是什么
4. 需要拆给 dev-2 / dev-1 的执行任务有哪些

## 方法论要求
- 先以过去正常工作的 GLM 联网搜索实现作为参照物
- 对比当前症状与上游依赖变化，不要先假设本地代码有问题

## 输出要求
请在以下路径输出方案文档：
- `/Users/lin/Desktop/work/chiralium/design/product/glm-web-search-degradation-mitigation-plan.md`

并在 result.json 中写明：
- 根因判断
- 是否建议立刻修复本地代码
- 建议拆解的后续任务
