# 任务：收口PPT精美模式Demo最终PPTX闭环

## 任务类型
开发

## 目标
根据 QA 对 `验证PPT精美模式Demo闭环` 的失败结论，补齐 PPT 精美模式 demo 的最终闭环：让 `polished` 路径不再只返回 zip demo 包，而是把已渲染出的页面图片真正装配进最终 `.pptx` 并通过现有 `display_type=file` 契约返回。

## 任务边界
- 本任务是最小补修/收口任务，只修最终闭环缺口。
- 不扩展图表页，不引入 GLM-Image，不新增页面。
- 不重做页图渲染 service；优先复用已经完成的 CogView 页图渲染结果与图片页装配能力。

## 输入事实
- QA 失败任务：`验证PPT精美模式Demo闭环`
- 失败结论：当前 polished 模式仍返回 zip demo 包（`skill.py` polished 分支），虽然 `build_pptx_bytes()` 已支持图片页装配，但 `skill.py` 没有把渲染页图接入该装配路径。
- 已有能力：
  1. polished 模式入口已存在
  2. CogView-3-Flash 页图渲染已完成
  3. `build_pptx_bytes()` 已支持 `slide.image_path` 整页图片插入
- 当前闭环断点：`skill.py` 没有把 `demo['pages']` 的 file_path 映射为 slide dict 后传给 `build_pptx_bytes()`。

## 约束
- write_scope:
  - `skills/custom/ppt_generator/1.0.0/skill.py`
  - `backend/tests/test_ppt_generator_skill.py`
  - `backend/tests/test_ppt_image_page_assembly.py`
- read_only: false
- target_environment: dev
- execution_mode: dev
- owner_approval_required: false
- 必须复用现有 `build_pptx_bytes()` 图片页装配能力，不要再另造一套导出路径。
- 继续保持 `simple` 模式无回归。

## 交付物
- polished 模式最终 `.pptx` 闭环代码
- 测试，至少证明：
  1. polished 路径最终返回 `.pptx` 而不是 zip
  2. `.pptx` 中确实包含图片页
  3. simple 模式不回归
- `result.json`

## 验收标准
1. `polished` 模式最终返回的是 `.pptx` 文件，不再只是 zip demo 包。
2. 该 `.pptx` 至少包含 demo 的图片页（cover/content/closing 中的已渲染图片）。
3. 仍沿用现有 `display_type=file` 契约。
4. `simple` 模式无回归。
5. 在 `result.json` 中写清：现在 polished 路径的最终文件形态、图片页如何接入、还有哪些能力仍未包含（例如图表页 / GLM-Image）。

## 下游动作
review
