# Review - 归档Hybrid最终Word五样例

## Verdict

`approve`

`final-archive/profiles/hybrid_experimental/` 已经形成可直接复核的 authoritative 五样例最终 Word 归档。5 个样例目录齐备，逐样例都能看到 `output.docx`、`pages.jsonl`、`metrics.json`、`warnings.json`、`validator-report.json`、`source_manifest.json`；5/5 `output.docx` 也都通过了 zip 完整性校验。

## Evidence

- 归档 `pages.jsonl` 与源 `hybrid-e2e-validation/*/hybrid-pages.jsonl` 做了 5/5 `cmp -s`，全部一致，说明 merged pages provenance 口径成立。
- 专项报告里的核心统计与 DOCX 实体一致：`word/media` 分别为 `4 / 0 / 2 / 1 / 20`；只有 `五下科学`、`数学八年级` 含表格 XML。
- `profile_manifest.json`、逐样例 `source_manifest.json`、专项 report 都诚实写明：源套件不是 timestamped model-eval run，且 `output.docx / metrics.json / warnings.json` 是在 `final-archive` 内基于 authoritative pages 现算生成，不是假装成源 run 直接产物。
- `final_acceptance` 之前明确剩余唯一 broader-release blocker 就是“缺 authoritative 的五样例 hybrid 最终 Word 正式归档”；这次归档补齐后，继续保持 `apple default + hybrid_experimental quality gray + formula audit-only / merge-disabled` 的发布边界，是自洽的。

## Non-blocking Notes

- `archive_manifest.json` 的 `reports` 索引还没有把 `hybrid_experimental_authoritative_archive_report.{json,md}` 显式列进去，且 `report_file_count=8` 与当前 `reports/` 目录实际文件数不一致。建议后续顺手校正。
- `README.md` 顶部“仅复制现有产物”的总述对 `hybrid_experimental` 不够精确，因为该 profile 的最终 `output.docx / metrics.json / warnings.json` 实际是在归档目录内生成的。后续可把这句改成更细的 provenance 描述。
