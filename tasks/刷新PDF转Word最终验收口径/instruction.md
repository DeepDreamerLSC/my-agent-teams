# 任务：刷新 PDF 转 Word 最终验收报告口径，同步 authoritative hybrid 归档已闭合

## 任务类型
verification

## 目标
把 `final-acceptance` 总验收产物更新到最新事实：`归档Hybrid最终Word五样例` 已完成并自动收口，authoritative hybrid 最终 Word 五样例正式归档已经形成，因此此前“缺 authoritative hybrid 最终 Word 正式归档”这条 blocker 需要从最终验收报告中移除或降级为“已闭合事项”，避免阶段性结论前后不一致。

## 任务边界
- 只更新 `final-acceptance` 报告与 summary 口径，不改主链代码，不改 `final-archive` 归档内容。
- 不因为 authoritative archive blocker 闭合，就自动放宽默认发布边界。
- 报告必须同时写清：证据 blocker 已闭合 ≠ 默认发布范围已扩大。

## 输入事实
- `归档Hybrid最终Word五样例` 已完成并自动收口，关键结论：
  - `authoritative_hybrid_final_word_archive_gap_closed = true`
  - 5/5 `output.docx` 可打开
  - 4/5 样例进入最终 `word/media`
  - 2/5 样例含 table XML
  - 显式 `answer_area / answer_section` 仍为 `0/5`
  - 默认发布边界仍保持 `apple default + hybrid_experimental quality gray + formula audit-only / merge-disabled`
- 可直接引用：
  - `/Users/linsuchang/Desktop/work/my-agent-teams/tasks/归档Hybrid最终Word五样例/result.json`
  - `/Users/linsuchang/Desktop/work/my-agent-teams/tasks/归档Hybrid最终Word五样例/review.json`
  - `/Users/linsuchang/Desktop/work/my-agent-teams/tasks/归档Hybrid最终Word五样例/verify.json`
  - `/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-archive/profiles/hybrid_experimental/profile_manifest.json`
  - `/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-archive/reports/hybrid_experimental_authoritative_archive_report.json`

## 约束
- write_scope: [`/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-acceptance/`]
- read_only: false
- 依赖上游任务: 无
- target_environment: dev
- execution_mode: dev
- owner_approval_required: false
- 必须诚实表达剩余限制：显式 `answer_area` 仍 `0/5`、公式仍 audit-only、语文五年级仍 document fallback。
- 如果你认为当前还不能建议“放宽 hybrid 发布承诺”，要在报告里明确写出来。

## 交付物
1. 更新：
   - `/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-acceptance/final_acceptance_report.md`
   - `/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-acceptance/final_acceptance_summary.json`
2. 报告中至少同步以下变化：
   - authoritative hybrid 最终 Word 归档 blocker 已闭合
   - 当前已有 5/5 hybrid 最终 DOCX、4/5 `word/media`、2/5 table XML 的正式证据
   - 仍不能放宽默认发布边界的原因（answer_area 0/5、formula audit-only、收益分布不均等）
3. `result.json`：说明
   - 最终验收口径已刷新到最新事实
   - 当前是否建议单独再开“放宽 hybrid 发布承诺”评估任务

## 验收标准
1. `final-acceptance` 不再把“缺 authoritative hybrid 最终 Word 正式归档”写成当前 blocker。
2. 报告与 summary 同步到同一口径，不互相冲突。
3. 结论能直接回答：当前 blocker 已闭合后，发布边界是否变化；如果不变，要说清原因。
4. 不改主链代码，只刷新验收结论产物。

## 下游动作
完成后进入 review-1 审查；通过后作为最新阶段性收口/发布边界结论。
