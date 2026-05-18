# 任务：用 5 个样例端到端验证 hybrid_experimental 管线

## 任务类型
development / validation

## 目标
用 5 个横评样例（五下科学、数学八年级、数学试卷、英语八年级、语文五年级）对 hybrid_experimental 管线做端到端验证，确认：
1. baseline pass-through 模式（enable_enhancement=False）输出与 apple_baseline 等价
2. 增强模式（enable_enhancement=True）能完整走通候选抽取→过滤→合并→校验链路
3. 页级 fallback 机制在候选合并失败时正确回退到 baseline PageIR
4. 最终输出 hybrid-pages.jsonl 和 validator-report.json 可被下游消费

## 任务边界
- **在范围内**：编写端到端测试、运行 5 样例、对比 baseline vs hybrid 输出、记录差异
- **不在范围内**：不修改 hybrid_pipeline.py 核心逻辑、不修改 normalizer、不做 DOCX 生成（只验证 PageIR 层）

## 输入事实
- hybrid_pipeline.py 已实现，配置 HybridPipelineConfig 控制 baseline_profile / enable_enhancement / candidate_profiles
- 7 个子模块（A-G）代码已就绪：question_region_detector / candidate_extractor / candidate_filter / page_ir_merger / hybrid_validator / review_integrator / hybrid_pipeline
- 5 个样例 PDF 在 `/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/model-eval/` 各 profile 目录下
- MinerU 和 PaddleOCR-VL 的 PageIR 已在 artifacts 目录中可用
- Qwen3-VL 服务在 127.0.0.1:18111（如果在线可做 review 集成测试，离线则跳过）

## 约束
- write_scope: 见 task.json
- read_only: false
- target_environment: dev
- execution_mode: dev
- owner_approval_required: false
- 样例归档已在 `artifacts/pdf2word/final-archive/`，优先从该目录读取源文件路径

## 交付物
1. `tests/test_hybrid_e2e.py` — 端到端测试文件，覆盖 baseline pass-through 和增强模式两条路径
2. `artifacts/pdf2word/hybrid-e2e-validation/report.json` — 5 样例验证报告，包含每页的 baseline vs hybrid 差异摘要
3. `result.json` 标准格式，包含 metric 总结

## 验收标准
1. `pytest tests/test_hybrid_e2e.py` 全部通过
2. baseline pass-through 模式：5 个样例的 hybrid PageIR 与 apple_baseline PageIR 完全一致（逐字段对比 blocks 列表）
3. 增强模式：至少 3 个样例能走通完整链路并产出非空 candidates + merge decisions
4. validator-report.json 中每页都有 verdict（accept/fallback），无未处理异常
5. 页级 fallback 至少被触发 1 次（可构造异常候选验证）

## 下游动作
验证通过后，hybrid_experimental 可进入集成测试阶段，接入 Skill API 路由对外暴露
