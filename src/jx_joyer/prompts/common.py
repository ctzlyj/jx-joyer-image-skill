def build_derivative_prompt(instruction: str, *, aspect_ratio: str) -> str:
    clean = instruction.strip()
    if not clean:
        raise ValueError("derivative instruction is required")
    return "\n".join([
        "请基于第一张参考图进行追加修改。",
        f"修改要求：{clean}",
        f"保持原图 {aspect_ratio} 的宽高比、主体身份、核心结构和未被点名修改的视觉元素。",
        "不要添加水印、二维码、无关品牌、乱码或误导性标签。",
    ])
