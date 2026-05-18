# 任务：实现 QuestionRegion 检测器

## 任务类型
development

## 目标
从 baseline PageIR 识别题号 anchor 与区域边界，输出 question-regions 结构，实现可判定性检查。

## 任务边界
- 新增 question_region_detector.py
- 输入：baseline PageIR（pages.jsonl）
- 输出：question-regions 结构（每页的题号位置、区域 bbox、可判定性标记）
- 不修改现有 PageIR 结构

## 输入事实
- 设计文档：design/pdf2word/hybrid_experimental增强管线设计.md（Section 6）
- 基线数据：artifacts/pdf2word/model-eval/20260514-144102/apple_baseline/
- 5 个样例中数学/英语可判定，语文五年级不可判定（无自动题号）
- PageIR 结构：pages.jsonl 包含 page_index、blocks（含 kind、content、bbox）

## 约束
- write_scope 以 task.json 为准
- 只做检测，不做修正
- 不可判定的页面必须标记为 unresolvable，不能强制推断

## 交付物
1. question_region_detector.py：QuestionRegionDetector 类
2. 测试文件：test_question_region_detector.py
3. result.json 包含 5 样例检测结果

## 验收标准
1. 数学/英语样例可检测出题号区域
2. 语文五年级标记为 unresolvable
3. 输出结构包含：page_index、question_id、region_bbox、resolvable
4. 测试通过

## 下游动作
完成后进入 hybrid_experimental 管线后续任务（候选过滤、PageIR 合并等）。
