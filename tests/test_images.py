from pathlib import Path

import pytest
from PIL import Image

from jx_joyer.images import concatenate_vertical, image_to_data_url, normalize_ecommerce_image, resize_for_ratio, safe_output_path


def test_data_url_uses_detected_png_media_type(tmp_path: Path) -> None:
    source = tmp_path / "source.bin"
    Image.new("RGBA", (10, 10), (1, 2, 3, 4)).save(source, format="PNG")
    assert image_to_data_url(source).startswith("data:image/png;base64,")


@pytest.mark.parametrize("ratio,expected", [("1:1", (800, 800)), ("3:4", (600, 800))])
def test_ecommerce_normalization(tmp_path: Path, ratio: str, expected: tuple[int, int]) -> None:
    source = tmp_path / "source.png"
    target = tmp_path / "result.jpg"
    Image.new("RGB", (1200, 1600), "red").save(source)
    normalize_ecommerce_image(source, target, aspect_ratio=ratio)
    with Image.open(target) as result:
        assert result.format == "JPEG"
        assert result.size == expected


def test_adaptive_keeps_source_aspect_ratio(tmp_path: Path) -> None:
    source = tmp_path / "source.png"
    target = tmp_path / "adaptive.png"
    Image.new("RGB", (400, 200), "blue").save(source)
    resize_for_ratio(source, target, ratio="adaptive", max_dimension=1000)
    with Image.open(target) as result:
        assert result.size == (400, 200)


def test_detail_segments_concatenate_in_order(tmp_path: Path) -> None:
    first = tmp_path / "first.png"
    second = tmp_path / "second.png"
    target = tmp_path / "detail.jpg"
    Image.new("RGB", (100, 50), "red").save(first)
    Image.new("RGB", (100, 70), "blue").save(second)
    concatenate_vertical([first, second], target)
    with Image.open(target) as result:
        assert result.size == (100, 120)
        assert result.getpixel((10, 10))[0] > result.getpixel((10, 10))[2]
        assert result.getpixel((10, 100))[2] > result.getpixel((10, 100))[0]


def test_safe_output_path_rejects_escape(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="output path"):
        safe_output_path(tmp_path, "../escape.png")



def test_generated_bytes_are_reencoded_for_target_extension(tmp_path: Path) -> None:
    from io import BytesIO
    from jx_joyer.images import bytes_to_image_file
    buffer = BytesIO()
    Image.new("RGB", (20, 10), "green").save(buffer, format="JPEG")
    target = tmp_path / "result.png"
    bytes_to_image_file(buffer.getvalue(), target)
    with Image.open(target) as result:
        assert result.format == "PNG"
