# 任务：升级visual_similarity为真实渲染对视觉证据

## 任务类型
开发 / P0 真实视觉证据

## 目标
把 visual_similarity.json 从“结构化事实已接通”升级为“真实 render pair 可追溯视觉证据”，为人工视觉 95 判定提供页级/区域级依据。

## 任务边界
- 本任务建立真实视觉 artifact，不直接改 final report 最终 no-go 逻辑。
- 保留 canonical artifact 名称 visual_similarity.json，不另起最终文件名。
- 必须覆盖全学科共性字段，不得做成单学科特例。

## 输入事实
- 架构整改意见（全学科）：`/Users/linsuchang/Desktop/work/my-agent-teams/.runtime/worktrees/chiralium/PDF-Word-205980b6/artifacts/pdf2word/final-archive/reports/PDF转Word视觉门禁全学科整改意见.md`
- 架构整改任务结果：`/Users/linsuchang/Desktop/work/my-agent-teams/tasks/制定PDF转Word视觉门禁整改意见/result.json`
- 当前高优先级问题说明：`/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-archive/reports/PDF转Word-五下科学样例复核与95门禁偏差说明.md`
- 代表样例：原 PDF `/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-output-samples/PDF转Word门禁样例-五下科学-source.pdf`；门禁 DOCX `/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-output-samples/PDF转Word门禁样例-五下科学-hybrid_experimental-output.docx`
- 当前统一前提：**不能只盯科学学科，必须把科学、数学、语文、英语统一纳入门禁与样例口径。**
- 当前已知边界：可以保留 `quality/hybrid_async` 工程门禁通过；不可继续宣称“全学科人工视觉 95% 已达成”。
- 本任务前置依赖：实现PDF与DOCX渲染对生成器

## 写入范围
仅允许修改以下路径：
  - `/Users/linsuchang/Desktop/work/chiralium/backend/app/services/pdf_to_word/visual_similarity_gate.py`
  - `/Users/linsuchang/Desktop/work/chiralium/backend/tests/test_pdf_to_word_visual_similarity_gate.py`
  - `/Users/linsuchang/Desktop/work/chiralium/backend/tests/fixtures/pdf_to_word/visual_similarity`

## 约束
- artifact 至少包含 render_pairs、page_scores、key_regions、vetoes、subject_page_type、human_review_required、evidence_paths。
- contract-only 或缺真实 render pair 的 artifact 不可继续计入人工视觉分。
- 字段命名必须稳定，供 C-05/C-07/S-01/S-02/S-03 继续消费。

## 交付物
1. 升级后的 visual_similarity gate 实现。
2. 对应测试与 fixture。
3. result.json 中写清楚后续 reporter / QA 的消费方式。

## 验收标准
- visual_similarity.json 可追溯到真实 render pair。
- 页级、区域级、veto 相关字段齐全。
- contract-only 路径不会再被误算为人工视觉通过。

## 下游动作
完成后，dev-1 与 qa-1 将基于新 artifact 接入 reporter veto 与全学科人工视觉复验。
