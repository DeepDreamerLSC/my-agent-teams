# 任务：实现PPT生成skill图片OCR输入链路

## 任务类型
开发

## 目标
为“PPT 生成 skill”补齐图片输入链路：当用户上传书本图片、截图或其他图片资料时，系统能够先做 OCR/内容提取，再把结果提供给 PPT 生成 skill 使用。

## 任务边界
- 本任务只负责 **图片输入 → 内容提取** 这一段。
- 不单独做页面，不修改独立功能入口。
- 不负责 PPTX 导出本身（由并行任务处理）。
- 不负责 skill 主文件的整体实现，只负责让图片输入能被后续 skill 消费。

## 输入事实
- 需求 ID：`a7f628a8-8332-45e9-887b-d50dbb070eed`
- 林总工已明确：用户流程是“上传图片或文档 → 系统解析内容 → 生成 PPT”。
- 当前方案注明：图片类输入先走 OCR，再进入 PPT 生成。
- 现有代码中：
  - 文档/PDF 已有 parser / extracted_text 思路
  - 图片上传已存在，但当前主链路对图片 OCR 与后续结构化消费还不完整

## 约束
- write_scope: `backend/app/services/parser_service.py, backend/app/services/file_service.py, backend/tests/test_parser_service.py, backend/tests/test_ppt_generator_image_input.py`
- read_only: false
- 依赖上游任务: 无
- target_environment: dev
- execution_mode: dev
- owner_approval_required: false
- 必须尽量复用现有 parser / uploaded_files / extracted_text 契约
- 不要引入单独功能页面

## 交付物
- 图片 OCR / 内容提取能力的实现或补强
- 让图片输入能以稳定结构提供给后续 skill 使用（例如 extracted_text / parsed_files / 等效结构）
- 至少一组测试验证：
  - 图片输入可被处理
  - 结果可被 PPT 生成链路消费
- `result.json`

## 验收标准
1. 上传图片后，系统能得到可供 PPT skill 使用的文本/结构化内容，而不是仅保留原始二进制图片。
2. 新逻辑与现有文档 parser 思路保持一致，不额外引入割裂的数据结构。
3. 测试通过，并在 `result.json` 中明确：图片输入最终产出的字段/结构是什么。
4. 不误伤现有 PDF / docx / xlsx 等解析逻辑。

## 下游动作
review
