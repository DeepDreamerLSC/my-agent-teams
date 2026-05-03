# 任务：切换 PPT 生成默认精美模式

## 任务类型
开发

## 目标
把 `ppt_generator` 的默认输出模式从 `simple` 切换为 `polished`。用户正常发起 PPT 生成请求时，不需要再手动说“精美模式”或显式传参，系统默认走精美模式；只有当用户/调用方明确指定 `simple` 时，才回落到普通模式。

## 任务边界
- 只负责 skill 层默认模式判定、manifest/契约说明、回归测试。
- 不负责 CogView 密钥/模型解析修复（并行任务处理）。
- 不负责前端按钮、UI 文案、部署脚本。
- 保持现有 simple / polished 两种显式模式入口兼容。

## 输入事实
- 当前实现位于：`skills/custom/ppt_generator/1.0.0/skill.py`。
- 当前 `_resolve_render_mode` 逻辑是：显式参数优先，否则只有命中“精美 / polished / cogview”等关键词才走 polished，默认回到 simple。
- 用户新要求：**PPT 生成默认使用精美模式，用户无需手动触发。**
- `manifest.json` 当前已声明 `simple / polished` 两种 render mode。
- 当前仓库里已有与 PPT 精美模式相关的 ready_for_merge 任务，但本任务为紧急产品行为切换，允许在你的 write_scope 内吸收必要调整；不要回退他人已完成能力。

## 约束
- write_scope:
  - `skills/custom/ppt_generator/1.0.0/skill.py`
  - `skills/custom/ppt_generator/1.0.0/manifest.json`
  - `backend/tests/test_ppt_generator_skill.py`
- read_only: false
- target_environment: dev
- execution_mode: dev
- owner_approval_required: false
- 必须保留：
  1. 显式 `render_mode=simple` / `mode=simple` 时仍走 simple
  2. 显式 `polished` 时继续走 polished
  3. 现有输出结构与文件导出契约不变
- 优先做最小行为切换，不要顺手重构无关逻辑。

## 交付物
- `skills/custom/ppt_generator/1.0.0/skill.py` 默认模式切换
- `skills/custom/ppt_generator/1.0.0/manifest.json` 如有必要补充默认行为说明
- `backend/tests/test_ppt_generator_skill.py` 回归测试
- `/Users/lin/Desktop/work/my-agent-teams/tasks/切换PPT生成默认精美模式/ack.json`
- `/Users/lin/Desktop/work/my-agent-teams/tasks/切换PPT生成默认精美模式/result.json`

`result.json` 必须写明：
- 默认模式切换前后的判定逻辑
- 显式 simple 保底策略
- 修改文件列表
- 测试命令与结果

## 验收标准
1. 普通 PPT 生成请求在未显式传 mode 时，默认进入 polished。
2. 显式传 `simple` 时，仍然进入 simple。
3. 显式传 `polished` 时，继续进入 polished。
4. 测试覆盖默认 polished 与显式 simple 两条路径。
5. 不引入对现有导出契约的破坏。

## 下游动作
review（通过后通知 arch-1 与上游生产修复一起合入）
