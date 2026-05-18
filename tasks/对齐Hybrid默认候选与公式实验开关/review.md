# 审查说明：对齐Hybrid默认候选与公式实验开关

## 结论

**通过（approve）。**

## 通过依据

- [parser_client.py](/Users/linsuchang/Desktop/work/chiralium/backend/app/services/pdf_to_word/parser_client.py:13) 已将 `DEFAULT_HYBRID_CANDIDATE_PROFILES` 收口为 `('mineru_full',)`；[parser_client.py](/Users/linsuchang/Desktop/work/chiralium/backend/app/services/pdf_to_word/parser_client.py:214) 的候选归一化逻辑也会在未显式配置时回落到该单候选默认值。
- [inference_config.yaml](/Users/linsuchang/Desktop/work/chiralium/backend/app/services/pdf_to_word/parser_adapters/inference_config.yaml:8) 与 [inference_config.yaml](/Users/linsuchang/Desktop/work/chiralium/backend/app/services/pdf_to_word/parser_adapters/inference_config.yaml:14) 已显式声明 `enable_formula_experiment: false` 和 `candidate_profiles: [mineru_full]`，不再把 `paddleocr_vl` 作为默认常驻候选。
- [hybrid_pipeline.py](/Users/linsuchang/Desktop/work/chiralium/backend/app/services/pdf_to_word/parser_adapters/hybrid_pipeline.py:164) 与 [hybrid_pipeline.py](/Users/linsuchang/Desktop/work/chiralium/backend/app/services/pdf_to_word/parser_adapters/hybrid_pipeline.py:167) 已将 `enable_formula_experiment` 透传到 `CandidateExtractor` / `CandidateFilter`；[test_hybrid_pipeline.py](/Users/linsuchang/Desktop/work/chiralium/backend/tests/test_hybrid_pipeline.py:410) 也直接断言这条接线为 `True -> True`。
- [candidate_filter.py](/Users/linsuchang/Desktop/work/chiralium/backend/app/services/pdf_to_word/parser_adapters/candidate_filter.py:185) 仍把 `formula_candidate` 作为 audit-only 直接拒绝，并写入 `formula_merge_enabled: false`，因此公式实验仍停留在 shadow/audit 观察面，不进入 merge。
- [conversion_service.py](/Users/linsuchang/Desktop/work/chiralium/backend/app/services/pdf_to_word/conversion_service.py:316) 当前只保留 `hybrid_candidate_profiles`、增强页数、候选数等服务层摘要字段，已不再导出 `hybrid_formula_experiment_enabled` / `hybrid_formula_experiment_mode`；[test_hybrid_backend_resolve.py](/Users/linsuchang/Desktop/work/chiralium/backend/tests/test_hybrid_backend_resolve.py:215) 到 [test_hybrid_backend_resolve.py](/Users/linsuchang/Desktop/work/chiralium/backend/tests/test_hybrid_backend_resolve.py:216) 对此有直接断言，而 [test_hybrid_backend_resolve.py](/Users/linsuchang/Desktop/work/chiralium/backend/tests/test_hybrid_backend_resolve.py:242) 到 [test_hybrid_backend_resolve.py](/Users/linsuchang/Desktop/work/chiralium/backend/tests/test_hybrid_backend_resolve.py:244) 也保留了 raw parser response 中的 formula experiment 可观测性。
- 我补跑了任务验收要求的 pytest：`PYTHONDONTWRITEBYTECODE=1 /Users/linsuchang/Desktop/work/chiralium/backend/.venv/bin/pytest /Users/linsuchang/Desktop/work/chiralium/backend/tests/test_hybrid_backend_resolve.py /Users/linsuchang/Desktop/work/chiralium/backend/tests/test_hybrid_pipeline.py`，结果为 `9 passed, 4 warnings`。

## 说明

本轮此前的阻塞点是 `conversion_service.py` 越界修改。现在 `instruction.md` 的 PM 返工补充已明确把该文件最小化纳入 write_scope，且限定用途为回收本任务自己引入的 formula service meta 改动。结合当前实现与测试，越界问题已被清理，不再构成阻塞。

非阻塞提醒：formula experiment 的状态现在应以 raw parser response `response.meta.hybrid_pipeline` 为准；service meta 只作为服务层摘要，不应再承载 formula shadow lane 细节。
