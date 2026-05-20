# 任务：制定PDF转Word视觉门禁整改意见

## 任务类型
设计 / 高优先级整改方案

## 目标
基于最新的五下科学样例复核结论，针对“当前工程门禁 95% 与人工逐页对照观感明显偏差”的问题，输出一份高优先级整改意见，并且直接给出可执行的任务拆分表，供 PM 收到后立即派发。

## 任务边界
- 只允许修改 `/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-archive/reports` 下文档。
- 本任务只做方案与拆分，不改代码、不改测试、不重跑大样本。
- 重点围绕“视觉门禁定义/样例使用/收口口径/后续实施拆分”四块，避免泛化到无关产品规划。

## 输入事实
- 最新高优先级复核文档：
  - `/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-archive/reports/PDF转Word-五下科学样例复核与95门禁偏差说明.md`
- 当前正确对比样例：
  - 原 PDF：`/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-output-samples/PDF转Word门禁样例-五下科学-source.pdf`
  - 门禁 DOCX：`/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-output-samples/PDF转Word门禁样例-五下科学-hybrid_experimental-output.docx`
- 已完成事实：
  - `重跑PDF转Word最终95判定` 已给出 go 结论（overall_score=97.8）
  - `收敛PDF转Word最终收口建议` 已收口
  - visual similarity canonical artifact 已接通，但当前用户明确指出人工视觉观感与门禁结论存在显著偏差

## 必答问题
1. 针对“五下科学”这个代表样例，当前门禁为什么会判过，但人工观感仍明显低于 95%？请归因排序。
2. 现有 95% 门禁定义里，哪些指标在高估真实还原度？哪些是必要但不充分？
3. 应如何改造成“更接近人工视觉 95%”的门禁？
4. 样例管理、对外口径、收口结论应如何纠偏，避免再次出现“拿错样例/口径误导”的问题？

## 约束
- 必须区分：当前是“工程门禁 95%”还是“人工视觉 95%”。
- 不得用空泛表述；必须给出可以直接派发的整改项。
- 输出中必须包含任务拆分表，至少列出：任务名、优先级、建议负责人、写入范围、预计工时、前置依赖。

## 交付物
1. 一份整改意见文档（建议直接落在 reports 目录，文件名清晰）。
2. 一份任务拆分表，能让 PM 收到后不再补问即可直接建任务。
3. 一段总括结论：当前 PDF→Word 是否应继续维持已收口状态、还是应按“门禁口径需整改”重新开启后续任务。

## 验收标准
- PM 读完后能立即按表拆任务，不再需要你补第二轮口头解释。
- 方案能同时回答“为什么偏差这么大”和“接下来怎么改”。
- 文档里要明确区分 P0/P1/P2，而不是只给一堆建议。

## 下游动作
PM 收到后将立即按整改清单拆分任务、派发并推进完成。
