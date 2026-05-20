# 设计语文正向样例与统一Manifest方案 — 审查结论

- **结论**：approve
- **是否建议收口**：建议交 PM 收口
- **审查人**：review-1
- **审查时间**：2026-05-20T08:24:17+08:00

## 1. 本轮确认结果

1. **negative_guard 与正向样例边界清楚**  
   方案已经明确：
   - `chinese_grade5` 必须保留为 `negative_guard`
   - 不能原地改造成 `positive_candidate`
   - 不能再用 negative_guard 充当语文正向95分母

2. **至少一个语文正向样例设计到位**  
   已给出 P0 样例：`chinese_long_reading_positive_v1`，并写清：
   - 页型与覆盖面
   - 进入正向95所需 artifacts
   - 人工视觉分阈值
   - fallback 限制

3. **统一 Manifest 方案足够落地**  
   已定义：
   - 顶层字段
   - 样例字段
   - canonical roles
   - qualification fields
   - hard invariants
   - migration strategy

4. **后续拆分路径清楚**  
   已给出 4 个下游任务，能够直接解锁：
   - 语文正向 manifest/夹具实现
   - FinalAcceptance 语文覆盖门禁
   - 语文正向样例视觉证据链重跑
   - 作文格页型专项补充评估

## 2. 我补做的核对

- 报告 `.md` / `.json` 两个交付物都存在。
- JSON 报告可正常解析，结构完整。
- `source_reports` 中列出的 7 条路径全部存在。
- `current_chinese_facts` 已锁定：
  - `sample_key=chinese_grade5`
  - `evaluation_role=negative_guard`
  - `eligible_for_human_visual_95=false`
- 首个正向候选 `chinese_long_reading_positive_v1` 的角色、资格、覆盖面和进入条件都已明确。
- unified manifest schema 已给出足够细的必填字段和硬性不变量，可直接供下游实现采用。

## 3. 非阻塞观察

`source_reports.current_chinese_manifest` 当前引用的是 `.runtime/worktrees/...` 下的临时 worktree 路径。当前文件还存在，所以**不阻塞**本轮设计审查；但建议在后续实现/归档时，把该 manifest 快照迁到稳定的 canonical 路径，避免 worktree 清理后证据链接失效。

## 4. 审查结论

本轮没有发现阻塞问题。该方案已经把“语文为什么目前不能计入全学科正向95”与“下一步如何用统一 manifest 正确纳入语文正向样例”讲清楚，也没有让 `negative_guard` 与 `positive_candidate` 角色再次混淆。

**建议：交 PM 收口，并继续拆实现任务。**
