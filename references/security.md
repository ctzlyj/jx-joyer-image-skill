# 安全边界

- Key 名称固定为 `JD_LLM_API_KEY`，只从当前进程环境读取。
- 不支持通过参数、JSON、`.env`、配置文件或交互提示保存 Key。
- 不打印 Authorization Header、完整图片 Data URL 或网关原始请求体。
- `manifest.json` 会递归拒绝常见凭据字段。
- 输出路径在解析后必须位于 `--output-dir` 内。
- 公开仓库不得包含真实商品数据、生产响应、Cookie、ERP、Space 数据或 Deployment 地址。
- 内部网关只可在京东内网或 VPN 中调用，不得暴露为公网代理。
- 真实模型调用前必须运行 `estimate` 并取得用户明确确认，然后才可加入 `--yes`。
- 测试默认使用 `httpx.MockTransport` 和程序生成的测试图片，不消耗 Oxygen 额度。
