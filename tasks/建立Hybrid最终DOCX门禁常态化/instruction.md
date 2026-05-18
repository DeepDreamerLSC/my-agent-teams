# 任务：建立 Hybrid 最终 DOCX 门禁常态化，固化 release evidence 检查

## 任务类型
integration

## 目标
把当前已经人工闭合过的 authoritative hybrid final DOCX 证据，收敛为**可重复执行、可自动校验、可用于 release 判断的固定门禁**。同时顺手收平当前 `final-archive` 中已知的非阻塞元数据不一致，避免证据文件与索引口径继续漂移。

## 任务边界
- 本任务的核心是“门禁常态化”，不是重新搭 hybrid 管线。
- 不改变默认发布边界；只固化 evidence gate。
- 允许修正当前 `archive_manifest.json` / `README.md` 的非阻塞元数据口径问题，但不要伪造新证据。

## 输入事实
- 当前 authoritative hybrid final archive 已成立：
  - `5/5` authoritative `output.docx`
  - `5/5` openable
  - `4/5` `word/media`
  - `2/5` table XML
  - `0/5` `answer_area`
  - `0/5` `answer_section`
- `review-1` 已指出两个非阻塞问题：
  1. `archive_manifest.json` 的 `reports` 索引没有完整纳入新的 hybrid authoritative report，`report_file_count` 与目录实际文件数不一致
  2. `README.md` 顶部“仅复制现有产物”对 `hybrid_experimental` 不够准确，因为该 profile 的 `output.docx / metrics.json / warnings.json` 是 archive-generated
- 现有相关文件：
  - `backend/tests/test_hybrid_e2e.py`
  - `backend/tests/test_model_eval_runner.py`
  - `backend/app/services/pdf_to_word/model_eval_runner.py`
  - `artifacts/pdf2word/final-archive/archive_manifest.json`
  - `artifacts/pdf2word/final-archive/README.md`

## 约束
- write_scope 以 task.json 为准
- 门禁至少要覆盖：
  1. `output.docx` openable
  2. `pages.jsonl` provenance 对齐
  3. `word/media` / table XML / fallback / source_manifest 事实可校验
  4. final-archive 元数据（manifest / README / reports 索引）与真实文件状态一致
- 不要把“当前 5 样例结论”硬编码成不可维护的散乱逻辑；优先做成可复用检查入口或清晰测试结构

## 交付物
1. 代码/测试：建立 final DOCX gate 的常态化检查能力
2. 修正 `archive_manifest.json` / `README.md` 的当前非阻塞元数据口径问题
3. `result.json`：写明
   - 你把哪些检查固化成门禁了
   - 当前门禁依赖哪些证据文件
   - 后续 pipeline 行为变更时如何刷新/复核

## 验收标准
1. release evidence 不再只靠一次性人工检查，而是有固定 gate。
2. `archive_manifest.json` / `README.md` 与真实归档状态一致。
3. 测试或检查入口可被 review/QA 复用。
4. 不改变默认发布边界，只固化证据门禁。

## 下游动作
完成后进入 review-1 审查；通过后交 qa-1 复核 final DOCX gate 与 archive 元数据一致性。
