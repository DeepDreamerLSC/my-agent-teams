# 任务：实现PDF与DOCX渲染对生成器

## 任务类型
开发 / P0 真实 render pair 入口

## 目标
提供真实 PDF 页渲染图与 DOCX 页渲染图的成对生成能力，作为后续 visual_similarity 和页级/区域级 veto 的唯一上游证据。

## 任务边界
- 本任务只负责 render pair 生成与元数据，不直接给最终 95 打分。
- 允许新增服务模块、测试与 fixture；不要放宽 default sync。
- 必须面向全学科，不要把字段或逻辑写成只适配五下科学。

## 输入事实
- 架构整改意见（全学科）：`/Users/linsuchang/Desktop/work/my-agent-teams/.runtime/worktrees/chiralium/PDF-Word-205980b6/artifacts/pdf2word/final-archive/reports/PDF转Word视觉门禁全学科整改意见.md`
- 架构整改任务结果：`/Users/linsuchang/Desktop/work/my-agent-teams/tasks/制定PDF转Word视觉门禁整改意见/result.json`
- 当前高优先级问题说明：`/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-archive/reports/PDF转Word-五下科学样例复核与95门禁偏差说明.md`
- 代表样例：原 PDF `/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-output-samples/PDF转Word门禁样例-五下科学-source.pdf`；门禁 DOCX `/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-output-samples/PDF转Word门禁样例-五下科学-hybrid_experimental-output.docx`
- 当前统一前提：**不能只盯科学学科，必须把科学、数学、语文、英语统一纳入门禁与样例口径。**
- 当前已知边界：可以保留 `quality/hybrid_async` 工程门禁通过；不可继续宣称“全学科人工视觉 95% 已达成”。
- 本任务前置依赖：建立PDF转Word最终门禁样例清单与分层治理

## 写入范围
仅允许修改以下路径：
  - `/Users/linsuchang/Desktop/work/chiralium/backend/app/services/pdf_to_word/render_pair_generator.py`
  - `/Users/linsuchang/Desktop/work/chiralium/backend/app/services/pdf_to_word/page_renderer.py`
  - `/Users/linsuchang/Desktop/work/chiralium/backend/tests/test_pdf_to_word_render_pair.py`
  - `/Users/linsuchang/Desktop/work/chiralium/backend/tests/fixtures/pdf_to_word/render_pair`

## 约束
- 输出必须包含页级 PNG/渲染文件路径、hash、页尺寸、失败语义。
- 遇到渲染失败要有显式错误语义，不能静默跳过。
- 产物要能被后续 visual_similarity.json 直接引用。

## 交付物
1. render pair 生成器代码。
2. 针对成功/失败/页数不一致等场景的自动化测试。
3. 至少一组可供后续任务复用的 render_pair fixture。

## 验收标准
- 给定 source PDF + output DOCX 能产出页级 render pair 与元数据。
- 失败语义、页尺寸、hash 等基础证据齐全。
- 测试可证明其可被后续视觉评分任务消费。

## 下游动作
完成后，dev-2 将继续升级 visual_similarity 为真实渲染对视觉证据。
