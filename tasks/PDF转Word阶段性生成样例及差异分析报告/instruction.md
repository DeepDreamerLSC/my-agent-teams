# 任务：PDF转Word阶段性生成样例及差异分析报告

## 任务类型
Owner 直派 / 阶段性汇总报告

## 目标
整理当前 PDF 转 Word 阶段已沉淀的多策略样例（Hybrid、MinerU、PaddleOCR、GLM、Qwen 等），输出一份结构化差异分析报告，供林总工快速查看当前阶段各方案表现、关键差异与后续改进方向。

## 输入范围
重点读取以下现有 artifacts：
- `/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-archive/profiles/`
- `/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-archive/reports/`
- `/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-acceptance/`
- `/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/model-eval/`
- `/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/phase3-paddle-quality/`
- `/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/phase4-formula-baseline/`
- `/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/p1-formula-crop/`

## 交付物
1. `/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-archive/reports/PDF转Word阶段性生成样例与差异分析报告.md`
2. `/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-archive/reports/PDF转Word阶段性生成样例与差异分析报告.json`
3. 在任务 `result.json` 中写明报告路径、阶段结论、关键改进方向，并作为飞书同步摘要。

## 报告结构要求
- 当前阶段方案清单与样例来源
- 典型文档类型（表格、图文混排、公式、英语阅读/长文等）
- 各方案输出样例描述
- 对比维度表格
- 方案评分对照
- 关键差异点总结
- 当前阶段需要改进的方向

## 约束
- 不伪造“截图”；如果当前 artifacts 里没有现成截图，就用样例路径、关键产物说明、结构化描述替代。
- 明确区分：工程门禁、样例归档、人工视觉95 结论，不混淆口径。
- 必须说明哪些方案适合作为主 parser、哪些适合作为增强链路、哪些仅适合作为 review / audit 能力。
- 对缺失样例/缺失 provenance 的地方要明确标注，不要模糊表述。

## 验收标准
- 林总工无需翻多个目录即可理解当前阶段各方案差异。
- 报告中必须明确：当前最优默认方案、当前增强链路方案、表格/公式/版面/图片四类能力的阶段判断、下一步改进方向。
