# 任务：发布智谱联网搜索健康探针修复到生产

## 背景
- 上游排查任务 `排查智谱模型联网搜索生产失效` 已完成，根因明确：生产后端仍在使用旧版 Zhipu provider-native 健康探针实现，导致将 `429 / request_failed` 直接判成 `unavailable`，前端据此把智谱/GLM 联网搜索按钮全部置灰。
- 修复任务 `修复智谱联网搜索健康探针生产失效` 已完成，并且 **review 已通过、QA 已通过并自动收口（done）**。
- 林总工已明确要求：**安排提交并部署**。

## 目标
由 arch-1 将“智谱联网搜索健康探针修复”相关改动整理、提交、推送到 `origin/master`，随后部署到生产环境，并完成最小验证。

## 执行要求
请按以下顺序执行：

1. **确认待发布改动范围**
   - 只纳入“智谱联网搜索健康探针修复”链路必需改动
   - 避免夹带无关修改
   - 如需额外补 release note，可一并处理

2. **更新 Release Note**
   - 用简洁一行一条的方式，记录本次发布内容
   - 至少包含：
     - 智谱/Zhipu 联网搜索健康探针从旧版实现切到结构化 `/web_search` 探针
     - `429 / request_failed` 从 `unavailable` 下调为 `degraded`，避免前端整链路误置灰

3. **提交并推送**
   - 在 `~/Desktop/work/chiralium` 中完成 `git add / commit / push`
   - commit message 请清晰表达“为什么发布这次修复”
   - 推送到：`origin/master`

4. **部署生产**
   - 执行：
     ```bash
     cd /Users/lin/Desktop/work/chiralium && ./scripts/deploy.sh prod
     ```
   - 脚本执行时间较长，请等待完成

5. **最小验证**
   - 生产健康检查通过
   - 至少确认：
     - 主站健康 OK
     - 智谱联网搜索 runtime 口径不再误报为 `unavailable`
   - 如可行，请补一句验证“前端不再因为 runtime unavailable 将智谱按钮直接置灰”

## 建议关注文件
- `~/Desktop/work/chiralium/backend/app/services/model_service.py`
- `~/Desktop/work/chiralium/backend/tests/test_chat.py`
- `~/Desktop/work/chiralium/backend/tests/test_chat_capabilities.py`
- Release Note 对应文件

## 交付要求
完成后写：
- `ack.json`
- `result.json`

`result.json` 需至少包含：
1. 最终提交 hash
2. 推送分支
3. 部署结果
4. 生产验证结果
5. 是否有遗留风险
