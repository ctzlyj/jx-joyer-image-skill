from __future__ import annotations

import base64
from io import BytesIO
from pathlib import Path
from typing import Iterable

from PIL import Image, ImageOps

from .constants import ECOMMERCE_FINAL_SIZES


def safe_output_path(root: str | Path, relative: str | Path) -> Path:
    resolved_root = Path(root).expanduser().resolve()
    candidate = (resolved_root / relative).resolve()
    if candidate != resolved_root and resolved_root not in candidate.parents:
        raise ValueError("output path escapes the configured root")
    return candidate


def detect_image_mime(path: str | Path) -> str:
    with Image.open(path) as image:
        image_format = (image.format or "").upper()
    return {
        "JPEG": "image/jpeg",
        "PNG": "image/png",
        "WEBP": "image/webp",
        "GIF": "image/gif",
        "BMP": "image/bmp",
    }.get(image_format, "application/octet-stream")


def image_to_data_url(path: str | Path) -> str:
    source = Path(path)
    encoded = base64.b64encode(source.read_bytes()).decode("ascii")
    return f"data:{detect_image_mime(source)};base64,{encoded}"


def write_image_bytes(data: bytes, target: str | Path) -> Path:
    path = Path(target)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(data)
    temporary.replace(path)
    return path


def normalize_ecommerce_image(source: str | Path, target: str | Path, *, aspect_ratio: str) -> Path:
    if aspect_ratio not in ECOMMERCE_FINAL_SIZES:
        raise ValueError(f"unsupported ecommerce aspect ratio: {aspect_ratio}")
    size = ECOMMERCE_FINAL_SIZES[aspect_ratio]
    with Image.open(source) as image:
        rgb = _as_rgb(image)
        normalized = ImageOps.fit(rgb, size, method=Image.Resampling.LANCZOS, centering=(0.5, 0.5))
        path = Path(target)
        path.parent.mkdir(parents=True, exist_ok=True)
        normalized.save(path, format="JPEG", quality=92, optimize=True)
    return Path(target)


def resize_for_ratio(source: str | Path, target: str | Path, *, ratio: str, max_dimension: int = 1536) -> Path:
    with Image.open(source) as image:
        if ratio.lower() == "adaptive":
            resized = image.copy()
            if max(resized.size) > max_dimension:
                resized.thumbnail((max_dimension, max_dimension), Image.Resampling.LANCZOS)
        else:
            width_ratio, height_ratio = _parse_ratio(ratio)
            if width_ratio >= height_ratio:
                size = (max_dimension, max(1, round(max_dimension * height_ratio / width_ratio)))
            else:
                size = (max(1, round(max_dimension * width_ratio / height_ratio)), max_dimension)
            resized = ImageOps.fit(image, size, method=Image.Resampling.LANCZOS, centering=(0.5, 0.5))
        path = Path(target)
        path.parent.mkdir(parents=True, exist_ok=True)
        output_format = "PNG" if path.suffix.lower() == ".png" else "JPEG"
        output = resized if output_format == "PNG" else _as_rgb(resized)
        output.save(path, format=output_format, quality=92)
    return Path(target)


def concatenate_vertical(sources: Iterable[str | Path], target: str | Path) -> Path:
    opened: list[Image.Image] = []
    try:
        for source in sources:
            with Image.open(source) as image:
                opened.append(_as_rgb(image).copy())
        if not opened:
            raise ValueError("at least one segment image is required")
        width = max(image.width for image in opened)
        normalized: list[Image.Image] = []
        for image in opened:
            if image.width == width:
                normalized.append(image)
            else:
                height = max(1, round(image.height * width / image.width))
                normalized.append(image.resize((width, height), Image.Resampling.LANCZOS))
        canvas = Image.new("RGB", (width, sum(image.height for image in normalized)), "white")
        y = 0
        for image in normalized:
            canvas.paste(image, (0, y))
            y += image.height
        path = Path(target)
        path.parent.mkdir(parents=True, exist_ok=True)
        canvas.save(path, format="JPEG", quality=92, optimize=True)
        return path
    finally:
        for image in opened:
            image.close()


def bytes_to_image_file(data: bytes, target: str | Path) -> Path:
    with Image.open(BytesIO(data)) as image:
        image.load()
        path = Path(target)
        path.parent.mkdir(parents=True, exist_ok=True)
        suffix = path.suffix.lower()
        output_format = "JPEG" if suffix in {".jpg", ".jpeg"} else "WEBP" if suffix == ".webp" else "PNG"
        output = _as_rgb(image) if output_format == "JPEG" else image.copy()
        output.save(path, format=output_format, quality=92)
        return path


def _parse_ratio(ratio: str) -> tuple[int, int]:
    try:
        width, height = (int(part) for part in ratio.split(":", 1))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid aspect ratio: {ratio}") from exc
    if width <= 0 or height <= 0:
        raise ValueError(f"invalid aspect ratio: {ratio}")
    return width, height


def _as_rgb(image: Image.Image) -> Image.Image:
    if image.mode in {"RGBA", "LA"} or (image.mode == "P" and "transparency" in image.info):
        rgba = image.convert("RGBA")
        background = Image.new("RGBA", rgba.size, "white")
        return Image.alpha_composite(background, rgba).convert("RGB")
    return image.convert("RGB")

