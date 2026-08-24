from __future__ import annotations

import json
from typing import Any


def build_detail_prompt(*, segment: str, facts: dict[str, Any], copy: dict[str, Any], creative_direction: str, width: int, height: int) -> str:
    return "\n".join([
        f"生成京东商品详情页模块：{segment}",
        f"目标画布：{width}x{height}",
        f"商品事实：{json.dumps(facts, ensure_ascii=False, sort_keys=True)}",
        f"已确认文案：{json.dumps(copy, ensure_ascii=False, sort_keys=True)}",
        f"创意方向：{creative_direction.strip() or '专业、清晰、可信'}",
        "参考图中的商品身份、颜色、结构、材质与图案必须保持一致。",
        "只呈现已确认事实，不虚构参数、认证、销量、功效或价格。",
        "中文文案应清晰可读，禁止水印、二维码、乱码和无关品牌。",
    ])
