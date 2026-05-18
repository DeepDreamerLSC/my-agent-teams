# 审查说明：集成Qwen3-VL-review到hybrid管线

## 结论

**驳回并请求补修（request_changes）。**

这轮比上一轮前进了一步：`ReviewIntegrator` 已经真正接到 `HybridExperimentalPipeline._review_ambiguous()` 里了，不再是“helper 写好了但主流程完全没接线”的状态。`filtered_candidates`、`merge_decisions`、`review_metrics`、`review_warnings` 也都会回写到 `last_run`。

我复跑了：

```bash
cd /Users/linsuchang/Desktop/work/chiralium/backend && TMPDIR=/private/tmp PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/chiralium-pyc PYTEST_ADDOPTS='-p no:cacheprovider' .venv/bin/python -m pytest tests/test_hybrid_pipeline.py tests/test_review_integrator.py -q
```

结果是 `7 passed, 4 warnings`。

## 阻塞点

阻塞点仍然是任务级的，而且这次更具体：

**默认真实 `qwen3_vl_8b` review 路径没有真正跑起来。**

当前 pipeline 在调用 review 时只传了：

- `review_worker`
- `pdf_path`
- `source_name`

但没有传：

- `rendered_pages`
- 或逐页的 `rendered_page`

而默认 `review_profile=qwen3_vl_8b` 对应的是 `VLMReviewAdapter`。这个 adapter 没有自定义 `review_page()`，所以会走 `ReviewIntegrator._review_page()` 里的 `backend + normalizer` 分支。该分支明确要求：

- `rendered_page` 存在
- 且其中有 `image_path`

否则就直接跳过整页 review。

## 最小复现结果

我做了一个最小复现：在 `enable_enhancement=True` 的 `HybridExperimentalPipeline` 中传入一个 adapter-backed fake `qwen3_vl_8b` worker，再对一个 ambiguous candidate 调用 `_review_ambiguous()`。

返回结果是：

- `reviewed_candidate_count = 0`
- `review_skipped_count = 1`
- `json_valid_rate = 0.0`
- warning 为：

```text
Qwen3-VL review 缺少 rendered_page，已跳过 page=1。
```

同时 candidate 仍然保持：

- `decision = ambiguous`
- `reason = assignment_ambiguous_requires_review`

这说明当前默认真实集成路径下：

- ambiguous candidate 并没有真正触发页面 review
- review 结果也没有实际影响 accept / reject / reassign 决策

也就是 instruction 里的验收标准 1 和 2 还没有满足。

## 建议修复

建议按下面两点补齐：

1. 在进入 `_review_ambiguous()` 前准备并传入 review 需要的渲染产物，至少要让每个 page 有可用的 `rendered_page.image_path`、`render_dpi`、页面尺寸等信息。
2. 增加一条 pipeline 级测试，证明默认 `qwen3_vl_8b` 路径下，ambiguous candidate 会真正触发 review，并把结果反映到最终 candidate decision / merge decision。

## 说明

这次驳回的原因不是 helper 逻辑本身有明显错误，而是“接上了 hook”还不等于“默认真实链路可用”。当前交付已经具备接线框架，但距离任务标题要求的“集成到 hybrid 管线并实际生效”还差最后一段关键输入。

审查时间：2026-05-15T20:17:01+08:00
