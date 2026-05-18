# 审查说明：实现QuestionRegion检测器

## 结论

**通过（approve）**。

这轮实现已经完成任务要求的主线交付：新增了 `QuestionRegionDetector` 和对应测试，能从 baseline `pages.jsonl` 识别题号 anchor，生成 question region，并输出页级 `resolvable` 判断与原因。实现也遵守了任务边界，只改了 detector 与测试文件，没有去修改现有 PageIR 结构。

## 复核要点

- 输出结构对齐验收要求：
  - `QuestionRegion` 包含 `page_index`、`question_id`、`region_bbox`、`resolvable`
  - `QuestionRegionPageResult` 提供页级 `resolvable`、anchor 数、原因和判定指标
- 判定策略对齐任务目标：
  - 题号 anchor 来自文本正则识别
  - anchor 数不足时直接标记 `question_region_not_detectable`
  - `bbox_present_ratio`、`reading_order_valid`、`region_non_overlap_ratio` 和 `page_confidence` 共同约束可判定性
  - 对疑似双栏页有基于 x-gap 的启发式拆列，避免左右栏串扰
- 真实样例结果不是主观判断：
  - 我复跑了 `apple_baseline` 的 5 个样例，结果与 `result.json` 一致
  - `语文五年级` 13 页全部不可判定，稳定返回 `question_region_not_detectable`
  - 数学、英语、科学样例均能检测到 question regions
- 测试已确认通过：
  - `pytest tests/test_question_region_detector.py -q`
  - 结果为 `5 passed, 4 warnings`

## 非阻塞提示

当前真实 artifacts 测试已经足够支撑本任务收口，但回归断言仍偏宽松，主要验证“能检测到”和检测率阈值，没有把 `result.json` 里的样例级精确统计固化下来。后续如果这个检测器进入 hybrid 主链路，建议补几条固定样例的精确断言，避免上游 `pages.jsonl` 轻微变化时被宽松测试放过去。

## 建议动作

建议 PM 直接推进后续 hybrid_experimental 相关任务，例如候选过滤、PageIR 合并和增强链路接入；当前审查没有发现需要退回返工的阻塞问题。

审查时间：2026-05-15T19:04:00+08:00
