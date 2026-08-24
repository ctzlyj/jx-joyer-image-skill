# JX Joyer Image Skill 零门槛使用设计

## 目标

让不了解 Skill、Python、JSON 或 CLI 的京东同事完成一次安装后，只需向 Codex 描述生图需求。Codex 自动识别业务场景、补齐必要信息、选择现有能力并直接执行。

## 用户体验

首次安装只提供一段可复制给 Codex 的中文话术。Codex 从公开 GitHub 仓库安装 Skill，并运行仓库内的 `install.ps1`。脚本自动检查 Windows、Python 3.11+、虚拟环境、依赖和 Skill 文件完整性，最后输出清晰的中文成功状态或修复步骤。

安装后，用户直接说“帮我给这款商品生成一套 3:4 商品图”“参考这几张图统一换背景”或“做一套商品详情页”。用户不需要选择命令、创建 JSON 或理解工作流名称。

## 自动路由

`SKILL.md` 将自然语言作为默认入口。Codex 根据意图和输入素材自动路由到商品套图、详情页、自由生图、参考图编辑、批量修图、派生修改或爆款复刻，只询问执行所必需且无法推断的信息。

Codex 在后台创建最小任务文件，需求明确后直接执行。`estimate` 保留为可选查询能力，不再要求用户确认调用次数。现有高级 CLI 保留，但从首页主流程移到高级用法。

## 安装与运行脚本

- 根目录新增 `install.ps1`，负责创建仓库内 `.venv`、安装当前包、运行环境检查和 Skill 校验。
- 新增 `scripts/run.ps1`，作为 Codex 默认调用入口；它优先使用仓库内虚拟环境，不要求用户手工激活。
- 离线命令如 `doctor`、`estimate` 和 `history` 不要求 Key。
- 真实模型命令缺少 Key 时，`run.ps1` 使用 PowerShell 安全输入读取本次 Key，传给单个 Python 子进程，并在 `finally` 中清空进程环境变量和临时明文变量。
- Key 不写入用户环境、注册表、配置文件、任务文件、日志、命令参数或 Git。

## 自动环境检查

安装脚本检查 Python 版本、虚拟环境创建、依赖安装、CLI 导入和固定网关配置。JD 内网网关连通性只给出状态提示，不发送模型请求；不在内网或 VPN 时输出可操作的中文说明，而不是 Python 堆栈。

`doctor` 保持机器可读结果，同时由 PowerShell 包装层提供面向普通用户的中文摘要。

## 文档结构

README 首页改成“给 Codex 一句话安装”“安全输入 Key”“直接描述需求”三步。首页提供常见自然语言示例和故障提示；命令、JSON schema 和开发安装移到高级用法文档。

## 安全与边界

- 固定使用 `http://llm-gw.jd.local/v1`、`GPT-5.6-Sol-joybuilder` 和 `GPT-image-2-joybuilder`。
- 无参考图调用 `/images/generations`，有参考图调用 `/images/edits`。
- 不依赖 Space 网站、ERP、浏览器、外部站数据或服务端 Key。
- 不打包 Windows 客户端或 EXE；`install.ps1` 只是 Skill 的本地安装引导。
- 需求明确后允许直接执行；不再把请求量预估或二次确认作为强制门槛。

## 验证

新增 PowerShell 脚本结构与安全约束测试，覆盖安装幂等性、虚拟环境选择、离线命令不索要 Key、在线命令安全提示，以及文档的新手入口。继续运行全部 pytest、Skill 校验、Python 编译、安全扫描和 `git diff --check`。
