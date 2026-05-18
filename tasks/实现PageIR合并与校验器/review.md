# 审查说明：实现PageIR合并与校验器

## 结论

**通过（approve）**。

这轮实现符合任务边界，只新增了 `page_ir_merger.py`、`hybrid_validator.py` 和对应测试，没有改现有 adapter。主线能力也已经闭合：

- `PageIRMerger` 只会把 `decision=accepted` 且 `kind in {image, table}` 的候选追加到 baseline PageIR
- baseline blocks 保持原顺序和内容不变
- 新增 block 会带来源与归属 metadata
- `HybridValidator` 会做页级 schema / geometry / baseline 保真校验
- 一旦校验失败，整页回退 baseline
- 可以输出 `hybrid-pages.jsonl` 和 `validator-report.json`

我复跑了 result.json 里的测试命令，结果为 `18 passed, 4 warnings`。

## 复核要点

- 合并策略符合任务目标：
  - 只追加 accepted `image/table`
  - 不删除、不覆盖 baseline text/material 主干
  - 追加 block 的 `order` 会排在 baseline 之后
- metadata 注入达标：
  - `candidate_id`
  - `source_profile`
  - `merge_action`
  - `merge_reason`
  - `assigned_question_id`
  - `assigned_region_id`
  - `assignment_status`
  - `assignment_score`
  - `confidence` 也保留在 `PDFSourceBlock` 本体上
- validator 行为符合验收：
  - baseline 前缀被改动会 `baseline_blocks_modified -> fallback`
  - bbox 越界会 `bbox_out_of_bounds -> fallback`
  - 缺 `source_profile` / `merge_action` 会 fallback
  - 页级失败只回退该页，不影响其他页

## 非阻塞提示

当前 merger 注入的 meta 已满足本轮必需字段，但还没有把设计文档示例里的 `merge_confidence`、`filters`、`validator_status` 一并写回 block meta。现在不影响本任务收口；不过后续如果要直接依赖 merged PageIR 做全链路审计，这些字段最好再补齐。

## 建议动作

建议 PM 直接推进下一步“接入 HybridExperimentalPipeline，形成完整 hybrid 增强链路”。这轮没有发现需要返工的阻塞问题。

审查时间：2026-05-15T19:45:31+08:00
