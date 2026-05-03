# 任务：前端置灰 DeepSeek 联网搜索并保持其他模型正常

## 背景
林总工已给出新的处理方向：
1. **DeepSeek 的联网搜索功能在前端置灰（不可点击），保留后端配置**
2. **确保 DeepSeek 对话功能正常（不依赖联网搜索也能用）**
3. **确保其他供应商模型（智谱/GLM 等）的联网搜索不受影响，能正常使用**

相关事实来源：
- `/Users/lin/Desktop/work/my-agent-teams/tasks/排查生产联网搜索DeepSeek可点不可用与GLM置灰/result.json`
- `/Users/lin/Desktop/work/my-agent-teams/tasks/分析AI对话供应商配置与生产一致性/result.json`
- `/Users/lin/Desktop/work/my-agent-teams/tasks/紧急修复生产DeepSeek对话无响应/result.json`
- `/Users/lin/Desktop/work/my-agent-teams/tasks/修正GLM健康探针改用智谱WebSearchAPI/result.json`
- `/Users/lin/Desktop/work/my-agent-teams/tasks/补充GLM联网搜索不可用前端提示/result.json`

## 你的任务
请按最小范围完成前端调整：

### A. DeepSeek
- 当前选择 DeepSeek 模型时：**联网搜索按钮直接置灰，不可点击**
- 要给出明确提示，不要让用户误以为功能可用
- **深度思考按钮保持与 DeepSeek 当前能力对应，不要误伤**

### B. DeepSeek 普通对话
- 不依赖联网搜索时，DeepSeek 对话功能应保持正常
- 不要把“置灰联网搜索”误做成“禁用整个 DeepSeek 对话”

### C. 其他供应商
- GLM / 智谱等其他 provider 的联网搜索逻辑保持当前独立策略
- 不要因为 DeepSeek 置灰而误伤 GLM / Zhipu / 其他 provider
- 当前 GLM 的 provider-native unavailable 提示逻辑继续按现有策略运行

## 方法论要求
- 先对照当前已经正常工作的其他 provider 联网搜索/深度思考接线实现
- 不要改后端配置语义，只做前端策略调整

## 验收标准
1. 选 DeepSeek 时，联网搜索按钮置灰且提示正确
2. 选 DeepSeek 时，普通对话依然正常，深度思考不受误伤
3. 选 GLM / 智谱时，联网搜索逻辑不被误伤
4. 真实组件级测试补齐并通过

## 交付物
完成后写：
- `/Users/lin/Desktop/work/my-agent-teams/tasks/前端置灰DeepSeek联网搜索并保持其他模型正常/result.json`
