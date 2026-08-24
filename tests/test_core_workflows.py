from io import BytesIO
from pathlib import Path

from PIL import Image

from jx_joyer.storage import TaskStore
from jx_joyer.workflows.core import WorkflowContext, run_copy, run_derive, run_edit, run_generate


def png_bytes(color: str = "red") -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (64, 64), color).save(buffer, format="PNG")
    return buffer.getvalue()


class FakeClient:
    def __init__(self) -> None:
        self.calls = []

    def generate_text(self, **kwargs):
        self.calls.append(("text", kwargs))
        return '{"short_title":"测试"}'

    def generate_image(self, **kwargs):
        self.calls.append(("generate", kwargs))
        return png_bytes()

    def edit_image(self, **kwargs):
        self.calls.append(("edit", kwargs))
        return png_bytes("blue")


def test_core_routes_zero_references_to_generation(tmp_path: Path) -> None:
    client = FakeClient()
    context = WorkflowContext(client=client, store=TaskStore(tmp_path))
    manifest = run_generate({"prompt": "生成红色商品", "size": "1024x1024"}, context)
    assert client.calls[0][0] == "generate"
    assert manifest.status == "succeeded"
    assert (tmp_path / manifest.id / manifest.assets[0].path).is_file()


def test_core_routes_references_to_edit(tmp_path: Path) -> None:
    reference = tmp_path / "reference.png"
    reference.write_bytes(png_bytes())
    client = FakeClient()
    context = WorkflowContext(client=client, store=TaskStore(tmp_path / "tasks"))
    manifest = run_edit({"prompt": "改成蓝色", "references": [str(reference)], "size": "1024x1024"}, context)
    assert client.calls[0][0] == "edit"
    assert client.calls[0][1]["images"] == [reference.resolve()]
    assert manifest.status == "succeeded"


def test_copy_and_derive_are_recorded(tmp_path: Path) -> None:
    source = tmp_path / "source.png"
    source.write_bytes(png_bytes())
    client = FakeClient()
    context = WorkflowContext(client=client, store=TaskStore(tmp_path / "tasks"))
    copy_manifest = run_copy({"instructions": "返回 JSON", "input": "商品"}, context)
    derive_manifest = run_derive({"source": str(source), "instruction": "增加阴影", "aspect_ratio": "1:1", "size": "1024x1024"}, context)
    assert copy_manifest.status == "succeeded"
    assert copy_manifest.request["result"] == '{"short_title":"测试"}'
    assert derive_manifest.status == "succeeded"
    assert client.calls[-1][0] == "edit"
