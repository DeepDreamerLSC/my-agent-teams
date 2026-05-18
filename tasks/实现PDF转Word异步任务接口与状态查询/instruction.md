# 任务：实现 PDF 转 Word 异步任务接口与状态查询，支撑 quality/hybrid 后台运行

## 任务类型
development

## 目标
为 PDF→Word 增加第一版 **异步 job API**，让 `quality / hybrid` 这类长耗时链路不再只能同步等待。首轮目标是打通：**创建 job + 查询状态 + 产物定位**，状态至少覆盖 `queued / running / succeeded / failed`。

## 任务边界
- 只做 PDF→Word 后端异步任务接口与最小可运行 job 执行骨架，不做前端页面。
- 本任务优先支持 `create job / get job status`；`cancel`、更复杂的超时治理和多机调度留给下游任务。
- 本轮请尽量收敛到 `app/api/pdf_to_word.py` + 新增 `app/services/pdf_to_word/job_service.py` + 专用异步测试文件完成，不要占用 `conversion_service.py`、`exercise_*`、`test_pdf_to_word_service.py` 等当前被其他任务持有的文件。
- 不改变默认发布边界：`apple default + hybrid_experimental quality gray + formula audit-only / merge-disabled`。
- 保持现有同步 `/api/pdf-to-word/convert` 路径可用，不能因引入 job 模式而回归。

## 输入事实
- 当前 `app/api/pdf_to_word.py` 只有同步 `/pdf-to-word/convert`，上传后直接返回 DOCX；长 PDF 或 `quality/hybrid` 模式会阻塞交互体验。
- 规划文档已把“异步任务产品化 / job API / 状态查询 / 阶段性 artifacts”列为下一阶段重点。
- 当前答案/教师版链路仍在 dev-2 收口，因此 dev-1 恢复后适合并行推进产品化主线。
- 现有 `PDFConversionService` 与 `pdf_to_word` service 目录已具备转换主链路，可作为 job worker 的最小执行核心。

## 约束
- `write_scope` 以 `task.json` 为准。
- 首轮实现优先选择**本地可运行、可测试、可回放**的最小 job 存储/执行方案；不要为了一次到位引入过重基础设施。
- job 产物至少要可追踪：输入文件名、mode/parser_backend、状态、失败原因、输出文件或 artifacts 路径。
- 同步主链路仍应保留给 baseline 稳定路径；异步能力主要服务 `quality/hybrid` 等长任务。
- 若遇到范围不清的取消/恢复/多机调度诉求，本任务只记录风险与下一步建议，不要无边界扩张。

## 交付物
1. `/api/pdf-to-word/jobs` 相关后端接口（至少创建 job、查询 job）。
2. `pdf_to_word` service 层的最小异步 job 执行与状态持久化/缓存骨架。
3. 相关测试更新，至少覆盖：创建 job、状态流转、成功/失败结果查询、同步 `/convert` 不回归。
4. `artifacts/pdf2word/p2-productization/` 下的样例说明或运行摘要，说明当前 job 产物结构与状态事实。
5. `result.json`：写明接口形态、状态枚举、产物路径、已知限制与下游建议。

## 验收标准
1. 可以通过 API 创建 PDF→Word job，并查询到 `queued / running / succeeded / failed` 状态之一。
2. job 成功后可获得输出文件或产物路径；失败时有可解释的错误信息。
3. 同步 `/api/pdf-to-word/convert` 路径不回归。
4. 指定测试通过，且实现不绕开现有 `PDFConversionService` 主链路。
5. 文档/产物中明确当前仍未覆盖的范围：取消、复杂超时治理、多机调度。

## 下游动作
完成后进入 review-1 审查；通过后作为 P2 异步产品化主链路，并供后续取消/超时、阶段性 artifacts 增强与更大样本回归复用。
