# 审查说明：设计视觉相似度最终门禁与慢模型灰度

## 结论

**审查意见：当前不建议直接收口，建议返修后再由 PM / owner 裁决。**

> 说明：本任务 `review_authority=owner`，以下是 reviewer 的具体审查意见，不代替 owner 最终裁决。

## 已确认通过项

1. 这轮交付的基础 stub / fixture / 测试是能跑通的。
2. 我补充复跑了：

```bash
cd /Users/linsuchang/Desktop/work/my-agent-teams/.runtime/worktrees/chiralium/task-11eaf3b2 && \
PYTHONPYCACHEPREFIX=/private/tmp/visual-gate-review-pyc python3 -m py_compile \
  backend/app/services/pdf_to_word/visual_similarity_gate.py \
  backend/tests/test_pdf_to_word_visual_similarity_gate.py

cd /Users/linsuchang/Desktop/work/my-agent-teams/.runtime/worktrees/chiralium/task-11eaf3b2 && \
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/visual-gate-review-pyc \
PYTHONPATH=backend /Users/linsuchang/Desktop/work/chiralium/backend/.venv/bin/python -m pytest \
  backend/tests/test_pdf_to_word_visual_similarity_gate.py -q \
  -o cache_dir=/private/tmp/chiralium-pytest-cache-visual-gate-review \
  --basetemp=/private/tmp/chiralium-pytest-temp-visual-gate-review
```

结果：`7 passed, 4 warnings`

warnings 为既有 FastAPI `on_event` deprecation warnings，不是本轮阻塞点。

3. 模式边界的主方向是对的：
   - 默认同步不触发 render diff / 慢模型；
   - `quality/hybrid_async` 才把视觉相似度纳入 95% 总分；
   - 当前实现明确是 contract/stub，不伪装成已接入真实渲染或慢模型调用。

## 阻塞问题

### 1. artifact 契约文件名与 2026-05-18 路线文档不一致

路线文档 `Final Fidelity Gate` 的输出列表写得很明确：

- `fidelity_metrics.json`
- `fidelity_report.md`
- `docx_inspect.json`
- `visual_similarity.json（Phase 3）`

但当前 visual similarity gate contract 冻结的 required artifact 是：

- `visual_similarity_report.json`

对应位置：

- `visual_similarity_gate.py:35-40`
- `visual_similarity_contract.json:34-40`
- `test_pdf_to_word_visual_similarity_gate.py:41`

这不是小的命名偏好问题，而是**设计契约本身出现分叉**：

- 如果现在把 `visual_similarity_report.json` 冻结进 contract，
- 后续真正接入 `quality/hybrid_async` artifact 链路时，
- 就会和已经批准的路线文档产生两个名字。

对于“设计/契约冻结”任务，这属于阻塞问题。

**建议：**
把 canonical required artifact 对齐为路线文档中的 `visual_similarity.json`。如果确实还想保留更长的 debug/report 文件名，可以额外加 optional artifact，但不要把不同名字冻结成 required contract。

### 2. 慢模型灰度候选夸大了当前现状，把 `glm_46v_flash` 冻结成 active candidate

当前 fixture / 测试把 slow model candidate 冻结成：

- `qwen3_vl_8b`
- `glm_46v_flash`

对应位置：

- `visual_similarity_contract.json:19-23`
- `test_pdf_to_word_visual_similarity_gate.py:42`

但上游现状并不是这样：

- `后续技术路线.md:199-208`
  - `qwen3_vl_8b`：review worker
  - `glm_46v_flash`：暂缓，当前 blocked
- `hybrid管线设计.md:52-54,474-475`
  - `qwen3_vl_8b`：只能做 review worker
  - `GLM-4.6V-Flash`：仅后续对照，不进入正式路线

也就是说，当前被真正认可的 slow-model gray 候选是 **Qwen review worker**；GLM 还没有被路线批准为正式 gray candidate。

本任务验收标准明确要求：

- 与 2026-05-18 路线文档一致
- **不夸大现状**

因此把 `glm_46v_flash` 冻结成 active candidate model，会误导后续实现把一个仍处于 blocked/暂缓状态的模型接入正式 gray contract，这也是阻塞问题。

**建议：**
- active `candidate_models` 只保留当前路线已认可的模型（如 `qwen3_vl_8b`）；
- 如果想保留 GLM 信息，可单独放到 `future_review_candidates` / `blocked_candidates` / `comparison_only_models` 这类非激活字段；
- 同步调整测试，不要再把 GLM 冻结成当前 contract 必选项。

## 非阻塞备注

- 当前任务目录没有 `verify.json`，但这是 owner 裁决型设计任务，我已经补做本地复跑，因此不构成本轮主要阻塞点。后续返修回提时如果能补一份 verify，会更利于留痕。

## 总结

这轮交付把视觉相似度 gate 的基本骨架和模式边界搭出来了，方向总体正确；但**既然本任务的目标是冻结“最终门禁与慢模型灰度”的 contract，就必须保证 artifact 名称和 active candidate 范围与既有路线完全一致**。当前在这两点上仍有偏差，因此我建议返修后再交给 PM / owner 做最终裁决。
