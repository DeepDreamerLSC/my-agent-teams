# 任务：打通DOCX渲染依赖并重跑四个正向样例真实视觉证据

## 任务类型
integration

## 目标
消除四个当前 positive_candidate（五下科学、数学八年级、数学试卷、英语八年级）在 canonical visual evidence 上的“renderer unavailable”阻塞，使 render_pair / visual_similarity 进入真实可评分状态，而不是继续停留在 docx_render_missing / artifact_not_ready。

## 任务边界
- 只处理四个既有 positive_candidate；不要改动语文正向样例任务的目录与 manifest。
- 不能用伪造 ready 状态掩盖真实质量问题；如果真实渲染后仍然 no_go，必须保留 no_go。
- 优先解决 DOCX→可渲染页面 的运行依赖问题；可通过接通受支持的本机转换器、补足稳定 fallback，或修复渲染链路实现达成。
- 若必须引入新的本机运行前提，必须在 result.json 中写清依赖、路径与复现命令。

## 输入事实
- /Users/linsuchang/Desktop/work/my-agent-teams/tasks/复验正向样例视觉证据链与FinalArchive门禁/result.json
- /Users/linsuchang/Desktop/work/my-agent-teams/tasks/补齐四个正向样例视觉证据链并接入FinalArchive/result.json
- /Users/linsuchang/Desktop/work/my-agent-teams/tasks/实现PDF与DOCX渲染对生成器/result.json
- /Users/linsuchang/Desktop/work/my-agent-teams/tasks/升级visual_similarity为真实渲染对视觉证据/result.json
- /Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-archive/reports/PDF转Word当前阶段与目标差距及优化计划.md

## 约束
- write_scope 仅限 task.json 声明范围。
- read_only: false
- 上游基线任务：补齐四个正向样例视觉证据链并接入FinalArchive（已完成）
- target_environment: dev
- execution_mode: dev
- owner_approval_required: false

## 交付物
1. 四个样例目录下更新后的 render_pair.json / visual_similarity.json / human_review_report.json / source_manifest.json（如需）。
2. 若涉及代码修复，提交对应补丁与测试/验证记录。
3. result.json 中逐样例列出 before/after：render_pair_status、visual_similarity_status、artifact_ready_for_scoring、sample_verdict。

## 验收标准
1. 四个样例的 render_pair.json 不再是 `docx_render_missing`。
2. 四个样例的 visual_similarity.json 不再因为 renderer unavailable 而保持 `artifact_not_ready`。
3. 即使真实渲染后仍为 no_go，也必须给出真实证据链结论，而不是缺证据结论。
4. 明确写出当前渲染方案依赖的本机路径/命令，保证 QA 可复验。

## 下游动作
完成后解锁“复验四个正向样例真实视觉证据重跑结果”。
