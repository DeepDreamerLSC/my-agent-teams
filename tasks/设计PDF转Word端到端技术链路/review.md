# 审查说明：设计 PDF 转 Word 端到端技术链路

## 结论

**通过（approve）**。

这份设计稿已经完成了本任务要求的主线交付：Phase 1 从 PDF 输入到 DOCX 输出的完整路径、模块接口契约、Phase 2/3 扩展点、错误处理与回退链路、性能预算，以及 formula 专项接口预留都写到了。更重要的是，它把 Phase 1 真正需要补齐的桥接点说清楚了：Hybrid 内部工作在 `PageIR`，但现有主链路消费的是 `parser_response.blocks`，因此 `validated PageIR -> parser_response` 必须被显式设计，而不是留给开发临场拼接。

## 复核要点

- 与 instruction.md 对齐：
  - 覆盖 Phase 1 完整数据流
  - 给出各模块 JSON 契约和字段说明
  - 说明 Phase 2 review worker 与 Phase 3 `paddleocr_vl` 扩展点
  - 写清每个节点的失败行为与回退策略
  - 提供耗时 / 内存预算
- 与既有方案一致：
  - 默认同步链路仍是 `apple_baseline -> PageIR -> ExerciseIR -> DOCX`
  - `hybrid_experimental` 仍需显式开启
  - Phase 1 只接 `mineru_full`
  - `formula_candidate` 仍是 audit-only
- 与现有代码骨架兼容：
  - `conversion_service` 仍通过 `parser_response.blocks` 接后续流程
  - `hybrid_pipeline` 当前已经具备 baseline / question-region / candidate / review / merge / validate 骨架
  - `review_integrator` 和 `PageInferenceRequest` 的 Phase 2 接入点已在代码中存在

## 非阻塞提示

1. 4.5 节的 `QuestionRegion` 契约还偏向旧口径，没有把当前 detector 已新增的 `determinable`、`skip_enhancement`、distinct/body 统计和完整 failure reason 枚举写进去。主线不受影响，但后续实现显式 trigger / audit 时可能还要回源码补一次。
2. 4.8 节展示了 review JSON 的内层对象结构，但没有把 `build_review_output_schema()` 真正返回的 wrapper 和 `strict=true` 这一层 transport contract 写出来。Phase 2 实现时最好补一句说明，避免有人把 `output_schema` 传成错误形状。

## 建议动作

建议 PM 继续用这份设计稿推进后续 Phase 1 实现任务拆分；不需要因为 reviewer 发现新的阻塞问题而退回重写。后续如果要把这份文档长期作为接口真相源，建议顺手把上面两处契约细节补完整。

审查时间：2026-05-16T15:07:56+08:00
