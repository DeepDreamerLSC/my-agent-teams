# 审查说明：补齐数学试卷Paddle归档样例

## 结论

**通过（approve）。**

## 通过依据

- 上轮阻塞点已经修复：`source_dir` 不再自指向 final-archive 自身目录，而是回到“原始 model-eval 来源”语义；[README.md](/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-archive/README.md:7) 已明确区分 `source_dir` 与 `archive_dir`，并在 [README.md](/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-archive/README.md:17) 、[README.md](/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-archive/README.md:27) 和 [README.md](/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-archive/README.md:43) 反复说明 `数学试卷` 仍保留 original-run provenance gap。
- profile 级与 sample 级契约已经一致：[profile_manifest.json](/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-archive/profiles/paddleocr_vl/profile_manifest.json:5) 继续把 profile 锚定在 `20260515-112748/paddleocr_vl` 原始 run；同时 [profile_manifest.json](/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-archive/profiles/paddleocr_vl/profile_manifest.json:40) 到 [profile_manifest.json](/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-archive/profiles/paddleocr_vl/profile_manifest.json:59) 已把 `数学试卷` 收口为 `source_dir=null`、`archive_dir=<final-archive/.../数学试卷>`、`provenance_status=source_missing_archive_consumable`，并在 [profile_manifest.json](/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-archive/profiles/paddleocr_vl/profile_manifest.json:89) 到 [profile_manifest.json](/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-archive/profiles/paddleocr_vl/profile_manifest.json:94) 用 `complete_sample_count=4` 与 `archive_consumable_sample_count=5` 区分“原始来源完整度”和“当前可消费样例数”。
- 样例自身的 manifest 也保持同一语义：[source_manifest.json](/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-archive/profiles/paddleocr_vl/数学试卷/source_manifest.json:4) 到 [source_manifest.json](/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-archive/profiles/paddleocr_vl/数学试卷/source_manifest.json:23) 直接声明 `source_dir=null`、`archive_dir`、`provenance_status=source_missing_archive_consumable`，并把 remaining gap 写进说明文本。
- 聚合 manifest 也与上述口径一致：[archive_manifest.json](/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-archive/archive_manifest.json:351) 到 [archive_manifest.json](/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-archive/archive_manifest.json:354) 先定义了 profile 级语义；[archive_manifest.json](/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-archive/archive_manifest.json:386) 到 [archive_manifest.json](/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-archive/archive_manifest.json:405) 对 `数学试卷` 写入 `source_dir=null` / `archive_dir` / `provenance_status` / remaining gap；[archive_manifest.json](/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-archive/archive_manifest.json:435) 到 [archive_manifest.json](/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-archive/archive_manifest.json:440) 也把 profile 级计数调整为 `complete_sample_count=4`、`archive_consumable_sample_count=5`。
- e2e 消费路径已经和新契约对齐：[test_hybrid_e2e.py](/Users/linsuchang/Desktop/work/chiralium/backend/tests/test_hybrid_e2e.py:129) 现在优先读取 `archive_dir`，缺失时才回退 `source_dir`；[test_hybrid_e2e.py](/Users/linsuchang/Desktop/work/chiralium/backend/tests/test_hybrid_e2e.py:804) 到 [test_hybrid_e2e.py](/Users/linsuchang/Desktop/work/chiralium/backend/tests/test_hybrid_e2e.py:815) 明确断言 `数学试卷` 的 `source_dir is None`、`archive_dir` 存在且 `provenance_status=source_missing_archive_consumable`。
- Phase 3 消费结果仍稳定：[report.json](/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/phase3-paddle-quality/report.json:110) 到 [report.json](/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/phase3-paddle-quality/report.json:163) 中，`数学试卷` 仍有 `selected_pages=[1,8,9,11]`、`candidate_counts={mineru_full:27,paddleocr_vl:51}`、`fallback_pages=0`，说明契约收口后没有把当前 phase3 消费链路打断。
- 我补跑了验收测试：`PYTHONPYCACHEPREFIX=/private/tmp/chiralium-pyc /Users/linsuchang/Desktop/work/chiralium/backend/.venv/bin/pytest /Users/linsuchang/Desktop/work/chiralium/backend/tests/test_hybrid_e2e.py -q`，结果为 `6 passed, 4 warnings`。

## 说明

本轮通过并不意味着 `数学试卷` 的 original-run provenance 已补齐。相反，当前交付的价值在于把这件事讲清楚并编码进契约：

- 原始 `20260515-112748` run 下仍没有 `数学试卷` 子目录
- 因此 `source_dir` 继续保持 `null`
- 现阶段只通过 `archive_dir` 让 phase3/e2e 稳定消费
- `provenance_status=source_missing_archive_consumable` 显式保留这条剩余缺口

我本地也复核了 `/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/model-eval/20260515-112748/paddleocr_vl/数学试卷` 目录仍不存在，因此这套“诚实暴露 gap、但契约自洽可消费”的收口方式符合本轮 instruction 的新口径。
