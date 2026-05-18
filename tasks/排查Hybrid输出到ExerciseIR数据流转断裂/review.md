# 审查说明：排查Hybrid输出到ExerciseIR数据流转断裂

## 结论

**审查通过（approve）。**

这轮和上一条被驳回的任务不同，已经不是“渲染器能处理合成 payload”，而是**真实 `HybridExperimentalPipeline` 产物已经能走进 ExerciseIR 和最终 Word**。

## 通过依据

- 我复跑了 `test_pdf_exercise_detector.py`、`test_pdf_exercise_docx_assembler.py`、`test_pdf_to_word_exercise_pipeline_integration.py`，全部通过。
- 更关键的是，我没有只信 `result.json`，而是直接用当前工作树里的 `tests.test_hybrid_e2e._run_pipeline(enable_enhancement=True)` 拉起真实 hybrid 样例，再把 `result.pages` 喂给 `detect_exercise_document()` 和 `assemble_exercise_docx_bytes()`。
- 这条复验链路下：
  - `数学试卷` 得到 `drawing_count=20`、`media_count=20`
  - `英语八年级` 得到 `drawing_count=2`、`media_count=2`
- 这说明 accepted visual candidates 已经不是停在审计文件里，而是真的进了 DOCX 主链路。

## 结果解释

- `数学试卷` 当前真实 hybrid 结果里有 21 个 accepted image blocks，其中 20 个最终体现在 DOCX 的 drawing/media 上；这已经满足任务验收里“DOCX 中能看到插入的 image/table（media_count>0）”的要求。
- `英语八年级` 当前真实 hybrid 结果里有 1 个 accepted image 和 1 个 accepted table。这个 table 的上游 meta 只有 `image_path`，没有 `table_html` 或 `table_rows`，所以 DOCX 侧按图片 fallback 落盘，最终表现为 `media_count=2`、`has_table_xml=false`。这和 `result.json` 里的说明一致，不是本轮回归。
- 纯 baseline 路径的 integration test 也通过了，没有看到既有文本/公式/选项结构化输出退化。

## 非阻塞提醒

当前 visual payload 仍然是通过 `ContentBlock.__post_init__()` + `inspect.stack()` 注入的，这个契约偏脆弱。它在当前链路下已经可用，但长期看最好还是把 image/table 的 payload 显式放进 ExerciseIR 契约层，并补一条专门覆盖真实 hybrid visual 输入的回归测试。

## 总结

这条任务已经完成了它该完成的事情：根因定位清楚，真实 hybrid visual blocks 已经进入 ExerciseIR，并且在真实样例 DOCX 里出现了可见输出。因此本轮给 `approve`。
