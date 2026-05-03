# Code Review - 紧急修复生产外箱尺寸计算直接尺寸输入模式

## 结论
- **审查结论：驳回（REQUEST CHANGES）**
- 依据：`instruction.md`、`result.json`、运行时代码与测试代码审查。
- 说明：任务目录当前 **无 `verify.json`**；本次结论基于代码与工件审查给出，未自行执行功能测试。

## 通过项
- 已补出 `direct_dimension` 运行时模式，并在明显属于“鞋盒实际尺寸 + 数量”的输入下优先纠偏，不再直接落入 reverse：
  - `/Users/lin/Desktop/work/chiralium/skills/custom/box-calculator/1.0.0/skill.py:136-154,178-206`
- 已补 `10个 / 10双` 识别、尺寸不匹配提示与 A-G 参考尺寸：
  - `/Users/lin/Desktop/work/chiralium/skills/custom/box-calculator/1.0.0/skill.py:27-30,455-459,510-518`

## 阻塞问题

### 1. 新增的总数兜底正则会把混装明细里的第一个“X双/个”误当总数，回归破坏原有 forward 混装输入
- 位置：
  - `/Users/lin/Desktop/work/chiralium/skills/custom/box-calculator/1.0.0/skill.py:27-30`
  - `/Users/lin/Desktop/work/chiralium/skills/custom/box-calculator/1.0.0/skill.py:120-121,208-215,455-459`
- 当前新增了：
  - `re.compile(r'(?<![0-9.])([0-9]+)\s*(?:双|个)(?![0-9.])', re.I)`
- `_parse_total_quantity()` 会按顺序取**第一个**匹配值直接返回；而 `_run_forward()` 又会把它当 `declared_total` 强校验总双数一致。
- 这会让原本应当继续支持的混装输入发生回归。例如：
  - `A 4 双，B 6 双，算纸箱`
- 按当前逻辑：
  1. `style_quantities` 会解析出 `A=4, B=6`
  2. `total_quantity` 会被第三条兜底正则提前解析成 **4**
  3. `_run_forward()` 再报错：`混装双数合计为 10 双，但声明总双数为 4 双`
- 这与任务要求中的“**不回归现有能力**”冲突，且会破坏原有 A-G 正向混装模式，属于阻塞问题。

## 测试问题

### 2. 缺少“混装但未显式声明总双数”的回归测试，导致上述回归未被捕获
- 位置：
  - `/Users/lin/Desktop/work/chiralium/backend/tests/test_box_calculator_skill.py:62-120`
- 当前新增测试覆盖了：
  - direct dimension 成功
  - `10个` 误落 reverse 的纠偏
  - mismatch 提示
- 但缺少关键非回归用例，例如：
  - `A 4 双，B 6 双，算纸箱`
- 这正是本次回归能够漏出的直接原因。

## 最终意见
本次修复把“直接尺寸输入模式”主问题补上了，但同时引入了 **forward 混装数量解析回归**。在修正总数兜底解析策略、并补上对应非回归测试前，暂不建议合入。
