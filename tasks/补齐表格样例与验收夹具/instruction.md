# 任务：补齐表格样例与验收夹具

## 任务类型
质量/验证夹具建设

## 目标
基于样本清单、DOCX gate 与表格 renderer，补齐一组可回归的表格正/负样例夹具，覆盖“真实 Word 表格通过”和“只有图片 fallback/结构缺失必须失败”两类场景。

## 任务边界
- 只允许修改 `backend/tests/fixtures/pdf_to_word/table_goldens/` 与 `backend/tests/test_pdf_to_word_table_fixtures.py`。
- 本任务不改生产 renderer、payload 或 gate 逻辑；只补齐夹具与验证。
- 不扩展到视觉相似度阶段。

## 输入事实
- 上游依赖：`冻结95还原度指标与样本清单`、`实现DOCX表格检查门禁`、`实现可编辑Word表格渲染`。
- 路线文档要求：含表格样例必须能区分 `<w:tbl>` 通过与图片 fallback 失败。
- 当前至少应覆盖英语八年级、五下科学等已知含表格场景，以及一个结构缺失负样例。

## 约束
- 夹具必须能被自动化测试消费，不能只留人工说明。
- 正负样例都要明确 expected outcome、关键单元格文本或结构断言。
- 不夸大当前真实能力。

## 交付物
1. 一组表格相关 golden / fixture 数据。
2. 一组自动化测试，覆盖通过/失败两类表格场景。
3. fixture 中明确 expected `has_table_xml` / `image_fallback_table_count` / 关键 cell 断言。

## 验收标准
- 至少有 1 组通过样例 + 1 组失败样例。
- 测试能稳定断言 `<w:tbl>` 与 fallback 失败语义。
- 夹具字段与样本清单、DOCX gate 口径一致。
- 不越界改生产代码。

## 下游动作
完成后，PM 将接续 95% 最终报告器与视觉相似度门禁设计任务。
