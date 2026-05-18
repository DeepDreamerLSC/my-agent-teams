# 审查说明：执行PDF转Word最终五样例总验收

## 结论

**驳回并请求补修（request_changes）。**

## 阻塞问题

### 1. 公式专项结论引用了过时证据，导致“当前状态”判断落后

当前总验收报告在公式专项部分仍然引用的是旧的 crop-manifest 评审产物：

- [final_acceptance_report.md](/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-acceptance/final_acceptance_report.md:80)
- [final_acceptance_summary.json](/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-acceptance/final_acceptance_summary.json:55)
- evidence path 也仍指向 [formula_crop_eval_report.json](/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/phase4-formula-crop-eval/review-20260517-formula-crop/formula_crop_eval_report.json:1)

所以它写出的结论还是：

- `ocr_ready_crop_count = 0`
- “真实公式 OCR / 可编辑输出尚未就绪”

但当前工作区里已经有同日更晚生成的真实实验闭环产物：

- [formula_crop_eval_report.json](/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/phase4-formula-crop-eval/20260517-174500/formula_crop_eval_report.json:1)

这份更新后的报告明确记录了：

- `generated_at = 2026-05-17T17:46:04+08:00`
- `ocr_ready_crop_count = 17`

而且 `ocr-results/` 下我本地实查是 `85` 个逐 crop 结果文件。

这不一定会改变最终默认发布建议，但会让“当前还差什么”的最终验收报告落后于同日已生成的证据。对于一份要直接给 PM / owner 作为收口输入的总验收报告，这属于阻塞问题。

建议修复：

1. 直接刷新公式专项部分，纳入 `20260517-174500` 这组真实 crop OCR 实验产物，并明确它仍然只作为 supplementary evidence。
2. 如果你坚持只引用更早、已审过的公式证据，也必须在报告里写明证据冻结点和排除更晚产物的原因，不能继续把 `ocr_ready_crop_count=0` 表述成“当前事实”。

### 2. 五样例人工抽检 checklist 不完整，缺少逐样例“答案/作答区处理”结论

instruction 对这项任务写得很明确：

- 交付物 3 要求：对 5 个样例的题号顺序、阅读顺序、图片/表格保留、公式现状、**答案/作答区处理**给出结论

但当前产物里：

- 五样例总览表只包含 “自动化结论 / 题号阅读顺序 / 图片表格 / 公式现状 / 当前判断”
  - 见 [final_acceptance_report.md](/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-acceptance/final_acceptance_report.md:89)
- 五个样例的逐段说明里，也没有把“答案/作答区处理”逐样例写出来
  - 见 [final_acceptance_report.md](/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-acceptance/final_acceptance_report.md:99)
- 只有一个聚合层面的总述：
  - 见 [final_acceptance_report.md](/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-acceptance/final_acceptance_report.md:182)
- summary.json 的 `samples[]` 结构也没有任何逐样例 `answer_area` / `option_handling` / `exercise_docx` 结论字段
  - 见 [final_acceptance_summary.json](/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-acceptance/final_acceptance_summary.json:89)

这意味着当前报告确实做了“五样例总述”，但没有把 instruction 明确要求的一个维度逐样例交付完整。

建议修复：

1. 在总览表里给每个样例补一列 `答案/作答区处理`。
2. 在 `samples[]` 中补结构化字段，例如 `answer_area_status`、`option_structure_status`、`exercise_docx_evidence`。
3. 在逐样例详情里写清楚每个样例这一项是：
   - 已正常
   - 依赖 fallback 保底
   - 代码 probe 成立但 authoritative Word 证据仍缺

## 非阻塞部分

核心主链判断本身没有被我复核出反例。我补跑了这轮自报的 32 个关键测试，结果是 `32 passed, 4 warnings`，说明这次退回的重点不是“主链不成立”，而是“最终验收报告还不够准确、也不够完整”。

返工时不需要推翻当前总体发布建议：

- `apple` 继续默认
- `hybrid_experimental` 继续 `quality` 灰度
- `formula` 继续 `audit-only`

需要修的是这份最终报告对**当前事实**的对齐，以及对**五样例人工抽检项**的补齐。
