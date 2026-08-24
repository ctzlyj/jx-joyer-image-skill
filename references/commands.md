# 命令参考

统一入口：`jx-joyer [--output-dir DIR] <command>`。可用命令：`doctor`、`estimate`、`copy`、`generate`、`edit`、`ecommerce`、`workbench`、`batch-edit`、`detail`、`replica`、`derive`、`history`。

- `doctor`：检查 Python 版本、Key 是否存在和固定网关配置，不发送模型请求。
- `estimate --task-file FILE`：计算预计文案与生图请求数，不发送模型请求。
- `copy --instructions TEXT --input TEXT --yes`：生成结构化文案。
- `generate --prompt TEXT [--size SIZE] --yes`：无参考图文生图。
- `edit --prompt TEXT --reference FILE [--reference FILE ...] [--size SIZE] --yes`：单图或多图参考编辑。
- `derive --source FILE --instruction TEXT [--aspect-ratio RATIO] [--size SIZE] --yes`：对现有结果追加修改。
- `ecommerce --task-file FILE --yes`：生成商品套图。
- `ecommerce --retry TASK_ID [--asset TYPE ...] --yes`：重试失败商品图。
- `ecommerce --derive TASK_ID --asset TYPE --instruction TEXT --yes`：派生商品图。
- `workbench --task-file FILE --yes`：自由生图、提示词队列或多参考图编辑。
- `batch-edit --task-file FILE --yes`：批量修图。
- `batch-edit --retry TASK_ID [--asset ID ...] --yes`：只重试失败项。
- `detail --task-file FILE --yes`：执行详情页 `create`、`copy`、`generate`、`derive`、`restore` 或 `export` 动作。
- `replica --task-file FILE --yes`：执行爆款复刻 `analyze`、`configure`、`copy`、`generate` 或 `cancel` 动作。
- `history [--kind KIND] [--limit N]`：读取本地任务历史。

所有真实模型命令都要求 `--yes`。这表示用户已看到 `estimate` 结果并明确同意消耗额度，不表示允许保存 Key。

CLI 成功时向 stdout 输出 JSON；错误时向 stderr 输出脱敏 JSON，并返回非零退出码。

