# 审查说明：预整理Hybrid回归抽检模板

## 结论

**驳回并请求补修（request_changes）。**

## 为什么驳回

这份模板的骨架基本已经搭好了，方向是对的：

- 有正样例 / 负样例分组
- 有逐页 7 步检查流程
- 覆盖了顺序/题号、candidate/fallback、ExerciseIR、DOCX、online review worker 五类检查项
- 有逐样例 JSON 模板、汇总模板和 checklist

问题不在结构，而在**文档里混入了已经过时的运行事实**。这会直接误导后续正式 QA。

最明显的两处：

- 文末仍写“5 个样例共 51 页全部 fallback_to_baseline=true”
- 文末仍写“当前 review_mode=skipped_no_review_worker”

但当前真实 `artifacts/pdf2word/hybrid-e2e-validation/report.json` 已经不是这个状态：

- 顶层 `review_mode=online_review`
- 样例级 fallback 也不是“全部 fallback”
  - 五下科学：1 页
  - 数学八年级：0 页
  - 数学试卷：0 页
  - 英语八年级：2 页
  - 语文五年级：13 页

所以它现在还不能被当作“正式 QA 只需补结论即可复用”的可靠骨架。

## 建议怎么修

不需要推翻结构，直接做小范围修正即可：

1. 删掉或改写所有把“当前现状”写死为旧状态的句子。
2. 保留 Step 7 的在线 review worker 指标栏目，但不要再写“当前为 skipped_no_review_worker”这类已经失效的说明。
3. 第 6 节“已知限制与注意事项”要改成稳定表述，只保留真正长期有效的限制，不要把会随报告变化的运行时状态硬写进去。

## 总结

结构已经接近可用，问题主要是旧事实残留。修掉这些过期现状描述后，这份模板就可以作为正式《补齐Hybrid回归样例与人工抽检流程》任务的前置输入。
