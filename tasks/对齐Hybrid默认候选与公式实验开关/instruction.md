# 任务：对齐 Hybrid 默认候选与公式实验开关

## 任务类型
development

## 目标
把 `hybrid_experimental` 的默认候选收口到 `mineru_full`，避免 `paddleocr_vl` 继续作为默认常驻增强源；同时把 `formula_experiment` 开关真正接到 pipeline 配置/实例化链路，但继续保持 formula merge 默认关闭、仅 shadow/audit。

## 任务边界
- 只处理 `parser_client.py`、`hybrid_pipeline.py`、`inference_config.yaml` 与对应测试。
- 不修改 Paddle 选择性触发策略本身，不重跑 Phase 3 长时间评测，不改 review worker。
- 不让公式进入默认 merge，不改 docx 正式公式并回逻辑。
- 不改默认同步 `apple_baseline` 链路。

## 输入事实
- Phase 4 local capability report 的结论已明确：`mineru_full` 应作为默认局部增强源；`paddleocr_vl` 只保留为 `table-heavy / image-dense` 页的定向 A/B，而不应继续作为默认常驻候选。
- 当前 `parser_client.py` 中 `DEFAULT_HYBRID_CANDIDATE_PROFILES = ('mineru_full', 'paddleocr_vl')`，而 `hybrid_experimental` 配置段未显式覆盖该默认值。
- 当前 `hybrid_pipeline.py` 实例化 `CandidateExtractor()` / `CandidateFilter(...)` 时，没有把 `enable_formula_experiment` 从配置透传进去。
- 现有公式策略仍应保持 audit-only/shadow；不能因为本任务放开 merge gate。

## 约束
- write_scope 以 task.json 为准。
- 默认同步路径仍然不受影响。
- 如果需要设置默认候选，优先通过 `hybrid_experimental` 配置与解析逻辑显式表达，不要继续依赖隐式双候选硬编码。
- `enable_formula_experiment` 只允许影响 shadow metrics / candidate features / config 可观测性，不允许放开公式 merge。
- 不得引入新的长耗时 profile 作为默认常驻增强源。

## 交付物
1. `hybrid_experimental` 默认候选收口实现。
2. `formula_experiment` 配置到 `CandidateExtractor / CandidateFilter` 的透传接线实现。
3. 对应测试，至少覆盖：默认候选不再常驻 Paddle、显式配置仍可覆盖、formula experiment 开关可观测、公式仍 audit-only。
4. result.json：写明默认候选最终值、formula experiment 可观测入口、是否仍保持 audit-only。

## 验收标准
1. `hybrid_experimental` 默认不再把 `paddleocr_vl` 作为常驻候选；未显式开启时默认增强源为 `mineru_full`。
2. 可通过配置/测试证明 `enable_formula_experiment` 已透传到 candidate extractor/filter。
3. formula 仍默认 `audit-only`，不进入 merge。
4. 指定测试通过，且不回归现有 backend resolve / hybrid pipeline 行为。

## 下游动作
完成后进入 review-1 审查；通过后作为默认 Hybrid 策略与公式 shadow lane 的代码基线。

## PM 返工补充
- 本轮 PM 仲裁接受 review-1 的阻塞结论：核心实现方向成立，但 `conversion_service.py` 上存在越界改动，需返工后再提审。
- 为了让你能**清理本任务自己引入的越界改动**，现最小化补充 `conversion_service.py` 到 write_scope；但该文件本轮**仅允许用于回收** `hybrid_formula_experiment_enabled / hybrid_formula_experiment_mode` 等本任务新增的 service meta 改动，不允许继续扩展新字段或混入其他能力。
- `parser_client.py`、`hybrid_pipeline.py`、`inference_config.yaml` 与既有两份测试中的核心收口应保留：默认候选仍收口为 `mineru_full`，`enable_formula_experiment` 仍需透传到 `CandidateExtractor / CandidateFilter`，formula 仍保持 audit-only / shadow-only。
- 协作环境下不要回滚他人无关修改；若 `conversion_service.py` 中存在其他任务的既有改动，只处理你本任务为通过验收所不再需要的那部分。
- 返工完成后重新运行本任务既定测试，并在 `result.json` 中明确说明：`conversion_service.py` 仅做越界改动回收，不承载新的功能交付；最终 modified_files 需与当前 write_scope 严格一致。
