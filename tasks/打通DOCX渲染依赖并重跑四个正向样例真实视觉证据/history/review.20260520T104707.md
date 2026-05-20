# 审查结论：request_changes

- 任务：打通DOCX渲染依赖并重跑四个正向样例真实视觉证据
- 审查人：review-1
- 审查时间：2026-05-20T10:45:42+08:00

## 先说结论
本轮**不建议直接收口**。

技术主目标其实已经基本达成：四个正向样例都从 `docx_render_missing / artifact_not_ready` 进入了真实 evidence 链路，当前事实是：
- `render_pair.json.status = success`
- `visual_similarity.json.status = scored_no_go`
- `artifact_ready_for_scoring = true`
- `human_review_report.sample_verdict = no_go`

也就是说，这轮**确实消除了 renderer unavailable 阻塞**，同时**没有伪造 GO**。

但 final-archive 里的 provenance 还没收干净，导致我现在不能 approve。

## 阻塞项

### 1. 四份 source_manifest 仍写着旧事实：`render_pair remains docx_render_missing`
我复核了四个样例目录，实际 `render_pair.json.status` 已全部是 `success`；但四份 `source_manifest.json.notes[-1]` 仍然写：

> These artifacts do not restore human visual 95 on their own because the render_pair remains docx_render_missing in the current environment.

这和本任务要达成的核心目标正面冲突。现在真实情况应该表述为：
- render_pair / visual_similarity 已 materialize 且可评分；
- 仍然 no_go 的原因是相似度阈值 / P0 veto，不是 `docx_render_missing`。

这类过时说明会误导下游 QA/PM，对 final-archive provenance 来说属于阻塞。

### 2. source_manifest 的 reproduce_command 仍指向 `/private/tmp/...`
四份 `source_manifest.json.docx_render_dependency.reproduce_command` 仍然是：

`PYTHONPATH=backend /Users/linsuchang/Desktop/work/chiralium/backend/.venv/bin/python /private/tmp/rerun_docx_visual_evidence.py`

但 `result.json.renderer_dependency.reproduce_command` 已经指向 task 目录里的稳定脚本 artifact。现在 archive 内留下的却是 `/private/tmp` 临时路径，这不够稳，也不利于 QA 长期复现。

建议把：
- 生成脚本中的硬编码路径
- 四份 source_manifest 中的 `reproduce_command`
- result.json 中的复现口径

统一到同一个**稳定、可追踪**的位置。

## 非阻塞但建议顺手修
- `result.json.status` 当前写的是 `success`，按 AGENTS 约束应改成 `done`。

## 建议的最小返修口径
1. 重写四份 `source_manifest.json` 的过时 note；
2. 把四份 `source_manifest.json` 的 `reproduce_command` 改为稳定 task artifact 路径，并同步修脚本硬编码；
3. 顺手把 `result.json.status` 规范成 `done`。

以上修完后，我倾向于可快速复审；代码主链路本身目前看没有新的阻塞。
