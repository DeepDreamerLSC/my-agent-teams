# 任务：实现候选过滤与归属匹配

## 任务类型
development

## 目标
实现候选面积/越界/重叠/重复过滤，以及 question-bound assignment，输出 candidates.filtered.jsonl 和 merge-decisions.jsonl。

## 任务边界
- 新增 candidate_filter.py
- 依赖 QuestionRegionDetector（已完成）和 CandidateExtractor（已完成）
- 不修改现有组件

## 输入事实
- QuestionRegionDetector：实现QuestionRegion检测器（已完成）
- CandidateExtractor：实现候选抽取与标准化（已完成）
- 候选增强可行性报告：design/pdf2word/图片公式候选增强可行性报告.md
- MinerU full：74 候选，48 assigned，39 good，64.9% 归属率
- formula_candidate 质量差（3/18 good），默认 reject
- 基线数据：artifacts/pdf2word/model-eval/20260514-144102/apple_baseline/

## 约束
- write_scope 以 task.json 为准
- formula 候选默认 reject（audit-only）
- 不可判定的页面跳过 question-bound enhancement
- 所有过滤决策必须记录原因

## 交付物
1. candidate_filter.py：CandidateFilter 类
2. 测试文件：test_candidate_filter.py
3. result.json 包含过滤统计

## 验收标准
1. 面积过小/越界/重复候选被过滤
2. question-bound assignment 正确归属
3. formula 候选标记为 reject
4. 不可判定页面的候选标记为 skipped
5. 测试通过

## 下游动作
完成后进入 PageIR merger + validator 任务。
