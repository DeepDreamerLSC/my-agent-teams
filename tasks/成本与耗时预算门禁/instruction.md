# 任务：成本与耗时预算门禁

## 任务类型
开发 / P1 成本预算门禁

## 目标
给 render pair、visual similarity、慢模型复核建立成本/耗时可观测门禁，明确何时继续自动化、何时降级为人工复核。

## 任务边界
- 本任务建立预算与降级规则，不直接提高视觉分。
- 必须覆盖全学科样例，而不是只看单一 science 页。
- 报告与代码都要可审计。

## 输入事实
- 架构整改意见（全学科）：`/Users/linsuchang/Desktop/work/my-agent-teams/.runtime/worktrees/chiralium/PDF-Word-205980b6/artifacts/pdf2word/final-archive/reports/PDF转Word视觉门禁全学科整改意见.md`
- 架构整改任务结果：`/Users/linsuchang/Desktop/work/my-agent-teams/tasks/制定PDF转Word视觉门禁整改意见/result.json`
- 当前高优先级问题说明：`/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-archive/reports/PDF转Word-五下科学样例复核与95门禁偏差说明.md`
- 代表样例：原 PDF `/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-output-samples/PDF转Word门禁样例-五下科学-source.pdf`；门禁 DOCX `/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-output-samples/PDF转Word门禁样例-五下科学-hybrid_experimental-output.docx`
- 当前统一前提：**不能只盯科学学科，必须把科学、数学、语文、英语统一纳入门禁与样例口径。**
- 当前已知边界：可以保留 `quality/hybrid_async` 工程门禁通过；不可继续宣称“全学科人工视觉 95% 已达成”。
- 本任务前置依赖：慢模型复核灰度接入低置信视觉页

## 写入范围
仅允许修改以下路径：
  - `/Users/linsuchang/Desktop/work/chiralium/backend/app/services/pdf_to_word/visual_gate_budget.py`
  - `/Users/linsuchang/Desktop/work/chiralium/backend/tests/test_pdf_to_word_visual_gate_budget.py`
  - `/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-archive/reports/PDF转Word视觉门禁成本预算报告.md`

## 约束
- 必须输出每样本 render/slow-model 耗时与预算阈值。
- 超预算时要有明确降级策略。
- 不能因为预算不足而伪造通过。

## 交付物
1. 预算门禁代码与测试。
2. 成本预算报告。
3. 降级策略说明。

## 验收标准
- 能说明每一类样例的大致成本边界。
- 超预算会触发明确降级或人工复核建议。
- 不会影响工程门禁与人工视觉门禁的定义边界。

## 下游动作
完成后，PM 才能决定是否把慢模型灰度扩到更大样本。
