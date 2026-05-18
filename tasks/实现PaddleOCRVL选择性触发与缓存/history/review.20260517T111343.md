# 审查说明：实现PaddleOCRVL选择性触发与缓存

## 结论

**请求修改（request_changes）。**

## 阻塞问题

1. 当前实现没有真正守住“Paddle 不能整本同步跑”这条核心边界。

   代码里的 `_select_paddle_pages()` 直接拿 baseline 全量页做 `page_scope`，然后把所有 `baseline_low_confidence` 页加入触发集合。结果是当某个样例整体低置信、但其实没有 enhancement context 时，Paddle 仍会被扩成整本页触发。

   这不是理论风险，而是已经出现在实际产物里：`语文五年级` 的 `profile-audits.json` 显示 `paddleocr_vl.selected_pages = [1..13]`，`selected_ratio=1.0`，等价于整本 Paddle 跑批，违反了任务边界和验收标准。

2. 测试门禁没有把这个问题挡住。

   现有单测覆盖了 quality 才触发、按页触发、缓存复用、非 quality 不触发，但没有覆盖“低置信不能把 Paddle 放大成整本触发”的负例。Phase 3 e2e 也只要求报告和审计产物存在，没有对 `selected_ratio` 或整本触发行为做断言，所以当前缺陷能全绿通过。

## 非阻塞观察

- 审计结构本身是对的：报告里已经有触发页、触发比例、缓存命中、fallback 等字段。返工时不需要推翻这套产物，只需要把触发上界重新收紧，并把对应 guardrail 也纳入测试和报告。

## 返工建议

1. 把 Paddle 的可触发页上界收紧到真正允许的 enhancement context 内，不能仅因 `baseline_low_confidence` 就对无 enhancement context 的整本页面集触发。
2. 补单测覆盖“所有页低置信但不允许整本 Paddle”的反例。
3. 补 e2e 门禁，至少能在产物里显式识别并拦截 `selected_ratio=1.0` 这类越界行为。

## 总结

当前版本已经具备缓存与审计框架，但触发策略仍越过了任务边界，因此本轮还不能通过。
