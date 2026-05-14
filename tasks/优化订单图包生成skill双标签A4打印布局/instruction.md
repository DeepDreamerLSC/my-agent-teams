# 任务：优化 订单图包生成 skill 双标签A4打印布局

## 任务类型
开发

## 目标
调整 `order-print-image-pack` 生成的标签图片/打印布局，使**每两张标签刚好撑满一个 A4 纸大小**，便于用户直接打印。

## 任务边界
- 只处理标签图片/导出布局，不改业务计算逻辑。
- 优先在现有导出链路中做最小改动。
- 不处理 Excel 格式兼容问题（另有任务）。
- 不做生产部署。

## 输入事实
- 林总工明确要求：输出的标签图片每两张要刚好撑满一个 A4 纸大小。
- 当前 skill 代码路径：
  - `/Users/linsuchang/Desktop/work/chiralium/skills/custom/order-print-image-pack/1.0.0/skill.py`
- 当前测试：
  - `/Users/linsuchang/Desktop/work/chiralium/backend/tests/test_order_print_image_skill.py`
- 你需要先确认当前标签图片是怎样排版/输出的，再决定最小改法。

## 约束
- write_scope:
  - `skills/custom/order-print-image-pack/1.0.0/skill.py`
  - `backend/tests/test_order_print_image_skill.py`
- read_only: false
- target_environment: dev
- execution_mode: dev
- owner_approval_required: false
- 任务采用池认领制；认领前请确认与你当前 active task 的 write_scope 不冲突。
- 输出目标是“方便打印”，优先满足 A4 双图满页，不追求额外美化。

## 交付物
- 打印布局调整代码
- 对应测试或最小可验证说明
- `result.json`

## 验收标准
1. 两张标签能按 A4 页尺寸合理铺满。
2. 现有标签生成主链路不回归。
3. 至少补一条能证明双标签 A4 布局的测试或验证说明。

## 下游动作
review
