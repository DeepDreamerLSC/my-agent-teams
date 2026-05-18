# 任务：评估局部能力新模型替代 Paddle 或补公式

## 任务类型
development

## 目标
只围绕**局部能力**做评估，不重启新的端到端 parser 横评：基于现有 model eval runner 与 Hybrid 审计产物，评估“是否存在更适合替代 Paddle 的局部增强模型”或“是否存在更适合补公式的局部能力模型”，输出 owner 可决策的对照报告。

## 任务边界
- 仅处理局部能力模型评估入口、评估脚本/测试与评估报告
- 可修改 `model_eval_runner.py`、`test_model_eval_runner.py`
- 可在 `artifacts/pdf2word/model-eval/` 与 `artifacts/pdf2word/phase4-local-model-eval/` 下产出评估结果
- 不改默认 parser 选型、不改 production chain、不实现新模型正式接线

## 输入事实
- 路线文档已明确：新模型评估延后到当前阶段，且只评估局部能力模型
- 上游已完成 Paddle 选择性触发、在线 review worker、Hybrid QA 基线（至少文档与主线门禁已具备）
- 评估关注点不是“整本 parser 更强”，而是：表格/图片增强是否可替代 Paddle，或公式识别是否有更合适的局部模型
- 输出必须让 owner 能判断：继续投入 Paddle / 公式 OCR / 其他局部模型哪条更值得

## 约束
- write_scope 以 task.json 为准
- 不重启新的全页 parser 横评
- 评估报告必须明确区分：表格/图片局部增强能力 vs 公式专项能力
- 若没有足够证据支持替代，也要清楚写出“不建议替代”的结论与原因

## 交付物
1. 局部能力模型评估入口与必要测试
2. 一份评估报告（写入 `artifacts/pdf2word/phase4-local-model-eval/`），至少包含：候选模型、评估维度、样例页、性能/质量对比、是否建议替代 Paddle 或补公式
3. result.json：写明推荐结论、证据和下一步建议

## 验收标准
1. 评估范围只限局部能力模型，不回到端到端 parser 比赛
2. 报告能明确回答“是否值得替代 Paddle”或“是否值得补公式模型”
3. 有可复现的 runner / 命令 / 样例说明
4. 结论可供 owner 直接做下一轮模型投入决策

## 下游动作
完成后进入 review-1 审查；审查通过后为后续是否引入局部能力新模型提供 owner 可决策报告。
