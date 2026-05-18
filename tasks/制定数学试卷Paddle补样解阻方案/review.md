# 审查说明：制定数学试卷Paddle补样解阻方案

## 结论

**审查通过（approve）。**

## 通过依据

1. 方案边界正确，没有越界做实现修改。

   本任务要求是解阻方案设计与事实核验，不允许重跑长时间 Paddle 任务，也不允许改主链代码。交付只新增了 `artifacts/pdf2word/phase3-paddle-unblock-plan/数学试卷Paddle补样解阻方案.md`，符合 write scope 和任务边界。

2. blocker 被重新界定为更准确、也更可执行的问题。

   报告没有停留在重复上游 `blocked` 结论，而是核实出一个新的关键事实：

   - `2026-05-17 12:38` 前，“当前机器 CPU 上长时间跑不出可归档 Paddle 样例”这个 blocker 成立；
   - 但到 `2026-05-17 13:32`，`final-archive/profiles/paddleocr_vl/数学试卷/` 已新增 `metrics.json`、`pages.jsonl`、`output.docx`、`warnings.json`；
   - 真正未闭环的是 `source_manifest/profile_manifest/archive_manifest/README` 与 `Phase 3 report` 仍停留在旧状态，`test_hybrid_e2e.py` 的正式消费链路也仍依赖 `sample.source_dir`。

   这使方案从“要不要继续加时跑 Paddle”升级为“先判定 provenance，再决定是否重开原任务”，判断是合理的。

3. 四条候选路径比较完整，且逐条回答了任务要求。

   报告明确比较了：

   - 当前机器延长推理窗口
   - 换更快设备或外部算力重跑
   - 接受降级补样
   - 接受保留缺口并固化 known gap

   每条路径都写了前提条件、收益、风险，以及是否满足原 blocked 任务验收，满足 instruction 的硬性要求。

4. 推荐动作是可执行的，而不是泛泛建议。

   方案给出的顺序很清晰：

   - 先确认 `2026-05-17 13:32` 新产物的来源与可追溯性；
   - 若能补证，就不要重开长时间重跑任务，而是开一个更小的 `provenance + manifest + Phase 3 刷新` 任务；
   - 若无法补证，再以更快设备或外部算力为前提重开原任务；
   - 默认不推荐“当前机器盲目加时”。

   这已经能直接支撑 PM 决定是否重开原 blocked 任务，以及在什么条件下重开。

5. 关键事实链条经过了文件级复核。

   我复核确认了：

   - `phase3-paddle-quality/数学试卷/profile-audits.json` 与 `report.json` 仍把 `paddleocr_vl` 记为 `candidate_count=0` 并提示缺 `source_dir`
   - `final-archive/profiles/paddleocr_vl/数学试卷/source_manifest.json` 仍是 `source_dir=null`
   - `final-archive/profiles/paddleocr_vl/profile_manifest.json`、`archive_manifest.json`、`README.md` 仍保留“数学试卷缺失”的旧叙述
   - 但样例目录下确实已经新增了 `13:32` 的真实文件
   - `model-eval/20260515-112748/paddleocr_vl/数学试卷` 仍不存在
   - `test_hybrid_e2e.py` 虽支持 profile manifest overlay，但正式读取仍依赖 `sample.source_dir`

   因此报告的核心结论是有事实支撑的。

## 非阻塞观察

- 报告里关于触发页 `1/8/9/11` 至少存在 `51` 个候选型 block 的判断，来自对 `pages.jsonl` 的静态统计，不等同于重生成后的 `profile-audits.json`。这不影响本轮“解阻方案成立”的结论，但后续若走 provenance/manifest 刷新任务，建议把该推断升级成正式审计结果。

## 总结

这次交付完成的不是代码实现，而是一次有效的决策前清障：它把 blocker 从过时的“完全无产物”更新成了“新产物存在，但 provenance 和消费链路未闭环”，并据此给出可执行的推荐顺序。作为设计任务，这份方案已经足够支撑 PM/owner 决策，可以通过。
