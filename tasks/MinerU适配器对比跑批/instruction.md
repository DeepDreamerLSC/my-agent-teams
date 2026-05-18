# 任务：MinerU 适配器对比跑批

## 任务类型
development（评估执行）

## 目标
MinerU 适配器完成后，用与 apple_baseline 相同的 5 个样例跑 `mineru` profile，生成对比数据。

## 任务边界
- 依赖 `MinerU本地Adapter接入PDF转Word` 任务完成（MinerU 适配器已可用）
- 不修改框架代码
- 输出结果到 artifacts 目录，与 apple_baseline 基线并列

## 输入事实
- 横评框架：`/Users/linsuchang/Desktop/work/chiralium/backend/app/services/pdf_to_word/model_eval_runner.py`
- MinerU 适配器：由 `MinerU本地Adapter接入PDF转Word` 任务产出
- apple_baseline 基线数据：由 `跑apple_baseline真实样例基线数据` 任务产出
- 样例目录：`/Users/linsuchang/Desktop/work/chiralium/example/扫描件 `（注意末尾空格）
- 5 个样例 PDF（与基线相同）：
  1. `数学 八年级下册pdf.pdf` — 双栏数学教材
  2. `数学试卷.pdf` — 试卷
  3. `英语 八年级下册.pdf` — 含图表
  4. `语文五年级.pdf` — 单栏中文
  5. `五下科学.pdf` — 含实验图/表格

## 约束
- write_scope: artifacts 输出目录
- 必须等 MinerU 适配器任务完成后再开始
- 样例路径中的目录名末尾有空格，需正确处理
- 如果某个样例运行失败，记录错误并继续下一个

## 交付物
1. 运行结果：`artifacts/pdf2word/model-eval/<timestamp>/mineru/<sample>/` 下每个样例包含：
   - `pages.jsonl`、`metrics.json`、`warnings.json`、`output.docx`
2. 对比报告 `artifacts/pdf2word/model-eval/<timestamp>/comparison_report.json`：
   - 每个样例的 apple_baseline vs mineru 关键指标对比
   - 题号序列对比（漏题、重复、乱序）
   - block_count / image_candidate_count / formula_candidate_count 对比
   - 耗时对比
   - 结论：mineru 在哪些样例上优于/劣于 apple_baseline

## 验收标准
1. MinerU 适配器 `is_available()` 返回 True 后才执行跑批
2. 5 个样例全部跑完（失败也记录）
3. 每个样例都有完整的 pages.jsonl、metrics.json、output.docx
4. comparison_report.json 包含逐样例的 apple_baseline vs mineru 对比
5. 报告中有明确结论：mineru 是否在 ≥3/5 样例上显著优于基线

## 下游动作
对比报告将提交给 PM 和 arch-1 评审，决定 MinerU 是否替换/增强当前 parser。如果 MinerU 优于基线，后续将进入 `parser_backend=hybrid` 或替换主 parser。
