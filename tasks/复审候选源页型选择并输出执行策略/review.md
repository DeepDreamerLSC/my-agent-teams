# Review

结论：`approve`

这次交付满足任务目标。`P1候选源页型选择策略.md` 和 `source_selection_strategy.json` 都已经把结论从“总量判断”收敛成了可执行的页型策略，明确区分了：

- 哪些页型默认优先 `mineru_full`
- 哪些页型只在 `selected pages / crops` 触发 `paddleocr_vl`
- 哪些场景保留 `baseline/document fallback`
- 哪些内容继续维持 `formula audit-only / merge-disabled`

我额外做了几轮独立核对，不只看 `result.json`：

- `source_selection_strategy.json` 可正常解析。
- 从 `final-archive/profiles/mineru_full/*/pages.jsonl` 与 `final-archive/profiles/paddleocr_vl/*/pages.jsonl` 直接按 `kind` 聚合后，策略中的 inventory 总量能复算对齐：
  - MinerU：`image=48`、`table=8`、`formula_candidate=18`
  - Paddle：`image=165`、`table=23`、`formula_candidate=9`
- 从 `hybrid-e2e-validation/*/hybrid-pages.jsonl` 中按 `source_profile + merge_action=accepted_candidate` 复算后，策略中的 accepted 总量也对齐：
  - MinerU：`image=25`、`table=3`
  - Paddle：`image=5`、`table=2`
  - formula accepted 仍都是 `0`
- `phase3-paddle-quality/report.json` 中的 Paddle selected pages 与策略矩阵一致：
  - 五下科学：`4,5`
  - 数学八年级：`7`
  - 数学试卷：`1,8,9,11`
  - 英语八年级：`1,4`
  - 语文五年级：空
- `hybrid_experimental_authoritative_archive_report.json` 与 `hybrid-e2e-validation/report.json` 中的 fallback 分布也与策略矩阵一致，尤其 `语文五年级` 继续保留 document fallback，没有被错误包装成可增强正样例。

非阻塞上下文：

- `paddleocr_vl/数学试卷` 的 inventory 依赖 final-archive 中通过 `archive_dir` 回填的样例，而不是原始 `20260515-112748` run；这条 provenance gap 目前已在 archive manifest / README 中保留，后续引用该样本时也应一并保留。
- 当前策略已经足够作为 P1 开发拆分依据，但更细的 per-source rejected/fallback 明细仍应按文中 execution task 落到正式 merge audit 里。
