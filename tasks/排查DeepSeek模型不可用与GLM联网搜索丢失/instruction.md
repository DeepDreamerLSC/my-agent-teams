# 任务：排查 DeepSeek 模型不可用与 GLM 联网搜索丢失

## 背景
线上收到两个问题：
1. **DeepSeek 模型报错，显示模型不可用**
2. **GLM 的联网搜索功能丢失**

按当前 PM 规则，这是排查类任务：先由一个 dev 做事实排查，确认根因后，再由 PM 决定是否拆分修复任务。

## 你的任务
请先做**只读排查 + 最小必要验证**，不要直接大范围改代码。重点遵守最新方法论：
- 先找**现有正常实现**做对比，不要先拍脑袋列方案
- 不要假设，去查代码、配置、接口响应、日志，确认事实

### 问题 A：DeepSeek 模型不可用
至少检查：
- DeepSeek 当前模型配置、provider、capability 输出是否正常
- `/api/models/available`、`/api/admin/models`、`/api/meta/*` 是否存在异常
- 聊天链路里 DeepSeek 请求为什么会返回“模型不可用”
- 是代码问题、配置问题、数据问题，还是外部依赖问题

### 问题 B：GLM 联网搜索功能丢失
至少检查：
- 先找 **GLM 联网搜索此前正常工作的实现/链路**，与当前行为做对比
- 当前 `GLM` 的 capability / provider / runtime 链路是否发生回退
- 是前端按钮状态丢失、后端 capability 丢失，还是 runtime 配置缺失
- 是否和这次 DeepSeek 修复链路有交叉影响

## 输出要求
完成后请在 result.json 中明确写出：
1. 两个问题各自的**根因判断**
2. 每个问题属于：代码 / 配置 / 数据 / 外部依赖 中的哪一类
3. 关键证据（文件、接口、日志、配置项）
4. 如果需要修复，建议拆给谁（dev-1 / dev-2 / arch-1）以及建议改动范围
5. 如果是配置问题，请明确列出缺失项，不要伪装成代码问题

## 交付物
完成后写：
- `/Users/lin/Desktop/work/my-agent-teams/tasks/排查DeepSeek模型不可用与GLM联网搜索丢失/ack.json`
- `/Users/lin/Desktop/work/my-agent-teams/tasks/排查DeepSeek模型不可用与GLM联网搜索丢失/result.json`
