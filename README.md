# JX Joyer Image Skill

面向京东同事的 Codex Skill 与 Python CLI，直接调用内部 Oxygen 网关完成电商商品套图、详情页、自由生图、参考图编辑、批量修图、派生修改和爆款复刻。

## 前提

- Python 3.11 或更高版本。
- 已连接京东内网或 VPN，可访问 `llm-gw.jd.local`。
- 使用者拥有自己的 Oxygen Key。

## 安装

```bash
python -m pip install -e ".[dev]"
```

也可通过 Codex 的 GitHub Skill 安装方式安装本仓库。

## Key

只在当前终端进程设置 `JD_LLM_API_KEY`。不要写入 `.env`、任务 JSON、命令参数、日志或聊天消息。

PowerShell：

```powershell
$env:JD_LLM_API_KEY = Read-Host "Oxygen Key"
```

Bash：

```bash
read -s JD_LLM_API_KEY && export JD_LLM_API_KEY
```

## 使用

先检查环境，不调用模型：

```bash
jx-joyer doctor
```

复杂任务先写 JSON，再估算调用次数：

```bash
jx-joyer estimate --task-file task.json
```

确认预计请求数量后执行：

```bash
jx-joyer --output-dir ./jx-joyer-output ecommerce --task-file task.json --yes
```

简单文生图：

```bash
jx-joyer generate --prompt "白底棚拍风格的红色保温杯商品主图" --size 1024x1024 --yes
```

完整命令见 `references/commands.md`，任务格式见 `references/task-schema.md`，能力映射见 `references/capabilities.md`。

## 输出

每次任务写入 `<output-dir>/<task-id>/`：

- `manifest.json`：非敏感任务参数、状态、请求计数和结果路径。
- `outputs/`：生成图片和导出文件。
- `inputs/`：用户明确要求复制时才保存输入副本。
- `previews/`：可选预览图。

## 安全

- 不依赖 `ct.space.jd.com`、Space ERP 或网站后端。
- 不读取网站用户数据或 `/app/data`。
- 无参考图使用 `/images/generations`；有参考图使用 `/images/edits`。
- 不创建空白参考图模拟文生图。
- 不包含任何真实 Key、Cookie 或生产响应。
- 真实调用会消耗个人 Oxygen 额度；Codex 必须先运行 `estimate` 并取得用户确认。

## 许可证

MIT
