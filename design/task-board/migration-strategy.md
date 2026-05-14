# 任务协作看板迁移策略

> 适用范围：`/Users/linsuchang/Desktop/work/my-agent-teams/dashboard/` 及其 SQLite 数据库  
> 当前数据库路径：`.omx/task-board/task-board.sqlite3`  
> 目标：把当前“仅能初始化 schema”的状态，升级为“有明确 schema version、保守迁移、幂等 rebuild、全量 backfill 语义”的可执行设计。

---

## 一、设计目标

本策略解决四个问题：

1. **schema 怎么升级**
   - 不再只依赖 `CREATE TABLE IF NOT EXISTS`
   - 明确 `SCHEMA_VERSION` 的含义与升级路径

2. **什么时候可以直接 rebuild**
   - 哪些场景允许删库重建 + 全量回填
   - 哪些场景必须保守迁移，不允许直接覆盖

3. **backfill 与增量 sync 如何配合**
   - 新表上线后如何补历史数据
   - 后续 `sync-task / sync-chat / rebuild-metrics` 的职责边界

4. **老库兼容语义是什么**
   - 老版本库如何识别
   - 遇到未知 schema version 怎么处理
   - 缺字段/缺表时是失败退出还是允许重建

---

## 二、基本原则

### 2.1 任务目录与 chat 文件仍是事实源
SQLite 只是派生读库，不是事实源。

事实源仍然是：
- `tasks/*/task.json`
- `tasks/*/ack.json`
- `tasks/*/result.json`
- `tasks/*/review.md`
- `tasks/*/verify.json`
- `tasks/*/transitions.jsonl`
- `chat/general/*.jsonl`
- `chat/tasks/*.jsonl`

因此：
- **能从事实源稳定重建的内容，优先允许 rebuild。**
- 不应把 SQLite 当成唯一不可丢失的系统记录。

### 2.2 优先“可恢复正确性”，再追求“在线无损迁移”
当前 dashboard 属于本地/共享分析看板，不是高可用线上数据库。

因此优先级应为：
1. 结果正确
2. 语义清晰
3. 操作幂等
4. 再考虑迁移过程是否最省事

结论：
- **开发阶段默认优先支持 rebuild + backfill。**
- **仅在共享库保留已有分析价值时，才要求保守迁移。**

### 2.3 迁移 runner 不是本任务范围，但接口边界必须先定义
本任务不实现 SQL migration runner，但必须定义好：
- schema version 存放位置
- migrate / rebuild / backfill 的命令语义
- dev-2 后续实现时的失败/退出规则

---

## 三、schema version 策略

## 3.1 version 存储位置
沿用 `metadata` 表中的：
- `key = 'schema_version'`
- `value = <整数版本>`

同时约定：
- `dashboard/db.py` 中的 `SCHEMA_VERSION` 是**代码期望版本**
- 数据库内的 `metadata.schema_version` 是**当前库实际版本**

## 3.2 version 语义
建议采用单调递增整数：
- `1`：仅 `tasks` / `task_events` 基础库
- `2`：引入 `communication_events`、相关索引、chat ingest state
- `3`：引入 `task_stage_durations`
- `4+`：后续 metrics / spans / analytics 扩展

### 原则
1. **每次有 schema 形态变化时必须升版本**，包括：
   - 新表
   - 删除列/表
   - 新索引（若查询依赖它）
   - 字段语义变化导致旧数据必须回填
2. 纯代码查询逻辑变化、纯文档变更，不升版本。
3. 仅追加可选索引、且旧库不加索引也不影响正确性时，可视项目节奏决定是否升版本；但建议仍升，保持可观测性。

## 3.3 启动时版本检查语义
建议后续实现时区分 4 种情况：

### 情况 A：数据库不存在
- 行为：直接初始化到 `SCHEMA_VERSION`
- 后续动作：允许执行全量 backfill

### 情况 B：数据库版本 == 代码版本
- 行为：正常启动
- 后续动作：执行正常 sync / query

### 情况 C：数据库版本 < 代码版本
- 行为：进入“待迁移”状态
- 不应静默升级
- 必须明确走：
  - `migrate`
  - 或 `rebuild-all`

### 情况 D：数据库版本 > 代码版本
- 行为：失败退出
- 原因：当前代码比数据库旧，不能假设兼容

---

## 四、操作类型定义

## 4.1 initialize
含义：
- 创建新库
- 建到当前 `SCHEMA_VERSION`
- 不负责导入历史数据

适用：
- 首次启动
- 新环境初始化

## 4.2 migrate
含义：
- 在**保留现有 SQLite 内容**前提下，把旧版 schema 升到新版
- 包括增表、加列、加索引、必要的数据补齐

适用：
- 已有共享库上已经沉淀了有价值的派生数据
- 不希望通过删库重建恢复
- 迁移可明确、安全、幂等

## 4.3 backfill
含义：
- 基于事实源，把某类历史数据补进现有库
- 不假定删库
- 通常在 `migrate` 或 `initialize` 之后执行

适用：
- 新增表后补历史行
- 重新扫描 `tasks/` 或 `chat/`
- 重新计算 durations / metrics

## 4.4 rebuild-all
含义：
- 删除或废弃旧 SQLite
- 按最新 schema 重建新库
- 对任务事实、chat、metrics 重新全量回填

适用：
- 开发阶段
- 本地单机场景
- schema 变化较大、写保守迁移成本过高
- 旧库只是可丢弃派生物

---

## 五、哪些场景可以直接 rebuild，哪些必须保守迁移

## 5.1 可直接 rebuild 的场景
以下场景默认允许 `rebuild-all`：

1. **开发者本地库**
   - 本地 `.omx/task-board/task-board.sqlite3`
   - 无多人共享依赖

2. **纯派生表首次引入**
   - 例如新加 `communication_events`
   - 其数据可以从 `chat/*.jsonl` 完整回填

3. **新索引/新聚合表引入且无唯一人工修补数据**
   - 例如 `task_stage_durations`
   - 其值可由 `tasks` / `task_events` 再计算

4. **迁移脚本复杂度明显大于重建成本**
   - 例如需要大规模重写 payload 语义

结论：
- 当前看板阶段，**绝大多数 schema 迭代都应优先支持 rebuild。**

## 5.2 必须保守迁移的场景
以下场景建议优先做 `migrate`，不要默认删库：

1. **共享 SQLite 被多人同时依赖查看**
   - 例如团队统一看板库
   - 删库会影响其他人使用

2. **新表/新列的数据无法完全从事实源回放**
   - 例如未来若出现人工标注、只存在库中的运营注记

3. **迁移仅为小范围增表/加索引，且保守迁移成本低**
   - 例如新增一个完全独立的新表

4. **回填成本过高或时间太长**
   - 如未来历史 chat 数据规模显著增长

## 5.3 当前阶段推荐默认值
对于 `my-agent-teams` 当前规模，建议默认策略是：

- **dev / 本地：默认 rebuild-first**
- **共享 / 团队常用库：migrate-first，必要时人工确认 rebuild**

---

## 六、迁移分类矩阵

## 6.1 可安全自动迁移的变更
这些变更可以作为后续 dev-2 优先实现的 `migrate` 范围：

1. 新增表
2. 新增索引
3. 新增非必填列（或有默认值的列）
4. 新增独立状态表（如 ingest state）

这些变更通常可做到：
- 幂等执行
- 对旧数据无破坏
- 迁移后再 backfill 补历史内容

## 6.2 不建议自动迁移、建议 rebuild 的变更
1. 列重命名
2. 列类型语义变化
3. payload_json 结构升级且历史数据需重写
4. 主键/唯一键策略变化
5. 表拆分/表合并
6. timeline 排序规则变化导致历史事件需整体重算

这些场景若强做自动迁移，很容易留下灰色兼容逻辑。

---

## 七、backfill 边界定义

## 7.1 full backfill
含义：
- 从全部 `tasks/` 与 `chat/` 事实源重扫
- 重建所有派生表

建议入口语义：
- `backfill-tasks`
- `backfill-chat`
- `rebuild-metrics`
- 或 `rebuild-all` 一次串完

适用：
- 新库初始化
- rebuild 后
- 历史数据规则明显变更后

## 7.2 incremental sync
含义：
- 只同步某一个 task 或某一批 chat 文件增量变化

适用：
- watcher 驱动更新
- 日常低成本保持库新鲜

### 原则
- `sync-task` / `sync-chat` 负责**增量事实同步**
- 不应隐式承担 schema migration

## 7.3 metrics rebuild
含义：
- 基于现有 `tasks / task_events / communication_events` 重算聚合表

适用：
- 新增指标
- 指标口径修正
- durations / analytics 规则变化

### 原则
- `metrics` 层应允许单独重建
- 不应要求每次都重扫原始 `tasks/` / `chat/`

---

## 八、推荐命令语义

> 本节定义的是**语义契约**，不是要求本任务实现脚本。

## 8.1 db init
- 若库不存在，建库到当前版本
- 若库已存在，不做迁移

## 8.2 db migrate
- 检查 `db_version < code_version`
- 仅执行允许的保守迁移
- 不做事实源回填，除非该迁移明确要求
- 成功后更新 `metadata.schema_version`

## 8.3 task-board-sync backfill
- 全量扫描 `tasks/`
- upsert `tasks / task_events`
- 不处理 chat

## 8.4 task-board-sync sync-task --task-dir ...
- 仅同步单个任务目录
- 不尝试升级 schema

## 8.5 task-board-sync sync-chat
- 扫描 `chat/general` 与 `chat/tasks`
- upsert `communication_events`
- 可支持 `--task-id` / `--channel`

## 8.6 dashboard-metrics rebuild
- 重算 `task_stage_durations`
- 后续也可重算 metrics 表

## 8.7 task-board-sync rebuild-all
建议语义固定为：
1. 校验当前环境是否允许 rebuild
2. 删除/归档旧 SQLite
3. init 到最新 schema
4. backfill tasks
5. backfill chat
6. rebuild metrics
7. 输出摘要

---

## 九、幂等要求

## 9.1 migration 幂等
- 同一版本迁移重复执行，不应报错或重复加索引
- 已存在的表/索引应安全跳过

## 9.2 backfill 幂等
- 同一 task / chat 文件重复扫描，不应产生重复事件
- 依赖稳定主键：
  - `task_id`
  - `event_key`
  - `event_id`

## 9.3 rebuild 幂等
- 在事实源未变化时，多次 rebuild 结果应一致
- 允许 `last_synced_at / observed_at` 等运行时字段不同
- 但核心业务记录数与键集合应一致

---

## 十、失败策略

## 10.1 版本不匹配
- `db_version < code_version`：拒绝正常 query/sync，提示 migrate 或 rebuild
- `db_version > code_version`：失败退出

## 10.2 backfill 失败
- 单条坏 JSONL / 单个坏 task 不应拖垮整批
- 但应输出：
  - 失败文件
  - 失败行号 / task_id
  - 成功/失败计数

## 10.3 rebuild 失败
- 不应覆盖旧库后再半途失败且无回退说明
- 建议：
  1. 先构建临时新库
  2. backfill 成功后再原子替换
  3. 或保留旧库备份

---

## 十一、与 communication_events / Chat Hub 的兼容要求

1. `communication_events` 的引入应视为 **schema version 升级**，不能只靠 `CREATE TABLE IF NOT EXISTS` 静默混过去。
2. 仅 ingest `chat/tasks/*.jsonl` 也应允许 full backfill，不强依赖 `general` 或 system events 先到位。
3. `source_type=system`、`severity`、`delivery` 等未来字段，不应阻塞当前 rebuild-first 策略；但若字段语义变化导致历史事件必须重写，应优先选 rebuild。
4. Chat Hub 与 dashboard 的桥接规则应单独文档化，不把复杂兼容逻辑埋进迁移脚本。

---

## 十二、建议的第一版实施顺序

### Step 1
先在文档和代码中统一：
- `SCHEMA_VERSION` 的意义
- metadata 版本读取规则
- 版本不匹配时的退出语义

### Step 2
实现最保守可用的迁移能力：
- 增表
- 加索引
- metadata version 更新

### Step 3
实现 `rebuild-all`：
- 新库初始化
- tasks backfill
- chat backfill
- metrics rebuild

### Step 4
后续再按需要追加更细 migration runner

> 推荐优先级：**先把 rebuild-first 路线跑通，再补有限 migrate 能力。**

---

## 十三、交付给 dev-2 的明确边界

dev-2 后续实现时，可直接采用以下约束：

1. **不得把 schema 变更隐式塞进普通 query/sync 路径。**
2. `initialize_db()` 负责“建到当前版本”，不等于“自动迁移旧库”。
3. `sync-task / sync-chat / rebuild-metrics` 都不承担 schema 决策。
4. `rebuild-all` 是当前阶段的一等公民，不是调试后门。
5. 自动迁移仅覆盖：
   - 新表
   - 新索引
   - 新非必填列
6. 发生表语义重构时，默认优先 rebuild，不强做在线迁移。

---

## 十四、一句话结论

> 当前任务协作看板最稳妥的演进路线，不是先追求复杂 migration runner，而是先明确 **version check + rebuild-first + limited migrate + explicit backfill** 的分层策略；只要这四层边界清楚，后续 `communication_events`、`task_stage_durations` 与 metrics 扩表就能稳定推进。
