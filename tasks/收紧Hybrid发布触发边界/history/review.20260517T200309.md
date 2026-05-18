# Review - 收紧Hybrid发布触发边界

## Blocking

- [settings.py](/Users/linsuchang/Desktop/work/chiralium/backend/app/services/pdf_to_word/settings.py:53) 的 gate 还漏了一条关键分支：它把缺失 `mode` 的请求按 `settings.default_mode` 归一化。结果是，只要环境把默认模式设成 `quality`，公共路径上的显式 `parser_backend=hybrid_experimental` 即使没显式传 `mode=quality`，也会被放行到 Hybrid。这和任务要求的“只有显式 `quality` / allowlist / 内部评测才允许进入”不一致。

## Evidence

- 我补跑了相关 25 个测试，全部通过；问题不是现有行为被测试覆盖住了，而是这条分支根本没被测试到。
- 我本地复现了这条漏判：`PDFToWordSettings(default_mode='quality', parse_backend='apple')` 下，`resolve_released_parser_backend('hybrid_experimental', mode=None, settings=...)` 当前返回 `hybrid_experimental`。
- `conversion_service.py` 和 `skill.py` 都会在缺少显式 `mode` 时回退到 `default_mode`，所以这个问题会穿透到 service/skill，而不只是 settings 辅助函数。

## Verdict

`request_changes`

建议把“显式 `mode=quality`”和“默认模式恰好是 quality”严格区分开，并补一条 `default_mode=quality + 缺失 mode + 显式 hybrid 请求` 的回归测试。
