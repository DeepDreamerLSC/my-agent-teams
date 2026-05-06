# 实现 PDF 转 Word Skill MVP 闭环

## 任务类型
development

## 目标
在 chiralium dev 环境实现 `pdf_to_word` custom skill 的第一阶段 MVP：不接真实 MinerU/MiniCPM-V 服务，先用 mock/fixture 解析结果跑通 PDF 输入校验、转换服务、最小 DOCX 生成、skill 返回 `display_type=file` 的闭环，为后续 MinerU sidecar 接入奠定服务边界。

## 任务边界
- 本任务只做 MVP mock/fixture 闭环，不接真实 MinerU/MiniCPM-V，不启动模型服务，不做生产部署。
- 不新增第三方依赖；如发现必须引入 `python-docx` 或其他依赖，写 `result.json.status=blocked` 并说明原因，等待 PM/林总工决策。
- 不修改 `chat.py` / `file_service.py` / 通用 skill 执行链路；从 `context.uploaded_files` 中复用现有 `stored_path`。
- 不做外部 API、异步 job、API key、计费、webhook。
- 只修改 task.json.write_scope 中列出的文件。

## 输入事实
- 架构评审任务：`/Users/lin/Desktop/work/my-agent-teams/tasks/评审PDF转WordSkill方案并拆解实施/result.json`。
- 设计文档：`/Users/lin/Desktop/work/chiralium/design/product/pdf-to-word-skill-mineru-minicpmv-design.md`。
- 前置任务 `补齐Skill文件解析开关同步` 已 done：manifest 顶层 `supports_file_parse=true` 可同步到 DB。
- 现有 custom skill 输出文件可通过 `display_type=file` + `file` payload 进入 generated file 链路。
- 当前 `backend/requirements.txt` 没有 `python-docx`，本 MVP 应用最小 OOXML/zip 方式或项目现有模式生成合法 docx。

## 约束
- write_scope 仅限：
  - `/Users/lin/Desktop/work/chiralium/skills/custom/pdf_to_word/1.0.0/manifest.json`
  - `/Users/lin/Desktop/work/chiralium/skills/custom/pdf_to_word/1.0.0/skill.py`
  - `/Users/lin/Desktop/work/chiralium/skills/custom/pdf_to_word/1.0.0/SKILL.md`
  - `/Users/lin/Desktop/work/chiralium/backend/app/core/config.py`
  - `/Users/lin/Desktop/work/chiralium/backend/.env.example`
  - `/Users/lin/Desktop/work/chiralium/.env.example`
  - `/Users/lin/Desktop/work/chiralium/backend/app/services/pdf_to_word/__init__.py`
  - `/Users/lin/Desktop/work/chiralium/backend/app/services/pdf_to_word/settings.py`
  - `/Users/lin/Desktop/work/chiralium/backend/app/services/pdf_to_word/models.py`
  - `/Users/lin/Desktop/work/chiralium/backend/app/services/pdf_to_word/conversion_service.py`
  - `/Users/lin/Desktop/work/chiralium/backend/app/services/pdf_to_word/docx_assembler.py`
  - `/Users/lin/Desktop/work/chiralium/backend/app/services/pdf_to_word/workspace.py`
  - `/Users/lin/Desktop/work/chiralium/backend/tests/test_pdf_to_word_skill.py`
  - `/Users/lin/Desktop/work/chiralium/backend/tests/test_pdf_to_word_service.py`
- `result.json.status` 只能使用 `done` / `failed` / `blocked`。
- 保持现有 docx_generator / ppt_generator / order-print-image-pack skill 不回归。

## 交付物
- `pdf_to_word` custom skill 目录与 manifest/skill/SKILL.md。
- `PDFConversionService`、最小模型/settings/workspace/docx assembler。
- 单测：`test_pdf_to_word_skill.py`、`test_pdf_to_word_service.py`。
- 本任务目录 `result.json`，包含修改文件、测试命令、风险。

## 验收标准
1. 新增 `pdf_to_word` manifest：`runtime_backend=subprocess`、`allowed_extensions=[".pdf"]`、`max_files=1`、`timeout_sec` 约 900、顶层 `supports_file_parse=true`。
2. `skill.py` 只做输入校验、模式解析、调用 `PDFConversionService`、返回 `display_type=file`；唯一 PDF 从 `context.uploaded_files` 选择并使用 `stored_path`。
3. `PDFConversionService` 使用 mock/fixture MinerU 结果生成最小可下载 DOCX；输出至少包含段落、表格降级文本/占位、warnings 与转换说明。
4. 返回 file payload 包含 `file_name`、`file_path`、`file_size`、DOCX MIME；DOCX 是合法 zip。
5. 无文件、多文件、非 PDF、文件不存在、转换异常均返回可读错误，不生成半成品。
6. 测试覆盖 SkillManager/manifest 可发现、skill 执行返回合法文件结果、DOCX 合法、meta 含 page_count/block_count/warnings，并验证其他文件型 skill 不受影响或说明最小回归覆盖。

## 下游动作
完成后进入 review 和 QA；通过后 PM 继续派发 MinerU HTTP sidecar Adapter 接入任务。

## 授权状态
林总工已要求“完成文档检查后开始安排实施”；本任务为 dev 环境 MVP 实施，不涉及生产部署。
