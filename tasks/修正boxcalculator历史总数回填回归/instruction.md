# 任务：修正 box-calculator 历史总数回填回归

## 背景
上轮补修任务：
- `/Users/lin/Desktop/work/my-agent-teams/tasks/修正boxcalculator数量兜底解析回归`

审查驳回点已明确：
- 你修掉了“本轮文本”和“上游 params”误传
- 但 `recent_messages` 合并路径仍可能把历史错误 `total_quantity` 回填回来
- 所以多轮对话场景下，`A 4 双，B 6 双，算纸箱` 仍可能再次报“总双数不一致”

## 你的任务
请做最小补修：

### A. 修正 recent_messages 回填逻辑
目标：
- 当当前 query 已经解析出 `style_quantities`，且当前文本没有显式总数语义时
- 不允许再从 `recent_messages` 把历史 `total_quantity` 回填回来
- 必须彻底隔离“不可信历史总数”对当前混装 forward 的污染

### B. 补多轮上下文回归测试
至少新增：
1. 上一轮历史消息含错误总数，当前轮 `A 4 双，B 6 双，算纸箱` 仍正常 forward
2. direct_dimension 在带 `recent_messages` 时不回归
3. 反向验算在带 `recent_messages` 时不回归

## 边界
- 只改 `skill.py` 与 `test_box_calculator_skill.py`
- 不扩散到 orchestrator 或其他模块
- 以最小修复 recent_messages 路径为准

## 交付物
完成后写：
- `/Users/lin/Desktop/work/my-agent-teams/tasks/修正boxcalculator历史总数回填回归/result.json`

请在结果中写明：
- 如何阻断历史错误 total_quantity 回填
- 新增了哪些 recent_messages 场景测试
- 测试结果
