# 任务：打通视觉相似度最终产物链路

## 任务类型
开发 / PDF 转 Word 95% 阻塞解除

## 目标
把 visual similarity 从当前“contract/stub 已冻结但真实 artifact 未接入”的状态，推进到 final archive / fidelity 最终判定真正可消费的状态：至少要能在 quality/hybrid_async 路径下产出 canonical `visual_similarity.json`，并让最终 95% 判定不再因为“artifact 缺失”而天然卡死在 83 分上限。

## 任务边界
- 只允许修改以下范围：
  - `backend/app/services/pdf_to_word/model_eval_runner.py`
  - `backend/app/services/pdf_to_word/visual_similarity_gate.py`
  - `backend/tests/test_model_eval_runner.py`
  - `backend/tests/test_pdf_to_word_visual_similarity_gate.py`
  - `backend/tests/test_pdf_to_word_fidelity_report.py`
  - `backend/tests/fixtures/pdf_to_word/visual_similarity/`
  - `backend/tests/fixtures/pdf_to_word/fidelity/`
- 不放宽 default sync，不把慢模型接入默认同步路径。
- 如果本轮只能先接通真实 artifact 链路而不能完成最终算法，也必须显式区分 required artifact 与 optional/debug artifact，不能伪造通过。

## 输入事实
- `执行PDF转Word表格收尾复验与95判定` 已给出 PM 仲裁结论：表格 gate 通过，但因为 final archive 中缺失 `visual_similarity.json`，整体 95% 宣称 no-go。
- 已完成设计：`设计视觉相似度最终门禁与慢模型灰度`；其中 required artifact 已冻结为 `visual_similarity.json`，active slow-model candidate 仅保留 `qwen3_vl_8b`。
- 已完成报告器：`建立95还原度最终报告器`；当前 reporter 已能正确消费 visual_similarity 维度，但真实 artifact 链路未接通。

## 约束
- 必须坚持 100 分制 contract，不得改低 threshold=95。
- 必须保持 canonical artifact 名称为 `visual_similarity.json`；`visual_similarity_report.json` / `visual_similarity_debug.json` 只能作为 optional/debug。
- 若本轮仍需灰度或 stub，必须确保最终判定能准确表达“真实已接入”与“仍缺实现”的边界。

## 交付物
1. 真实 visual similarity artifact 链路接线。
2. 覆盖 artifact 生成/消费的测试与 fixture。
3. 一份任务内运行说明（写入 result.json 或附加 artifact 均可），明确 QA 下一次如何重跑最终 95% 判定。

## 验收标准
- quality/hybrid_async 路径下不再因为缺失 `visual_similarity.json` 而直接触发 `visual_similarity_missing`。
- `model_eval_runner` / fidelity report / visual similarity gate 的 contract 名称一致。
- 测试能够证明 canonical artifact 生成与最终判定消费链路已接通。
- 不放宽 default sync 边界，不把慢模型默认化。

## 下游动作
完成后，qa-1 将重跑 PDF 转 Word 最终 95% 判定，PM 再决定是否整体收口。
