# 补齐 PPT 图片 OCR 进入生成 Skill 主链路

## 任务类型
development

## 目标
接续已阻塞的「实现PPT生成skill图片OCR输入链路」任务，把图片 OCR 结果真正接入 PPT 生成 skill 当前可消费的主链路：图片上传后可被解析为 `parsed_files` 或等效稳定结构，并被 `ppt_generator` 在生成 PPT 时消费。

## 任务边界
- 只补齐图片 OCR 结果进入 skill 输入与 PPT skill 消费闭环。
- 不做 PPT 精美模式的新视觉能力，不改变 CogView 页图渲染策略。
- 不改生产配置，不做生产部署。
- 不新增第三方依赖。

## 输入事实
- 原任务 `/Users/lin/Desktop/work/my-agent-teams/tasks/实现PPT生成skill图片OCR输入链路/result.json` 已说明当前窄 write_scope 无法闭环。
- review-1 驳回点：`ContextAssembler.ensure_parsed_files()` 未解析图片；`ppt_generator` 当前主要消费 `context.parsed_files`；`ppt_generator` manifest 未允许图片输入；`UploadedFileSummary` schema 未暴露新增字段。
- 当前已有 ParserService 图片 OCR 能力和 uploaded_files.extracted_text 落库基础。
- 与 `ppt_generator` 文件有潜在冲突，需等待 `实现PPT精美模式入口与CogView页图渲染Demo` 完成/收口后再认领。

## 约束
- write_scope 仅限：
  - `/Users/lin/Desktop/work/chiralium/backend/app/services/context_assembler.py`
  - `/Users/lin/Desktop/work/chiralium/backend/app/schemas/file.py`
  - `/Users/lin/Desktop/work/chiralium/skills/custom/ppt_generator/1.0.0/skill.py`
  - `/Users/lin/Desktop/work/chiralium/skills/custom/ppt_generator/1.0.0/manifest.json`
  - `/Users/lin/Desktop/work/chiralium/backend/tests/test_context_assembler.py`
  - `/Users/lin/Desktop/work/chiralium/backend/tests/test_ppt_generator_image_input.py`
  - `/Users/lin/Desktop/work/chiralium/backend/tests/test_ppt_generator_skill.py`
- result.json.status 只能使用 `done` / `failed` / `blocked`。
- 必须保持现有 PDF/docx/xlsx 解析逻辑不回归。

## 交付物
- 图片 OCR 结果进入 `parsed_files` 或等效稳定 skill 输入结构的实现。
- `ppt_generator` manifest 支持图片附件输入。
- `ppt_generator` 消费图片 OCR 文本的实现或明确等效路径。
- schema / tests 更新。
- `result.json`。

## 验收标准
1. 上传图片后，`ContextAssembler.ensure_parsed_files()` 或等效链路能产出 PPT skill 可消费的 OCR 内容。
2. `ppt_generator` 在图片输入场景能读取该 OCR 内容并纳入生成 prompt。
3. `ppt_generator` manifest 允许 `.png/.jpg/.jpeg/.webp` 图片输入。
4. `UploadedFileSummary` 或相关 schema 对新增字段保持稳定契约，不只停留在原始 dict。
5. 测试覆盖图片 OCR -> skill 输入 -> PPT 生成 prompt 消费，不误伤文档/PDF 解析。

## 下游动作
完成后进入 review，再由 QA 验证图片上传 -> OCR -> PPT skill 消费闭环。

## 授权状态
这是原阻塞任务的扩大 scope 后续任务，dev 环境执行，不涉及生产部署。
