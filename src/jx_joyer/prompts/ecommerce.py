from __future__ import annotations

from collections.abc import Iterable

TASK_LABELS = {
    "main": "电商主图",
    "scene": "电商场景图",
    "sellingPoints": "电商卖点图",
    "whiteBackground": "电商白底图",
    "certification": "电商认证图",
    "gridScene": "电商四宫格图",
}
FIELD_KEYS = {"sellingPoints": "selling_points", "longTitle": "long_title", "shortTitle": "short_title"}


def missing_copy_fields(*, selected: list[str], selling_points: list[str], long_title: str, short_title: str) -> list[str]:
    missing = {
        "sellingPoints": len(selling_points) < 3 or any(not item.strip() for item in selling_points[:3]),
        "longTitle": not long_title.strip(),
        "shortTitle": not short_title.strip(),
    }
    order = ["sellingPoints", "longTitle", "shortTitle"]
    return [field for field in order if field in selected and missing[field]]


def build_copy_prompt(product_name: str, fields: Iterable[str]) -> str:
    requested = [FIELD_KEYS[field] for field in fields]
    if not requested:
        raise ValueError("at least one missing copy field is required")
    requirements = {
        "selling_points": "selling_points：正好 3 个可信短卖点，每个 4-10 个汉字",
        "long_title": "long_title：适合商品上架的电商长标题",
        "short_title": "short_title：适合图片主标题的短标题",
    }
    lines = ["你是资深京东电商文案策划。", f"商品：{product_name}", "只返回严格 JSON，并且只包含以下字段："]
    lines.extend(f"- {requirements[field]}" for field in requested)
    lines.append("不得虚构医疗、功效、认证、销量或绝对化承诺。")
    return "\n".join(lines)


def build_ecommerce_prompt(
    *,
    task_type: str,
    product_name: str,
    user_prompt: str,
    selling_points: list[str],
    long_title: str,
    short_title: str,
    aspect_ratio: str,
) -> str:
    if task_type not in TASK_LABELS:
        raise ValueError(f"unsupported ecommerce task type: {task_type}")
    task_rules = {
        "main": "以商品为绝对视觉中心，形成适合首屏点击的高级主图。",
        "scene": "把商品置于真实可信且符合使用逻辑的生活或商业场景。",
        "sellingPoints": "清晰呈现卖点信息，文字层级明确且适合手机阅读。",
        "whiteBackground": "纯白背景，商品完整，边缘干净，禁止新增营销文字。",
        "certification": "使用克制可信的信息区展示可确认的认证或品质信息，不得捏造证书。",
        "gridScene": "在统一画布中形成四宫格场景，商品身份和风格保持一致。",
    }
    copy_lines = [point.strip() for point in selling_points if point.strip()]
    blocks = [
        f"任务：{TASK_LABELS[task_type]}",
        f"商品：{product_name}",
        f"构图：严格 {aspect_ratio}，商品完整且不裁切关键部位。",
        task_rules[task_type],
        "参考图是商品外观的唯一依据，严格保留颜色、轮廓、材质、图案、文字、结构、配件和比例。",
    ]
    if user_prompt.strip():
        blocks.append(f"个性化要求：{user_prompt.strip()}")
    if copy_lines:
        blocks.append("卖点：" + "；".join(copy_lines))
    if long_title.strip():
        blocks.append("长标题：" + long_title.strip())
    if short_title.strip():
        blocks.append("短标题：" + short_title.strip())
    blocks.append("不添加水印、二维码、无关 logo、乱码、价格或未经确认的促销信息。")
    return "\n".join(blocks)
