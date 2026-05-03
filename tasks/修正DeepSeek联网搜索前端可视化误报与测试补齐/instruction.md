# 任务：修正 DeepSeek 联网搜索前端可视化误报与测试补齐

## 背景
原任务：
- `/Users/lin/Desktop/work/my-agent-teams/tasks/补充DeepSeek联网搜索前端提示与能力可视化/instruction.md`

审查意见：
- `/Users/lin/Desktop/work/my-agent-teams/tasks/补充DeepSeek联网搜索前端提示与能力可视化/review.md`

本次是 review 驳回后的补修任务，请只处理审查指出的问题，不要扩散改动范围。

## 必修问题
1. **Models 页 capability 可视化不能继续使用前端硬编码 provider 能力表**
   - `Models.tsx` 必须改为消费后端真实返回的 `capabilities`
   - provider anomaly（如 `deepseek-*` + 非 `deepseek` provider）可以继续保留，但只能作为辅助异常提示
   - 能力标签展示必须以后端契约为准，避免再次出现误报

2. **补真实 Models 页面接线测试**
   - 不能只测测试文件里的局部 columns 拼装逻辑
   - 至少补一条真实 `Models` 组件测试：mock `/api/admin/models` 返回 `provider + capabilities` 数据，断言页面真实渲染出的能力标签与异常提示

3. **补 useChatOptions 的 runtime status 前向兼容测试**
   - mock `/api/meta/chat-capabilities`
   - 至少覆盖：
     - `web_search_runtime_status='degraded'`
     - 非法值 / 未知值
   - 断言 hook 最终导出的 `webSearchRuntimeStatus`

## 保持不回归
- 不要回退已经正确的 ChatToolbar 三态提示（不支持 / unavailable / degraded）
- 不要破坏现有 capability-driven 行为
- 只在 `write_scope` 内修改

## 交付物
完成后写：
- `/Users/lin/Desktop/work/my-agent-teams/tasks/修正DeepSeek联网搜索前端可视化误报与测试补齐/result.json`

请在 `result.json` 中包含：
- 修改文件列表
- 如何改为消费后端真实 capabilities
- 新增/更新了哪些真实接线测试
- 测试命令与结果
