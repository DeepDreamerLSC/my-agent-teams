# 审查说明：实现HybridMVP图片表格并回链路

## 结论

**审查通过（approve）。**

这轮可以通过。生产 `HybridExperimentalPipeline` 已经不再停留在 baseline passthrough stub，而是实际串起了 question region 检测、候选抽取/过滤、PageIR 合并和 validator 回退链路。

## 通过依据

- 我复跑了 `tests/test_hybrid_e2e.py`，结果是 `3 passed, 4 warnings`。warnings 仍是 FastAPI `on_event` 既有弃用告警，不是本任务新增问题。
- `result.json` 与 `/private/tmp/hybrid-e2e-validation-dev1-round3/report.json` 一致表明：`数学试卷` 接受了 21 个 image/table 候选且 `fallback_pages=0`，`英语八年级` 接受了 2 个候选且 `fallback_pages=0`。
- `语文五年级` 仍然按预期跳过增强：`resolvable_page_count=0`、`enhancement_pages=[]`、`candidate_count=0`。这满足任务要求的“题号区域不可判定时整份样例不做增强”。
- 静态审阅 `hybrid_pipeline.py` 和 `hybrid_validator.py` 后，确认 baseline 文本块仍由 validator 保护，异常页仍是整页回退，不存在“增强把 baseline 前缀替换掉”的新风险。

## 非阻塞观察

- `fallback_pages` / `document_fallback` 目前混入了 baseline 自身 bbox 越界导致的 fallback 信号。`语文五年级` 明明没有增强页，报告却仍显示 `fallback_pages=13`、`document_fallback=true`，所以这两个指标暂时不能直接解释为“增强失败率”。
- `_prepare_baseline_result()` 只要存在任一增强页，就会对整份 baseline 做 geometry normalization。结果是某些不在 `enhancement_pages` 的页面也会和原始 baseline 有 diff；例如 `数学八年级` 的 page 5 没有接受候选，但 `final_equals_baseline=false`。

## 总结

这条任务的主目标已经达到：真实生产链路已接通，关键样例能插入 image/table，题号不可判定样例会跳过增强，测试复跑也通过。因此本轮给 `approve`，后续把指标语义和审计 diff 再收紧即可。
