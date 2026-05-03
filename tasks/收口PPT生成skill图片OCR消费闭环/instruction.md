# 任务：收口PPT生成skill图片OCR消费闭环

## 任务类型
开发

## 目标
补齐“图片上传 → OCR / 内容提取 → PPT 生成 skill 实际消费”的**当前主链路闭环**，使图片输入不只是把 OCR 文本落库，而是能真正被现有 `ppt_generator` skill 稳定消费并生成 PPTX。

## 任务边界
- 本任务是对 `实现PPT生成skill图片OCR输入链路` 审查驳回后的**补修/收口任务**。
- 重点不是再做一次 OCR，而是把 OCR 结果接到当前 skill 主链路与稳定 schema 契约上。
- 不做独立功能页面。
- 不扩展成新的大功能，只补齐当前主链路闭环。

## 输入事实
- 上游已完成：`实现PPT生成skill文档主链路`，PPT skill 主链路可基于文档/PDF 解析文本生成 `.pptx`。
- 被驳回任务：`实现PPT生成skill图片OCR输入链路`
- `review.md` 明确指出的阻塞问题：
  1. 图片 OCR 结果还没有真正进入 `ppt_generator` 当前可消费主链路
  2. `uploaded_file_summary` 新增字段没有进入稳定 schema，外部消费者实际拿不到
  3. 测试未证明“图片上传 → OCR → skill 消费”的闭环已成立

## 约束
- write_scope:
  - `backend/app/services/context_assembler.py`
  - `backend/app/core/chat_capabilities.py`
  - `backend/app/services/parser_service.py`
  - `backend/app/services/file_service.py`
  - `backend/app/schemas/file.py`
  - `skills/custom/ppt_generator/1.0.0/skill.py`
  - `skills/custom/ppt_generator/1.0.0/manifest.json`
  - `backend/tests/test_parser_service.py`
  - `backend/tests/test_ppt_generator_image_input.py`
  - `backend/tests/test_ppt_generator_skill.py`
- read_only: false
- 依赖上游任务: `实现PPT生成skill文档主链路`
- target_environment: dev
- execution_mode: dev
- owner_approval_required: false
- 必须优先复用现有 parser / uploaded_files / extracted_text / parsed_files 契约
- 不要引入割裂的新结构；如果要扩充 schema，优先补现有稳定 schema，而不是私下扩 dict 字段

## 交付物
- 代码补修，形成图片输入的实际 PPT skill 消费闭环
- 补齐稳定 schema 契约（如确需让外部消费者拿到新增字段）
- 测试，至少证明：
  1. 图片 OCR 结果可进入 `parsed_files` 或等效稳定 skill 输入结构
  2. `ppt_generator` 当前主链路能实际消费图片 OCR 结果
  3. 若对外宣称 `uploaded_file_summary` 暴露了新增字段，则 schema / API 序列化后仍然存在
- `result.json`

## 验收标准
1. 上传图片后，不只是 `uploaded_files.extracted_text` 有内容，而是 `ppt_generator` 当前主链路确实能消费到图片 OCR 结果。
2. `ppt_generator` 的 manifest / 输入能力与实际支持的输入类型保持一致。
3. 若扩展了 `UploadedFileSummary` 稳定契约，则需要补齐 schema 并证明外部消费者可拿到新增字段。
4. 测试覆盖“图片上传 → OCR → skill 消费 → 生成 PPT”的主链路闭环。
5. 不误伤现有 docx/pdf/xls/xlsx 解析与文档/PDF 生成 PPT 的主链路。

## 下游动作
review
