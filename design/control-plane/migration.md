# 控制面迁移与回滚

## 初始化

现有 `dashboard/db.py::connect_db(..., initialize=True)` 会先创建旧任务读模型，再运行控制面迁移。控制面版本存放在 `metadata.control_plane_schema_version`，当前为 `1`。迁移只创建 `control_plane_*` 表和索引，不删除或重写 `tasks`、`task_events`、`communication_events`。

```bash
python3 -m pytest -q tests/control_plane/test_control_plane_service.py
python3 scripts/control-plane.py project import-legacy --config config.json
python3 scripts/control-plane.py project list
```

## 向后兼容

`project import-legacy` 从旧 `config.json.projects` 的 `dev_root/prod_root/target_branch` 导入项目登记。不存在的目录、非 Git 目录或根目录冲突会出现在 `skipped`，不会删除旧配置，也不会把项目标成 online。

## 回滚

1. 停止 dashboard/watcher 后备份 SQLite。
2. 保留 `tasks/`、`transitions.jsonl` 和旧配置。
3. 若需要移除控制面，先导出 `control_plane_*` 表，再删除控制面表；旧任务读模型不受影响。
4. 外部项目接入使用 `project bootstrap --apply` 生成的备份与 `project uninstall --apply` 的 managed backup 恢复，绝不覆盖业务项目未提交修改。

未知的控制面 schema 版本会失败退出，不能静默降级；数据库版本高于当前代码时必须先升级控制面代码。
