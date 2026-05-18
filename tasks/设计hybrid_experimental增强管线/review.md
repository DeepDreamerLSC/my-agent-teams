# 审查说明：设计 hybrid_experimental 增强管线

## 结论

**通过（approve）**。

这份设计文档已经完成了本任务要求的主线交付：覆盖了整体架构、PageIR 合并、增强触发、校验与回退、性能并发、指标设计 6 个部分，并补充了配置示例、数据流、接口草案、灰度上线顺序和可拆解子任务列表。对 reviewer 来说，这已经不是“方向性想法”，而是一份可以交给 PM 做方案确认、再继续拆实现任务的设计稿。

## 复核要点

- 文档结构和 instruction.md 对齐：
  - `parser_backend=hybrid_experimental` 的入口、模式关系和数据流
  - baseline 与 enhancer 的 PageIR 合并规则、冲突处理、来源标注
  - 低置信页 / 图片页 / 表格页 / 公式疑似页的触发条件
  - validator、页级回退、整本回退和审计日志
  - 异步执行、超时、并发、缓存策略
  - `json_valid_rate`、`review_acceptance_rate`、题号缺失率前后对比等指标
- 文档没有越界改代码：
  - 本轮只新增设计文档，符合“只做设计、不修改代码”的任务边界
  - 产出文件也在 `task.json.write_scope` 内
- 与现有统一推理框架总体兼容：
  - 设计明确沿用 `inference_config.yaml`、`BackendConfig`、`ProfileConfig`、adapter、normalizer、`PageIR` 体系
  - 没有要求绕开现有框架另开一套模型专用入口

## 非阻塞提示

1. 文档 4.4 节把合并顺序写成 `baseline order + 0.1/+0.2` 这类小数序，但当前代码里的 `PDFSourceBlock.order` 还是 `int`，排序器也按整数排序。设计可以先过，但实现前需要把这个点改成“局部重排后统一重编号”或同步调整数据模型。
2. 指标部分写了 `image_attachment_rate` 和 `formula_candidate_recall_proxy`，已经覆盖了同一问题域，但和任务里点名的“图片归属准确率、公式候选召回率”仍不是完全同一口径。建议 PM 在确认方案时把自动代理指标和人工标注指标分别钉死，避免实现后返工。

## 建议动作

建议 PM 直接以这份设计稿做方案确认，再按文档第 14 节拆实现任务；不需要因为 reviewer 发现新的阻塞问题而返工整份设计。

审查时间：2026-05-15T18:19:10+08:00
