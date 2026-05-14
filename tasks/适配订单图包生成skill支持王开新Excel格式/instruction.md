# 任务：适配 订单图包生成 skill 支持王开新Excel格式

## 任务类型
开发

## 目标
适配 `order-print-image-pack` 对王开最新上传的 Excel 格式，使其能正确识别并输出与旧成功样本等价的图包结果。需要先分析**新旧 Excel 样本格式差异**，再在 skill 中兼容新格式。

## 任务边界
- 本任务允许修改 skill 的 Excel 解析/字段映射/格式适配逻辑。
- 不处理“同 session 文件复用”与“友好错误提示”——这两条已另有独立任务。
- 不做生产部署。

## 输入事实
- 王开最新成功上传样本（新格式）：
  - `file_id = 44960e88-b8cb-49e8-866b-07a2d2f743e5`
  - `original_name = 佳佳丽订单汇总5.5.xlsx`
  - `stored_path = /Users/linsuchang/Desktop/prod/chiralium/uploads/original/44960e88-b8cb-49e8-866b-07a2d2f743e5.xlsx`
- 王开历史成功样本（旧格式，可作参照物）：
  - `39659b84-6f25-46c8-89a7-9898aa585176` -> `订单汇总总单(1).xlsx`
  - `770c4794-9fae-497b-a451-45865502b0ba` -> `订单汇总总单(1).xlsx`
  - `71b39b50-5270-4e4e-8e27-dc7be6eca71a` -> `短款分品牌订单.xlsx`
- `order-print-image-pack` 当前代码路径：
  - `/Users/linsuchang/Desktop/work/chiralium/skills/custom/order-print-image-pack/1.0.0`
- 需要重点回答：
  1. 新样本与旧成功样本相比，sheet / 表头 / 列顺序 / 合并单元格 / 数值字段有什么变化
  2. 当前 skill 的哪段逻辑导致“格式变化后输出不对”
  3. 最小兼容改动是什么

## 约束
- write_scope:
  - `skills/custom/order-print-image-pack/1.0.0/skill.py`
  - `backend/tests/test_order_print_image_skill.py`
- read_only: false
- target_environment: dev
- execution_mode: dev
- owner_approval_required: false
- 允许只读查看生产样本文件内容，但不得修改生产文件。
- 适配目标是“兼容新格式”，不是牺牲旧格式成功路径。
- 修改前必须先对比旧成功样本与新样本差异，再动代码。

## 交付物
- skill 代码适配
- 新旧格式对比结论
- 对应测试
- `result.json`

## 验收标准
1. 明确写出新旧 Excel 格式差异。
2. skill 能兼容王开最新样本格式。
3. 旧成功样本路径不回归。
4. 至少补一条针对新格式样本的自动化测试。

## 下游动作
review
