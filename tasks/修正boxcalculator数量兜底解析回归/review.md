# Code Review - 修正 box-calculator 数量兜底解析回归

## 结论
- **审查结论：驳回（REQUEST CHANGES）**
- 依据：`instruction.md`、`result.json`、`skill.py` 与 `test_box_calculator_skill.py` 代码审查。
- 说明：任务目录当前 **无 `verify.json`**；本次结论基于代码与工件审查给出，未自行执行功能测试。

## 通过项
- 已把总数解析拆成“显式总数”与“兜底总数”两层，`10个/10双` 的 direct_dimension 兼容仍在：
  - `/Users/lin/Desktop/work/chiralium/skills/custom/box-calculator/1.0.0/skill.py:27-30,117-123,457-465`
- 已补 plain query 与上游错误 `params.total_quantity` 的回归测试：
  - `/Users/lin/Desktop/work/chiralium/backend/tests/test_box_calculator_skill.py:78-108`

## 阻塞问题

### 1. `recent_messages` 合并路径仍会把历史 `total_quantity` 回填回来，forward 混装回归在多轮对话下没有真正修掉
- 位置：
  - `/Users/lin/Desktop/work/chiralium/skills/custom/box-calculator/1.0.0/skill.py:117-123`
  - `/Users/lin/Desktop/work/chiralium/skills/custom/box-calculator/1.0.0/skill.py:139-159`
  - `/Users/lin/Desktop/work/chiralium/skills/custom/box-calculator/1.0.0/skill.py:161-181`
- 当前修复会在“文本里已解析出 `style_quantities`、但没有显式总数语义”时先把 `request['total_quantity']` 置空，这是对的。
- 但紧接着又调用 `_merge_recent_request()`；而 `_merge_recent_request()` 在 `merged['mode']` 还没被判成 `forward` 之前，不会提前 `break`，仍会执行：
  - `if merged['total_quantity'] is None: merged['total_quantity'] = historical['total_quantity']`
- 这意味着：
  - 当前轮 `A 4 双，B 6 双，算纸箱` 虽然不再从**本轮文本**里误取 `4`
  - 但仍可能从 **recent_messages** 里把旧的 `total_quantity=4` 或其他历史总数回填回来
  - 然后 `_run_forward()` 再次报出“总双数不一致”
- 这条路径是真实运行时代码，不是理论分支；当前补修还没有把“混装明细下不可信总数必须被彻底隔离”做完整。

## 测试缺口

### 2. 没有覆盖 `recent_messages` 场景，因此上面的剩余回归没有被测出来
- 位置：
  - `/Users/lin/Desktop/work/chiralium/backend/tests/test_box_calculator_skill.py:49-181`
- 当前新增测试全部使用 `context={}`，只覆盖了：
  - 本轮文本直输
  - 上游 params 误传
  - direct_dimension / reverse 非回归
- 但没有覆盖最关键的多轮上下文场景，例如：
  - 上一轮消息里带了错误总数
  - 当前轮只发 `A 4 双，B 6 双，算纸箱`
  - `recent_messages` 是否又把旧总数回填回来
- 由于 skill 运行时代码显式依赖 `context.recent_messages`，这个缺口会直接漏掉真实风险。

## 最终意见
这次补修修掉了“本轮文本直输”和“上游 params 误传”两条路径，但 **没有修掉 `recent_messages` 回填历史总数** 这条真实运行时路径，所以 forward 混装回归在多轮对话里仍可能复现。建议补齐该逻辑和对应测试后再合入。
