# 任务：推进公式裁块 OCR 失败归因与对比专项，保持 merge-disabled

## 任务类型
development

## 目标
在现有公式裁块评测入口与 OMML 基线之上，补齐 **失败归因、分桶统计与对比结论**，把当前“公式仍 audit-only / merge-disabled”的原因讲清楚，并形成下一轮可执行的 A/B 输入，而不是只停留在总成功率描述。

## 任务边界
- 本任务是公式专项评测与诊断任务，不是放开公式 merge 的任务。
- 不锁死某一个模型；结论应尽量保持模型无关，只基于当前可跑 profile 给出事实归因。
- 不改变默认发布边界，公式仍保持 `audit-only / merge-disabled`。

## 输入事实
- 当前已有：
  - 公式裁块评测入口；
  - OMML 基线资产；
  - 真实 crop OCR 实验闭环。
- 现状仍是：exact success 偏低，且存在 `alignment failed / format failed / empty / blocked` 等失败类型。
- P1 文档已明确：公式专项要继续推进，但不能提前并回正文。

## 约束
- `write_scope` 以 `task.json` 为准。
- 优先在现有 `model_eval_runner.py` 评测框架内补齐失败归因，不要新起散乱脚本。
- 输出必须把失败至少按以下类别拆开：`alignment failed / format failed / empty / blocked / conversion failed`（如命名略有不同可统一归类）。
- 需要给出“哪些失败更适合通过 crop/materialization/清洗修复，哪些更依赖模型能力”的判断。

## 交付物
1. 代码与测试：扩展公式裁块评测摘要与产物，支持失败归因分桶。
2. 产物输出：写入 `artifacts/pdf2word/p1-formula-crop/`，至少包含 JSON 摘要与 Markdown 结论。
3. `result.json`：写明
   - 当前各失败桶规模；
   - 哪些问题适合下一轮继续 A/B；
   - 为什么现阶段仍不能放开 merge。

## 验收标准
1. 当前公式裁块评测不再只有总成功率，而是能稳定输出失败分桶。
2. 能区分数据/裁块问题、格式转换问题、模型识别问题。
3. 产物能直接支持下一轮公式专项任务拆解。
4. 默认公式策略仍保持 `audit-only / merge-disabled`，没有被偷偷放开。

## 下游动作
完成后进入 review-1 审查；通过后交 qa-1 复核公式裁块评测产物与失败归因口径。
