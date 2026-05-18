# 任务：补齐公式 crop 评测资产与 OMML 基线

## 任务类型
development

## 目标
把 `phase4-formula-crop-eval` 当前缺失的 `crop_image_path / omml` 资产尽量实化为可复跑输入：在不改变 formula audit-only 默认策略的前提下，补齐可 materialize 的 crop 图片与可从 latex 派生的 OMML 基线，重新生成公式 crop 评测报告，降低当前公式专项缺口。

## 任务边界
- 只处理公式 crop eval 的 manifest/materialization/report 与相关测试。
- 可修改 `model_eval_runner.py`、`formula_pipeline.py`、对应测试，以及重生成 `artifacts/pdf2word/phase4-formula-crop-eval/` 产物。
- 不改变公式默认 audit-only / merge-disabled 策略。
- 不接入新的线上模型，不重启端到端 parser 横评，不做 prod 改造。

## 输入事实
- `phase4-formula-baseline` 已固化 9 个 focus pages、18 个公式候选。
- 当前 `phase4-formula-crop-eval` 报告显示主要缺口集中在 `crop_image_path` 与 `omml`：现有报告里对应缺失资产均为 17。
- baseline 示例里大量候选已带有 `bbox` 与 `latex` 占位信息，说明下一步缺口主要在：把 crop 资产 materialize 出来，以及把可转换的 latex 变成 OMML 基线，而不是继续停留在 placeholder。
- `formula_pipeline.py` 已具备 `latex -> omml` 的基础转换能力。

## 约束
- write_scope 以 task.json 为准。
- 保持公式默认 `audit-only`；不能把本任务演变成公式并回主链路。
- 如果某些 latex 无法稳定转换为 OMML，必须显式记录失败原因，不能伪造成功资产。
- 优先复用现有 bbox / page render / formula pipeline 能力，保证产物可复跑、可复核。

## 交付物
1. 公式 crop eval 资产 materialization / OMML 基线补齐实现。
2. 对应测试，至少覆盖：可生成 crop 资产路径或真实文件、可区分转换成功/失败、报告统计正确。
3. 刷新后的 `artifacts/pdf2word/phase4-formula-crop-eval/` 产物。
4. result.json：写明缺口补齐前后各项资产数量变化、仍残留哪些缺口、下一轮模型实验应直接读取哪些文件。

## 验收标准
1. 公式 crop eval 在 bbox/page 信息充分时，能够 materialize 评测所需 crop 资产或至少落成明确的可复跑资产契约。
2. 报告能清楚区分：已 materialize 的 crop、已补齐的 OMML、转换失败项、仍缺失资产。
3. formula 默认 audit-only 行为不变。
4. 指定测试通过，且新产物可作为下一轮公式 OCR 专项的直接输入。

## 下游动作
完成后进入 review-1 审查；通过后作为下一轮公式 OCR / crop-level 公式专项的直接输入基线。
