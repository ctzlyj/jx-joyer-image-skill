# JX Joyer Image Skill

面向京东同事的 Oxygen 生图助手。安装一次后，直接把图片和需求告诉 Codex，它会自动选择商品套图、详情页、自由生图、参考图编辑、批量修图、派生修改或爆款复刻能力。

## 第一步：让 Codex 安装

把下面这句话完整发给 Codex：

> 请从 https://github.com/CTctikki/jx-joyer-image-skill 安装这个 Skill，并运行 install.ps1 完成环境检查。不要执行真实生图。

Codex 会自动安装独立运行环境并检查 Python、依赖和京东内网状态。安装阶段不会调用模型，也不会消耗 Oxygen 额度。

## 第二步：直接描述需求

不需要理解 Skill、命令行或 JSON，也不需要选择模型。直接上传素材并说明想要什么，例如：

- “为这款保温杯生成一套 3:4 京东商品图，红色调，突出保温 24 小时。”
- “参考这三张图，把产品统一放到干净的厨房场景，生成 1:1 图片。”
- “根据商品图做一套详情页，突出材质、尺寸、使用场景和售后保障。”
- “把这 8 张商品图统一改成白底，产品主体不要变化。”
- “这张结果保持构图不变，把背景改成春节氛围。”
- “分析这张爆款图的版式，并用我的商品重新制作。”
- “生成一张极简棚拍风格的蓝色咖啡杯主图。”

Codex 会自动分析需求、选择能力、补齐任务参数。只有确实缺少必要信息时才会提问。

## 第三步：确认调用量并安全输入 Key

Codex 会先告诉你预计需要多少次文案请求和图片请求。你确认后，终端才会提示：

```text
请输入你的 Oxygen Key（输入内容不会显示）
```

在终端输入自己的 Key；输入过程会被遮罩。不要把 Key 发到聊天中，也不要写进文档、截图或任务文件。Key 只用于本次命令，结束后会从进程环境中清除。

还没有 Key，可查看[申请教程](https://joyspace.jd.com/pages/sROLhJ3F7ZCZZEOWonh6)。真实调用前需要连接京东内网或 VPN。

## 能做什么

- 商品套图：六类图片、文案补齐、1:1/3:4、1K/2K/4K、失败重试和派生修改。
- 商品详情页：六个核心模块、文案、单段或全量生成、修订恢复、派生和长图导出。
- 自由工作台：文生图、多参考图编辑、提示词队列、固定比例和自适应比例。
- 批量修图：多源图、公共参考图、逐项结果和失败重试。
- 爆款复刻：模板分析、切片、文案、分片生成和取消。
- 本地历史：请求量预估、任务清单、输出文件和错误脱敏。

## 输出位置

默认结果保存在当前工作目录的 `jx-joyer-output/<task-id>/`：

- `outputs/`：生成图片和导出文件。
- `manifest.json`：不含 Key 的任务状态、请求数和结果路径。
- `inputs/`：仅在明确要求复制输入时创建。
- `previews/`：可选预览图。

## 常见问题

- 提示无法连接网关：先连接京东内网或 VPN，再让 Codex 重新运行环境检查。
- 提示缺少 Python：安装 Python 3.11 或更高版本，然后再次发送第一步的安装话术。
- 生图失败：把错误信息告诉 Codex；不要发送 Key。Codex 会使用现有重试和错误映射排查。
- 想修改结果：直接引用生成图片并描述修改内容，无需重新解释整个流程。

## 高级用法

手工安装或开发：

```powershell
python -m pip install -e ".[dev]"
powershell -NoProfile -ExecutionPolicy Bypass -File .\install.ps1
```

通过安全包装器运行离线检查：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\run.ps1 -- doctor
```

复杂任务的命令见 `references/commands.md`，格式见 `references/task-schema.md`，能力映射见 `references/capabilities.md`。

## 安全边界

- 固定网关：`http://llm-gw.jd.local/v1`。
- 固定文案模型：`GPT-5.6-Sol-joybuilder`。
- 固定生图模型：`GPT-image-2-joybuilder`。
- 无参考图调用 `/images/generations`；有参考图调用 `/images/edits`。
- 不依赖 Space 网站、ERP、浏览器存储、外部站数据、COS/CDN 或 Windows 客户端。
- 不保存真实 Key、Cookie 或生产响应。

## 许可证

MIT
