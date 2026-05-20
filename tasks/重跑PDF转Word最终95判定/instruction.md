# 任务：重跑PDF转Word最终95判定

## 任务类型
质量 / 最终复验

## 目标
在 visual similarity canonical artifact 链路已经打通后，重新执行 PDF 转 Word 最终 95% 判定，明确回答：当前版本是否已经达到 quality/hybrid_async 的 95% 门槛、表格与 visual similarity 是否都满足口径、PDF 转 Word 是否可以整体收口。

## 任务边界
- 本任务以只读复验为主，不修改生产代码。
- 允许读取上游任务产物、最终报告输出、fixture、final archive/final acceptance 结果，并在任务目录内沉淀复验结论。
- 若仍未达标，只记录 blocker 与建议回补任务，不补代码。

## 输入事实
- 已完成：`建立95还原度最终报告器`、`设计视觉相似度最终门禁与慢模型灰度`、`打通视觉相似度最终产物链路`。
- 上一轮终验的 no-go 原因是 `visual_similarity.json` 缺失；该阻塞已由新任务解除，现需重新判定最终 95% 结论。
- 表格主链此前已经通过终验，当前重点是 visual similarity 接入后的整体分数与 blocker 状态。

## 约束
- 结论必须基于结构化产物、自动化测试结果和真实 artifact，不允许口头判断。
- 不得放宽 threshold=95，不得把 default sync 边界写成已放宽。
- 若 visual similarity 仍只有 contract-only/stub 语义，必须明确标注，不得伪造通过。

## 交付物
1. 一份最新最终复验结论（通过 / 不通过 / 有条件通过）。
2. 一份包含 overall_score、blocking_failures、tables、visual_similarity 状态的汇总。
3. 一份 PM 可直接用于最终收口的 go / no-go 建议。

## 验收标准
- 能明确回答当前版本是否达到 95% 目标。
- 能明确回答 visual similarity 17 分维度是否已真实并入最终判定。
- 若未达标，能把问题定位到具体 blocker，而不是泛化描述。
- 结论与已冻结 contract、表格 gate 与 release boundary 口径一致。

## 下游动作
完成后，PM 将据此决定 PDF 转 Word 项目是否整体收口，或继续拆分剩余缺口任务。
