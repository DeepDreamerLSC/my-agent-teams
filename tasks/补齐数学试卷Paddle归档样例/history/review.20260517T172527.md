# 审查说明：补齐数学试卷Paddle归档样例

## 结论

**驳回并请求补修（request_changes）。**

## 阻塞问题

当前结果确实做成了两件事：

- `phase3-paddle-quality/数学试卷/` 已刷新到不再是纯 artifact gap，`paddleocr_vl` 候选数变为 `51`
- `backend/tests/test_hybrid_e2e.py` 回归通过，说明当前回填目录已能被 Phase 3 / e2e 链路稳定消费

但这轮任务的核心目标不是“让 report 和 e2e 变绿”，而是补成 **可追溯归档闭环**。这一点仍然没有完成。

### 具体阻塞点

`final-archive/README.md` 明确写着：

- `source_manifest.json` 用来记录“原始来源”
- 本次归档优先使用 `artifacts/pdf2word/model-eval/` 内的原始 runner 产物作为归档来源

但当前 `数学试卷` 的 provenance 写法是：

- [source_manifest.json](/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-archive/profiles/paddleocr_vl/数学试卷/source_manifest.json:4) 把 `source_dir` 写成了 `final-archive/profiles/paddleocr_vl/数学试卷` 自身目录
- [profile_manifest.json](/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-archive/profiles/paddleocr_vl/profile_manifest.json:4) 仍把整个 profile 锚定在 `run_label=20260515-112748` 的 `model-eval/.../paddleocr_vl`
- 但同一个 [profile_manifest.json](/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-archive/profiles/paddleocr_vl/profile_manifest.json:39) 又把 `数学试卷.source_dir` 改写成 final-archive 自身目录
- [result.json](/Users/linsuchang/Desktop/work/my-agent-teams/tasks/补齐数学试卷Paddle归档样例/result.json:93) 还明确承认 `original_run_level_provenance_complete = no`

这说明当前解决的是：

- “让 phase3/e2e 能消费这套回填文件”

而没有解决：

- “这套文件到底来自哪一次真实可复核的原始运行”

换句话说，`source_dir` 被拿来表示“当前消费目录”，而不是 README 契约里的“原始来源目录”。这会把 provenance 语义混淆掉。

### 为什么这是阻塞问题

instruction 已经写得很明确：

- 如果当前文件无法证明来自真实可复核运行，**不能直接当作 done**
- 验收标准 1 要求的是“不再只是有零散文件但不可追溯，而是形成可复核的 Paddle profile 归档闭环”

而当前交付自己也承认：

- 只能证明 `final-archive/profiles/paddleocr_vl/数学试卷` 这套回填产物可被 phase3/e2e 稳定消费
- **无法回指到最初 `20260515-112748` model-eval 运行目录**

因此，按当前任务口径，这轮还不能以 `done` 收口。

## 我复核到的真实状态

- 已成立的部分：
  - `phase3-paddle-quality/数学试卷/profile-audits.json` 已刷新为 `candidate_count=51`
  - 总 [report.json](/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/phase3-paddle-quality/report.json) 中 `数学试卷` 不再停留在旧的 artifact gap 口径
  - `pytest /Users/linsuchang/Desktop/work/chiralium/backend/tests/test_hybrid_e2e.py -q` 实测 `6 passed`
- 仍未成立的部分：
  - `source_manifest.json` 没有提供可回指原始 run 的真实来源
  - `profile_manifest.json` 对 `数学试卷` 混用了“原始 run 标签”和“final-archive 自指 source_dir”两套语义
  - `result.json` 在承认 `partial_provenance_gap` 的同时，又把任务总结写成“provenance/manifest/report 闭环已补齐”，口径前后不一致

## 建议修复

1. 不要继续把 `source_dir=final-archive/.../数学试卷` 当作 provenance 已闭环的证明。
2. 二选一处理：
   - 真正补出可回指的 provenance 证据，并按契约写入 manifest
   - 或者保留“原始来源仍缺失”的事实，把任务状态和 summary 调整为未完成闭环，而不是 `done`
3. 如果 owner 决定接受新的降级口径，即“只要求 Phase 3 / e2e 可稳定消费回填样例”，那应先显式修改任务验收，再统一调整 README / manifest 契约，而不是在现有契约下直接把回填目录冒充原始来源。

## 非阻塞部分

这轮对 `phase3-paddle-quality` 的刷新和 `test_hybrid_e2e.py` 的 overlay 回归断言本身是有价值的，建议返工时保留，不要回退。需要修的核心只有 provenance 语义与任务状态口径。
