# 审查说明：建立公式专项实验开关与评测基线

## 结论

**审查通过（approve）。**

## 阻塞问题

本轮未发现阻塞验收的问题。

## 通过依据

1. 默认行为保持正确：
   `formula_candidate` 仍然只做 audit-only，不进入正文 merge；过滤结果也继续统一落在 `formula_candidate_rejected_audit_only`。

2. “实验开关存在但默认关闭”已经被代码和测试明确表达：
   - `CandidateExtractor(enable_formula_experiment=False)` / `CandidateFilter(enable_formula_experiment=False)` 显式暴露开关
   - 默认模式是 `disabled_audit_only`
   - 即使显式开启，当前也仍是 `shadow_collect_only`，不会打开 merge

3. Phase 4 公式专项基线产物已经可复用：
   - 固化了重点样例与重点页
   - 包含公式候选计数
   - 包含 audit-only 原因
   - 预留了 `latex` / `omml` / `image_path` 三个后续扩展字段

4. 测试证据完整：
   指定 pytest 命令通过，`test_candidate_extractor.py` 与 `test_candidate_filter.py` 共 10 个用例全部通过。

## 非阻塞观察

- 当前实验开关还停留在 extractor/filter 构造参数层，尚未接到 `HybridPipelineConfig` 或更上层运行时配置入口。这不影响本轮“显式开关 + 基线产物”验收，但后续若要真正开展公式 OCR / crop 实验，建议再补一个专门的配置接线任务。

## 总结

这次交付已经把公式专项的默认关闭策略、审计口径和复用基线收口清楚，可以作为 Phase 4 后续公式实验的起点继续推进。
