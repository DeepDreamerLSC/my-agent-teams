# 任务：设计 hybrid_experimental 增强管线

## 任务类型
development（架构设计）

## 目标
基于横评结论，设计 `parser_backend=hybrid_experimental` 模式的技术架构，实现多模型 PageIR 合并、增强触发策略、校验与回退机制。

## 任务边界
- 只做设计，输出设计文档到 `design/pdf2word/`
- 不修改代码
- 设计方案需要 PM 确认后才能拆子任务

## 输入事实
- 横评已完成，结论：apple_baseline 继续作为默认主 parser
- 横评报告：`design/pdf2word/PDF转Word本地模型横评最终报告.md`
- 架构方案：`design/pdf2word/PDF转Word本地模型横评推理架构落地方案.md`
- 统一推理框架已完成：inference_config.yaml + BackendConfig + ProfileConfig + Adapter + Normalizer + PageIR
- 已有 6 个 profile 的评测数据（artifacts/pdf2word/model-eval/）
- 推荐增强策略：apple_baseline 主 PageIR + PaddleOCR-VL 增强 + MinerU 候选 + Qwen3-VL review

## 设计要求

### 1. 整体架构
- hybrid_experimental 的调用入口和配置方式
- 与现有 `parser_backend=apple` 的关系和切换方式
- 增强管线的阶段划分（baseline → 增强 → review → 校验 → 输出）

### 2. PageIR 合并策略
- 主 PageIR（baseline）与增强 PageIR 的合并规则
- 冲突处理：同一位置的 block 如何选择/覆盖
- 来源标注：每个 block 必须带来源 profile、置信度

### 3. 增强触发策略
- 何时触发增强模型：低置信页检测、图片密集页、公式疑似页、表格页
- 触发条件的量化指标
- 哪些增强模型用于哪些场景

### 4. 校验与回退机制
- 增强输出的校验规则
- 校验失败时的回退策略（回退到 baseline）
- 审计日志

### 5. 性能与并发
- 增强模型调用是否异步/并行
- 超时策略
- 常驻模型服务 vs 按需加载

### 6. 新增指标
- review_acceptance_rate、json_valid_rate
- 图片归属准确率、公式候选召回率
- 增强前后题号缺失率对比

## 交付物
### 设计文档：`design/pdf2word/hybrid_experimental增强管线设计.md`
- 架构图、配置示例、数据流、接口定义
- 可拆解的子任务列表

## 约束
- write_scope 以 task.json 为准
- 只做设计文档输出，不修改任何代码
- 方案需 PM 确认后才能进入实现

## 验收标准
1. 覆盖全部 6 个设计要求
2. 包含可拆解的子任务列表
3. 与现有统一推理框架兼容
4. 方案提交 PM 确认后才能进入实现

## 下游动作
PM 确认方案后，拆解为实现任务派发给 dev-1/dev-2。
