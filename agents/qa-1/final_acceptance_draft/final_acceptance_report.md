# PDF 转 Word 最终五样例总验收报告

- 任务 ID：`执行PDF转Word最终五样例总验收`
- 验收时间：`2026-05-17T17:55:53+08:00`
- 验收角色：`qa-1`

## 1. 一句话结论

可以把当前 PDF 转 Word 认定为“**阶段性端到端完成**”，但这个结论有明确边界：

- **可认定完成的范围**：`apple` 默认主链 + 显式 `hybrid_experimental / quality` 增强链路，五样例均已有自动化闭环与回退保护。
- **默认发布建议**：继续保持 `apple` 为默认同步路径；`hybrid_experimental` 继续只在 `quality` / 灰度下显式开启。
- **不建议现在放开的范围**：不建议把 `hybrid_experimental` 放成更广泛默认，更不建议把公式能力视为已上线能力。

## 2. 证据与方法

本次总验收同时使用了四类证据：

1. 自动化回归
   - `pytest tests/test_hybrid_e2e.py tests/test_hybrid_backend_resolve.py tests/test_hybrid_pipeline.py tests/test_question_region_detector.py tests/test_hybrid_validator.py tests/test_pdf_to_word_exercise_pipeline_integration.py tests/test_pdf_exercise_docx_assembler.py -q`
   - 结果：`32 passed, 5 warnings`
   - warnings 为既有 `FastAPI on_event` 弃用告警与 `pytest cache` 写权限告警，无新增功能性失败。
2. 现有验收产物
   - `artifacts/pdf2word/hybrid-e2e-validation/report.json`
   - `artifacts/pdf2word/phase3-paddle-quality/report.json`
   - `artifacts/pdf2word/phase4-formula-baseline/summary.json`
   - `artifacts/pdf2word/phase4-formula-crop-eval/review-20260517-formula-crop/formula_crop_eval_report.json`
3. 人工抽检
   - 核对五样例 `apple_baseline` 归档 DOCX 可打开性与文本线性化结果。
   - 逐样例核对 `hybrid-pages.jsonl` / `validator-report.json` 的顺序、fallback、图片/表格候选接受情况。
4. 当前代码态 probe
   - 实时检查 review worker：
     - `GET http://127.0.0.1:18111/health` → `healthy`
     - `GET http://127.0.0.1:18111/v1/models` → `mlx-community/Qwen3-VL-8B-Instruct-3bit`
   - 用当前代码把真实 `hybrid-pages.jsonl` 送入 `exercise_detector + exercise_docx_assembler`，验证图片/表格能否真正进入 Word。

## 3. 自动化总体验收结论

### 3.1 Hybrid 主链闭环

- `hybrid-e2e-validation/report.json` 生成时间为 `2026-05-17T02:13:57.602315+08:00`。
- 关键指标：
  - `sample_count = 5`
  - `pass_through_all_equal = true`
  - `enhancement_chain_sample_count = 4`
  - `fallback_triggered_sample_count = 3`
  - `review_mode = online_review`
- `online_review_probe.metrics` 已在既有报告中达到：
  - `json_valid_rate = 1.0`
  - `review_acceptance_rate = 1.0`
  - `service_available = true`

结论：`baseline -> question_region -> candidate -> merge -> validator -> fallback -> review probe` 这条增强主链已经闭环，不再停留在骨架或占位阶段。

### 3.2 当前代码态关键回归

- 本轮复跑的 32 个关键测试全部通过，覆盖：
  - Hybrid e2e
  - Hybrid backend resolve
  - Hybrid pipeline
  - Question region detector
  - Hybrid validator
  - Exercise pipeline integration
  - Exercise DOCX assembler

结论：当前代码态与既有验收产物没有出现新的主链回归。

### 3.3 Paddle 与 Formula 专项信息

- `phase3-paddle-quality/report.json` 生成时间：`2026-05-17T16:15:22.290529+08:00`
  - `total_selected_pages = 9`
  - `paddle_candidate_count = 61`
  - `mineru_candidate_count = 57`
  - `fallback_triggered_sample_count = 3`
- `phase4-formula-baseline/summary.json` 生成时间：`2026-05-17T10:38:30+08:00`
  - `formula_candidate_count = 18`
  - 覆盖 3 个样例、9 个 focus pages
  - 默认策略仍为 `formula_candidate_merge_default = false`
- `phase4-formula-crop-eval` 评审产物生成时间：`2026-05-17T12:21:38+08:00`
  - `manifest_ready_crop_count = 17`
  - `ocr_ready_crop_count = 0`

结论：Paddle 已形成选择性增强证据，但仍不是应当默认常驻的候选来源；公式资产已可审计，但真实 OCR/可编辑输出尚未就绪。

## 4. 五样例人工抽检与逐样例结论

### 4.1 五样例总览

| 样例 | 自动化结论 | 题号/阅读顺序 | 图片/表格 | 公式现状 | 当前判断 |
|---|---|---|---|---|---|
| 五下科学 | 6 页中 5 页 valid，1 页 fallback | 第 1 页发现 `wrong_order`，已自动回退；其余页可用 | Hybrid 接受 8 个候选，含 image/table；ExerciseIR→DOCX probe 产出 `4` 个 media 且含 table XML | `mineru_full` 有 3 个公式候选，但默认 audit-only | 正样例，可继续灰度 |
| 语文五年级 | 13/13 页 fallback，document fallback=true | 不做增强判定，整体保 baseline | 无接受的 image/table 候选 | 无公式收益 | 负样例，主链可运行但无增强收益 |
| 数学八年级 | 8/8 页 valid，无 fallback | 顺序可用 | Hybrid 接受 5 个候选，含 image/table；probe 产出 `2` 个 media 且含 table XML | `mineru_full` 有 14 个公式候选，但默认 audit-only | 正样例，可继续灰度 |
| 英语八年级 | 12 页中 10 页 valid，2 页 fallback | 第 3/11 页发现 `wrong_order`，已自动回退 | 仅接受 1 个 image 候选，收益有限 | 1 个公式候选，默认 audit-only | 正样例，但增强收益有限 |
| 数学试卷 | 12/12 页 valid，无 fallback | 顺序可用 | Hybrid 接受 21 个 image 候选；probe 产出 `20` 个 media | 公式不是当前主收益 | 图片密集样例收益最大，但 Paddle provenance 仍未闭环 |

### 4.2 逐样例详情

#### 五下科学

- 自动化：
  - `fallback_pages = [1]`
  - `appended_pages = [3, 4, 5]`
  - `accepted_candidate_total = 8`
- 抽检判断：
  - 第 1 页因题号顺序问题触发回退，说明回退保护生效。
  - `hybrid-pages.jsonl` 中出现 `image=5`、`table=3`。
  - 当前代码 probe 可产出 `4` 个 `word/media/*`，并包含 table XML。
- 结论：这是“增强有效但必须保留 page fallback”的代表样例。

#### 语文五年级

- 自动化：
  - `fallback_pages = 1..13`
  - `candidate_count = 0`
  - `document_fallback = true`
- 抽检判断：
  - 属于当前 `question_region_not_detectable / no enhancement context` 类型。
  - baseline 文本链路可运行，但该样例不应被当作增强成功样例。
- 结论：是有效的负样例，证明系统会保守回退，而不是硬做错误增强。

#### 数学八年级

- 自动化：
  - `fallback_pages = []`
  - `appended_pages = [2, 6, 7]`
  - `accepted_candidate_total = 5`
- 抽检判断：
  - `hybrid-pages.jsonl` 中出现 `image=3`、`table=2`。
  - 当前代码 probe 可产出 `2` 个 `word/media/*`，并包含 table XML。
  - 公式候选较多（14 个），但当前仍全部停留在 audit-only。
- 结论：图片/表格增强有效，公式仍不应计入已发布能力。

#### 英语八年级

- 自动化：
  - `fallback_pages = [3, 11]`
  - `appended_pages = [4]`
  - `accepted_candidate_total = 1`
- 抽检判断：
  - 增强收益明显低于数学试卷/五下科学。
  - 题号顺序异常页已被 validator + fallback 吃掉，没有把错误增强带入最终结果。
- 结论：说明当前 Hybrid 不是“所有样例都显著增益”，更适合作为显式 quality 模式。

#### 数学试卷

- 自动化：
  - `fallback_pages = []`
  - `appended_pages = [1, 5, 7, 8, 9, 10, 11]`
  - `accepted_candidate_total = 21`
- 抽检判断：
  - `hybrid-pages.jsonl` 中出现 `image=21`，是图片密集样例收益最高的一组证据。
  - 当前代码 probe 可产出 `20` 个 `word/media/*`。
  - `phase3-paddle-quality/report.json` 显示该样例 `paddleocr_vl = 51`、`mineru_full = 27`，Paddle 在该类页面上确有增益潜力。
  - 但该样例仍存在 `paddleocr_vl` provenance / manifest / 报告契约未完全收口问题。
- 结论：这是继续保留质量灰度价值的核心样例，但还不足以支撑更大范围默认放开。

## 5. 对“图片/表格/公式/作答区”的专项判断

### 5.1 图片与表格

- 当前 authoritative 归档中的 `apple_baseline` 五份 DOCX 均可正常打开，但 `5/5` 均无 `word/media/`。
- 这说明当前归档中的默认发布证据仍以“文本线性化”结果为主，不是“已经正式归档的图片/表格保留版 Word”。
- 但本轮 probe 证明：基于真实 `hybrid-pages.jsonl`，当前代码的 `ExerciseIR -> exercise_docx_assembler` 已能在至少 3 个正样例中产出真实 `word/media/*` 和 table XML。

结论：

- **可以认定**：当前代码链路已经具备把 accepted image/table 候选带入 Word 的能力。
- **不能直接认定**：现有五样例“正式归档、可发布”的最终 Word 产物已经全部完成了图片/表格保留的验收闭环。

### 5.2 公式

- 公式候选已收集到 18 个，但默认策略仍是：
  - `formula_candidate_extracted = true`
  - `formula_candidate_merge_default = false`
- crop eval 结果中：
  - `manifest_ready_crop_count = 17`
  - `ocr_ready_crop_count = 0`

结论：公式能力当前只能记为“审计资产已补齐、默认发布仍关闭”；真实公式 OCR 结果仍在并行推进，只能作为 `in-flight supplementary evidence`，不能记为本轮默认发布已完成能力。

### 5.3 答案 / 作答区

- `tests/test_pdf_to_word_exercise_pipeline_integration.py` 与 `tests/test_pdf_exercise_docx_assembler.py` 已通过，说明结构化题目、选项、作答区、可编辑公式的下游链路没有崩。
- 但当前五样例 authoritative 归档 DOCX 仍以 page text 线性化为主，缺少一份正式的“五样例 Hybrid 最终 Word 归档”来做同口径人工验收。

结论：作答区处理在代码和测试层可视为已闭环，但在“五样例正式归档 Word”口径上仍缺最终发布证据。

## 6. 分层结论

### 6.1 已可视为阶段性完成的能力

1. `apple` 默认主链可稳定产出五样例 Word。
2. `hybrid_experimental` 的增强编排、validator、page fallback、review worker、ExerciseIR/DOCX 下游路径已经全部打通。
3. 五样例中 4 个样例存在可验证增强链路，1 个负样例能保守回退，不会把不可判定页面强行增强。

### 6.2 known gap，但不阻塞当前主链的事项

1. `语文五年级` 在当前规则下仍是 document fallback / no enhancement context。
2. 公式仍处于 `audit-only`，并行中的公式 OCR 结果只作为 supplementary evidence，不计入本轮默认发布判断。
3. 英语八年级增强收益有限，说明 Hybrid 适合作为 quality 模式而不是普适默认。

### 6.3 仍阻塞“更大范围默认发布 / 放开 Hybrid 默认”的事项

1. 五样例缺少一份 authoritative、正式归档的 `hybrid` 最终 Word 发布证据；当前 `apple_baseline` 归档 5/5 无 `word/media/`。
2. `数学试卷` 的 `paddleocr_vl` provenance / manifest / phase3 报告契约还未完全收口，影响图片密集样例的证据强度。
3. 公式专项仍处于 `in-flight / supplementary evidence`，当前不影响阶段性主链收口，但不能进入本轮默认发布承诺。

## 7. 默认发布建议

### 7.1 建议采纳

1. **继续 `apple` 作为默认同步路径。**
2. **继续保留 `hybrid_experimental` 为显式 `quality` / 灰度能力。**
3. **继续保持 `formula` 为 `audit-only / shadow-only`。**

### 7.2 不建议现在采纳

1. 不建议把 `hybrid_experimental` 放成 `auto` 或更广泛默认。
2. 不建议把 `paddleocr_vl` 恢复为默认常驻候选。
3. 不建议把“图片/表格已在最终发布 Word 中稳定保留”写成已完成事实，除非先补齐 authoritative final artifact。

## 8. 建议 PM / Owner 的下一步

1. 以当前报告作为“阶段性收口通过”结论，允许继续 `apple default + hybrid quality gray`。
2. 新开一个更小的“Hybrid 最终 Word 五样例正式归档”任务，把当前已可工作的 image/table 落 Word 证据做成 authoritative 发布产物。
3. 单独收口 `数学试卷` Paddle provenance / manifest / phase3 报告问题。
4. 公式继续独立推进，不要并入当前默认发布门禁。
