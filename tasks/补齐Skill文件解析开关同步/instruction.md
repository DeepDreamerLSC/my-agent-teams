# 补齐 Skill 文件解析开关同步

## 任务类型
development

## 目标
修复 custom skill 文件解析能力开关的同步缺口：当 skill manifest 显式声明 `supports_file_parse=true` 时，`SkillRecord.supports_file_parse` 必须在文件系统同步和 zip 上传审批流中同步为 true。该前置修复用于支持后续 `pdf_to_word` skill 避免在执行前被通用 PDF 预解析链路拖慢或拦截。

## 任务边界
- 只修改 `backend/app/services/admin_skill_service.py` 与 `backend/tests/test_admin_skills.py`。
- 不新增第三方依赖。
- 不修改 chat.py、file_service.py、SkillManager 执行链路或任何现有 custom skill 文件。
- 不改变未声明 `supports_file_parse` 的现有 skill 行为，缺省仍为 false。

## 输入事实
- arch-1 评审任务 `/Users/linsuchang/Desktop/work/my-agent-teams/tasks/评审PDF转WordSkill方案并拆解实施/result.json` 结论：PDF 转 Word MVP 前必须补齐 manifest -> DB 的 `supports_file_parse` 同步。
- 当前 `SkillRecord.supports_file_parse` 是 DB 字段。
- 当前 `admin_skill_service.sync_filesystem_skills_to_db()` 与 `upload_skill()` 流程存在硬编码 false 或未从 manifest 同步该字段的问题。
- 后续 `pdf_to_word` manifest 会把 `supports_file_parse` 放在顶层；可兼容 `parameters.supports_file_parse` 作为旧草案兜底。

## 约束
- 所有路径使用绝对路径确认。
- 遵守 chiralium 当前测试风格，优先补单测锁定行为。
- 不引入生产部署动作。
- 保持向后兼容：manifest 缺省或非布尔值时不得把现有技能误改为支持文件解析。

## 交付物
- 修改后的 `/Users/linsuchang/Desktop/work/chiralium/backend/app/services/admin_skill_service.py`。
- 更新后的 `/Users/linsuchang/Desktop/work/chiralium/backend/tests/test_admin_skills.py`。
- 本任务目录 `/Users/linsuchang/Desktop/work/my-agent-teams/tasks/补齐Skill文件解析开关同步/result.json`，包含修改摘要、测试命令与结果、风险。

## 验收标准
- `sync_filesystem_skills_to_db()` 新建 custom skill DB 记录时，从 manifest 顶层 `supports_file_parse` 读取布尔值；缺省保持 false。
- `upload_skill()` 审批流创建 SkillRecord 时也同步同一字段。
- 兼容 `parameters.supports_file_parse` 作为兜底，但新 manifest 统一使用顶层字段。
- 若已有 DB 记录为 false，而 manifest 显式声明 true，同步时应更新为 true，避免环境漂移。
- 单测覆盖至少三类：manifest 顶层 true、manifest 缺省 false、zip upload true。
- 现有未声明 `supports_file_parse` 的 skill 行为不变。
- 运行相关后端测试通过，至少包括：`backend/tests/test_admin_skills.py`。

## 下游动作
完成后 PM 创建/入池 PDF 转 Word Skill MVP 任务，并将本任务作为其依赖。

## 授权状态
林总工已要求完成文档检查后开始安排实施；本任务为 dev 环境代码修改，不涉及生产部署。
