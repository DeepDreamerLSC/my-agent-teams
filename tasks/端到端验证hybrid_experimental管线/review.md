# 审查说明：端到端验证hybrid_experimental管线

## 结论

**审查通过（approve）。**

这轮可以通过，不是因为问题被绕开了，而是因为我上轮驳回的两个阻塞点都已经真正修掉了。

## 已修复点 1

上轮的第一个阻塞点是：

- `page_diffs` 通过 `zip(...)` 直接拼装
- 没有任何页数一致性断言
- 一旦某段链路少页，测试可能静默截断并继续通过

现在 `build_hybrid_e2e_report()` 已经先显式检查：

- `len(baseline_pages)`
- `len(merged_pages)`
- `len(enhancement_result.pages)`
- `len(validation_report.page_results)`

四者必须完全一致，否则会直接抛出带样例名和页数的 `AssertionError`。

这意味着“每页都有 verdict”已经不再只是口头要求，而是被真正落实成了测试门禁。

我还额外复核了当前落盘的 `report.json`，5 个样例都满足：

- 五下科学：`6 == 6`
- 数学八年级：`8 == 8`
- 数学试卷：`12 == 12`
- 英语八年级：`12 == 12`
- 语文五年级：`13 == 13`

所以这次不是“代码里加了断言但报告仍然有坑”，而是**代码和现有产物都对齐了**。

## 已修复点 2

上轮第二个阻塞点是：

- 测试把 `final_equals_baseline == true` 写成所有页都必须满足的硬断言

这个约束会把“当前 5 个样例暂时全部 fallback”错误固化成长期回归基线。后续如果 validator 真正开始接受增强页，测试反而会因为产品行为变好而失败。

现在这个硬断言已经去掉了。

保留下来的增强模式门禁是合理的：

- 真实生产 `HybridExperimentalPipeline` 被调用
- 产物路径存在
- verdict 合法
- 至少 3 个样例走通完整链路
- 至少 1 次 fallback 被触发

这才是任务验收真正需要长期稳定守住的契约。

## 复跑结果

我复跑了当前测试：

```bash
cd /Users/linsuchang/Desktop/work/chiralium/backend
TMPDIR=/private/tmp PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/chiralium-pyc PYTEST_ADDOPTS='-p no:cacheprovider' .venv/bin/python -m pytest tests/test_hybrid_e2e.py -q
```

结果：

```text
3 passed, 4 warnings
```

warnings 仍然是 FastAPI `on_event` 的既有弃用告警，不是这条任务引入的新问题。

## 非阻塞说明

有一个小点我保留为非阻塞观察：

- 当前 `result.json` 仍然是 13:35 的旧摘要
- 没有同步记录这次第二轮补修新增的两个修复点

这不影响当前通过，因为代码状态、测试状态和落盘产物都已经满足审查要求。

但从任务审计角度看，后续如果还有类似多轮补修，最好把最终一轮真实改动同步回 `result.json`，这样 PM/QA 只看任务目录就能准确知道最后到底修了什么。

## 总结

这轮通过的原因很简单：

1. **页数一致性断言已补，`zip(...)` 静默漏页问题已消除**
2. **错误的 `final_equals_baseline` 全局硬约束已移除**
3. **测试复跑通过**
4. **现有 report 产物本身也没有页数截断问题**

因此这条任务已经满足进入下一阶段集成测试的条件。
