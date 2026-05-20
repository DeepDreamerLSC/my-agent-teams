# 任务：图像密集试卷题块顺序与图文绑定专项

## 任务类型
开发 / P2 图像密集专项

## 目标
针对图像密集试卷页建立题块顺序、图像裁剪与图文绑定专项检查，补齐数学试卷等 image-dense 页型的后续扩面能力。

## 任务边界
- 本任务是 P2 扩面，不先于 P0/P1 主线。
- 必须复用前面已建的 render pair / visual diff 能力。
- 不改变主线门禁定义。

## 输入事实
- 架构整改意见（全学科）：`/Users/linsuchang/Desktop/work/my-agent-teams/.runtime/worktrees/chiralium/PDF-Word-205980b6/artifacts/pdf2word/final-archive/reports/PDF转Word视觉门禁全学科整改意见.md`
- 架构整改任务结果：`/Users/linsuchang/Desktop/work/my-agent-teams/tasks/制定PDF转Word视觉门禁整改意见/result.json`
- 当前高优先级问题说明：`/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-archive/reports/PDF转Word-五下科学样例复核与95门禁偏差说明.md`
- 代表样例：原 PDF `/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-output-samples/PDF转Word门禁样例-五下科学-source.pdf`；门禁 DOCX `/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-output-samples/PDF转Word门禁样例-五下科学-hybrid_experimental-output.docx`
- 当前统一前提：**不能只盯科学学科，必须把科学、数学、语文、英语统一纳入门禁与样例口径。**
- 当前已知边界：可以保留 `quality/hybrid_async` 工程门禁通过；不可继续宣称“全学科人工视觉 95% 已达成”。
- 本任务前置依赖：升级visual_similarity为真实渲染对视觉证据、视觉差异Debug报告与HTML对照页

## 写入范围
仅允许修改以下路径：
  - `/Users/linsuchang/Desktop/work/chiralium/backend/app/services/pdf_to_word/image_dense_visual_gate.py`
  - `/Users/linsuchang/Desktop/work/chiralium/backend/tests/test_pdf_to_word_image_dense_visual_gate.py`
  - `/Users/linsuchang/Desktop/work/chiralium/backend/tests/fixtures/pdf_to_word/visual_similarity/image_dense`

## 约束
- 题块错序、图像裁剪或位置偏差要能被识别。
- debug 视图必须能定位问题。
- 不得把 image-dense 的专项规则硬编码成单样例。

## 交付物
1. image-dense 专项 gate。
2. fixture 与测试。
3. 后续扩面建议。

## 验收标准
- 数学试卷等图像密集页型有专项保障。
- 题块顺序与图文绑定异常可被识别。
- 可作为后续更大样本扩面的基础。

## 下游动作
完成后，可继续评估更多图像密集页型是否纳入正式门禁。
