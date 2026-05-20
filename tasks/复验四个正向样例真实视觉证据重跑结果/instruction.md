# 任务：复验四个正向样例真实视觉证据重跑结果

## 任务类型
verification

## 目标
复验四个既有 positive_candidate（五下科学、数学八年级、数学试卷、英语八年级）的真实视觉证据重跑结果，确认此前“renderer unavailable”阻塞是否已解除，并给出可供全学科人工视觉95阶段结论使用的明确输入。

## 任务边界
- 只做只读复验，不改业务代码。
- 若 render_pair 仍缺失、visual_similarity 仍为 artifact_not_ready（且原因仍是证据链未就绪），则继续判 blocked。
- 若证据链已就绪但样例仍 no_go，应输出 done + no_go 结论，而不是 blocked。

## 输入事实
- /Users/linsuchang/Desktop/work/my-agent-teams/tasks/复验正向样例视觉证据链与FinalArchive门禁/result.json
- /Users/linsuchang/Desktop/work/my-agent-teams/tasks/打通DOCX渲染依赖并重跑四个正向样例真实视觉证据/result.json
- /Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-archive/profiles/hybrid_experimental

## 约束
- write_scope: []
- read_only: true
- target_environment: dev
- execution_mode: dev
- owner_approval_required: false

## 交付物
1. result.json 中逐样例写清：render_pair_status、visual_similarity_status、artifact_ready_for_scoring、fidelity_veto_status、sample_verdict。
2. 明确说明“阻塞是否解除”和“是否允许进入全学科人工视觉95阶段结论重跑”。

## 验收标准
1. 若四个样例已具备真实可评分证据链，则任务应输出 done，不因 no_go 结论误判为 blocked。
2. 若任何样例仍因证据链未就绪无法判断，则必须继续 blocked，并写清具体样例与原因。
3. 输出结论必须可直接供“重跑全学科人工视觉95并更新阶段结论”消费。

## 下游动作
完成后作为“重跑全学科人工视觉95并更新阶段结论”的前置输入。
