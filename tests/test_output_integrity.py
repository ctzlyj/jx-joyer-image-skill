from pathlib import Path
import importlib.util

from PIL import Image, ImageDraw


SCRIPT = Path(__file__).parents[1] / "scripts" / "verify_output_integrity.py"
SPEC = importlib.util.spec_from_file_location("verify_output_integrity", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def test_allows_only_declared_logo_region(tmp_path: Path) -> None:
    generated = tmp_path / "generated.png"
    final = tmp_path / "final.png"
    Image.new("RGB", (200, 200), "white").save(generated)
    image = Image.open(generated).convert("RGB")
    ImageDraw.Draw(image).rectangle((10, 10, 39, 39), fill="red")
    image.save(final)
    result = MODULE.verify_integrity(generated, final, [(10, 10, 30, 30)], 0.1, 1.0)
    assert result["status"] == "passed"


def test_rejects_rectangular_source_patch_outside_overlay(tmp_path: Path) -> None:
    generated = tmp_path / "generated.png"
    final = tmp_path / "final.png"
    Image.new("RGB", (200, 200), "white").save(generated)
    image = Image.open(generated).convert("RGB")
    draw = ImageDraw.Draw(image)
    draw.rectangle((10, 10, 39, 39), fill="red")
    draw.rectangle((70, 70, 169, 169), fill="black")
    image.save(final)
    result = MODULE.verify_integrity(generated, final, [(10, 10, 30, 30)], 0.1, 1.0)
    assert result["status"] == "failed"
