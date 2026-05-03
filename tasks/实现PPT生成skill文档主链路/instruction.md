# 任务：实现PPT生成skill文档主链路

## 任务类型
开发

## 目标
在 chiralium 现有 skill 体系中新增一个 **PPT 生成 skill** 的主链路，先完成“用户上传文档/PDF → 解析内容 → 生成 PPTX 文件”的可运行能力，并保持与现有 skill 格式一致。

## 任务边界
- 本任务只负责 **skill 主链路** 与 **PPTX 导出能力**。
- 重点覆盖文档/PDF输入，不单独做功能页面。
- 不负责图片 OCR 输入链路（由并行任务处理）。
- 不负责额外的新页面 UI。

## 输入事实
- 需求 ID：`a7f628a8-8332-45e9-887b-d50dbb070eed`
- 林总工已明确方向：
  1. 以 **skill** 形式交付，而不是单独页面
  2. 用户流程：上传图片或文档 → 系统解析内容 → 生成 PPT
  3. 生成后可根据用户提示词进行微调
  4. 必须集成到现有 skill 体系中
- 仓库内已有可参考实现：
  - `skills/custom/docx_generator/1.0.0/*`
  - `backend/app/services/office_export_service.py`
  - skill 结果文件回传链路已存在，可复用现有 `display_type=file` 机制

## 约束
- write_scope: `skills/custom/ppt_generator/1.0.0/manifest.json, skills/custom/ppt_generator/1.0.0/skill.py, backend/app/services/office_export_service.py, backend/requirements.txt, backend/tests/test_ppt_generator_skill.py`
- read_only: false
- 依赖上游任务: 无
- target_environment: dev
- execution_mode: dev
- owner_approval_required: false
- 必须优先复用现有 skill manifest / 执行方式 / 文件回传格式
- 生成物必须是可下载的 `.pptx`

## 交付物
- 新增 PPT 生成 skill（manifest + skill.py）
- 新增或扩展 PPTX 导出能力
- 至少一组后端测试，验证：
  - skill 可被发现
  - skill 能基于解析文本生成 PPTX 文件
  - skill 返回结果符合现有 file-display 契约
- `result.json`

## 验收标准
1. skill 目录结构与生产现有其他 custom skill 保持一致。
2. 用户上传 PDF/文档后，skill 能利用已解析文本生成结构化 PPTX 文件。
3. skill 返回结果可被现有聊天链路识别为 `display_type=file`。
4. 测试通过，并在 `result.json` 中说明：新增 skill 名称、主要文件、生成 PPT 的基本结构。

## 下游动作
review
