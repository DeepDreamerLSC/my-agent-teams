# 任务：集成 Qwen3-VL review 到 hybrid 管线

## 任务类型
development

## 目标
在 HybridExperimentalPipeline 中集成 Qwen3-VL review worker，只处理 ambiguous candidate（归属不确定的候选），实现 review 指标。

## 任务边界
- 新增 review_integrator.py
- 复用 Qwen3-VL strict review prompt（已改造）和 VLMReviewAdapter
- 只在 ambiguous candidate 上触发 review
- JSON 失败时 drop candidate，不影响页面

## 输入事实
- Qwen3-VL review worker 已改造为 strict review JSON（page_review/issues）
- 当前 json_valid_rate 约 40%（模型能力边界，非代码问题）
- Qwen3-VL 服务：127.0.0.1:18111，模型路径 /Users/linsuchang/Desktop/work/models/qwen3-vl-8b-3bit
- Python 3.12 venv：/Users/linsuchang/Desktop/work/chiralium/.venv-mlx/
- HybridExperimentalPipeline 已有扩展点
- CandidateFilter 已实现，ambiguous candidate 有标记

## 约束
- write_scope 以 task.json 为准
- review worker 只处理 ambiguous candidate，不处理已确定的候选
- JSON 解析失败时 drop 该 candidate，不能影响整页
- review 结果不影响 baseline 正文 blocks
- 如果 Qwen3-VL 服务不可用，跳过 review 步骤不报错

## 交付物
1. review_integrator.py：ReviewIntegrator 类
2. 测试文件：test_review_integrator.py
3. result.json 包含 review 指标

## 验收标准
1. ambiguous candidate 触发 review
2. review 结果能影响候选采纳/拒绝决策
3. JSON 解析失败时 drop candidate 不崩溃
4. 服务不可用时优雅跳过
5. 新增指标：review_acceptance_rate、json_valid_rate
6. 测试通过

## 下游动作
完成后 hybrid_experimental 管线全部组件就绪，可做端到端集成测试。
