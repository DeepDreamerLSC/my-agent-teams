# 任务：实现 DeepSeek 固定供应商注册表与能力输出

## 背景

上游方案任务：
- `/Users/lin/Desktop/work/my-agent-teams/tasks/设计DeepSeek供应商与能力支持方案`
- 方案文档：`/Users/lin/Desktop/work/chiralium/design/product/deepseek-provider-capability-support-plan.md`

按方案，这是 execution 子任务 A，目标是先把“固定 provider registry + 模型能力输出”这层契约打好，为后续 DeepSeek thinking / web_search 与前端 UI 接入提供统一事实源。

## 目标

实现后端统一 provider registry，并让模型相关接口输出 capability 字段，至少覆盖：
- DeepSeek 进入固定 provider 列表
- 元数据接口可返回 provider 信息
- 模型列表 / 可用模型接口可返回 capability
- 前后端不再依赖 `provider == 'zhipu'` 作为唯一能力判断依据

## 依据方案（必须阅读）
- `/Users/lin/Desktop/work/chiralium/design/product/deepseek-provider-capability-support-plan.md`
- 重点章节：provider registry、能力矩阵、接口契约、write_scope recommendation

## 建议实现范围
- `/Users/lin/Desktop/work/chiralium/backend/app/core/model_providers.py`（新增）
- `/Users/lin/Desktop/work/chiralium/backend/app/services/model_service.py`
- `/Users/lin/Desktop/work/chiralium/backend/app/api/meta.py`
- `/Users/lin/Desktop/work/chiralium/backend/app/api/models.py`
- `/Users/lin/Desktop/work/chiralium/backend/app/api/admin_models.py`
- `/Users/lin/Desktop/work/chiralium/backend/app/schemas/model.py`
- `/Users/lin/Desktop/work/chiralium/backend/tests`

## 验收标准
1. DeepSeek 出现在固定 provider 列表
2. 至少有一个元数据接口能输出 provider registry
3. `/api/admin/models` 或 `/api/models/available` 能输出 capability 字段
4. DeepSeek 的能力至少能表达：
   - thinking = supported
   - web_search = supported（mode=tool_call）
5. 旧 provider 不回归

## 测试要点
- provider registry 输出正确
- DeepSeek provider 校验通过
- capability 字段输出正确
- 非 DeepSeek provider 不误报能力

## 注意
- 本任务只做“契约与能力输出层”，不要提前做完整聊天 tool-call 链路
- 后续聊天链路任务与前端任务会依赖本任务结果

## 交付物
完成后写：
- `/Users/lin/Desktop/work/my-agent-teams/tasks/实现DeepSeek固定供应商注册表与能力输出/result.json`
结果中说明：
- 修改了哪些后端文件
- 提供了哪些接口/字段
- 测试命令与结果
