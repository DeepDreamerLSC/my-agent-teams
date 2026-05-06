# 评审 PDF 转 Word Skill 方案并拆解实施

## 任务类型
design

## 目标
对 `/Users/lin/Desktop/work/chiralium/design/product/pdf-to-word-skill-mineru-minicpmv-design.md` 做架构评审，并输出可执行实施拆分，帮助 PM 进入实施派发。重点确认：MinerU 主解析 + MiniCPM-V 增强 + custom skill + 后续 API 化这条路线是否与当前 chiralium skill/runtime/API 体系匹配。

## 任务边界
- 这是只读设计/实施拆解任务，不修改 chiralium 业务代码。
- 必须阅读设计文档与相关现有实现：`skills/custom/`、`backend/app/services/skill_service.py`、`backend/app/api/chat.py`、`backend/app/services/admin_skill_service.py`、`backend/app/services/file_service.py`。
- 不直接创建子任务，不直接派发其他 agent；只在 result.json 中给 PM 可执行建议。
- 若发现设计存在必须先修正的问题，明确标出阻塞级别与建议修正文档位置。

## 输入事实
- 新需求：设计 PDF 转 Word skill，用于开罗尔平台；核心架构为 MinerU 主解析 + MiniCPM-V 增强；需要封装 API，后续可能对外提供。
- 已产出设计文档：`/Users/lin/Desktop/work/chiralium/design/product/pdf-to-word-skill-mineru-minicpmv-design.md`。
- 当前 custom skill 采用 `skills/custom/<skill-name>/<version>/manifest.json`，多数可执行 skill 还包含 `skill.py`。
- 当前 custom skill 文件输出通过 `display_type=file` + `file` payload 进入 chat 链路注册 generated file。
- 当前 `supports_file_parse` 是 DB 字段，默认同步为 false；PDF 转 Word 是否应从 manifest 同步该字段需要你评审。

## 约束
- 遵守 `/Users/lin/Desktop/work/my-agent-teams/AGENTS.md` 与 chiralium 现有代码约定。
- 所有共享资源使用绝对路径。
- 不假设 MinerU/MiniCPM-V 已在生产可用；需要区分 MVP mock、内网服务接入、生产部署前置条件。
- 不安排生产部署，不修改生产目录。
- 输出必须足够具体，便于 PM 直接创建 dev/qa 任务的 write_scope 与验收标准。

## 交付物
在本任务目录写 `result.json`，至少包含：
- `status`: `success` 或 `blocked`
- `summary`: 评审结论
- `design_doc`: 设计文档绝对路径
- `implementation_slices`: 建议任务列表，每项包含 title、agent_or_pool、task_type、write_scope、dependencies、acceptance
- `risks`: 风险与前置条件
- `recommended_first_task`: 你建议 PM 先派发的第一项实施任务
- `notes`: 其他需要 PM/林总工注意的事项

## 验收标准
- 明确判断当前设计是否可实施。
- 明确第一阶段 MVP 是否必须改 `admin_skill_service` 的 manifest 同步逻辑。
- 明确 MinerU 与 MiniCPM-V 应以 sidecar/service/CLI 哪种方式先接入。
- 给出不超过 6 个实施切片，每个切片 write_scope 无明显重叠。
- 标出与当前活跃 chiralium 任务的潜在 write_scope 冲突。
- result.json 是合法 JSON。

## 下游动作
PM 根据 arch-1 的 result.json 创建/入池 PDF 转 Word skill MVP、MinerU 接入、MiniCPM-V 增强、API 与 QA 验证任务。

## 授权状态
林总工已要求“完成文档检查后开始安排实施”；本任务用于实施前架构评审与任务拆解，不涉及生产部署。
