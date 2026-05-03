# 任务：增加 GLM 联网搜索健康探针与状态输出

## 背景
林总工已明确 GLM 联网搜索的处理方向简化为：
1. 加一个联网 API 健康度探测
2. 如果探测确认联网不可用，前端直接报出正确的错误提示

参考依据：
- `/Users/lin/Desktop/work/my-agent-teams/tasks/排查DeepSeek模型不可用与GLM联网搜索丢失/result.json`
- `/Users/lin/Desktop/work/chiralium/design/product/glm-web-search-degradation-mitigation-plan.md`

## 你的任务
请先实现后端侧最小可用能力：
1. 为 GLM / zhipu 的 provider-native 联网搜索增加健康探针或状态输出
2. 给前端提供一个可消费的状态（例如 healthy / degraded / unavailable / unknown）
3. 当确认联网不可用时，状态必须能稳定暴露出来，供前端直接提示

## 方法论要求
- 先以过去正常工作的 GLM 原生联网搜索实现为参照物
- 不要假设，确认实际请求路径、现有 capability、接口输出
- 不要把 DeepSeek 的 tool_call runtime 语义直接套到 GLM 上

## 边界
- 只改 `write_scope` 内文件
- 本次不做模型自动切换，不重写本地搜索链路
- 只做最小健康探针 / 状态输出能力

## 验收标准
1. 后端能输出 GLM provider-native 联网搜索状态
2. 状态足以让前端区分“可用 / 不可用”并提示用户
3. 不影响现有 DeepSeek 或其他 provider 链路
4. 测试通过

## 交付物
完成后写：
- `/Users/lin/Desktop/work/my-agent-teams/tasks/增加GLM联网搜索健康探针与状态输出/result.json`
