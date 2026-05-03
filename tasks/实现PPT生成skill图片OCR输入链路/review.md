# Code Review - 实现PPT生成skill图片OCR输入链路

## 结论
- **审查结论：驳回（REQUEST CHANGES）**
- 依据：`instruction.md`、`result.json`、相关后端实现与测试代码审查。
- 说明：任务目录当前 **无 `verify.json`**；本次结论基于代码与工件审查给出，未自行执行功能测试。

## 通过项
- 图片 OCR 解析本身已接到现有 `ParserService` 主链：
  - `/Users/lin/Desktop/work/chiralium/backend/app/services/parser_service.py:65-106,129-201`
- `docx/pdf/xls/xlsx` 既有本地 fallback 逻辑未被直接改坏：
  - `/Users/lin/Desktop/work/chiralium/backend/app/services/parser_service.py:107-128,225-260`

## 阻塞问题

### 1. OCR 结果还没有真正进入 PPT skill 当前可消费的主链路
- 位置：
  - `/Users/lin/Desktop/work/chiralium/backend/app/services/context_assembler.py:84-95`
  - `/Users/lin/Desktop/work/chiralium/backend/app/api/chat.py:1280-1318`
  - `/Users/lin/Desktop/work/chiralium/skills/custom/ppt_generator/1.0.0/skill.py:126-173`
  - `/Users/lin/Desktop/work/chiralium/skills/custom/ppt_generator/1.0.0/manifest.json:18-32`
- 具体问题：
  1. `ContextAssembler.ensure_parsed_files()` 仍只对 `CHAT_PARSEABLE_EXTENSIONS` 执行解析，而该集合只包含 `doc/docx/pdf/xls/xlsx`，**不包含图片**；因此图片不会进入 `parsed_files`。
  2. `ppt_generator` 当前消费的是 `context.parsed_files`，并不消费 `uploaded_files[].extracted_text`。
  3. `ppt_generator` 的 manifest 也仍然只允许 `document`、`.pdf/.doc/.docx`，并未允许图片输入。
- 影响：虽然图片 OCR 文本已经能写入 `uploaded_files.extracted_text`，但**还没有形成“图片上传 → OCR → PPT skill 可实际消费”的当前主链路**，与任务摘要中“供后续 skill 作为等效结构消费”的说法不一致。

### 2. `uploaded_file_summary` 新增字段没有进入稳定 schema，外部消费者实际拿不到
- 位置：
  - `/Users/lin/Desktop/work/chiralium/backend/app/services/file_service.py:247-278`
  - `/Users/lin/Desktop/work/chiralium/backend/app/schemas/file.py:18-23`
  - `/Users/lin/Desktop/work/chiralium/backend/app/api/chat.py:356-358`
- 当前 `uploaded_file_summary()` 虽然返回了：
  - `extracted_text`
  - `parse_status`
  - `parser_source`
- 但 `UploadedFileSummary` schema 仍只声明：
  - `file_id`
  - `file_name`
  - `file_size`
  - `mime_type`
  - `download_url`
- 同时多个对外链路仍会把它包进 `UploadedFileSummary(**...)`，这意味着新增字段不会成为稳定对外契约。
- 影响：`result.json` 里“通过 uploaded_file_summary 稳定暴露 extracted_text / parse_status / parser_source”的结论目前并不成立。

## 测试问题
- 位置：
  - `/Users/lin/Desktop/work/chiralium/backend/tests/test_parser_service.py:86-144`
  - `/Users/lin/Desktop/work/chiralium/backend/tests/test_ppt_generator_image_input.py:1-23`
- 当前测试已覆盖：
  - 图片可被 OCR 模型解析并写回 `extracted_text`
  - `uploaded_file_summary()` 原始 dict 包含新增字段
- 但未覆盖：
  1. 图片 OCR 结果能否进入 `parsed_files` 或等效稳定 skill 输入结构
  2. `ppt_generator` 当前主链路是否真的能消费图片 OCR 结果
  3. `UploadedFileSummary` / API 序列化后新增字段是否仍然存在
- 因此测试不足以证明任务目标已经闭环。

## 最终意见
本次改动完成了“图片可 OCR 并落库到 `uploaded_files.extracted_text`”这一半，但**还没有把结果接入 PPT skill 当前可实际消费的稳定主链路，也没有把新增字段补进稳定 schema 契约**。在补齐这两点前，暂不建议合入。
