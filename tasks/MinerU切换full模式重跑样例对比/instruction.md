# 任务：MinerU 切换 full 模式重跑样例对比

## 任务类型
development（配置调整 + 评估执行）

## 目标
将 MinerU 从 lite 模式切换为 full 模式（启用完整 layout + formula + table 模型），用统一框架重跑 5 个样例，评估 full 模式是否显著优于 apple_baseline。

## 任务边界
- 只改 inference_config.yaml 中 MinerU 的 parse_mode 配置
- 用 model_eval_runner 重跑，不用独立脚本
- 生成新的对比报告
- 不修改 normalizer / adapter / runner 代码

## 输入事实
- MinerU 已接入统一架构（DocumentOCRAdapter + MinerUNormalizer）
- 当前配置：`model_mode=lite`（之前 0/5 优于基线）
- 基线数据：`artifacts/pdf2word/model-eval/20260514-144102/apple_baseline/`
- 样例目录：`/Users/linsuchang/Desktop/work/chiralium/example/扫描件 `（末尾空格）
- MinerU CLI：`magic-pdf pdf-command --method ocr --inside_model True --model_mode full`
- inference_config.yaml 中 MinerU backend 配置位置：backends 段的 mineru_cli 相关配置

## 约束
- write_scope 以 task.json 为准
- 必须通过 model_eval_runner 跑批
- full 模式首次运行会下载额外模型（layoutlm、formula 等），耗时较长，timeout 需考虑
- 保留之前的 lite 模式跑批数据，不覆盖

## 交付物

### 1. 配置更新
- `inference_config.yaml`：MinerU backend 的 `extra.model_mode` 或相关配置改为 `full`
- 确认 MinerU full 模式所需模型已下载（layout、formula、table 模型）

### 2. 样例跑批
- 用 model_eval_runner 对 5 个样例跑 mineru profile（full 模式）
- 输出到新 timestamp 目录，不覆盖 lite 模式数据

### 3. 对比报告
- 生成 mineru_full vs apple_baseline 对比
- 额外对比 mineru_full vs mineru_lite（展示 full 模式提升）
- 关注维度：题号序列完整度、图片/公式候选数、表格识别、耗时

## 验收标准
1. MinerU 配置已切换为 full 模式
2. 5 个样例全部通过 model_eval_runner 跑完
3. 新的 artifacts 在独立 timestamp 目录下
4. 对比报告包含 mineru_full vs baseline 和 mineru_full vs mineru_lite
5. 有明确结论：full 模式是否优于 lite 和 baseline

## 下游动作
如果 full 模式达到 >=3/5 优于基线，考虑进入 parser_backend=hybrid 或替换主 parser。
