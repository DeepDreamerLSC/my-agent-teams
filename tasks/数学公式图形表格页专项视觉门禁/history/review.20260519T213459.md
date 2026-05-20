# Review - 数学公式图形表格页专项视觉门禁

## 结论
- **审查结果：request_changes**
- **recommended_next_action：dev**
- **当前是否可直接收口：否**

这轮实现方向是对的：
- 已把数学专项 gate 单独抽出来；
- 已覆盖公式 / 图形 / 表格 / 题块顺序四类信号；
- formula audit-only、图形绑定回退、题块顺序回退、表格低分这些“显式失败路径”也确实有测试。

但当前还有两个阻塞缺口，会让上游通过“漏传 payload”的方式直接绕过数学专项 gate。

## 阻塞项 1：focus page 缺失专项 region payload 时会直接通过
当前实现里，`_build_math_pages()` 对：
- `formula_regions`
- `graphic_regions`
- `table_regions`

统一都是 `page.get(... ) or []`。

问题在于：
如果 page 已经声明自己是公式/图形/表格 focus page，但上游根本没把对应 region list 传下来，系统不会把它视为 not-ready，而是直接按“没有 region 要检查”处理。

我做了最小复现：
- 把 fixture 的 `pages[0].formula_regions=[]`
- 或把 `pages[1].graphic_regions=[]`

结果 report 仍然是：
- `status=ready`
- `artifact_ready_for_scoring=true`
- 没有任何 veto

这与任务要求 **“必须同时考虑公式/图形/表格/题块顺序”** 不一致。因为现在只要专项 region payload 漏传，gate 就被绕过去了。

### 最小返修口径
当 page 声明：
- `focus_tags` 包含 `formula`
- `focus_tags` 包含 `graphic`
- `focus_tags` 包含 `table`

对应 region list 就不应允许为空；否则应进入：
- `artifact_not_ready`
- 并带明确 failure，例如 `formula_regions_missing:p1` / `graphic_regions_missing:p2`

同时补 1~2 条 pytest 固化这个 contract。

---

## 阻塞项 2：图形-题干绑定证据可以被整体省略而不失败
当前“图形与题干绑定”这件事，只有在以下前提都满足时才会失败：
- `binding_pairs` 已经存在
- 且里面提供了 `binding_iou`

但如果上游直接把这部分证据整体省略：
- `binding_pairs=[]`
- 甚至 graphic region 自己的 `binding_iou` 也不传

当前 gate 仍然会 `ready` 通过。

我做了两组最小复现：
1. `pages[1].question_order.binding_pairs=[]`
2. 同时删除 `pages[1].graphic_regions[0].binding_iou`，并保持 `binding_pairs=[]`

两种情况下，report 仍然是：
- `status=ready`
- `artifact_ready_for_scoring=true`
- `vetoes=[]`

这和任务要求 **“图形与题干绑定异常要能显式暴露”** 不符。因为“没有绑定证据”本身就已经是一个应暴露的问题，现在却被静默当成通过。

### 最小返修口径
对 `graphic` / `question_order` focus 页面补强 contract：
- 至少要有可核对的 `binding_pairs`
- 每个 binding pair 都必须有 `binding_iou`
- 缺失时应进入 `artifact_not_ready` 或明确 blocker

并补测试覆盖：
- `binding_pairs=[]`
- `binding_iou` 缺失

---

## 其余部分的评价
除上述两个阻塞问题外，其余方向我认为是成立的：
- formula audit-only 不再冒充真实视觉分，这点成立；
- 图形绑定 / 题块顺序 / 表格低分确实都有 veto code；
- 下游透传 `downstream_visual_similarity_contract` 的整体思路也对。

也就是说，这轮不是推翻重做，而是**把“缺失专项证据不能静默通过”这一层 contract 补齐**。

## 我补做的核对
我额外做了：
- `py_compile`
- 定向 `pytest`
- `git diff --check`
- 4 组最小复现脚本

结果是：
- 官方测试都通过；
- 但最小复现证明：**缺失 formula/graphic payload、缺失 binding_pairs / binding_iou 目前会被静默放过。**

## 建议
建议 **打回给 dev 最小返修**：
1. focus page 缺失 formula/graphic/table region payload 时，不得继续 `ready`；
2. graphic/question_order 页面缺失 binding 证据时，不得继续 `ready`；
3. 补对应 pytest 后再回提。

返修后我可以快速复审。
