# 任务：扩展 Hybrid 指标与审计产物

## 任务类型
开发

## 目标
为 hybrid_experimental 管线输出完整的审计产物，便于人工抽检和后续 Phase 2 的 review 触发决策。

## 任务边界
- 输出到 `artifacts/pdf2word/hybrid-phase1/` 目录
- 不修改 hybrid_pipeline.py（由前置任务处理）
- 只读取管线输出并格式化

## 输入事实
- 当前管线只输出 hybrid-pages.jsonl 和 validator-report.json
- 缺少：原始候选汇总、过滤决策、合并决策的独立审计文件
- 架构师方案要求：candidates.raw/filtered、merge-decisions、validator-report 完整落盘

## 约束
- write_scope: `artifacts/pdf2word/hybrid-phase1/`
- 前置依赖：`实现HybridMVP图片表格并回链路` 完成
- 产物格式必须可被后续 review worker 消费

## 交付物
- `artifacts/pdf2word/hybrid-phase1/` 下的完整审计产物：
  - `candidates.raw.jsonl`：每个样例的原始候选列表
  - `candidates.filtered.jsonl`：过滤后的候选列表
  - `merge-decisions.jsonl`：每个候选的合并/跳过决策及原因
  - `validator-report.json`：页级 validator 结果
  - `metrics-summary.json`：汇总指标

## 验收标准
1. 5 个横评样例各有完整的审计产物
2. candidates.raw 数量 >= candidates.filtered 数量
3. merge-decisions 中每条记录有 decision（accept/skip/fallback）和 reason
4. metrics-summary 包含 accepted_candidate.question_id 完整率、bad_merge_rate、validator_fallback_rate

## 下游动作
产物供人工抽检和 Phase 2 review 触发策略参考。
