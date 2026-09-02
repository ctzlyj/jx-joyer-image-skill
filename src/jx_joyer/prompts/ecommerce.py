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
    copy_lines = [point.strip() for point in selling_points if point.strip()]
    evidence_rule = (
        "事实与证据门禁：数字、参数、规格、倍率、效果、认证和对比结论，只能来自商品标题、参考图或已有卖点中明确提供或可直接观察的信息；"
        "禁止虚构数字、参数、倍率、效果、认证或竞品差异。"
    )
    main_rule = (
        "以商品为绝对视觉中心，形成适合首屏点击的高级主图。\n"
        "从已有卖点中只选择一个最强、最可信、最容易视觉证明的核心购买理由，不把三个卖点并列堆放。\n"
        "围绕该核心理由组织 1 条主标题、1 条解释性副标题和最多 2 个可信证据标签，所有文字必须服务于同一个核心主题。\n"
        + evidence_rule
        if copy_lines
        else "以商品为绝对视觉中心，形成适合首屏点击的高级主图；不要为了补齐版式虚构卖点、参数或促销承诺。"
    )
    selling_point_rule = (
        "作为主图之后的卖点解释图，不要简单重复主图文案；选择一个需要进一步说明的重点卖点，通过商品结构、材质、细节、使用状态或步骤形成视觉证据。\n"
        "可使用 1 条卖点标题和 1-2 条支持信息，但所有内容必须围绕同一卖点。\n"
        + evidence_rule
        if copy_lines
        else "没有已有卖点时，不要新增营销文字、数字、参数、效果或促销承诺；仅通过商品全貌、结构、材质和可直接观察的细节形成专业的商品解释画面。"
    )
    scene_source = "商品标题、参考图和已有卖点" if copy_lines else "商品标题和参考图"
    task_rules = {
        "main": main_rule,
        "scene": (
            f"根据{scene_source}判断真实使用者、地点、动作与使用时刻，明确呈现谁在什么场景下如何使用商品，以及能够直接看见的使用体验。\n"
            "不确定具体人群或场景时，使用中性、真实、符合品类常识的典型使用场景，不凭空增加用户身份、功能承诺或夸张效果。"
        ),
        "sellingPoints": selling_point_rule,
        "whiteBackground": "纯白背景，商品完整，边缘干净，禁止新增营销文字。",
        "certification": "使用克制可信的信息区展示可确认的认证或品质信息，不得捏造证书、编号、检测数据、机构、公章或认证标志文字。",
        "gridScene": (
            "在统一画布中形成四宫格，用于补充主图与卖点图尚未回答的购买疑问；每格只表达一个信息点，四格信息不得重复。\n"
            "可安排商品全貌，以及材质、结构、工艺、使用步骤、真实差异或场景细节；对比画面必须有真实依据。\n"
            + evidence_rule
        ),
    }
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
