# 任务：建立 PDF 转 Word 更大样本回归入口与样例清单，支撑 golden/meta 常态化

## 任务类型
development

## 目标
在现有五样例 authoritative/final-archive 验证基础上，为 PDF→Word 补一个**可持续扩展的更大样本回归入口**：支持从样例清单/manifest 出发生成 golden/meta 级摘要，先把“如何纳入更多真实样例、如何输出统一回归摘要”这层基础设施落下来，供后续 QA/owner 常态化扩大样本。

## 任务边界
- 只做回归入口、样例清单/manifest 规范、摘要产物与对应测试，不改现有转换主链路和 hybrid 发布边界。
- 优先复用 `model_eval_runner.py` 现有能力与现有 `final-archive / hybrid-e2e-validation` 产物，不要新起一套割裂脚本。
- 本轮目标不是补齐真实“大样本内容”本身，而是把**样例清单 + 回归摘要输出骨架**搭好，至少能覆盖当前五样例并预留后续扩样位。
- 不处理答案/教师版业务规则细节，不处理公式 merge 放开，不做前端。

## 输入事实
- 规划文档已将“更大样本回归 / golden/meta / 人工抽检模板常态化”列为下一阶段重点。
- 当前已有的稳定事实主要集中在：
  - `artifacts/pdf2word/final-archive/profiles/hybrid_experimental/*`
  - `artifacts/pdf2word/hybrid-e2e-validation/*`
  - `artifacts/pdf2word/final-archive/reports/hybrid_experimental_authoritative_archive_report.json`
- `backend/app/services/pdf_to_word/model_eval_runner.py` 已具备：
  - 普通 profile eval
  - `--local-capability-eval`
  - `--final-docx-gate`
  - `--formula-crop-eval`
- 但目前还没有一个明确面向“更大样本回归”的统一入口，用来声明样例集、沉淀样例元信息、输出后续 QA/owner 可持续复用的 regression summary。

## 约束
- `write_scope` 以 `task.json` 为准。
- 新入口必须能在没有新增真实 PDF 文件的前提下，先基于现有五样例 archive/e2e 产物跑通。
- 样例清单/manifest 中要保留可扩展字段，例如：sample_name、source_pdf（若未知可留空或说明）、page_type/subject、当前基线来源、是否 authoritative、可用 artifact 路径等。
- 回归摘要中必须诚实暴露当前局限：现阶段仍主要是五样例基线，尚未证明教辅长尾全面覆盖。
- 测试要覆盖：样例清单解析、摘要生成、关键聚合字段存在，不接受只改文档不补测试。

## 交付物
1. `model_eval_runner.py` 中可复用的“更大样本回归入口”或等价子命令/模式。
2. `artifacts/pdf2word/p2-regression/` 下的首版样例清单与回归摘要产物，至少包括：
   - 样例 manifest / meta
   - 当前回归摘要（aggregate + per-sample）
   - 已知限制说明
3. `test_model_eval_runner.py` 对应测试更新，至少覆盖：
   - 样例清单读取
   - 摘要生成
   - 关键字段与聚合统计
4. `result.json`：说明入口形式、manifest 结构、当前五样例如何接入、后续如何扩样。

## 验收标准
1. 能通过统一入口基于现有五样例 archive/e2e 产物生成 regression summary，而不是靠手工拼报告。
2. 样例 manifest / meta 结构清晰，可继续追加新样例而不破坏当前格式。
3. 测试通过，且不破坏现有 `model_eval_runner` 的其他模式（如 final-docx-gate / formula-crop-eval）。
4. 产物中明确区分“当前五样例基线”与“未来更大样本扩展位”，不夸大已覆盖范围。

## 下游动作
完成后进入 review-1 审查；通过后作为 P2 更大样本回归基础设施，并供后续 QA/owner 扩大样本集与人工抽检复用。
