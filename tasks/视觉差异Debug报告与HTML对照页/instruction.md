# 任务：视觉差异Debug报告与HTML对照页

## 任务类型
开发 / P1 Debug 可视化

## 目标
产出可直接打开的每页 diff / key-region crop / 失败原因对照页，降低 PM/QA/架构师人工排查成本。

## 任务边界
- 本任务是 debug 能力，不改变最终门禁阈值。
- HTML/Markdown/静态产物均可，但必须足够直观。
- 要支持全学科关键区域，不只支持科学表格页。

## 输入事实
- 架构整改意见（全学科）：`/Users/linsuchang/Desktop/work/my-agent-teams/.runtime/worktrees/chiralium/PDF-Word-205980b6/artifacts/pdf2word/final-archive/reports/PDF转Word视觉门禁全学科整改意见.md`
- 架构整改任务结果：`/Users/linsuchang/Desktop/work/my-agent-teams/tasks/制定PDF转Word视觉门禁整改意见/result.json`
- 当前高优先级问题说明：`/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-archive/reports/PDF转Word-五下科学样例复核与95门禁偏差说明.md`
- 代表样例：原 PDF `/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-output-samples/PDF转Word门禁样例-五下科学-source.pdf`；门禁 DOCX `/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-output-samples/PDF转Word门禁样例-五下科学-hybrid_experimental-output.docx`
- 当前统一前提：**不能只盯科学学科，必须把科学、数学、语文、英语统一纳入门禁与样例口径。**
- 当前已知边界：可以保留 `quality/hybrid_async` 工程门禁通过；不可继续宣称“全学科人工视觉 95% 已达成”。
- 本任务前置依赖：实现PDF与DOCX渲染对生成器、升级visual_similarity为真实渲染对视觉证据

## 写入范围
仅允许修改以下路径：
  - `/Users/linsuchang/Desktop/work/chiralium/backend/app/services/pdf_to_word/visual_diff_report.py`
  - `/Users/linsuchang/Desktop/work/chiralium/backend/tests/test_pdf_to_word_visual_diff_report.py`
  - `/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-acceptance/debug-html`

## 约束
- 输出至少包含页级对照、关键区域裁切、失败原因。
- 不得把 debug 产物混入 final-gated 样例清单。
- 要能被 PM/QA 在本地直接打开查看。

## 交付物
1. visual diff report 代码。
2. HTML 对照页或等价静态报告。
3. 相关测试。

## 验收标准
- 可快速定位哪个页、哪个区域导致 no-go。
- 产物结构清晰，可供 review/QA 二次利用。
- 全学科关键区域都可展示。

## 下游动作
完成后，P2 图像密集试卷等专项扩面将直接复用该 debug 视图。
