# 设计公式AuditOnly风险标注与阶段拆分方案 — 审查结论

- **结论**：approve
- **是否建议收口**：建议交 PM 收口
- **审查人**：review-1
- **审查时间**：2026-05-20T08:18:01+08:00

## 1. 本轮确认结果

1. **为什么公式不能计入当前95主口径，回答到位**  
   文档没有停留在“先别做公式”的抽象结论，而是给出了明确原因：
   - 当前仍是 `audit-only / merge-disabled`；
   - 候选存在不等于终态还原成功；
   - crop 级实验当前最优也只有 `2/17`；
   - 还有 `1` 个 baseline candidate 未 materialize；
   - 公式区域缺终态 render_pair / visual_similarity / human_review 证据。

2. **下一阶段门禁清楚**  
   已明确给出 `G1-G6`：
   - candidate inventory 完整性
   - crop 模型精度底线
   - structured output / conversion
   - DOCX 可编辑 roundtrip
   - 区域视觉与人工复核
   - 成本与 fallback guard

3. **阶段拆分可执行**  
   已拆成 4 个 phase：
   - Phase 0 AuditOnly 风险标注
   - Phase 1 素材化与输出清洗实验
   - Phase 2 可编辑公式灰度实验
   - Phase 3 公式能力专项 GO 评估

4. **风险标注契约足够具体**  
   `formula_audit_risks.json` 的建议字段、canonical values、示例 payload 都给出来了，便于后续实现任务直接接线。

## 2. 我补做的核对

- 报告 `.md` / `.json` 两个交付物都存在。
- JSON 报告可正常解析，结构完整。
- 报告引用的 6 条证据路径全部存在。
- `risk_taxonomy=6`、`next_phase_entry_gates=6`、`phase_split=4`、`recommended_next_tasks=4`，结构足够支撑后续拆任务。
- 关键数字与上游来源一致：
  - `formula_candidate_count=18`
  - `qwen3_vl_8b exact success=2/17`
  - `1 个 baseline candidate 未 materialize`

## 3. 审查结论

本轮没有发现阻塞问题。该设计已经把“当前继续 audit-only”与“未来如何进入可编辑公式阶段”之间的边界讲清楚，也没有把公式实验错误混入当前全学科95恢复主线。

**建议：交 PM 收口，并按文档里的 4 个后续任务继续拆分实验实施。**
