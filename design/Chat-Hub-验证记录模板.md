# Chat Hub Lite 验证记录模板

> 用于验证期（1-2 周）每日记录。重点不是“消息是不是多了”，而是：
> 1. PM 中转是否减少
> 2. 任务定义是否更稳定
> 3. critical / 生产任务是否仍正确走双通道

---

## 基本信息

- 日期：
- 记录人：
- 验证周期第几天：

## 当日任务样本

| task_id | 标题 | 是否发了 task_announce | 是否有 agent 主动跟进 | 是否回写关键结论 |
|--------|------|------------------------|------------------------|------------------|
|        |      |                        |                        |                  |

## 核心指标

### 1. PM 手工中转次数
- 当日手工中转次数：
- 相比前几天趋势：

### 2. instruction 二次补写次数
- 当日有多少任务在派发/公告后还需要补 instruction：
- 原因：

### 3. Chat 实际使用情况
- question 数量：
- answer 数量：
- task_done / decision 数量：
- 是否出现“大家仍然绕开 chat，只找 PM”：

### 4. 关键结论回写率
- 有多少条关键结论被回写到：
  - `features/<feature-id>/decisions.log`
  - `notes/dev.md / arch.md / qa.md`
- 是否出现“只在 chat 里说了，但没落盘”：

### 4.5 协议/数据质量观察
- `lint-chat.sh` 是否通过：
- 是否出现非法 `reply_to` / `task_id` 错配 / 重复 `msg_id`：
- 是否出现应该是 system 事件却被人工消息冒充的情况：
- 是否出现 priority / severity 理解混乱：

### 5. 超时与 PM 介入
- `working 超时` 提醒次数：
- PM 介入次数：
- 介入后做了什么（补 instruction / 缩边界 / 拆子任务 / 改派）：

### 6. critical / 生产任务双通道检查
- 是否有 critical / 生产任务：
- 是否同时走了：
  - `task_announce`
  - `send-to-agent.sh`
- 是否有遗漏：

### 6.5 看板/事件对齐观察
- 如果看板/communication ingest 已接入：
  - task thread 是否能被稳定抽取
  - system notice / direct nudge 是否有统一事件口径
  - 是否出现 timeline 无法排序/事件归属错误

## 当日观察

### 做得好的地方
- 

### 暴露出来的问题
- 

### 建议次日调整
- 
