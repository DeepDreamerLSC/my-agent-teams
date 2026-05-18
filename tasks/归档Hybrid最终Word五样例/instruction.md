# 任务：归档 Hybrid 最终 Word 五样例，补齐 authoritative 发布证据

## 任务类型
integration

## 目标
基于当前已经打通的 `parser_backend=hybrid_experimental` / quality 增强链路，补齐一份**authoritative 的五样例最终 Word 正式归档**，让后续发布判断不再只依赖 probe / 中间产物，而有可直接打开、可复核、可追溯 provenance 的最终 DOCX 证据。

## 任务边界
- 本任务的核心是**生成并归档 authoritative hybrid 最终产物**，不是放大默认发布范围，也不是修改默认路由。
- 不要求把 `hybrid_experimental` 改成默认；默认建议仍应保持 `apple default + hybrid_experimental/quality gray + formula audit-only`。
- 如现有实现已足够生成 authoritative 归档，优先只落盘产物与 manifest，不做无关代码改造。
- 如在生成 authoritative 归档时遇到最小必要的集成缺口，可以在 write_scope 内补齐归档/报告产物，但不要改 tasks/scripts/prompts 等受保护路径。
- 若最终发现当前链路仍无法生成可信 authoritative 归档，必须诚实记录失败样例与原因，不得伪造“5/5 已成立”。

## 输入事实
- `执行PDF转Word最终五样例总验收` 已收口，结论是：PDF 转 Word 已阶段性端到端完成，但**唯一核心 broader-release blocker** 仍是“缺 authoritative 的五样例 hybrid 最终 Word 正式归档”。
- 当前 final-acceptance 已明确指出：
  - 继续 `apple` 默认
  - `hybrid_experimental` 仅 `quality` / 灰度显式开启
  - `formula` 继续 `audit-only / merge-disabled`
- 当前可参考证据：
  - `/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-acceptance/final_acceptance_report.md`
  - `/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-acceptance/final_acceptance_summary.json`
  - `/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/hybrid-e2e-validation/`
  - `/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-archive/`
- 五个目标样例：`五下科学`、`语文五年级`、`数学八年级`、`英语八年级`、`数学试卷`。

## 约束
- write_scope: [`/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-archive/`]
- read_only: false
- 依赖上游任务: 无
- target_environment: dev
- execution_mode: dev
- owner_approval_required: false
- 归档必须使用**诚实 provenance**：run_label、source_dir、copied_files、missing_files、残余限制都要与实际一致。
- 归档对象必须是 **hybrid 最终 Word / 最终 pages / metrics / warnings**，而不是只复制中间校验文件。
- 如果显式 `answer_area` 仍然没有 materialize，也要把“0/5 或 n/5”的真实结果写清楚，不能为了闭 blocker 而过度宣称。

## 交付物
1. 在 `/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-archive/profiles/` 下新增或补齐 `hybrid_experimental/` authoritative 归档：
   - 5 个样例子目录
   - 每样例至少包含：`output.docx`、`pages.jsonl`、`metrics.json`、`warnings.json`（若某项缺失需在 manifest 中诚实记录）
   - `profile_manifest.json`
2. 更新 `/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-archive/archive_manifest.json`，把 `hybrid_experimental` 纳入正式归档索引。
3. 在 `/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/final-archive/reports/` 下新增一份归档报告（md 或 json 均可，建议两者之一清晰即可），至少逐样例回答：
   - 是否成功形成 authoritative 最终 DOCX
   - `word/media` 是否存在、数量多少
   - 图片 / 表格是否进入最终 Word
   - 显式 `answer_area` / `answer_section` 是否 materialize
   - 仍存在哪些 residual limitation
4. `result.json`：写清
   - 这次是否真正补齐了 broader-release blocker
   - 如果没有完全补齐，还差哪一环
   - 是否建议在后续单独创建“放宽 hybrid 发布承诺”任务

## 验收标准
1. `final-archive` 中出现可追溯的 `hybrid_experimental` 正式归档，而不是只有中间验证产物。
2. 五样例逐样例都有 authoritative 结论；成功/失败都要落到 manifest 和报告里。
3. 报告能直接回答：当前是否已经补齐“hybrid 最终 Word 正式证据”这条 blocker。
4. 不改变默认发布口径；如果 evidence 仍不足，必须明确保留 `apple default + hybrid quality gray` 边界。
5. 审查与 QA 能仅基于本次归档产物判断是否可作为 owner/PM 后续放宽发布承诺的依据。

## 下游动作
完成后进入 review-1 审查；通过后由 qa-1 复核归档完整性，作为是否放宽 hybrid 发布承诺的直接证据。
