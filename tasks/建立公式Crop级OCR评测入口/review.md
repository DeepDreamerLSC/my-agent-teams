# 审查说明：建立公式Crop级OCR评测入口

## 结论

**审查通过（approve）。**

## 通过依据

1. 入口目标收口正确。

   这次新增的是 `model_eval_runner.py --formula-crop-eval`，它直接建立在现有 `phase4-formula-baseline/` 之上，只生成 crop 级 OCR 评测契约和报告，不重启端到端横评，也没有接入新的线上模型。

2. 默认公式行为没有被改坏。

   报告里明确保留：
   - `default_mode = disabled_audit_only`
   - `merge_enabled_by_default = false`

   说明本任务仍然保持 formula 默认 audit-only，没有偷偷打开 merge gate。

3. 交付物已经能直接服务下一轮公式专项。

   产物里同时具备：
   - `formula_crop_eval_report.json`
   - `formula_crop_inputs.jsonl`
   - `formula_crop_missing_assets.json`
   - `expected-crops/`
   - `ocr-results/`

   这已经不是口头方案，而是一套可复跑、可消费的输入契约。

4. 报告回答了“现在能评什么、还缺什么”。

   当前结论很清楚：
   - focus pages: `9`
   - formula candidates: `18`
   - manifest-ready crops: `17`
   - unmaterialized candidates: `1`
   - OCR-ready crops: `0`
   - missing `crop_image_path`: `17`
   - missing `omml`: `17`

   这正是下一轮公式 OCR 专项需要的输入。

5. 测试和复跑都成立。

   我复跑了 `test_model_eval_runner.py`，结果 `11 passed`；同时实际复跑 `--formula-crop-eval` 命令，新报告与提交产物关键指标完全一致。

## 非阻塞观察

- baseline 里 18 个公式候选目前只 materialize 成 17 条 crop 输入，仍有 1 条候选没有展开成 example。这个缺口已经被报告诚实暴露，后续在真正接模型前应先补齐，但不影响本轮“评测入口已建立”的验收。

## 总结

这次交付已经把公式专项从“口头上说要做 crop-level OCR”推进成了可复跑的评测入口和资产契约，可以通过。
