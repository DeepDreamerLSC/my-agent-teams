# 审查说明：MinerU 切换 full 模式重跑样例对比

## 结论

**通过（approve）**。这次任务把 MinerU 的 `model_mode` 切到了 full，并用 `model_eval_runner` 重跑了 5 个样例，产出了新的对比报告。结果很明确：full 模式没有达到 `>=3/5` 的阈值，也没有优于 `apple_baseline` 或旧的 lite 跑批，但任务本身的切换、执行和报告交付都完成了。

## 审查范围

- `tasks/MinerU切换full模式重跑样例对比/instruction.md`
- `tasks/MinerU切换full模式重跑样例对比/result.json`
- `tasks/MinerU切换full模式重跑样例对比/task.json`
- `backend/app/services/pdf_to_word/parser_adapters/inference_config.yaml`
- `artifacts/pdf2word/model-eval/20260515-090642/comparison_report.json`

## 复核结果

- `inference_config.yaml` 中 MinerU 的 `mineru_model_mode` 已切到 `full`。
- `model_eval_runner` 已重新跑完 5 个样例，且输出到了新的时间戳目录。
- `comparison_report.json` 同时覆盖了 `mineru_full vs apple_baseline` 和 `mineru_full vs mineru_lite`。
- 报告结论与 `result.json` 一致：full 模式没有形成稳定提升，当前不建议替换主 parser。

## 非阻塞建议

1. 当前 full 模式是通过 `inference_config.yaml` 里的 CLI wrapper 内联脚本切换的。功能上没问题，但后续如果继续扩展更多模式，建议把这段逻辑抽成更小的可测函数，维护成本会更低。
2. `comparison_report.json` 属于 artifacts 产物，不在本任务声明的 write_scope 里。现在流程上能跑通，但元数据边界最好补齐，避免后续审计时产生歧义。

## 下一步

建议进入 QA / 归档。就当前样例集来看，full 模式不构成替换 baseline 的依据。

审查时间：2026-05-15T09:58:00+08:00
