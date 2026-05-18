# 任务：打通公式 Crop 级 OCR 实验闭环

## 任务类型
development

## 目标
基于已经补齐好的 `phase4-formula-crop-eval` 资产（`formula_crop_inputs.jsonl`、`expected-crops/`、OMML baseline），打通一条**不锁死单一模型**的公式 Crop 级 OCR 实验链路：真实产出 `ocr-results/`、刷新评测报告，并给出当前本地可用模型在公式专项上的可用性结论。

## 任务边界
- 只处理公式 crop 级 OCR 实验入口、结果落盘、评测统计与相关测试。
- 可修改 `model_eval_runner.py`、`formula_pipeline.py`、`inference_config.yaml`、对应测试，以及刷新 `artifacts/pdf2word/phase4-formula-crop-eval/`。
- 不改变公式默认 `audit-only / merge-disabled` 策略，不把实验结果直接接入主 DOCX 链路。
- 不锁死 `Qwen3-VL`；优先做**通用实验闭环**，能够消费已注册且当前环境可运行的公式能力 profile。

## 输入事实
- `补齐公式Crop评测资产与OMML基线` 已完成：17 个 crop PNG、17 个 OMML baseline、0 remaining missing asset。
- 当前仍缺“真实识别结果闭环”：`ocr-results/` 目录还只是落点，没有真实模型输出与对比报告。
- owner 已明确“在线 review worker 收口即可，不锁死 Qwen3-VL”；因此本轮应优先形成通用实验入口，而不是把公式专项绑死到某一个模型名。

## 约束
- write_scope 以 task.json 为准。
- 至少要支持：读取 `formula_crop_inputs.jsonl` 与 `expected-crops/`，对一个或多个当前可用 profile 跑真实 OCR/识别，落盘到 `ocr-results/`，并与 OMML/latex baseline 做结构化对比。
- 如果某个 profile 当前环境不可跑，必须在报告中写清 blocked 原因；但至少要让实验框架本身可复跑，且优先产出 1 条真实结果链路。
- 结果统计必须区分：成功识别、空结果、格式失败、基线对齐失败、仍需人工复核项。
- 不得放开公式默认 merge，不得把实验 OCR 结果直接写回主转换链路正文。

## 交付物
1. 公式 crop OCR 实验入口与结果落盘实现。
2. 对应测试，至少覆盖：读取 crop 输入、写入 `ocr-results/`、生成对比统计、blocked/failure 分类。
3. 刷新后的 `phase4-formula-crop-eval/` 产物：包含至少 1 组真实实验结果与更新后的报告。
4. result.json：写明本轮实际跑了哪些 profile、成功/失败数量、当前最值得继续投入的公式专项方向。

## 验收标准
1. `phase4-formula-crop-eval` 不再只有 baseline 与 expected-crops，而是出现真实 `ocr-results/` 与可复跑评测报告。
2. 实验入口不锁死单一模型名，能表达“可用 profile 运行结果 / blocked 原因 / 对比统计”。
3. formula 默认 `audit-only / merge-disabled` 行为不变。
4. 指定测试通过，且产物可直接被 PM/QA 读取用于后续决策。

## 下游动作
完成后进入 review-1 审查；通过后作为公式 OCR 专项是否继续接线、是否需要引入局部新模型的直接依据。
