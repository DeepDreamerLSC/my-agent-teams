# 任务：实现候选抽取与标准化

## 任务类型
development

## 目标
从 MinerU/PaddleOCR-VL PageIR 抽取 image/table/formula 候选，标准化为统一候选格式。

## 任务边界
- 新增 candidate_extractor.py
- 输入：MinerU/PaddleOCR-VL 的 pages.jsonl
- 输出：统一候选格式（candidate_id、source_profile、page_index、bbox、block_kind、content、confidence）
- formula 候选默认标记为 audit-only
- 不修改现有 normalizer

## 输入事实
- 设计文档：design/pdf2word/hybrid_experimental增强管线设计.md（Section 7-8）
- MinerU 数据：artifacts/pdf2word/model-eval/20260515-090642/mineru/
- PaddleOCR-VL 数据：artifacts/pdf2word/model-eval/20260515-112748/paddleocr_vl/
- 候选增强可行性报告：design/pdf2word/图片公式候选增强可行性报告.md
- MinerU full 是最稳候选源（64.9% 归属率）
- formula_candidate 质量差（3/18 good）

## 约束
- write_scope 以 task.json 为准
- 只做抽取和标准化，不做归属匹配（后续任务）
- formula 候选必须标记为 audit-only，不能直接并回
- 候选必须保留 source_profile 标记

## 交付物
1. candidate_extractor.py：CandidateExtractor 类
2. 测试文件：test_candidate_extractor.py
3. result.json 包含 5 样例抽取统计

## 验收标准
1. 从 MinerU 和 PaddleOCR-VL 数据中正确抽取候选
2. image/table/formula 候选 kind 正确
3. formula 候选标记为 audit-only
4. 测试通过

## 下游动作
完成后进入 hybrid_experimental 管线后续任务（候选过滤、PageIR 合并等）。
