# 任务：定位 DeepSeek 联网搜索生产异常并给出技术方案

## 背景

生产环境 `chiraliumai.cn` 当前出现 DeepSeek 联网搜索异常：
1. **flash 模型**：联网搜索按钮是禁用状态
2. **pro 模型**：联网搜索按钮可以点按，但不生效

这是一个复杂问题，按当前 PM 职责边界，本阶段只需要你做：
- 问题定位
- 技术分析
- 技术方案设计

不要直接修改代码，也不要自行创建 execution 子任务。

## 你的任务

请围绕以下问题做只读分析并输出方案：

### A. flash 模型为什么联网搜索按钮被禁用
至少检查：
- 后端 provider registry / capability 输出
- `/api/models/available` / `/api/admin/models` / 相关 meta 接口
- 前端 capability 驱动逻辑（模型能力 → ChatToolbar）
- 生产环境里 flash 模型配置是否与预期不一致

### B. pro 模型为什么按钮可点但不生效
至少检查：
- 前端是否成功把 web_search 开关传到请求
- 后端 capability gating 是否放行
- DeepSeek tool-call runtime 是否真正触发
- 平台级 web_search provider 配置是否缺失或降级为空结果
- 是否存在生产环境特有配置/凭据问题

## 输出要求

请在以下路径输出方案文档：
- `/Users/lin/Desktop/work/chiralium/design/product/deepseek-web-search-production-incident-plan.md`

文档至少包含：
1. 需求分析 / 现象拆分
2. 证据（代码路径、配置、可能的生产配置差异）
3. 根因判断（区分 flash / pro）
4. 技术方案
5. 验收标准
6. 测试要点
7. 建议拆解给 be-1 / fe-1 的 execution 子任务清单
8. 风险评估

## 注意

- 本任务完成后，PM 会先把方案摘要通过飞书发给林总工确认
- **在林总工确认前，不会拆 execution 子任务**
- 只输出方案，不直接写代码

## 交付物

完成后写：
- `/Users/lin/Desktop/work/my-agent-teams/tasks/定位DeepSeek联网搜索生产异常/result.json`

结果中请包含：
- 方案文档路径
- flash / pro 两类问题的根因摘要
- 建议后续拆解任务列表
