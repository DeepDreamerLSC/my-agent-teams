# 审查说明：补评GLM-4.6V-Flash模型横评

## 结论

**审查通过（approved）。**

这次 rework 已经把我上一轮驳回的两个阻塞点都收掉了。

## 已修复点 1

上一轮的问题之一是：

- 任务实际写入了 `artifacts/pdf2word/model-eval/20260516-104815/...`
- 但 `task.json.write_scope` 里没有把这段 artifacts 路径纳入授权

现在 `task.json.write_scope` 已经补上了：

- `/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/model-eval/20260516-104815/`

这意味着历史补评产物现在与任务定义一致，不再是越界写入。

## 已修复点 2

上一轮另一个阻塞点是：

- 结果宣称 18121 服务可用
- 但我复核时服务已停，`is_available()` 也为 `False`

本轮 `result.json` 已经把事实口径改正为：

- 这是一次性评测服务
- 当前已停止
- `adapter_available_now=false`
- `profile_enabled_after_rework=false`

并且 `inference_config.yaml` 里 `glm_46v_flash` 现在确实是：

```yaml
enabled: false
```

这点很关键，因为它避免了后续调用方再把这个 profile 误当成“仓库当前默认可用能力”。

换句话说，当前状态已经从：

- “配置上看起来可用，但实际服务已经停了”

修正为：

- “历史补评数据保留，但 profile 明确默认停用”

这与任务的真实定位是一致的：

- 用于补评和横评汇总
- 不作为当前默认 parser 能力暴露

## 为什么现在可以通过

这轮任务的核心不是把 GLM-4.6V-Flash 变成长期在线服务，而是：

1. 完成一次真实补评
2. 保留可用于横评汇总的数据
3. 不让仓库当前状态继续误导后续使用者

现在这三点都满足了：

- 历史跑批 artifacts 仍在
- `comparison_report.json` 仍可用于横评汇总
- profile 已显式 `disabled`

所以从审查角度，这条任务已经可以收口。

## 非阻塞观察

仍然有一个值得记录的技术风险：

- 5/5 样例都带有 `VLM review JSON 解析失败，已返回空结果。` warning

这不影响本轮通过，因为当前 profile 已经默认停用，历史数据只是作为横评补录对象保留。

但如果未来还想再次启用 `glm_46v_flash` 作为 VLM review 对照，就不能忽略这个问题，仍需要单独治理：

- prompt
- schema
- normalizer
- structured JSON 输出稳定性

## 总结

本轮 rework 已经把“范围越界”和“错误暴露默认可用 profile”这两个阻塞点修掉了。当前仓库状态和 `result.json` 叙述已经一致，历史补评产物也保留完好，因此本任务可以通过审查。
