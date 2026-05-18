# 审查说明：接入hybrid_experimental配置开关

## 结论

**驳回并请求补修（request_changes）**。

这轮实现已经把 `hybrid_experimental` 这个名字接进了 settings、Skill/API、`parser_client`、`conversion_service`、registry 和 `inference_config.yaml`，并且 `auto` 仍然只会解析到 apple/mock，没有误把默认流量切到 hybrid。相关 pytest 也都通过了。

但按任务目标和验收口径看，当前仍有一个阻塞问题：**registry / adapter / model_eval 入口上的 hybrid 配置开关没有真正打通。**

## 阻塞点

`create_adapter('hybrid_experimental')` 现在确实会返回独立的 `HybridExperimentalAdapter`，`profile_name` 也已经是 `hybrid_experimental`。这一点比上一轮进步了。

问题在于它直接继承了 `AppleBaselineAdapter.parse()`，而 `AppleBaselineAdapter.parse()` 在构造 parser request 时把 `parser_backend` 硬编码成了 `apple`：

- `apple_baseline_adapter.py` 里调用 `build_parser_request_payload(...)`
- 传入的是 `parser_backend='apple'`

我本地对 `adapter.parse()` 做了打桩复现，实际捕获到底层请求仍然是：

```python
{'parser_backend': 'apple'}
```

这意味着：

- `model_eval_runner -> create_adapter('hybrid_experimental') -> adapter.parse()` 这条链路
- 实际没有保留 `hybrid_experimental` backend 身份
- 也就不会触发 `parser_client.py` 里专门给 hybrid 预留的 normalize/warning 逻辑

所以现在“Skill/API/service 入口支持 hybrid”和“adapter/eval 入口支持 hybrid”是割裂的，任务还不能算完整收口。

## 我复核到的真实状态

- 已完成且正确的部分：
  - `SUPPORTED_PARSER_BACKENDS` 已纳入 `hybrid_experimental`
  - Skill 参数和 service 参数可以显式透传 `hybrid_experimental`
  - `conversion_service` 不会把它回退成 apple/mock
  - `parser_client` 会把 hybrid 响应统一标记为 `hybrid_experimental`
  - `inference_config.yaml` 已新增 disabled 的 `hybrid_experimental` profile
  - `auto` 仍不指向 hybrid
- 仍未完成的部分：
  - adapter/eval 入口上的 request backend 身份仍是 `apple`

## 建议修复

建议把修复范围收敛到 adapter 路径，不要回退已经打通的 service/skill 部分。可行做法有两种：

1. 在 `HybridExperimentalAdapter` 中覆盖 `parse()`，只改写底层 request 的 `parser_backend='hybrid_experimental'`。
2. 把 `AppleBaselineAdapter.parse()` 里的 backend 字面量抽成可覆写属性，让 `HybridExperimentalAdapter` 只覆盖该属性。

无论采用哪种方式，最低要求都是让这条链路成立：

`create_adapter('hybrid_experimental') -> adapter.parse()`  
底层 request payload 中的 `parser_backend` 必须保持为 `hybrid_experimental`

## 建议动作

建议 PM 退回补修，要求开发补一条专门覆盖 adapter/eval 路径的回归测试，而不只验证 service/skill 入口。

审查时间：2026-05-15T19:09:22+08:00
