# 审查说明：对齐Hybrid默认候选与公式实验开关

## 结论

**驳回并请求补修（request_changes）。**

## 阻塞问题

这轮功能目标大体是完成的：

- `hybrid_experimental` 默认候选已经从常驻 `mineru_full + paddleocr_vl` 收口为 `mineru_full`
- `enable_formula_experiment` 已经从 YAML 顶层配置透传到了 `HybridPipelineConfig -> CandidateExtractor / CandidateFilter`
- `formula_candidate` 仍然保持 audit-only / shadow-only，不会进入 merge gate
- `pytest test_hybrid_backend_resolve.py test_hybrid_pipeline.py -q` 实测通过

但当前仍有一个阻塞问题：**本轮发生了越界修改。**

### 具体阻塞点

instruction 已经把任务边界写得很清楚：

- 只处理 `parser_client.py`
- `hybrid_pipeline.py`
- `inference_config.yaml`
- 以及对应测试

`task.json.write_scope` 也只放行了上述实现/配置文件和两份测试文件。

但本轮实际还修改了 [conversion_service.py](/Users/linsuchang/Desktop/work/chiralium/backend/app/services/pdf_to_word/conversion_service.py:316)，新增了：

- `hybrid_formula_experiment_enabled`
- `hybrid_formula_experiment_mode`

这些 service meta 字段。

问题不在于这两个字段本身是否合理，而在于：

- 它们不属于本轮 instruction 明确允许修改的文件范围
- 它们也不在 `task.json.write_scope` 内

在当前任务治理规则下，这类越界修改不能直接放行。

## 我复核到的真实状态

- 已成立的部分：
  - [parser_client.py](/Users/linsuchang/Desktop/work/chiralium/backend/app/services/pdf_to_word/parser_client.py:13) 的 `DEFAULT_HYBRID_CANDIDATE_PROFILES` 已收口为 `('mineru_full',)`
  - [inference_config.yaml](/Users/linsuchang/Desktop/work/chiralium/backend/app/services/pdf_to_word/parser_adapters/inference_config.yaml:7) 显式配置了 `enable_formula_experiment: false` 与 `candidate_profiles: [mineru_full]`
  - [hybrid_pipeline.py](/Users/linsuchang/Desktop/work/chiralium/backend/app/services/pdf_to_word/parser_adapters/hybrid_pipeline.py:164) 确实把 `enable_formula_experiment` 透传给了 `CandidateExtractor`
  - [hybrid_pipeline.py](/Users/linsuchang/Desktop/work/chiralium/backend/app/services/pdf_to_word/parser_adapters/hybrid_pipeline.py:167) 也透传给了 `CandidateFilter`
  - [candidate_filter.py](/Users/linsuchang/Desktop/work/chiralium/backend/app/services/pdf_to_word/parser_adapters/candidate_filter.py:185) 对 `formula_candidate` 仍直接拒绝 merge，并写入 `formula_merge_enabled: false`
  - 定向 pytest 实测 `9 passed`
- 未通过的部分：
  - [conversion_service.py](/Users/linsuchang/Desktop/work/chiralium/backend/app/services/pdf_to_word/conversion_service.py:316) 被一并改动，但它不在本轮授权范围内

## 建议修复

1. 如果 `conversion_service.py` 的 service meta 扩展不是本轮验收必需项，就把这部分改动从本任务里拿掉。
2. 如果你们确认这两个 meta 字段确实属于本轮能力收口的一部分，那应先让 PM 补 scope 或更新 `write_scope`，再重新提交。
3. 核心逻辑实现本身不需要推倒重来，返工重点只在“收回越界修改”或“补足授权范围”。

## 非阻塞部分

本轮关于默认候选和公式实验开关的核心实现方向是正确的，返工时建议保留：

- 默认候选收口为 `mineru_full`
- YAML 显式表达 `candidate_profiles`
- `enable_formula_experiment` 透传到 extractor/filter
- `formula_candidate` 继续 audit-only / shadow-only
