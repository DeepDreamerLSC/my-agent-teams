# 审查说明：收口Qwen3VL审查Worker严格JSON闭环

## 结论

**驳回并请求补修（request_changes）。**

## 为什么驳回

这轮代码链路本身做得基本对：

- `ReviewIntegrator` 已经具备 ambiguous candidate 才进入 review、invalid JSON 重试、最终失败只 drop ambiguous candidate、不拖垮整页的闭环。
- `report.json` 也已经补上了 `online_review_probe`、`json_valid_rate`、`review_acceptance_rate`、`service_available` 等真实在线指标位。
- 我复跑了任务要求的 pytest，结果是 `19 passed, 4 warnings`。

但本任务的标题和验收目标都明确指向 **Qwen3-VL 审查 Worker**。我在非沙箱环境直接复核 `qwen3_vl_8b` 的真实服务配置后，发现关键事实不成立：

- `inference_config.yaml` 里 `qwen3_vl_8b_local` 指向 `http://127.0.0.1:18111/v1`
- 这个端口当前 `GET /v1/models` 返回的模型 ID 不是 Qwen3-VL，而是 `mlx-community/GLM-4.6V-Flash-4bit`

也就是说，当前报告里的 `online_review` 和 `1.0 / 1.0` 指标，只能证明“18111 上某个在线 VLM 服务可用并跑通了 strict JSON review”，**不能证明 Qwen3-VL worker 已真实恢复并收口**。这与 `result.json` 的核心陈述不一致，因此不能给 `approve`。

## 已确认正确的部分

- `review_integrator.py` 已实现 invalid JSON 重试与最终 drop：
  - `review_integrator.py:391-423`
  - `review_integrator.py:533-542`
- 对应测试已经覆盖：
  - invalid JSON 直接 drop：`test_review_integrator.py:306-338`
  - invalid JSON 重试后成功：`test_review_integrator.py:340-372`
  - service unavailable 时优雅 skip：`test_review_integrator.py:375-405`
- hybrid e2e 报告生成逻辑已能区分：
  - `online_review`
  - `service_unavailable`
  - `no_review_targets`
  见 `test_hybrid_e2e.py:306-360`、`471-512`

## 建议补修

先不要回退现有 strict JSON / integrator / report 代码，问题不在这里。建议直接做最小修正：

1. 修正本机服务与端口映射，让 `qwen3_vl_8b_local` 真正命中 Qwen3-VL 服务。
2. 或者如果当前实际决定改用 GLM 做 review worker，就同步修正任务目标、profile 命名和 result.json 描述，不要继续写成 Qwen3-VL。
3. 修正后重新生成 `artifacts/pdf2word/hybrid-e2e-validation/report.json`，并在结果里附上真实 `GET /v1/models` 返回值，证明在线 review 用的确实是哪一个模型。

## 总结

代码闭环基本成立，但“Qwen3-VL 已恢复并完成真实在线审查”这个关键交付事实目前不成立，所以本轮应退回补证据或补环境修正。
