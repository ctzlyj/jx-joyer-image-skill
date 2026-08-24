from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def select_replica_references(template: Path, images: dict[str, Path], *, purpose: str) -> list[Path]:
    main = images.get("main")
    if main is None:
        raise ValueError("main product image is required")
    normalized = purpose.lower()
    preferred = "scene" if any(word in normalized for word in ("scene", "usage", "experience")) else "logo" if any(word in normalized for word in ("brand", "logo", "service")) else "detail"
    auxiliary = images.get(preferred)
    if auxiliary is None:
        auxiliary = next((value for key, value in images.items() if key != "main"), None)
    return [template, main] + ([] if auxiliary is None else [auxiliary])


def build_replica_prompt(*, purpose: str, layout_summary: str, facts: dict[str, Any], exact_text: list[str], width: int, height: int) -> str:
    return "\n".join([
        f"目标画布：{width}x{height}",
        f"模块用途：{purpose}",
        f"布局摘要：{layout_summary}",
        "模板图只约束构图、配色、版式节奏和视觉结构。",
        "必须替换模板中的商品、Logo、文字、价格和促销元素。",
        f"商品事实：{json.dumps(facts, ensure_ascii=False, sort_keys=True)}",
        "必须逐字绘制：" + " | ".join(exact_text),
        "商品外观以用户商品参考图为准，禁止沿用模板商品身份。",
    ])
