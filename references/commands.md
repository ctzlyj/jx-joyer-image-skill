# 命令参考

普通用户不需要运行这些命令。请直接向 Codex 描述图片需求，由 Skill 自动选择命令、生成任务文件并解释请求量。

## 推荐入口

所有命令优先通过安全包装器运行，它会自动使用 Skill 自带的 `.venv`，并在真实调用缺少 Key 时提供遮罩输入：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\run.ps1 -- doctor
```

统一格式：

```text
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/run.ps1 -- [--output-dir DIR] <command>
```

可用命令：`doctor`、`estimate`、`copy`、`generate`、`edit`、`ecommerce`、`workbench`、`batch-edit`、`detail`、`replica`、`derive`、`history`、`export`。

- `doctor`：检查 Python、Key 是否存在和固定网关配置，不发送模型请求。
- `estimate --task-file FILE`：计算预计文案与图片请求数，不发送模型请求。
- `copy --instructions TEXT --input TEXT --yes`：生成结构化文案。
- `generate --prompt TEXT [--size SIZE] --yes`：无参考图文生图。
- `edit --prompt TEXT --reference FILE [--reference FILE ...] [--size SIZE] --yes`：单图或多图参考编辑。
- `derive --source FILE --instruction TEXT [--aspect-ratio RATIO] [--size SIZE] --yes`：对现有结果追加修改。
- `ecommerce --task-file FILE --yes`：生成商品套图。
- `ecommerce --retry TASK_ID [--asset TYPE ...] --yes`：重试失败的商品图。
- `ecommerce --derive TASK_ID --asset TYPE --instruction TEXT --yes`：派生修改商品图。
- `workbench --task-file FILE --yes`：执行提示词队列或多参考图任务。
- `workbench --retry TASK_ID [--asset ID ...] --yes`：仅重试失败图，省略 `--asset` 时选择全部失败项；保留成功结果。
- `batch-edit --task-file FILE --yes`：批量修图。
- `batch-edit --retry TASK_ID [--asset ID ...] --yes`：重试失败项。
- `detail --task-file FILE [--yes]`：执行详情页 `create`、`copy`、`generate`、`derive`、`restore` 或 `export`。
- `replica --task-file FILE [--yes]`：执行爆款复刻 `analyze`、`configure`、`copy`、`generate` 或 `cancel`。
- `history [--kind KIND] [--limit N]`：读取本地历史，不发送模型请求。
- `history --task TASK_ID`：回读单个任务及逐图状态，不需要 Key。
- `export --task TASK_ID [--asset ID ...]`：在该任务 `exports/` 下生成 ZIP；省略 `--asset` 时导出全部成功图片。无需 `--yes` 或 Key，不包含原参考图和任务清单。

`--yes` 是 CLI 的真实执行标志。Codex 在需求明确后自动添加，不需要用户额外确认调用次数；没有 `--yes` 时，包装器不会索要 Key，也不会调用模型。

## 直接 CLI

已经手工激活虚拟环境的高级用户仍可使用：

```powershell
jx-joyer doctor
jx-joyer estimate --task-file task.json
```

Key 只能通过当前进程的 `JD_LLM_API_KEY` 提供，不能放进参数、任务文件或日志。
