# 任务：排查 王开 生产 skill 失败根因

## 任务类型
排查

## 目标
基于林总工的更正信息，重新定位并排查用户“王开”在生产环境失败的真实 skill——**订单图包生成 / PPT 精美模式相关链路**，判断故障点是否位于：CogView 密钥、图片生成链路、PPTX 装配链路，或其上下游配置/运行时逻辑。

## 任务边界
- 本任务是**只读排查**，先不要直接修改 chiralium 代码。
- 可以读取：
  - 生产数据库中的 feedback / chat / message 数据
  - 当前开发仓库中的 PPT 精美模式、订单图包生成相关代码与测试
  - 历史任务链与工件
- 不要写生产库，不要部署，不要直接修代码。
- 若确认根因后需要修复，只在 `result.json` 中给出建议下游任务。

## 输入事实
- Docker 环境已确认可用，生产库容器：`chiralium_prod_postgres`
- 数据库：`chiralium_prod_db`
- 用户：`chiralium`
- 生产用户“王开”当前已定位到：
  - `users.id = bece02b8-7b3b-4431-9d91-5467491ceba7`
  - `username = 用户7251`
  - `remark = 王开`
- 按林总工要求，已用以下关键词重查最近反馈：
  - `订单图包`
  - `PPT`
  - `生成`
- **查询结果：在王开当前这个 user_id 下，最近 feedback_issues / feedback_requests 中没有直接命中这些关键词的记录。**
- 在全库最近 21 天范围内，命中 `PPT/生成` 的可见反馈主要是另一位用户（remark=小兔）的记录，不能直接当作王开的那条失败反馈。
- 因此：
  1. 林总工的更正信息优先于当前关键词反馈检索结果；
  2. 需要继续从“王开的最近对话 / message feedback / 会话上下文 / 相关附件 / 近期订单图包/PPT 任务链”反查真实失败链路。
- 当前已知重点链路：
  - 订单图包相关 skill：
    - `/Users/lin/Desktop/work/chiralium/skills/custom/order-print-image-pack/1.0.0`
  - PPT 精美模式 / 图片生成：
    - `/Users/lin/Desktop/work/chiralium/skills/custom/ppt_generator/1.0.0`
    - `/Users/lin/Desktop/work/chiralium/backend/app/services/ppt_page_render_service.py`
  - PPTX 装配相关：
    - `/Users/lin/Desktop/work/chiralium/backend/app/services/office_export_service.py`
- 当前重点排查环节：
  1. **生产环境 CogView / 智谱图片模型可用性与密钥来源**
  2. **图片生成请求链路是否在生产中正确选中模型与 base_url**
  3. **订单图包/PPT 精美模式的页图生成后，是否在 PPTX/图包装配阶段失败**
  4. **是否存在 user message / recent_messages / parsed_files 输入导致的特殊失败模式**

## 约束
- write_scope: []
- read_only: true
- target_environment: dev
- execution_mode: dev
- owner_approval_required: false
- 若要引用生产库信息，只记录必要事实，不泄露密钥明文。
- 若没找到直接命中的反馈记录，必须在结论里明确说明“数据库关键词检索未命中”，并给出你采用的替代证据链。

## 交付物
- `/Users/lin/Desktop/work/my-agent-teams/tasks/排查王开生产skill失败根因/ack.json`
- `/Users/lin/Desktop/work/my-agent-teams/tasks/排查王开生产skill失败根因/result.json`

`result.json` 必须至少包含：
- 是否找到与“王开”本次失败最相关的具体记录 / 证据链
- 最可能的真实失败对象（订单图包生成 / PPT 精美模式哪一条）
- 对 CogView 密钥、图片生成链路、PPTX 装配链路的逐项判断
- 根因判断（已解决 / 未解决 / 无法确认）
- 若需要修复，给出建议下游任务标题

## 验收标准
1. 不能再把本次问题误判为 box-calculator / 外箱计算链路。
2. 结论中必须明确说明数据库关键词检索是否命中；若未命中，要说明替代排查路径。
3. 至少对以下三段链路逐项给出判断：
   - CogView 密钥 / 生产图片模型
   - 图片生成链路
   - PPTX / 图包装配链路
4. 若判断已解决，需给出对应历史修复链路；若未解决，需给出后续修复建议。

## 下游动作
review
