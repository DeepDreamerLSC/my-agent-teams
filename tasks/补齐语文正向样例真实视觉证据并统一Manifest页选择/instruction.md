# 任务：补齐语文正向样例真实视觉证据并统一Manifest页选择

## 任务类型
development

## 目标
把语文正向样例从 staged seed 推进到真实 visual evidence ready：统一三份 manifest 的 `selected_pages_or_crops`，并为 `语文正向样例` 真正落下可评分的 `render_pair / visual_similarity / fidelity_veto / human_review_report`，使其后续可被 QA 重新判定是否进入全学科95重跑分母。

## 任务边界
- 保持 `chinese_grade5` 严格为 `negative_guard`，不得误计入正向分母。
- 不得通过伪造 ready 状态跳过真实 evidence 生成；若真实 evidence 生成后仍 no_go，必须保留 no_go。
- 当前任务只补语文正向样例，不改动四个既有 positive_candidate 的事实状态。

## 输入事实
- /Users/linsuchang/Desktop/work/my-agent-teams/tasks/复验语文正向样例进入全学科95分母/result.json
- /Users/linsuchang/Desktop/work/my-agent-teams/tasks/实现语文正向长文作文样例与统一Manifest/result.json
- /Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-output-samples/unified-sample-manifest.json
- /Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-output-samples/final-gated-manifest.json
- /Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-output-samples/chinese-samples-manifest.json
- /Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-archive/profiles/hybrid_experimental/语文正向样例

## 约束
- write_scope: ['/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-output-samples', '/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-archive/profiles/hybrid_experimental/语文正向样例', '/Users/linsuchang/Desktop/work/chiralium/backend/tests/fixtures/pdf_to_word/chinese_positive']
- read_only: false
- 依赖上游任务: ['升级FinalAcceptance为HumanVisual强依赖门禁']
- target_environment: dev
- execution_mode: dev
- owner_approval_required: false

## 交付物
1. 统一后的 three-manifest 语文样例页选择字段（`selected_pages_or_crops` 等）。
2. `语文正向样例` 目录下真实生成的 `render_pair.json / visual_similarity.json / fidelity_veto.json / human_review_report.json / source_manifest.json`。
3. result.json 中明确写清：当前语文正向样例是否已从 `staged_seed` 进入 `real_scoring_ready`，以及若仍 no_go 的具体原因。

## 验收标准
1. `unified-sample-manifest.json`、`final-gated-manifest.json`、`chinese-samples-manifest.json` 对语文正向样例的 `selected_pages_or_crops` 一致。
2. `语文正向样例` 不再停留在 `render_pair=staged_positive_candidate_pending_generation` / `visual_similarity=artifact_missing`。
3. `chinese_grade5` 仍严格保持 `negative_guard`。
4. 后续 QA 可以据此重新判断语文正向样例是否能进入全学科95重跑分母。

## 下游动作
完成后恢复“复验语文正向样例进入全学科95分母”。
