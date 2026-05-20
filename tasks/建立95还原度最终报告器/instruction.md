# 任务：建立95还原度最终报告器

## 任务类型
质量/验证报告实现

## 目标
把 95% 还原度路线文档中的评分维度、权重、表格分项和 P0 阻断项串成一份最终报告器，能输出 `fidelity_metrics.json` / `fidelity_report.md` 风格的汇总结果，并明确给出通过/失败原因。

## 任务边界
- 只允许修改 `model_eval_runner.py`、`backend/tests/test_pdf_to_word_fidelity_report.py`、`backend/tests/fixtures/pdf_to_word/fidelity_report/`。
- 本任务只做报告汇总与输出，不改 renderer / gate / normalizer。
- 本轮不接视觉相似度细分实现；如果该分项暂缺，只能按路线文档口径显式标记未接入，不能假装已完成。

## 输入事实
- 上游依赖：`冻结95还原度指标与样本清单`、`实现DOCX表格检查门禁`、`补齐表格样例与验收夹具`。
- 路线要求：最终报告至少要给出 `overall_score`、各维度得分、表格专项字段、blocking_failures、pass/fail。
- 表格是硬门禁：检测到表格但没有 Word 表格 XML时不能通过。

## 约束
- 报告器必须基于结构化输入产出，不能依赖人工口头判定。
- 若某维度尚未实装，要显式留出缺口标记，不能把未实现项计作通过。
- 不改默认同步 SLA，不新增慢模型触发。

## 交付物
1. fidelity 报告输出逻辑。
2. 覆盖通过 / blocker / 缺项三类场景的测试与 fixture。
3. 至少一个示例输出，证明 overall_score、表格分项和 blocker 能同时落盘。

## 验收标准
- 测试能断言 overall_score、blocking_failures、tables.has_table_xml 等关键字段。
- 报告器能正确处理“表格失败导致整体不过”的场景。
- 未接视觉相似度或其他后续分项时，会显式标记而不是假通过。
- 不越界改 normalizer / renderer / gate。

## 下游动作
完成后，PM 将以该报告器作为 quality/hybrid_async 模式是否达到 95% 的统一出口。
