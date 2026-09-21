import json
from io import BytesIO
from pathlib import Path

from PIL import Image

from jx_joyer.storage import TaskStore
from jx_joyer.workflows.core import WorkflowContext
from jx_joyer.workflows.ecommerce import derive_ecommerce, retry_ecommerce, run_ecommerce


def png_bytes(color: str = "red", size=(1152, 1536)) -> bytes:
    buffer = BytesIO()
    Image.new("RGB", size, color).save(buffer, format="PNG")
    return buffer.getvalue()


class FakeClient:
    def __init__(self, *, fail_first_image: bool = False) -> None:
        self.calls = []
        self.fail_first_image = fail_first_image

    def generate_text(self, **kwargs):
        self.calls.append(("text", kwargs))
        return json.dumps({"selling_points": ["手工卖点", "耐用", "易清洁"], "short_title": "模型短标题"}, ensure_ascii=False)

    def generate_image(self, **kwargs):
        self.calls.append(("generate", kwargs))
        if self.fail_first_image:
            self.fail_first_image = False
            raise RuntimeError("temporary")
        return png_bytes()

    def edit_image(self, **kwargs):
        self.calls.append(("edit", kwargs))
        return png_bytes("blue")


def test_ecommerce_preserves_manual_copy_and_normalizes_portrait(tmp_path: Path) -> None:
    client = FakeClient()
    context = WorkflowContext(client=client, store=TaskStore(tmp_path))
    manifest = run_ecommerce({
        "product_name": "测试商品",
        "prompt": "高级清爽",
        "image_types": ["main", "sellingPoints"],
        "copy_fields": ["sellingPoints", "longTitle", "shortTitle"],
        "product_copy": {"selling_points": ["手工卖点", "", ""], "long_title": "手工长标题", "short_title": ""},
        "aspect_ratio": "3:4",
        "quality": "4K",
        "reference_images": [],
    }, context)
    assert manifest.status == "succeeded"
    assert manifest.image_requests == 2
    assert manifest.text_requests == 1
    assert manifest.request["product_copy"]["long_title"] == "手工长标题"
    assert manifest.request["product_copy"]["short_title"] == "模型短标题"
    image_calls = [call for call in client.calls if call[0] == "generate"]
    assert all(call[1]["size"] == "2448x3264" for call in image_calls)
    for asset in manifest.assets:
        with Image.open(tmp_path / manifest.id / asset.path) as image:
            assert image.size == (600, 800)
            assert image.format == "JPEG"
    assert "手工长标题" in manifest.assets[0].prompt


def test_ecommerce_uses_edit_when_references_exist(tmp_path: Path) -> None:
    reference = tmp_path / "reference.png"
    reference.write_bytes(png_bytes())
    client = FakeClient()
    context = WorkflowContext(client=client, store=TaskStore(tmp_path / "tasks"))
    run_ecommerce({"product_name": "商品", "image_types": ["main"], "reference_images": [str(reference)]}, context)
    assert [name for name, _ in client.calls] == ["edit"]


def test_ecommerce_retry_only_failed_asset(tmp_path: Path) -> None:
    client = FakeClient(fail_first_image=True)
    context = WorkflowContext(client=client, store=TaskStore(tmp_path))
    manifest = run_ecommerce({"product_name": "商品", "image_types": ["main", "scene"]}, context)
    assert manifest.status == "partial"
    failed = [asset.id for asset in manifest.assets if asset.status == "failed"]
    retried = retry_ecommerce(manifest.id, failed, context)
    assert retried.status == "succeeded"
    assert all(asset.status == "succeeded" for asset in retried.assets)


def test_manual_copy_without_auto_copy_survives_retry(tmp_path: Path) -> None:
    client = FakeClient(fail_first_image=True)
    context = WorkflowContext(client=client, store=TaskStore(tmp_path))
    copy = {"selling_points": ["手填卖点", "", ""], "long_title": "手填长标题", "short_title": "手填短标题"}
    manifest = run_ecommerce({"product_name": "商品", "image_types": ["main"], "copy_fields": [], "product_copy": copy}, context)
    retried = retry_ecommerce(manifest.id, [], context)
    assert retried.request["product_copy"] == copy
    assert all(call[0] != "text" for call in client.calls)
    assert "手填卖点" in retried.assets[0].prompt
    assert "手填长标题" in retried.assets[0].prompt


def test_ecommerce_derivative_inherits_ratio(tmp_path: Path) -> None:
    client = FakeClient()
    context = WorkflowContext(client=client, store=TaskStore(tmp_path))
    manifest = run_ecommerce({"product_name": "商品", "image_types": ["main"], "aspect_ratio": "3:4"}, context)
    derived = derive_ecommerce(manifest.id, "main", "增加阴影", context)
    assert derived.request["aspect_ratio"] == "3:4"
    assert client.calls[-1][0] == "edit"
