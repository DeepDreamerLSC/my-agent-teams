# 任务：英语阅读段落与选项区视觉门禁

## 任务类型
开发 / P1 英语专项

## 目标
针对英语阅读块、选项缩进、题干与选项距离建立专项视觉门禁，避免文本完整但观感线性化仍被误判为高还原。

## 任务边界
- 本任务只做英语专项关键区域，不改变总体门禁定义。
- 要兼容 fallback 页场景。
- 与公共 visual_similarity/veto 对接。

## 输入事实
- 架构整改意见（全学科）：`/Users/linsuchang/Desktop/work/my-agent-teams/.runtime/worktrees/chiralium/PDF-Word-205980b6/artifacts/pdf2word/final-archive/reports/PDF转Word视觉门禁全学科整改意见.md`
- 架构整改任务结果：`/Users/linsuchang/Desktop/work/my-agent-teams/tasks/制定PDF转Word视觉门禁整改意见/result.json`
- 当前高优先级问题说明：`/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-archive/reports/PDF转Word-五下科学样例复核与95门禁偏差说明.md`
- 代表样例：原 PDF `/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-output-samples/PDF转Word门禁样例-五下科学-source.pdf`；门禁 DOCX `/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-output-samples/PDF转Word门禁样例-五下科学-hybrid_experimental-output.docx`
- 当前统一前提：**不能只盯科学学科，必须把科学、数学、语文、英语统一纳入门禁与样例口径。**
- 当前已知边界：可以保留 `quality/hybrid_async` 工程门禁通过；不可继续宣称“全学科人工视觉 95% 已达成”。
- 本任务前置依赖：升级visual_similarity为真实渲染对视觉证据、建立全学科人工视觉复核Rubric与基线报告

## 写入范围
仅允许修改以下路径：
  - `/Users/linsuchang/Desktop/work/chiralium/backend/app/services/pdf_to_word/english_visual_gate.py`
  - `/Users/linsuchang/Desktop/work/chiralium/backend/tests/test_pdf_to_word_english_visual_gate.py`
  - `/Users/linsuchang/Desktop/work/chiralium/backend/tests/fixtures/pdf_to_word/visual_similarity/english`

## 约束
- 阅读段落换行、选项缩进、题干-选项距离必须可评分。
- 关键页 fallback 严重偏差应可进入 veto。
- 不能只以 OCR 文本完整性替代视觉分。

## 交付物
1. english 专项视觉 gate。
2. fixture 与测试。
3. 专项说明。

## 验收标准
- 英语阅读/选项区可产生专项分数或失败原因。
- 文本完整但版面明显崩坏时不会误过。
- 结果可被最终 reporter 消费。

## 下游动作
完成后，英语样例将纳入全学科最终人工视觉复验。
