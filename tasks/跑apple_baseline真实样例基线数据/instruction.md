# 任务：跑 apple_baseline 真实样例基线数据

## 任务类型
development（评估执行）

## 目标
用已搭建的 `model_eval_runner.py` 对 5 个真实 PDF 样例跑 `apple_baseline` profile，输出基线指标数据，作为后续模型对比的对照基准。

## 任务边界
- 不修改框架代码（model_eval_runner.py、parser_adapters/）
- 只运行 apple_baseline profile
- 输出结果到 artifacts 目录

## 输入事实
- 横评框架：`/Users/linsuchang/Desktop/work/chiralium/backend/app/services/pdf_to_word/model_eval_runner.py`
- 适配器：`/Users/linsuchang/Desktop/work/chiralium/backend/app/services/pdf_to_word/parser_adapters/`
- 样例目录：`/Users/linsuchang/Desktop/work/chiralium/example/扫描件 `（注意末尾空格）
- 5 个样例 PDF：
  1. `数学 八年级下册pdf.pdf`（8 页，1.1MB）— 双栏数学教材，含公式
  2. `数学试卷.pdf`（12 页，7.1MB）— 试卷，含公式/表格/多栏
  3. `英语 八年级下册.pdf`（12 页，3.3MB）— 含图表/图片
  4. `语文五年级.pdf`（13 页，5.0MB）— 单栏为主，中文文本密集
  5. `五下科学.pdf`（6 页，1.6MB）— 含实验图/表格

## 约束
- write_scope: artifacts 输出目录
- 样例路径中的目录名末尾有空格，需正确处理
- 如果某个样例运行失败，记录错误并继续下一个，不要中断整个批次

## 交付物
1. 运行结果目录：`artifacts/pdf2word/model-eval/<timestamp>/apple_baseline/<sample>/` 下每个样例包含：
   - `pages.jsonl` — 每页 PageIR
   - `metrics.json` — 耗时、内存、block 统计
   - `warnings.json` — 警告列表
   - `output.docx` — 生成的 Word 文件
2. 基线摘要报告 `artifacts/pdf2word/model-eval/<timestamp>/apple_baseline/baseline_summary.json`，包含：
   - 每个样例的题号序列（从 pages.jsonl 中提取）
   - 每个样例的 block_count / image_candidate_count / formula_candidate_count
   - 每个样例的 total_seconds / per_page_seconds
   - 失败样例列表（如有）

## 验收标准
1. 5 个样例全部跑完（失败也要记录，不能跳过）
2. 每个样例都有 pages.jsonl、metrics.json、output.docx
3. baseline_summary.json 汇总了所有样例的关键指标
4. metrics 中记录了真实耗时数据（不是 mock 数据）

## 下游动作
完成后基线数据将用于：GLM-OCR 适配器跑批对比、MinerU 适配器跑批对比。PM 将基于基线数据判断当前 apple_baseline 的真实质量水平。
