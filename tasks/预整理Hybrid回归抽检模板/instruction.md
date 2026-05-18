# 任务：预整理 Hybrid 回归抽检模板

## 任务类型
verification

## 目标
在不等待在线 review worker 最终收口的前提下，先把 Hybrid 回归抽检模板的主体框架搭起来：样例分组、页面级检查步骤、ExerciseIR/DOCX 抽检项、报告模板结构先固化，后续只需补入最终在线 review 指标即可。

## 任务边界
- 仅整理 QA 口径文档与模板框架
- 可在 `artifacts/pdf2word/final-archive/reports/` 新增或更新文档
- 不修改生产代码、不改测试、不改 `hybrid-e2e-validation/report.json`
- 不直接关闭正式任务《补齐Hybrid回归样例与人工抽检流程》

## 输入事实
- `实现Hybrid题号顺序与阅读顺序校验器` 已完成，可将顺序/题号类检查点提前纳入模板
- 当前 `hybrid-e2e-validation/report.json` 已有 5 样例、candidate / fallback / online review 等关键字段，可作为模板字段来源
- 林总工已确认：后续验收方向是“在线 review worker 收口即可”，不再锁死 Qwen3-VL，因此 QA 模板中相关栏目应写成通用的 online review worker 指标位
- 正式任务《补齐Hybrid回归样例与人工抽检流程》仍需等待在线 review worker 最终收口后补齐定稿指标

## 约束
- write_scope 以 task.json 为准
- 输出应能被后续正式 QA 基线任务直接复用
- 模板必须覆盖：正样例/负样例、重点抽检页、PageIR 差异、ExerciseIR 挂接、DOCX 可视结果、fallback 行为、online review worker 指标占位
- 本任务不要求给出最终 json_valid_rate / review_acceptance_rate 阈值结论，只需预留检查栏目

## 交付物
1. 一份预整理的 Hybrid 回归抽检模板文档（写入 `artifacts/pdf2word/final-archive/reports/`）
2. 明确的样例分组草案：正样例、负样例、重点抽检页
3. 供正式 QA 任务复用的检查清单结构
4. result.json：说明哪些栏目已可固定，哪些栏目需等待在线 review worker 最终收口后补入

## 验收标准
1. 文档可直接作为正式任务《补齐Hybrid回归样例与人工抽检流程》的输入骨架
2. 至少覆盖顺序/题号、candidate/fallback、ExerciseIR、DOCX、online review worker 五类检查项
3. 能让 qa-1 在正式任务启动时少做结构设计，只需补齐最终指标与结论

## 下游动作
完成后并入正式《补齐Hybrid回归样例与人工抽检流程》任务，作为其前置文档输入；待在线 review worker 最终收口后，再由 qa-1 补齐最终指标口径。
