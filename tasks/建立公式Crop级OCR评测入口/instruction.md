# 任务：建立公式 crop 级 OCR 评测入口

## 任务类型
development

## 目标
建立一个可复跑的公式 `crop-level OCR` 评测入口，把当前 `phase4-formula-baseline` 里的 focus pages / placeholder 字段转成下一轮公式专项可直接使用的评测输入与报告结构，但仍然保持公式能力默认 `audit-only`，不进入生产 merge 链路。

## 任务边界
- 只处理公式专项的评测入口、报告结构、复跑命令与测试闭环。
- 不把 `formula_candidate` 接入默认 merge，不改现有 `CandidateFilter` 的 audit-only 默认行为。
- 不引入新的线上模型接线，不做 prod 改造。
- 不重启端到端 parser 横评；评测入口应建立在既有 `phase4-formula-baseline` 产物之上。

## 输入事实
- `建立公式专项实验开关与评测基线` 已完成，`phase4-formula-baseline/` 已固化 3 个样例、9 个重点页、18 个公式候选。
- 目前 `focus-pages.json` 中 `latex / omml / image_path` 仍是占位字段，说明公式专项若继续推进，应先从 crop-level OCR 基准做起，而不是把现有 audit-only 候选直接并回主链。
- `评估局部能力新模型替代Paddle或补公式` 的结论也明确指出：公式 lane 当前不建议直接接任何现成模型，应先开独立专项。

## 约束
- write_scope 以 task.json 为准。
- 入口必须可复跑，至少给出明确命令、输出目录和报告 schema。
- 默认链路仍然保持公式 audit-only，不得在本任务里改变 merge gate。
- 若需要回写 baseline，只能补“评测输入所需信息/占位说明”，不能把 placeholder 当成生产能力已完成来宣称。

## 交付物
1. `model_eval_runner.py` 中一条可复跑的公式 crop 级 OCR 评测入口。
2. 对应测试，证明入口可运行且输出结构稳定。
3. `artifacts/pdf2word/phase4-formula-crop-eval/` 下的首份评测报告或样例产物。
4. result.json：写清复跑命令、输入基线、报告结构、目前仍缺的真实 OCR 资产。

## 验收标准
1. 存在明确可复跑的公式 crop 级 OCR 评测命令与输出目录。
2. 报告能直接回答：当前 focus pages 里有哪些可评页、缺哪些输入资产、下一步怎么接模型实验。
3. 指定测试通过，且不改变公式默认 audit-only 行为。
4. 产物能作为下一轮公式专项任务的直接输入，而不是停留在口头方案。

## 下游动作
完成后进入 review-1 审查；审查通过后作为公式专项下一轮是否投入 crop-level OCR 的评测入口。
