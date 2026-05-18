# 任务：补齐数学试卷 Paddle 归档样例

## 任务类型
development

## 目标
把 `数学试卷` 在 `paddleocr_vl` profile 下的归档，从“当前可被 phase3/e2e 消费但 provenance 语义混乱”的状态，收口为“**语义诚实、契约自洽、仍可稳定消费**”的状态。

## 任务边界
- 只处理 `数学试卷` 这个样例在 `paddleocr_vl` profile 下的 provenance 契约、manifest/README 对齐、phase3 报告与 e2e 消费口径。
- 不修改 Paddle 触发策略，不改 candidate_filter，不改默认 Hybrid 策略，不做长时间重跑。
- 可修改 `final-archive/README.md`、`archive_manifest.json`、`profiles/paddleocr_vl/profile_manifest.json`、`profiles/paddleocr_vl/数学试卷/`、`phase3-paddle-quality/数学试卷/`、`phase3-paddle-quality/report.json`、`test_hybrid_e2e.py`。

## 输入事实
- 当前 blocker 已不是“完全无产物”，而是 provenance 契约本身冲突：`source_manifest.json` / `profile_manifest.json` 把 `source_dir` 写成 final-archive 自指目录，而 README 仍把它定义为“原始来源”。
- 当前回填产物已经足够被 `phase3-paddle-quality` 与 `test_hybrid_e2e.py` 稳定消费，但**不能再冒充原始 run 目录**。
- 原始 `20260515-112748` run 下仍缺 `数学试卷` 子目录；如果这跳证据仍补不出来，必须显式保留 gap，而不是伪装成已闭环。

## 约束
- write_scope 以 task.json 为准。
- **不允许**再把任何定义为“原始来源”的字段直接指向 `final-archive/.../数学试卷` 自身目录。
- 如需让 phase3/e2e 继续消费当前归档，必须通过**明确区分**“原始来源”和“当前归档消费目录”的契约实现；可以新增或改名字段，但不能继续混淆语义。
- 不得伪造 original-run provenance complete；若原始 run 证据仍不存在，必须诚实暴露 remaining gap。
- 本轮重点是 **contract / manifest / report / harness 收口**，不是继续做长时间 Paddle 补跑。

## 交付物
1. `README.md`、`archive_manifest.json`、`profile_manifest.json`、`数学试卷/source_manifest.json` 口径一致的 provenance 契约。
2. 刷新后的 `phase3-paddle-quality/数学试卷/`、`phase3-paddle-quality/report.json`，以及必要时更新的 `test_hybrid_e2e.py`，确保样例仍可被 phase3/e2e 消费。
3. result.json：写明当前样例的“原始来源字段”“归档消费字段”（若有）分别是什么、remaining provenance gap 是否仍存在、为何本轮可按契约收口。

## 验收标准
1. `source_manifest / profile_manifest / README / archive_manifest` 不再语义冲突。
2. `test_hybrid_e2e.py` 回归通过，且 `数学试卷` 仍可被 phase3/e2e 稳定消费。
3. 若 original run-level provenance 仍缺失，必须被明确、诚实、可复核地暴露；在此条件下，本任务可按“**契约收口**”完成，不再要求伪造 original-run closed。
4. 不修改 Paddle 触发策略与默认链路边界。

## 下游动作
完成后进入 review-1 审查；审查通过后，作为 `数学试卷` Paddle 样例的 provenance/contract 收口结论。
