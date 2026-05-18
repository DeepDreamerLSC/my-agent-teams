# Review - 收紧Hybrid发布触发边界

## Verdict

`approve`

上轮阻塞点已经修复：现在只有“请求本身显式带 `mode=quality` 且显式请求 `parser_backend=hybrid_experimental`”才会进入 Hybrid。`default_mode=quality` 不再被当成显式 `quality` 请求；缺失 `mode` 时，即使显式请求 Hybrid，也会回落到 `apple`。

## Evidence

- 我补跑了相关 27 个测试，全部通过。
- 我重新复现了上轮驳回分支：
  - `resolve_released_parser_backend('hybrid_experimental', mode=None, settings=default_mode_quality)` 现在返回 `apple`
  - `resolve_released_parser_backend('hybrid_experimental', mode='quality', settings=default_mode_quality)` 返回 `hybrid_experimental`
- 四层口径已经对齐：
  - `settings.py` 只看原始 `requested_mode`
  - `conversion_service.py` 不再把 `effective/default mode` 传进 Hybrid gate
  - `skill.py` 把 `requested_mode` 和最终显示/执行的 `mode` 分开
  - API 测试覆盖了“缺失 mode + 显式 hybrid 请求”仍不放行 Hybrid

## Notes

没有发现新的阻塞问题。当前实现已经满足任务要求：`auto/apple` 默认路径不会误入 Hybrid，显式 `quality + hybrid_experimental` 受控入口也保留可用。
