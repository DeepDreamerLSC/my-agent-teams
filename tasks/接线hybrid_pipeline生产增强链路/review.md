# 审查说明：接线hybrid_pipeline生产增强链路

## 结论

**通过（approved）。**

第二轮补修已经修掉上轮驳回的主问题：`_extract_candidates()` 现在会先做 profile alias 规范化，再调用 adapter factory，因此仓库里既有的 `candidate_profiles=('mineru_full', 'paddleocr_vl')` 不会再因为真实推理配置里只有 `mineru` 而直接 `KeyError`。

我复跑了：

```bash
pytest tests/test_hybrid_pipeline.py tests/test_hybrid_validator.py -q
pytest tests/test_hybrid_e2e.py -q
```

结果分别是：

- `6 passed, 4 warnings`
- `3 passed, 4 warnings`

## 本轮确认点

我额外做了一个最小复现，给 `HybridExperimentalPipeline` 注入 recording `adapter_factory`，并用：

```python
candidate_profiles=('mineru_full', 'paddleocr_vl')
```

去调用真实 `_extract_candidates()`。

实际收到的 adapter profile 序列是：

```text
['mineru', 'paddleocr_vl']
```

这说明：

- `mineru_full -> mineru` 的规范化已经在真实生产接线路径上生效
- 同时候选创建时仍保留原始 `source_profile` 命名，没有破坏既有 candidate/filter/merge 元数据约定

## 非阻塞说明

当前 alias 表只覆盖了本轮需要的：

- `mineru_full -> mineru`
- `mineru`
- `paddleocr_vl`

如果后续再引入 `mineru_lite` 或其他历史别名，还需要继续补映射。但这不影响本轮验收。

## 说明

这次通过的原因很明确：上轮阻塞点已经被真实修复，不只是测试规避。现在 `hybrid_pipeline.py` 至少能够按当前既有 profile 命名约定进入真实候选抽取链路，不会在 adapter 创建阶段直接报错。

审查时间：2026-05-16T00:05:41+08:00
