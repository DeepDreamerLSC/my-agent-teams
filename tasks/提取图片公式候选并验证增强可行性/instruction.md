# 任务：提取图片公式候选并验证增强可行性

## 任务类型
development（数据分析 + 可行性验证）

## 目标
从已有 PaddleOCR-VL 和 MinerU 评测数据中提取图片/公式候选，与 apple_baseline PageIR 做离线合并，评估增强候选的质量和归属准确率。

## 任务边界
- 只读取已有评测 artifacts，不重新跑模型
- 不修改框架代码
- 产出分析报告到 `design/pdf2word/`

## 输入事实
- 评测数据路径（都在 /Users/linsuchang/Desktop/work/chiralium/ 下）：
  - apple_baseline：artifacts/pdf2word/model-eval/20260514-144102/apple_baseline/
  - MinerU lite：artifacts/pdf2word/model-eval/20260514-170529/mineru/
  - MinerU full：artifacts/pdf2word/model-eval/20260515-090642/mineru/
  - PaddleOCR-VL：artifacts/pdf2word/model-eval/20260515-112748/paddleocr_vl/
- 每个样例目录下有：pages.jsonl、metrics.json、warnings.json、output.docx
- 横评数据：baseline 图片/公式=0，MinerU 48图+18公式，PaddleOCR-VL 48图+10表格
- 5 个样例（PaddleOCR-VL 缺数学试卷）

## 分析要求

### 1. 候选提取
- 从 pages.jsonl 中提取图片/公式/表格候选 block
- 记录：page_index、bbox、block_kind、content、confidence

### 2. 归属匹配
- 候选与 baseline 同页题号做 bbox 空间匹配
- 判断归属题目，统计归属成功率

### 3. 增强模拟
- 模拟候选插入 baseline PageIR
- 评估：插入后题干是否被打断、图片位置是否合理

### 4. 可行性报告
- 逐样例分析，候选质量评级（可用/需修正/不可用）
- 合并策略建议（给 arch-1 hybrid 管线设计提供输入）

## 交付物
### 可行性报告：`design/pdf2word/图片公式候选增强可行性报告.md`
1. 候选统计（样例 × 模型 × block_kind）
2. 归属匹配结果
3. 增强模拟结论
4. 合并策略建议

## 约束
- write_scope 以 task.json 为准
- 只读取已有评测 artifacts，不重新跑模型
- 不修改框架代码

## 验收标准
1. 覆盖所有 5 个样例
2. 有量化归属匹配统计
3. 有合并策略建议
4. 报告可被 arch-1 直接引用

## 下游动作
报告直接输入 arch-1 的 hybrid_experimental 管线设计任务。
