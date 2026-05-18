# 任务：制定数学试卷 Paddle 补样解阻方案

## 任务类型
design

## 目标
基于当前 `补齐数学试卷Paddle归档样例` 的真实 blocker，输出一份可执行的解阻方案，明确后续应走哪条路径：延长真实推理时限 / 换更快设备 / 接受降级补样口径 / 接受保留缺口，并给出推荐结论。

## 任务边界
- 只做解阻方案设计与事实核实，不直接重跑长时间 Paddle 任务，不修改主链代码。
- 可以读取现有任务产物、Phase 3 报告、final-archive profile manifest、已有 model-eval/workspace 产物。
- 只允许把输出写入 `artifacts/pdf2word/phase3-paddle-unblock-plan/`。
- 不改默认 Hybrid / Paddle 触发策略，不改 prod 配置，不直接变更 blocked 任务状态。

## 输入事实
- `补齐数学试卷Paddle归档样例` 当前已被执行者标记为 `blocked`。
- blocker 已核实为：`数学试卷` 在 `paddleocr_vl` profile 下缺少真实归档产物；dev-2 在本机 CPU 上尝试对 Phase 3 实际触发的 4 页（1/8/9/11）及整样例重跑 PaddleOCR-VL，模型可加载但长时间无单页结果落盘。
- 当前 `final-archive/profiles/paddleocr_vl/数学试卷/` 仍只有 `source_manifest.json`；`phase3-paddle-quality/数学试卷/profile-audits.json` 仍显示 `candidate_count=0` 且提示缺少归档 `source_dir`。
- dev-2 已补 `test_hybrid_e2e.py` 的 profile-manifest overlay 读取逻辑，意味着后续若拿到 profile 级真实产物，可直接被 e2e / Phase 3 报告消费。

## 约束
- write_scope 以 task.json 为准。
- 方案必须是可执行决策，不接受泛泛而谈。
- 至少比较以下 4 条路径：
  1. 继续在当前机器上给更长 Paddle 推理窗口
  2. 换更快设备/外部已有算力重跑真实样例
  3. 接受降级补样（例如只要求 pages/metrics/warnings，不强制 output.docx）
  4. 接受保留缺口并在报告中显式固化 known gap
- 每条路径都要写清：前提条件、预期收益、风险、是否满足当前 blocked 任务原始验收。

## 交付物
1. `artifacts/pdf2word/phase3-paddle-unblock-plan/` 下的一份方案报告（md 或 json 均可，但要可直接阅读）。
2. 一个明确推荐结论：PM 下一步应该重开原任务、改派资源，还是直接接受缺口。
3. result.json：写清 blocker 真实性、各路径比较和推荐动作。

## 验收标准
1. 报告能直接支撑 PM/owner 做决策，而不是重复描述 blocker。
2. 四条候选路径比较完整，且明确指出哪条最推荐。
3. 推荐结论能回答：原 blocked 任务是否值得重开、以什么条件重开。
4. 不修改主链代码和默认策略边界。

## 下游动作
完成后进入 review-1 审查；审查通过后由 PM 依据方案决定是否重开补齐数学试卷Paddle归档样例或接受已知缺口。
