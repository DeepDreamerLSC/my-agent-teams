# 任务：实现DOCX表格检查门禁

## 任务类型
质量门禁实现

## 目标
实现一套可机读的 DOCX inspect / gate 基础能力，至少能判断：DOCX 是否有效、`word/document.xml` 是否存在、`<w:tbl>/<w:tr>/<w:tc>` 数量、图片 fallback 痕迹以及 `has_table_xml` 结论，供后续表格渲染和 95% report 复用。

## 任务边界
- 只允许修改 `backend/app/services/pdf_to_word/fidelity_gate.py`、`backend/tests/test_pdf_to_word_fidelity_gate.py`、`backend/tests/fixtures/pdf_to_word/docx_inspect/`。
- 本任务不负责改 DOCX 生成逻辑；只负责检查/判定。
- 不实现视觉相似度，不引入慢模型。

## 输入事实
- 主要输入：
  - `/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-archive/reports/95还原度与Word表格验收路线.md`
  - `/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-archive/reports/端到端技术链路.md`
- 路线文档已明确：检测到表格但 DOCX 没有 `<w:tbl>` 时，必须标记 `table_detected_but_no_word_table`，不能静默通过。
- 现有真实问题就是英语/科学等样例可能只落图片 fallback，`has_table_xml=false`。

## 约束
- gate 输出必须是后续脚本可消费的结构化 JSON，而不是只打印日志。
- 检查逻辑要能区分：有表格 XML、只有图片 fallback、DOCX 无效、关系文件缺失等场景。
- 不要把“只有图片 fallback”包装成通过。

## 交付物
1. 一份可复用的 DOCX inspect / gate 逻辑（写入 `fidelity_gate.py`）。
2. 覆盖正/负样例的 fixture（`backend/tests/fixtures/pdf_to_word/docx_inspect/`）。
3. 一组自动化测试（`backend/tests/test_pdf_to_word_fidelity_gate.py`）。

## 验收标准
- 测试可验证 `docx_valid`、`word_document_xml_present`、`w_tbl_count`、`w_tr_count`、`w_tc_count`、`has_table_xml`、`image_fallback_table_count` 等关键字段。
- 对“检测到表格但没有 `<w:tbl>`”的样例能稳定给出 fail / blocker 结论。
- 逻辑不依赖人工打开 Word。
- 不越界修改 renderer 或 parser。

## 下游动作
完成后，PM 将用该 gate 接续表格样例夹具、最终 fidelity report 与渲染验收。
