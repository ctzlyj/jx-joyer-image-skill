def build_workbench_prompt(prompt: str, *, ratio: str, reference_roles: list[str]) -> str:
    clean = prompt.strip()
    if not clean:
        raise ValueError("prompt is required")
    lines = [f"生成要求：{clean}", f"目标比例：{ratio}"]
    for index, role in enumerate(reference_roles, start=1):
        lines.append(f"参考图{index}（{role}）：仅按该角色使用，不混淆商品身份与风格信息。")
    lines.extend([
        "有商品参考图时严格保持商品主体的颜色、轮廓、材质、结构、图案和文字。",
        "禁止水印、二维码、乱码、无关品牌与未经要求的营销信息。",
    ])
    return "\n".join(lines)
