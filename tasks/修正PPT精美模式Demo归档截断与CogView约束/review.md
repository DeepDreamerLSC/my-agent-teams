# Code Review - 修正PPT精美模式Demo归档截断与CogView约束

## 结论
- **审查结论：通过（APPROVE）**
- 依据：`instruction.md`、`result.json`、`ppt_generator` / `ppt_page_render_service` 实现与相关测试代码审查。
- 说明：任务目录当前 **无 `verify.json`**；本次结论基于代码与工件审查给出，未自行执行功能测试。

## 通过项

### 1. `presentation_plan.json` 已不再按字节硬截断
- polished demo 归档现在直接完整写入 `presentation_plan.json`：
  - `/Users/lin/Desktop/work/chiralium/skills/custom/ppt_generator/1.0.0/skill.py:317-323`
- 不再存在此前那种把 UTF-8/JSON 从中间切断的实现。
- 测试已验证 zip 内该文件可以 `utf-8` 解码并被 `json.loads()` 正常解析，且长中文字段未损坏：
  - `/Users/lin/Desktop/work/chiralium/backend/tests/test_ppt_generator_skill.py:98-162`

### 2. 显式 `image_model_id` 已被严格限制在 CogView demo 边界内
- 新增 `_is_allowed_demo_image_model()` 统一约束：仅允许 `provider=zhipu` 且 `model_name ∈ {cogview-3-flash, cogview-3}`：
  - `/Users/lin/Desktop/work/chiralium/backend/app/services/ppt_page_render_service.py:82-88`
- `_resolve_demo_image_model()` 在显式 `image_model_id` 路径下已强制校验，不合法直接抛错：
  - `/Users/lin/Desktop/work/chiralium/backend/app/services/ppt_page_render_service.py:90-105`
- 自动选择路径也仍然只会挑 CogView 候选：
  - `/Users/lin/Desktop/work/chiralium/backend/app/services/ppt_page_render_service.py:107-112`
- 测试已覆盖“非 CogView override 被拒绝”：
  - `/Users/lin/Desktop/work/chiralium/backend/tests/test_ppt_page_render_service.py:117-140`

### 3. 原有 polished demo / simple 模式未回归
- polished 模式入口与 demo archive 主链路仍保持：
  - `/Users/lin/Desktop/work/chiralium/skills/custom/ppt_generator/1.0.0/skill.py:69-125`
- `simple` 模式仍继续输出 `.pptx`，未受本次补修影响：
  - `/Users/lin/Desktop/work/chiralium/skills/custom/ppt_generator/1.0.0/skill.py:105-125`

## 非阻塞备注
- 当前工作区里 `manifest.json`、`office_export_service.py` 等仍有并行任务留下的未提交改动，但本次补修自身关注的两个 review blocker 已被正面解决，不影响本任务审查结论。

## 最终意见
本轮补修已经完整解决上轮两个阻塞点：**demo 包中的 `presentation_plan.json` 现在始终保持合法 UTF-8 / 可解析 JSON，且 `image_model_id` 不再能绕过 CogView 限制。** 建议通过。
