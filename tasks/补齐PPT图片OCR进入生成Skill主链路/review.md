# Code Review - 补齐PPT图片OCR进入生成Skill主链路

审查结论：APPROVE

## 审查范围
- `backend/app/services/context_assembler.py`
- `backend/app/schemas/file.py`
- `skills/custom/ppt_generator/1.0.0/skill.py`
- `skills/custom/ppt_generator/1.0.0/manifest.json`
- `backend/tests/test_context_assembler.py`
- `backend/tests/test_ppt_generator_image_input.py`
- `backend/tests/test_ppt_generator_skill.py`
- `result.json`

## 结论依据
1. `ContextAssembler.ensure_parsed_files()` 已将图片 OCR 与文档解析统一进入稳定的 `parsed_files` 结构，并补充 `file_type / mime_type / attachment_kind / parse_status` 元信息；扩展名识别也支持 `file_type` 缺省时回退原始文件名后缀。见 `backend/app/services/context_assembler.py:78-103,154-159`。
2. `UploadedFileSummary` 已稳定暴露 `extracted_text / parse_status / parser_source`，不再依赖原始 dict 临时字段。见 `backend/app/schemas/file.py:18-26`。
3. `ppt_generator` 已改为优先消费 `parsed_files`，并在额度未满时兜底消费 `uploaded_files.extracted_text`，同时按 `attachment_kind / mime_type / file_type / 后缀` 识别图片附件并打上“图片 OCR 附件”标签。见 `skills/custom/ppt_generator/1.0.0/skill.py:192-291`。
4. manifest 已允许 `.png/.jpg/.jpeg/.webp` 与 `image/png,image/jpeg,image/webp`。见 `manifest.json:33-44`。

## 验证证据
- 复跑目标测试：
  - `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/Users/lin/Desktop/work/chiralium/backend /Users/lin/Desktop/work/chiralium/backend/.venv/bin/python -m pytest -q -p no:cacheprovider backend/tests/test_context_assembler.py backend/tests/test_ppt_generator_image_input.py backend/tests/test_ppt_generator_skill.py`
  - 结果：`14 passed`。
- 复跑扩展相关回归：
  - `... pytest -q -p no:cacheprovider backend/tests/contracts/test_chat_response_contract.py backend/tests/test_files.py backend/tests/integration/test_file_flow.py`
  - 结果：`11 passed / 1 failed`，失败点为 `backend/tests/test_files.py` 仍断言 `preview.webp` 上传后 `parse_status=skipped`。

## 审查判断
- 该失败对应的是旧断言仍按“图片不进入 OCR 主链路”的历史口径检查 `preview.webp`；而本任务目标正是让图片 OCR（含 webp）进入主链路，因此当前实现将其标记为 `pending` 与任务目标一致。
- 失败用例文件不在本任务 `write_scope`，本次实现也未破坏目标测试与现有 PDF/docx/xlsx 主消费路径，因此我将其记录为后续契约同步事项，而不作为本轮阻塞项。

## 非阻塞风险
- 当前任务目录没有新的 `verify.json`，后续仍应由 QA 补充闭环验证。
- `backend/tests/test_files.py` 的旧期望需要在后续任务中与新图片 OCR 契约同步，否则扩展相关回归命令会持续报这一条历史断言失败。

## 最终意见
本任务已完成“图片 OCR -> 稳定 skill 输入 -> PPT prompt 消费”的闭环，目标测试通过，设计与实现一致，代码审查通过。
