# 任务：补齐 QuestionRegion 可判定性与跳过策略

## 任务类型
开发

## 目标
完善 question_region_detector 的可判定性检查，明确正负样例页的可判定门槛，不可判定页直接跳过增强，不做页尾兜底拼接。

## 任务边界
- 修改 `question_region_detector.py`
- 不修改其他管线模块

## 输入事实
- 当前 question_region_detector 已实现基础题号 anchor 检测
- 横评中 `语文五年级` 样例的题号区域不可判定，应作为负样例跳过
- `数学试卷`、`英语八年级`、`五下科学`、`数学八年级` 应作为正样例通过
- 架构师方案门禁：题号区域不可判定的页面直接跳过增强

## 约束
- write_scope: `question_region_detector.py`
- 可判定性门槛需要用 5 个横评样例验证

## 交付物
- 更新后的 question_region_detector.py，包含可判定性判定逻辑和跳过策略
- 在 result.json 中说明正/负样例判定结果

## 验收标准
1. `语文五年级` 的题号区域被判定为不可判定，该样例页全部跳过增强
2. 其余 4 个样例的题号区域被判定为可判定
3. 不可判定页不会产生空候选或无效 merge decision

## 下游动作
完成后解锁 `实现HybridMVP图片表格并回链路` 任务。
