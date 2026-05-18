# 审查说明：补齐公式Crop评测资产与OMML基线

## 结论

**审查通过（approve）。**

## 通过依据

1. 任务边界收得住，没有把公式 lane 越界改成主链 merge。

   这轮只补公式 crop eval 资产、OMML 基线、报告与测试，没有改公式默认 audit-only / merge-disabled 策略，也没有接入新的线上模型或重启端到端横评。刷新后的报告仍明确：

   - `default_enabled = false`
   - `default_mode = disabled_audit_only`
   - `merge_enabled_by_default = false`

2. 交付已经从“期望路径”推进成了“真实可复跑资产”。

   `model_eval_runner.py` 现在会：

   - 优先复用 baseline 已声明的 `image_path`
   - 否则从 `artifacts/pdf2word/model-eval/*/_workspace/renders/<sample>/page-XXX.png` 和对应 meta 中发现可复用 page render
   - 按 `bbox` 真正裁切出 crop PNG 到 `expected-crops/`
   - 对 `latex`（为空时回退 `text`）直接生成 OMML
   - 对失败项单独记入 `formula_crop_missing_assets.json`

   这满足了“materialize 评测所需 crop 资产或至少形成明确可复跑契约”的验收要求。

3. 刷新后的资产与报告统计自洽。

   我复核确认：

   - `formula_crop_inputs.jsonl` 有 `17` 条输入
   - `expected-crops/` 下实际有 `17` 个 PNG
   - `ocr-results/` 目录已建立但仍为空，符合“只约定下一轮 OCR 输出落点”的任务边界
   - `formula_crop_eval_report.json` 聚合显示：
     - `formula_candidate_count = 18`
     - `manifest_crop_count = 17`
     - `unmaterialized_candidate_count = 1`
     - `materialized_crop_count = 17`
     - `materialized_omml_count = 17`
     - `remaining_missing_asset_count = 0`
     - `omml_conversion_failure_count = 0`
     - `crop_materialization_failure_count = 0`

   这与 result.json 的前后资产变化描述一致。

4. OMML 成功/失败分流与 crop materialization 路径都有测试覆盖。

   我复跑了两组结果中声明的测试：

   - `test_model_eval_runner.py`：`11 passed`
   - `test_pdf_formula_pipeline.py`：`4 passed`

   其中 `test_model_eval_runner.py` 已覆盖：

   - render materialization
   - 报告统计
   - expected-crops 落盘
   - remaining missing asset 汇总

   `test_pdf_formula_pipeline.py` 也补了 plain-text formula-like 内容转 fallback OMML 的断言。

5. 下一轮公式 OCR 专项的输入已经明确。

   报告和 result.json 都把下轮应直接读取的文件说明清楚了：

   - `formula_crop_inputs.jsonl`
   - `expected-crops/`
   - `ocr-results/`
   - `formula_crop_eval_report.json`
   - `formula_crop_missing_assets.json`

   这已经是可直接消费的输入基线，而不是停留在方案层。

## 非阻塞观察

- 当前仍有 `1` 个 baseline 公式候选未进入 `examples`，因此聚合里保留了 `unmaterialized_candidate_count = 1`。这是诚实暴露的上游 baseline 覆盖缺口，不是本轮评测资产层的伪造遗漏，不影响本轮通过。

## 总结

这轮交付已经把公式 crop eval 资产从“缺 `crop_image_path / omml` 的 placeholder 基线”补成了“17 个真实 crop PNG + 17 个 OMML 基线 + 0 剩余缺口”的可复跑输入，同时保持 formula 默认 audit-only 不变，可以通过。
