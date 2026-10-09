# 生图模型三选一同步回执（2026-10-09）

## 同步范围

- 生图主模型从 `GPT-image-2-joybuilder`（服务不可用/额度耗尽）切换为 `Oxygen-Product-Pro`，与 Space 网页版默认模型保持一致。
- 降级链更新为 `Oxygen-Product-Pro` -> `GPT-Image-2.5-Flare-joybuilder` -> `GPT-Image-2.5-Sunburst-joybuilder`；`/images/generations` 与 `/images/edits` 沿用同一降级链，移除已不再使用的 `Oxygen-Imagen`。
- 三款模型于 2026-10-08/09 在公司网关真实调用验证：文生图 `/images/generations` 与参考图编辑 `/images/edits` 均返回可用 PNG。
- 尺寸约束改为按模型映射：`Oxygen-Product-Pro` 就近映射到实测可用的 1024x1024、1024x1536、1536x1024；GPT-Image-2.5 系列按请求尺寸透传（最高 4K*）。
- `Oxygen-Product-Pro` 返回 `data[0].url`（京东 CDN），客户端二次下载且不携带网关凭证；GPT-Image-2.5 系列返回 `b64_json`，两种响应格式均已兼容。
- README 新增《生图模型》15 维完整对比表；`SKILL.md` 与 `references/capabilities.md` 同步说明固定降级链，不开放模型参数。
- 版本号升级为 `0.4.0`。

## 验证

- 全量单测 114 项通过，含新增的主模型尺寸映射、额度降级与双 GPT 降级链用例。
- 更新后用真实网关 Key 冒烟：`/images/generations` 与 `/images/edits` 均按新链路返回 PNG；真实 Key 未写入源码、测试、文档或日志。
