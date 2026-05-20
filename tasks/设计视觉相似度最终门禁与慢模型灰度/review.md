# 审查说明：设计视觉相似度最终门禁与慢模型灰度

## 结论

**审查通过（approve）。**

> 说明：本任务 `review_authority=owner`，本次为 reviewer 审查通过意见，可提交 PM / owner 做最终收口裁决。

## 本轮重点复核点

按 PM/owner 的返修要求，我本轮只重点核两件事：

1. `required_artifacts` 是否已统一为 `visual_similarity.json`
2. active `candidate_models` 是否只保留 `qwen3_vl_8b`，并把 `glm_46v_flash` 移到非激活字段

结论：这两点都已修正到位。

## 通过依据

### 1. required artifact 已对齐路线文档 canonical name

当前 contract 里：

- `required_artifacts` 已包含 `visual_similarity.json`
- `visual_similarity_report.json` 已不再是 required
- `visual_similarity_report.json` / `visual_similarity_debug.json` 被明确放到 optional/debug 位置

这与 2026-05-18 路线文档中 Final Fidelity Gate 的输出约定一致，也避免了后续 quality/hybrid_async artifact 链路出现命名分叉。

### 2. active slow-model candidate 已收敛

当前 fixture / gate 校验里：

- `candidate_models == [qwen3_vl_8b]`
- `glm_46v_flash` 不再是 active gray candidate
- `glm_46v_flash` 仅保留在：
  - `blocked_candidates`
  - `comparison_only_models`

这与上游路线中“Qwen 可做 review worker、GLM 仍是 blocked/对照项”的现状一致，不再夸大当前路线能力。

### 3. 主边界未被回退或污染

返修后仍保持：

- 默认同步不触发 render diff / 慢模型
- `quality/hybrid_async` 才让视觉相似度进入 95% 总分
- 当前实现仍明确是 contract/stub，不伪装成真实 renderer 或慢模型已接入

## 补充验证

我额外复跑了：

```bash
cd /Users/linsuchang/Desktop/work/my-agent-teams/.runtime/worktrees/chiralium/task-11eaf3b2 && \
PYTHONPYCACHEPREFIX=/private/tmp/visual-gate-rereview-pyc python3 -m py_compile \
  backend/app/services/pdf_to_word/visual_similarity_gate.py \
  backend/tests/test_pdf_to_word_visual_similarity_gate.py
```

以及：

```bash
cd /Users/linsuchang/Desktop/work/my-agent-teams/.runtime/worktrees/chiralium/task-11eaf3b2 && \
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/visual-gate-rereview-pyc \
PYTHONPATH=backend /Users/linsuchang/Desktop/work/chiralium/backend/.venv/bin/python -m pytest \
  backend/tests/test_pdf_to_word_visual_similarity_gate.py -q \
  -o cache_dir=/private/tmp/chiralium-pytest-cache-visual-gate-rereview \
  --basetemp=/private/tmp/chiralium-pytest-temp-visual-gate-rereview
```

结果：`7 passed, 4 warnings`

warnings 为既有 FastAPI `on_event` deprecation warnings，不构成阻塞。

## 非阻塞备注

- 本轮任务目录仍无 `verify.json`。不过本任务属于 owner 裁决型设计冻结，当前 `result.json`、静态契约复核和补充复跑测试已经足以支撑 review 通过。

## 总结

上一轮 review 提出的两项阻塞问题都已被正面修复：

- **artifact canonical name 已对齐为 `visual_similarity.json`**
- **active slow-model candidate 已收敛为仅 `qwen3_vl_8b`，GLM 已降为非激活字段**

因此这次我给出 **approve**，可以进入 PM / owner 收口流程。
