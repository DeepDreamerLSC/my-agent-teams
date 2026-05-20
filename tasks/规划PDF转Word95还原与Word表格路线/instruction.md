# 任务：面向 95% 还原度重规划 PDF 转 Word 路线，明确 Word 表格结构化呈现与验收方案

## 任务类型
架构设计 / 技术规划

## 目标
基于当前 PDF2Word 路线、既有样例事实与现有主链路实现，补一轮更明确的后续规划：
1. 把总体目标提升到**可度量的 95% 还原度**；
2. 把“**表格必须以可编辑 Word 表格呈现，且单元格内容/结构/基本格式尽量还原**”提升为明确要求，而不是占位或图片 fallback；
3. 输出后续实施任务拆解与阶段门禁，供 PM 直接继续派发。

## 任务边界
- 只做架构/规划文档更新，不改生产代码。
- 需要回看并更新现有规划文档，而不是另起完全脱离现状的新方案。
- 保持当前总架构原则：`PageIR -> ExerciseIR -> DOCX`，不改成“大 VLM 直接 PDF 转 Word”。

## 输入事实
1. 当前路线文档：
   - `/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-archive/reports/后续技术路线.md`
   - `/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-archive/reports/端到端技术链路.md`
   - `/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-archive/reports/横评最终报告.md`
2. 当前规划里，表格仍不是最高优先级，而且 DOCX 侧仍允许“表格占位 / 图片 fallback / 后续再扩真实表格”。
3. 真实链路现状：`排查Hybrid输出到ExerciseIR数据流转断裂` 已证明 visual blocks 能进入 ExerciseIR 与 DOCX，但英语样例中的 table 仍可能因为缺少 `table_html/table_rows` 而以图片 fallback 落盘，`has_table_xml=false`。
4. 当前 owner 新要求：
   - 最终目标要朝 **95% 还原度** 收口；
   - **表格必须用 Word 表格格式呈现**；
   - 表格内容也要尽量按原文档格式填充，而不是只插截图。

## 你需要回答的核心问题
1. “95% 还原度”在本项目里应如何拆成可执行、可验收的指标？
2. 表格能力应如何从当前“candidate -> payload -> 占位/图片 fallback”升级成“真实可编辑 Word 表格”？
3. 在不破坏默认同步链路的前提下，哪些任务必须前置，哪些可以并行？
4. 现有路线里哪些优先级需要调整（尤其是表格，从 P2/P占位提升到更前置位置）？
5. 为达成 95%，除了表格，还必须补哪些能力：题号顺序、答案区、图片归属、公式、视觉相似度、样本扩充、final gate 等？

## 约束
- 不要给“泛泛而谈”的规划，必须落到明确模块、数据契约、阶段门禁和任务拆解。
- 必须基于现有代码/产物事实规划，不能假设目前已经具备真实 table structure IR。
- 必须明确区分：
  - **当前已经做到的**
  - **当前只做到 placeholder / fallback 的**
  - **为达成 95% 新增必须做的**
- 默认同步路径仍不能被慢模型拖慢；如果 95% 目标只适合 quality/async 模式，也要明确写清。

## 交付物
请输出并/或更新以下文档：
1. 更新 `/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-archive/reports/后续技术路线.md`
   - 重新排序后续 Phase / 优先级；
   - 明确把表格结构化 Word 呈现纳入主路线。
2. 更新 `/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-archive/reports/端到端技术链路.md`
   - 明确 table 的端到端契约：candidate -> normalized table IR -> ExerciseIR -> DOCX table renderer -> final gate。
3. 新增 `/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-archive/reports/95还原度与Word表格验收路线.md`
   - 给出 95% 还原度定义、指标拆分、验收门禁、阶段任务清单、依赖关系。

## 验收标准
1. 文档能明确说明：要达成 95% 还原度，后续至少还差哪些任务。
2. 文档能明确回答：表格如何从当前 fallback 形态演进为真实 Word 表格。
3. 文档中包含**可派发的任务拆解清单**，PM 可以直接据此创建 dev/qa 任务。
4. 文档必须写清哪些能力只进入 quality/async 模式，哪些需要进入默认发布门禁。
5. 结论必须和当前既有 artifacts / task result 事实一致，不能把现状说得比实际更好。

## 下游动作
方案完成后，PM 将基于该文档继续拆分：
- 表格结构化抽取与 Word 渲染任务
- 95% 还原度指标 / gate 任务
- 题号/答案/图片/视觉相似度等补强任务
