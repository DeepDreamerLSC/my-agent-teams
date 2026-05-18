# 审查说明：实现候选抽取与标准化

## 结论

**通过（approve）**。

这轮实现已经完成了任务要求的主线交付：新增了 `CandidateExtractor` 和对应测试，能从 MinerU / PaddleOCR-VL 的 `pages.jsonl` 中抽取 `image`、`table`、`formula_candidate`，并整理成统一候选结构。`formula_candidate` 也按要求默认标记为 `audit_only`，没有直接进入可并回候选。

## 复核要点

- 字段和任务要求对齐：
  - `candidate_id`
  - `source_profile`
  - `page_index`
  - `bbox`
  - `block_kind`
  - `content`
  - `confidence`
- `formula_candidate` 策略对齐设计：
  - 默认 `audit_only=True`
  - `features.audit_reason` 明确写出默认只审计
- 没有越界修改：
  - 只新增了 `candidate_extractor.py` 和 `test_candidate_extractor.py`
  - 没有改现有 normalizer，符合任务边界
- 结果统计不是拍脑袋：
  - 我用实现重新复跑了离线 artifacts，得到的样例级统计与 `result.json` 一致
  - MinerU full 5 样例总分布确实是 `74 = image 48 + table 8 + formula_candidate 18`
  - PaddleOCR-VL 当前也确实只有 4 个样例目录，统计为 `58 = image 48 + table 10`

## 非阻塞提示

当前测试已经足以覆盖本任务收口，但真实 artifacts 的断言还比较宽松，主要是检查 `>0` 和 `audit_only_count == formula_candidate_count`。如果后续这个模块进入 hybrid 主链路，建议再补几条固定样例的精确计数断言，避免上游 `pages.jsonl` 结构变化时回归被宽松测试放过去。

## 建议动作

建议 PM 直接推进到后续任务，例如候选过滤、归属匹配和 PageIR 合并；这轮不需要因为 reviewer 发现新的阻塞问题而返工。

审查时间：2026-05-15T18:34:25+08:00
