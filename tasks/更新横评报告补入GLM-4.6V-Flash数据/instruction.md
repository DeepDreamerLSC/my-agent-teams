# 任务：更新横评报告补入 GLM-4.6V-Flash 数据

## 任务类型
文档更新 / 数据整合

## 目标
将补评 GLM-4.6V-Flash 任务的 5 样例评测数据补入横评最终报告，消除 "blocked" 标记。

## 任务边界
- 只修改 `artifacts/pdf2word/final-archive/reports/横评最终报告.md`
- 不修改任何代码或评测数据文件

## 输入事实
- 补评数据路径：`artifacts/pdf2word/model-eval/20260516-104815/glm_46v_flash/`（5 个样例）
- 汇总报告：`artifacts/pdf2word/model-eval/20260516-104815/comparison_report.json`
- 当前报告标记 glm_46v_flash 为 "blocked / 无完整 run"，需要更新为实际数据

## 约束
- write_scope: `artifacts/pdf2word/final-archive/reports/横评最终报告.md`
- 结论必须与补评任务 result.json 一致：GLM-4.6V-Flash VLM review JSON 解析 5/5 失败，不适合作为 VLM review 对照

## 交付物
更新后的 `横评最终报告.md`，包含：
- 数据源表和 Profile 定位表中 glm_46v_flash 的实际数据
- 汇总指标对比表补入完整行
- 逐样例对比表补入每样例数据
- 分维度评级补入
- 淘汰/降级原因更新

## 验收标准
1. 报告中不再有 glm_46v_flash 的 "blocked" 标记
2. 指标对比表有 glm_46v_flash 完整行
3. 结论与 comparison_report.json 一致

## 下游动作
报告更新后，供架构师设计后续技术路线时引用完整数据。
