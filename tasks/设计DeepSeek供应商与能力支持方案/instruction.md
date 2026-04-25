# 任务：设计 DeepSeek 供应商接入与能力支持技术方案

## 背景

生产环境反馈管理中当前存在 1 条有效待处理的 DeepSeek 相关问题：
- **Issue ID**：`3ffc8586-973e-4d28-a8d4-3febdd474b8f`
- **标题**：`DeepSeek供应商未作为固定配置且不支持深度思考与联网搜索`
- **模块**：`模型管理和AI对话`
- **严重程度**：`general`
- **状态**：`pending_action`

问题描述（来自生产反馈）：
1. DeepSeek 没有被纳入模型管理中的固定供应商列表
2. 使用 DeepSeek 模型时，不支持“深度思考”和“联网搜索”能力

这是一个**复杂任务**。按最新职责边界，本阶段只需要你输出技术方案，PM 会在你完成后基于方案拆 execution 子任务派给 be-1 / fe-1。

## 你的任务

请输出一份可直接指导实施的技术方案文档，至少包含：

### 1. 需求分析
- 问题拆分：
  - 供应商接入问题
  - 能力支持问题（深度思考 / 联网搜索）
- 判断哪些是后端改动、哪些可能涉及前端/管理后台

### 2. 技术方案
- DeepSeek 作为固定供应商接入当前模型管理体系的方案
- DeepSeek 在对话链路中支持深度思考、联网搜索的实现路径
- 兼容现有 provider / model / capability 开关的方式

### 3. 接口契约
- 如果需要改 API / schema / 配置项，请写清楚
- 前后端边界要明确，方便 PM 后续拆给 be-1 / fe-1

### 4. 验收标准
- 明确可验证的完成条件

### 5. 测试要点
- 关键场景、回归范围、边界 case

### 6. write_scope 建议
- 供 PM 后续拆 execution 子任务时参考
- 尽量拆出：
  - 后端执行范围
  - 前端执行范围

### 7. 风险评估
- 兼容性风险
- 回滚思路

## 输出位置

请在以下路径输出方案文档：
- `/Users/lin/Desktop/work/chiralium/design/product/deepseek-provider-capability-support-plan.md`

## 约束

- 本任务是 **domain 级方案任务**，不要直接实现代码
- 不要创建子任务；子任务由 PM 在你交付方案后再拆
- 所有共享资源使用绝对路径

## 交付物

完成后写：
- `/Users/lin/Desktop/work/my-agent-teams/tasks/设计DeepSeek供应商与能力支持方案/result.json`

结果中请包含：
- 方案文档路径
- 关键决策摘要
- 建议拆解给 be-1 / fe-1 的子任务清单
