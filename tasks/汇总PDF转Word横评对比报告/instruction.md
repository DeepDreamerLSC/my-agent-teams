# 任务：汇总 PDF 转 Word 横评对比报告

## 任务类型
development（分析汇总）

## 目标
汇总 7 个 profile 的横评数据，输出最终对比报告，明确给出最优模型推荐和后续路线建议。

## 任务边界
- 只做数据汇总和分析，不修改代码
- 产出设计文档到 design/pdf2word/ 目录
- 不跑样例，不部署模型

## 输入事实
- 横评框架：统一推理架构已完成（Phase A-D）
- 基线数据：`artifacts/pdf2word/model-eval/20260514-144102/apple_baseline/`
- 所有 profile 的跑批数据在 `artifacts/pdf2word/model-eval/` 下各 timestamp 目录
- 可用 profile 结果（用于汇总）：
  - apple_baseline：基线，5 样例全通过
  - mineru (lite)：0/5 优于基线
  - mineru (full)：0/5 优于基线和 lite
  - glm_ocr (MLX)：0/5 优于基线，blocks 有效但数量远低
  - qwen3_vl_8b：5/5 样例完成，0/5 优于基线，VLM 输出稳定性弱（JSON 解析失败多），定位为 VLM review 补充能力而非主 parser
  - paddleocr_vl：4/5 样例完成（数学试卷因 CPU 推理过慢未完成），block 数量较高但推理耗时极长（4 样例累计 2.63h）
  - glm_46v_flash：**blocked**（MLX 权重 7GB 下载速度仅 0.9MB/s，无法完成），报告中标注为"未完成评估"
- 技术方案：`design/pdf2word/PDF习题转Word详细技术方案.md`
- 架构方案：`design/pdf2word/PDF转Word本地模型横评推理架构落地方案.md`

## 约束
- write_scope 以 task.json 为准
- 基于当前可用数据汇总，不需要等 GLM-4.6V-Flash
- 结论必须基于数据，不能凭感觉
- PaddleOCR-VL 按 4/5 样例数据汇总，注明第 5 个缺失原因

## 交付物

### 最终横评报告：`design/pdf2word/PDF转Word本地模型横评最终报告.md`

内容要求：

1. **横评概览**
   - 7 个 profile 一览表（模型、类型、推理后端、角色定位）
   - 测试环境（M5 Max 128GB，5 个样例）

2. **逐样例对比**
   - 每个样例 × 每个模型的关键指标
   - 题号序列完整度、block 数量、图片/公式候选数、耗时

3. **汇总指标对比**
   - 每个模型的平均 block 数、平均耗时、题号召回率
   - 优于基线的样例数

4. **分维度评级**
   - OCR 文本质量
   - 版面结构识别
   - 图片/公式候选
   - 表格识别
   - 性能（耗时、内存）

5. **最终推荐**
   - 最优主 parser 候选
   - 是否建议进入 parser_backend=hybrid
   - VLM review worker 的推荐模型（如适用）
   - 被淘汰的模型及原因

6. **后续路线建议**
   - 基于横评结论的技术路线调整
   - 质量补齐优先级（图片/公式/答案）
   - 后续模型评估计划

## 验收标准
1. 覆盖所有 6 个有数据的 profile（apple_baseline, mineru_lite, mineru_full, glm_ocr, qwen3_vl_8b, paddleocr_vl）
2. GLM-4.6V-Flash 标注为"blocked 未完成评估"并说明原因
3. 每个维度有量化指标支撑
4. 有明确的最优模型推荐
5. 有后续路线建议
6. 报告可直接用于飞书推送摘要

## 下游动作
报告完成后 PM 飞书推送摘要给林总工，基于推荐结论推进后续质量补齐工作。
