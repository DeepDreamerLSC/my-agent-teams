# 任务：评估 M5 Max 本地运行 MinerU 与视觉模型方案

## 任务类型
design — 架构评估与方案调整

## 目标
原 PDF 转 Word 方案设计为 HTTP sidecar 架构（MinerU service + MiniCPM-V service），因为假设运行环境资源有限。但当前部署环境是 **Apple M5 Max 128GB RAM 的 Mac Studio**，算力和内存充裕。请重新评估是否可以改为本地进程/本地模型调用方案，简化部署和运维复杂度。

## 任务边界
- 只出评估结论和修订后的实施方案，不写代码
- 评估结果写入 result.json
- 需要对比原 sidecar 方案与本地方案的优劣

## 输入事实
- 硬件环境：Apple M5 Max，128GB 统一内存，macOS
- 当前项目：chiralium 后端（FastAPI，Python）
- 已完成：PDF 转 Word Skill MVP（mock/fixture 闭环）已跑通
- 原方案设计文档：`/Users/linsuchang/Desktop/work/chiralium/design/product/pdf-to-word-skill-mineru-minicpmv-design.md`
- 原方案拆解：见 `/Users/linsuchang/Desktop/work/my-agent-teams/tasks/评审PDF转WordSkill方案并拆解实施/result.json` 的 implementation_slices
- MinerU：PDF 解析工具，支持 macOS/Apple Silicon
- MiniCPM-V：视觉语言模型，用于局部 OCR 增强
- 当前 docker runtime network=none，不适合 sidecar 通信

## 约束
- write_scope: []（只读评估，不修改任何文件）
- read_only: true
- 依赖上游任务: 无
- target_environment: dev
- execution_mode: dev
- owner_approval_required: false

## 评估要点
1. **MinerU 本地进程模式**：M5 Max 128G 是否可以直接在 skill subprocess 或 backend worker 中调 MinerU Python API/CLI，而无需单独部署 sidecar service？性能和内存占用如何？
2. **视觉模型本地运行**：128G 统一内存是否足以在本地跑 MiniCPM-V 或其他苹果友好的视觉模型（如mlx-vlm、ollama + llava 等）？推荐哪个方案？
3. **Apple ML 框架适配**：是否有 Core ML / MLX 优化的 PDF 解析或 OCR 方案可替代 MinerU + MiniCPM-V 组合？Vision.framework 能否承担部分工作？
4. **部署复杂度对比**：本地方案 vs sidecar 方案的部署、调试、监控差异
5. **方案修订**：如果本地方案可行，请修订原 implementation_slices 中 #3（MinerU）和 #4（MiniCPM-V）的 write_scope、acceptance、dependencies

## 交付物
1. result.json 中包含：
   - 方案评估结论（本地 vs sidecar 推荐）
   - 修订后的 implementation_slices（如方案调整）
   - 风险评估
   - 环境依赖清单（需要安装什么）

## 验收标准
1. 明确回答"本地可行还是 sidecar 更优"
2. 如果本地可行，给出修订后的实施切片（含 write_scope、acceptance、dependencies）
3. 列出需要预装的环境依赖（Python 包、系统库、模型权重等）
4. 评估结论经过代码/文档验证，不是纯推测

## 下游动作
PM 根据评估结论创建后续实施任务（MinerU 接入 + 视觉模型接入）
