# 任务：补充 DeepSeek 联网搜索前端提示与能力可视化

## 背景
已批准的架构方案见：
- `/Users/lin/Desktop/work/chiralium/design/product/deepseek-web-search-production-incident-plan.md`

当前生产事故已确认：
- flash 禁用是因为生产模型 provider 漂移，前端只是如实反映 capability
- pro 可点不生效是因为后端 runtime 缺少搜索 provider 配置，用户侧缺乏明确提示

## 你的任务
请在前端补足“可见性”和“可理解性”，避免用户再次遇到“按钮可点但不生效 / 为什么被禁用却看不懂”的问题：

1. 管理后台模型页增强可视化
   - 明确展示 provider 与关键 capability（thinking / web_search）
   - 让类似 `deepseek-v4-flash provider=custom` 这类异常更容易被管理员发现

2. 聊天页/工具栏补充明确提示
   - 当模型 capability 不支持 web_search 时，禁用态要有更清楚的文案或提示
   - 当后端后续提供 runtime unavailable / disabled / degraded 信号时，前端要显式反馈，而不是让用户感知为“点击没反应”
   - 兼容当前接口，避免阻塞；如依赖后端新增字段，请按最终落地契约接线

3. 补测试
   - 真实组件级 DOM 断言优先
   - 覆盖 Models 页 provider/capability 展示
   - 覆盖 ChatToolbar / Chat 页关于禁用态、不可用提示的展示逻辑

## 依赖说明
- 该任务依赖：`修复DeepSeek联网搜索后端守卫与可观测性`
- 你可以先完成独立 UI 部分，但最终契约需以后端任务落地结果为准

## 边界
- 只改 `write_scope` 内文件
- 不直接改后端代码
- 保持现有 capability-driven 行为不回归

## 验收标准
1. 管理后台能更直观看出 provider/capability 异常
2. 聊天页对“禁用”和“runtime 不可用”两类状态都有清晰反馈
3. 真实组件级测试覆盖到位

## 交付物
完成后写：
- `/Users/lin/Desktop/work/my-agent-teams/tasks/补充DeepSeek联网搜索前端提示与能力可视化/result.json`

请在 `result.json` 中包含：
- 修改文件列表
- 新增交互/提示说明
- 测试命令与结果
