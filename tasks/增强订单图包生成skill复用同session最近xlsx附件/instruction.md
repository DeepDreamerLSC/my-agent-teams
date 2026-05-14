# 任务：增强 订单图包生成 skill 复用同 session 最近 xlsx 附件

## 任务类型
开发

## 目标
为 `order-print-image-pack` 增加“同一对话内近期文件复用”能力：当用户在同一 session 第二次/后续使用 skill 时，如果本次没有重新上传 xlsx，但同一 session 最近一次相关消息里已上传了 `.xlsx` 订单汇总文件，系统应自动复用该文件，而不是直接报「请先上传一个 .xlsx 订单汇总文件」。

## 任务边界
- 这是**平台层能力**，优先从 `skill_service` / `context` / `chat` 输入组装层解决，而不是只在 skill 内写死特例。
- 可以针对 `order-print-image-pack` 先接入，但实现方式应尽量可复用到其他“依赖最近上传文件”的 skill。
- 暂时不改业务计算逻辑。
- 不做生产部署。

## 输入事实
- 生产 chat_logs 已确认：王开在同一 session `57c57394-1cb4-4035-ae82-20e444fbbe5d` 中，第二次点击“请生成”时 `file_ids=[]`，从而触发 `请先上传一个 .xlsx 订单汇总文件`。
- 当前 `order-print-image-pack` 只看当前请求 `context.uploaded_files`：
  - `/Users/linsuchang/Desktop/work/chiralium/skills/custom/order-print-image-pack/1.0.0/skill.py:716-723`
- 平台层当前已存在与上下文/文件相关的关键位置：
  - `/Users/linsuchang/Desktop/work/chiralium/backend/app/services/context_assembler.py`
  - `/Users/linsuchang/Desktop/work/chiralium/backend/app/api/chat.py`
  - `/Users/linsuchang/Desktop/work/chiralium/backend/app/services/skill_service.py`
- 目标不是让用户跨 session 复用文件，只在**同一 session 最近一次已上传相关 xlsx 文件**时生效。

## 约束
- write_scope:
  - `backend/app/api/chat.py`
  - `backend/app/services/context_assembler.py`
  - `backend/app/services/skill_service.py`
  - `skills/custom/order-print-image-pack/1.0.0/skill.py`
  - `backend/tests`
- read_only: false
- target_environment: dev
- execution_mode: dev
- owner_approval_required: false
- 只复用**同 session 最近一次**匹配的 `.xlsx` 附件，不要跨用户、不跨 session。
- 若当前请求本身已带 xlsx，仍应优先使用当前请求附件。
- 若最近上下文里没有可用 xlsx，保留原错误提示。

## 交付物
- 平台/skill 代码改动
- 对应测试
- `result.json`

## 验收标准
1. 在同一 session 中：第一次上传 xlsx 后，第二次不重新上传但继续点击 skill，系统能复用最近 xlsx，不再直接报“请先上传一个 .xlsx 订单汇总文件”。
2. 当前请求自己带了 xlsx 时，仍优先使用当前请求文件。
3. 跨 session / 无历史附件时，不误复用。
4. 至少补一条针对“同 session 复用最近 xlsx” 的自动化测试。

## 下游动作
review
