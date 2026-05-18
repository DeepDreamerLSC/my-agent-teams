# 任务：收紧 Hybrid 发布触发边界，确保 auto/apple 默认不误入 hybrid

## 任务类型
development

## 目标
把当前 PDF 转 Word 的 hybrid 触发边界收紧到正式口径：**只有显式 `quality` / allowlist / 内部评测** 才允许进入 `hybrid_experimental`；`auto`、`apple`、默认同步路径不能因为配置继承或参数解析而误入 hybrid。

## 任务边界
- 这是代码与配置约束任务，不是文档任务。
- 不改变 hybrid 主链能力本身，只修正触发与暴露边界。
- 不要把当前显式 `quality + hybrid_experimental` 的可用路径做坏。

## 输入事实
- 当前正式口径是：
  - `apple default`
  - `hybrid_experimental quality gray`
  - `formula audit-only / merge-disabled`
- 从当前代码与测试可见：
  - `resolve_effective_parser_backend('auto')` 当前会落到 `apple`
  - 但 `settings.parse_backend` / `skill._resolve_parser_backend()` / API 参数组合仍可能让默认行为间接落到 `hybrid_experimental`
  - 现有测试允许 `balanced + parser_backend=hybrid_experimental` 这类组合，需要根据正式口径重新收紧
- 相关文件：
  - `backend/app/services/pdf_to_word/parser_client.py`
  - `backend/app/services/pdf_to_word/conversion_service.py`
  - `backend/app/services/pdf_to_word/settings.py`
  - `skills/custom/pdf_to_word/1.0.0/skill.py`
  - `skills/custom/pdf_to_word/1.0.0/manifest.json`

## 约束
- write_scope 以 task.json 为准
- 必须保证：
  1. `auto` / 默认同步路径不进 hybrid
  2. `apple` 明确仍是默认同步 parser
  3. `hybrid_experimental` 只能通过显式、受控条件进入
- 若需要 allowlist / 开关，请使用当前代码体系内已有配置方式，避免引入过重新机制
- 测试必须覆盖 skill / service / API 三层口径一致性

## 交付物
1. 代码修改：收紧 hybrid 触发边界
2. 测试补充/更新：至少覆盖
   - `auto` 默认仍走 `apple`
   - 仅显式 `quality + hybrid_experimental`（或你定义的正式受控条件）可进入 hybrid
   - skill / API / service 口径一致
   - `mock` / `apple` 既有路径不回归
3. `result.json`：写明你如何定义“受控进入 hybrid”的正式条件

## 验收标准
1. `auto/apple` 默认路径不会误入 hybrid。
2. hybrid 只能在显式、受控条件下进入。
3. skill / API / service 三层行为一致。
4. 相关测试通过，且不破坏现有 apple/mock 主路径。

## 下游动作
完成后进入 review-1 审查；通过后交 qa-1 验证默认触发边界与显式 quality 路径。
