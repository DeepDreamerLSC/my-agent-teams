# 审查说明：MinerU适配器对比跑批

## 结论

**通过（approve）**。

本轮结果已经收束为一份可信的对比报告：

- 5 个样例目录完整；
- `comparison_report.json` 已按修正后的逻辑重算；
- 最终结论明确为 **0/5 样例显著优于 apple_baseline**，未达到 `>=3/5` 阈值；
- 报告里把 `cli_direct`、`report_recomputed_without_rerun` 和可用性复核都写清了，结论与数据一致。

## 审查范围

- `tasks/MinerU适配器对比跑批/instruction.md`
- `tasks/MinerU适配器对比跑批/result.json`
- `tasks/MinerU适配器对比跑批/task.json`
- `artifacts/pdf2word/model-eval/20260514-170529/manifest.json`
- `artifacts/pdf2word/model-eval/20260514-170529/comparison_report.json`
- `artifacts/pdf2word/model-eval/20260514-170529/mineru/mineru_summary.json`
- `artifacts/pdf2word/model-eval/20260514-144102/apple_baseline/baseline_summary.json`

## 复核结果

### 已满足部分

- 5 个样例都落盘完整：`pages.jsonl`、`metrics.json`、`warnings.json`、`output.docx` 均存在；
- `comparison_report.json` 包含逐样例的 apple_baseline vs mineru 对比；
- overall conclusion 已明确给出 `0/5`、`>=3/5`、`false`，不会再出现之前那种误判为 `mineru_better` 的问题；
- availability 复核结果已写入报告。

### 结论质量

这次修正是有效的：

- 原来把空题号/漏题很多的样例判成 “better” 的问题已经消失；
- 现在 `mineru_worse / not_better` 的分布与样例实际表现一致；
- 总结结论与样例级数据一致，没有自相矛盾。

## 非阻塞说明

1. 当前执行方式明确标注为 `cli_direct`，且 `comparison_report` 是**在不重跑样例**前提下重算的。对本任务来说这是可接受的，因为本轮修改的是判定逻辑而不是样例产物本身；但它不等同于一轮新的全量 profile 跑批。
2. 题号序列对比仍然是启发式数字抽取，不是人工标注真值；不过报告已经把这一边界条件反映出来了。

## 下一步

建议进入 QA / PM 收口。

审查时间：2026-05-14T18:39:17+08:00
