from io import BytesIO
import json
from pathlib import Path

from PIL import Image

from jx_joyer.storage import TaskStore
from jx_joyer.workflows.core import WorkflowContext
from jx_joyer.workflows.detail import create_detail_project, derive_detail_segment, export_detail, generate_detail_segments, generate_detail_copy, restore_detail_revision


def png_bytes(color="red"):
    buffer=BytesIO(); Image.new("RGB", (1024, 1536), color).save(buffer, format="PNG"); return buffer.getvalue()


class FakeClient:
    def __init__(self): self.calls=[]
    def generate_text(self, **kwargs):
        self.calls.append(("text", kwargs)); return json.dumps({"hero":{"headline":"核心标题","body":"正文"}}, ensure_ascii=False)
    def generate_image(self, **kwargs):
        self.calls.append(("generate", kwargs)); return png_bytes()
    def edit_image(self, **kwargs):
        self.calls.append(("edit", kwargs)); return png_bytes("blue")


def setup_project(tmp_path: Path):
    client=FakeClient(); context=WorkflowContext(client, TaskStore(tmp_path / "tasks"))
    reference=tmp_path / "product.png"; reference.write_bytes(png_bytes())
    manifest=create_detail_project({"name":"测试详情","facts":{"材质":"棉"},"references":[str(reference)],"creative_direction":"清新"}, context)
    return client, context, manifest


def test_detail_copy_and_generate_all_core_segments(tmp_path: Path) -> None:
    client, context, manifest=setup_project(tmp_path)
    copied=generate_detail_copy(manifest.id, context)
    assert copied.request["project"]["copy"]["hero"]["headline"] == "核心标题"
    generated=generate_detail_segments(manifest.id, [], context)
    assert generated.status == "succeeded"
    assert [asset.kind for asset in generated.assets] == ["hero","product","benefits","experience","proof","service"]
    assert all(call[0] == "edit" for call in client.calls if call[0] != "text")
    for asset in generated.assets:
        with Image.open(context.store.directory(manifest.id) / asset.path) as image:
            assert image.size == (750,1125)


def test_detail_revision_derive_restore_and_export(tmp_path: Path) -> None:
    _, context, manifest=setup_project(tmp_path)
    generated=generate_detail_segments(manifest.id, ["hero","product"], context)
    derived=derive_detail_segment(manifest.id, "hero", "增加柔和阴影", context)
    project=derived.request["project"]
    assert project["segments"]["hero"]["current_revision"] == 2
    restored=restore_detail_revision(manifest.id, "hero", 1, context)
    assert restored.request["project"]["segments"]["hero"]["current_revision"] == 1
    exported=export_detail(manifest.id, context)
    export_asset=next(asset for asset in exported.assets if asset.kind == "detail-export")
    with Image.open(context.store.directory(manifest.id) / export_asset.path) as image:
        assert image.size == (750,2250)
