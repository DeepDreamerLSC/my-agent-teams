# prompts 归档说明

旧角色 prompt 已于 2026-05-12 迁入 `../design/archive/prompts/`。

当前 agent 角色文件由 `../design/agent-templates/` 生成：

```bash
bash scripts/build-agent-files.sh --dry-run
bash scripts/build-agent-files.sh
```

保留本目录是为了兼容 `config.json.prompts_root` 和历史保护路径配置；不要在这里新增当前角色规则。
