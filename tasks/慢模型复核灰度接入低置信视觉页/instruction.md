# 任务：慢模型复核灰度接入低置信视觉页

## 任务类型
开发 / P1 慢模型灰度

## 目标
只在 quality/hybrid_async 的低置信视觉页上灰度接入慢模型复核，提升关键页的辅助判定能力，但不改变默认同步路径。

## 任务边界
- 默认同步路径不接慢模型。
- 本任务只做低置信页灰度，不改变现有主链的默认时延边界。
- 必须与人工 rubric 对齐，不得自行发明与人工视觉无关的阈值。

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
  - `/Users/linsuchang/Desktop/work/chiralium/backend/app/services/pdf_to_word/visual_similarity_slow_review.py`
  - `/Users/linsuchang/Desktop/work/chiralium/backend/app/services/pdf_to_word/visual_similarity_gate.py`
  - `/Users/linsuchang/Desktop/work/chiralium/backend/tests/test_pdf_to_word_visual_similarity_slow_review.py`
  - `/Users/linsuchang/Desktop/work/chiralium/backend/tests/test_pdf_to_word_visual_similarity_gate.py`

## 约束
- 仅允许 low-confidence pages 触发 qwen3_vl_8b。
- 必须可关闭、可追踪、可回退。
- 要输出每页是否触发慢模型及原因。

## 交付物
1. 慢模型灰度接入代码与测试。
2. 触发条件与回退语义说明。
3. result.json 中给出成本与时延观察点。

## 验收标准
- default sync 不受影响。
- 低置信页可触发慢模型复核且有审计痕迹。
- 测试覆盖触发/不触发/回退场景。

## 下游动作
完成后，可继续推进成本预算门禁与更大样本扩面。
