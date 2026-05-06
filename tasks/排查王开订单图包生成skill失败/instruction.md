# 任务：排查 王开 订单图包生成 skill 失败

## 任务类型
排查

## 目标
基于生产数据库的**对话日志表**，排查用户“王开”在生产环境使用 `order-print-image-pack`（订单图包生成）skill 失败的真实根因。先把三次失败的具体错误信息、发生时间、输入上下文提炼清楚，再定位代码链路中的故障点。

## 任务边界
- 本任务是**只读排查**，先不要直接修改 chiralium 代码。
- 允许读取：
  - 生产数据库中的 `chat_logs / chat_sessions / chat_messages`
  - 当前开发仓库中 `order-print-image-pack` skill 的实现与测试
  - 如有必要，相关附件/输入链路的辅助代码
- 不要写生产库，不要部署，不要修改生产环境。
- 本任务**不要再转去排查 PPT / polished / CogView / box-calculator**；林总工已明确本次起点是“订单图包生成 skill 本身”。

## 输入事实
- Docker 环境可用，生产库容器：`chiralium_prod_postgres`
- 数据库：`chiralium_prod_db`
- 用户：`chiralium`
- 王开当前用户：
  - `user_id = bece02b8-7b3b-4431-9d91-5467491ceba7`
  - `username = 用户7251`
  - `remark = 王开`
- 已从生产 `chat_logs` 表直接查到 3 次与 `skill:order-print-image-pack` 相关的失败记录（session_id 相同：`57c57394-1cb4-4035-ae82-20e444fbbe5d`）：
  1. `2026-05-05 11:46:42 +08`
     - query: `请生成`
     - model_used: `skill:order-print-image-pack`
     - error_message: `标签导出失败：invalid literal for int() with base 10: '0.5'`
  2. `2026-05-05 11:48:27 +08`
     - query: `请生成`
     - model_used: `skill:order-print-image-pack`
     - error_message: `请先上传一个 .xlsx 订单汇总文件`
  3. `2026-05-05 12:03:21 +08`
     - query: `请生成`
     - model_used: `skill:order-print-image-pack`
     - error_message: `标签导出失败：invalid literal for int() with base 10: '0.5'`
- 相关 session：`57c57394-1cb4-4035-ae82-20e444fbbe5d`
- 当前重点代码路径：
  - `/Users/lin/Desktop/work/chiralium/skills/custom/order-print-image-pack/1.0.0`
- 需要重点核对：
  1. xlsx 输入识别与文件类型判断
  2. xlsx 内容解析时是否错误把 `0.5` 当整型字段处理
  3. 订单图包生成链路中的参数/列映射/数值转换逻辑
  4. 同一 session 中为什么既出现“未上传 xlsx”又出现“0.5 int 转换失败”两类错误

## 约束
- write_scope: []
- read_only: true
- target_environment: dev
- execution_mode: dev
- owner_approval_required: false
- 优先输出“哪一行/哪类字段导致 `int('0.5')`”的最短根因路径。
- 若只能定位到模块层，也必须说明还差哪一步证据。

## 交付物
- `/Users/lin/Desktop/work/my-agent-teams/tasks/排查王开订单图包生成skill失败/ack.json`
- `/Users/lin/Desktop/work/my-agent-teams/tasks/排查王开订单图包生成skill失败/result.json`

`result.json` 必须至少包含：
- 三次失败记录的结构化整理（时间、错误、session、query）
- 你认为最关键的主错误（`0.5` 转换失败 vs xlsx 检测失败）
- 最可能的真实代码根因
- 对应 skill 代码中的可疑函数/行段
- 是否需要后续修复任务（给出建议任务标题）

## 验收标准
1. 必须以生产 chat_logs 里的三次失败记录为起点，而不是 feedback 推断。
2. 必须明确这次问题就是 `order-print-image-pack`，不能再转到其他 skill。
3. 必须解释清楚 `invalid literal for int() with base 10: '0.5'` 最可能来自哪段逻辑。
4. 若需要修复，必须给出可直接派发的修复建议。

## 下游动作
review
