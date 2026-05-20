# Review - 科学实验页表格与图片区关键区域视觉门禁

## 结论
- **审查结果：request_changes**
- **recommended_next_action：dev**
- **当前是否可直接收口：否**

这轮实现方向是对的：
- 已经把科学实验页的表格区、图片区、实验记录区、邻接关系拆出来单独打分；
- happy / 表格失败 / 图片绑定失败三条主路径也都补了；
- 明显失败场景能产出 veto，这部分是成立的。

但当前还有两个阻塞缺口，会让上游通过“漏传关键区域/关系元数据”的方式直接绕过科学专项 gate。

## 阻塞项 1：关键 source region 缺失时，不会进入 not-ready / veto
当前实现只看 `source_regions` 里实际传进来的内容。

问题是：
如果上游直接漏传某个关键 region，例如：
- `table`
- `image`
- `experiment_record`
- `question_stem`

系统不会把它当成 contract 不完整，而是直接“不检查这个区域了”。

我做了最小复现：
1. 从 happy fixture 里删掉 `table` source region；
2. 甚至直接把 `source_regions=[]`。

结果：
- 删掉 `table` 后，report 仍然是 `overall_score=0.9637`、`human_review_required=false`、`vetoes=[]`；
- `source_regions=[]` 后，report 甚至会给出 `overall_score=0.0`，但仍然 `human_review_required=false`、`vetoes=[]`。

这说明：**关键 source region 可以直接从 payload 中消失，而 gate 不会把它当成 blocker。**

这与任务要求“必须覆盖表格外框/行列观感、图片区、实验记录区”不一致。

### 最小返修口径
建议把科学专项 gate 升级成强 contract：
- science experiment mixed page 必须具备关键 source region；
- 缺失任一关键 region 时，应进入 not-ready 或 blocker；
- 并补 pytest 固化“删掉关键 region 不得继续通过”。

---

## 阻塞项 2：关系检查完全依赖 `adjacent_to`，省略后会整体消失
当前：
- 图片与题干绑定
- 表格与题干邻接
- 表格与图片区邻接
- 实验记录区邻接

这些 relation 都是靠 `source_regions[].adjacent_to` 生成的。

问题在于：
如果上游直接把 `adjacent_to` 省略或清空，relation 根本不会被建立，于是相关检查会整体消失，而页面仍然能高分通过。

我做了最小复现：
- 把 happy fixture 里所有 region 的 `adjacent_to=[]`

结果：
- report 仍然返回 `overall_score=0.9538`
- `human_review_required=false`
- `vetoes=[]`
- `relation_scores=[]`

也就是说，**图片与题干绑定、实验记录区邻接关系可以被完全跳过而不报错。**

这和任务要求“必须覆盖图片与题干绑定、实验记录区邻接关系”直接冲突。

### 最小返修口径
建议补强 relation contract：
- 对 science experiment mixed page，必须存在必要关系定义；
- 如果 `adjacent_to` 缺失到无法构造 image-question / table-question / record-table 等关键关系，应该进入 not-ready 或 blocker；
- 并补 pytest 覆盖 `adjacent_to` 缺失/清空场景。

---

## 其余部分的评价
除上述两点外，其余方向我认为是成立的：
- 表格失真 / 图片绑定断裂 / 实验记录区邻接异常这些“显式失败路径”确实已经能打到 veto；
- `recommended_common_code` 透传给后续公共 veto 链路的思路也是对的。

所以这轮不是推翻重做，而是要把：
**“关键 source region 和关键 relation 不能被静默省略”** 这一层 contract 补齐。

## 我补做的核对
我额外做了：
- `py_compile`
- 定向 `pytest`
- `git diff --check`
- 3 组最小复现脚本

结果是：
- 官方测试通过；
- 但最小复现证明：**缺失关键 source region 或清空 `adjacent_to`，当前会被静默放过。**

## 建议
建议 **打回给 dev 最小返修**：
1. 缺失关键 source region 时，不得继续通过；
2. 缺失关键 relation 定义时，不得继续通过；
3. 补对应 pytest 后再回提。

返修后我可以快速复审。
