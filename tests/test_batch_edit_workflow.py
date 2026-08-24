from io import BytesIO
from pathlib import Path

from PIL import Image

from jx_joyer.storage import TaskStore
from jx_joyer.workflows.batch_edit import retry_batch_edit, run_batch_edit
from jx_joyer.workflows.core import WorkflowContext


def png_bytes(color="red"):
    buffer = BytesIO(); Image.new("RGB", (64, 64), color).save(buffer, format="PNG"); return buffer.getvalue()


class FakeClient:
    def __init__(self, fail_first=False):
        self.calls=[]; self.fail_first=fail_first
    def edit_image(self, **kwargs):
        self.calls.append(kwargs)
        if self.fail_first:
            self.fail_first=False
            raise RuntimeError("temporary")
        return png_bytes("blue")


def test_batch_edit_prepends_source_then_common_references(tmp_path: Path) -> None:
    source = tmp_path / "source.png"; source.write_bytes(png_bytes())
    common = tmp_path / "style.png"; common.write_bytes(png_bytes("green"))
    client = FakeClient()
    manifest = run_batch_edit({"prompt": "统一蓝色背景", "sources": [str(source)], "common_references": [str(common)], "aspect_ratio": "1:1", "image_size": "2K"}, WorkflowContext(client, TaskStore(tmp_path / "tasks")))
    assert client.calls[0]["images"] == [source.resolve(), common.resolve()]
    assert manifest.status == "succeeded"


def test_batch_retry_only_retries_failed_items(tmp_path: Path) -> None:
    sources=[]
    for index in range(2):
        path=tmp_path / f"source-{index}.png"; path.write_bytes(png_bytes()); sources.append(str(path))
    client=FakeClient(fail_first=True); context=WorkflowContext(client, TaskStore(tmp_path / "tasks"))
    manifest=run_batch_edit({"prompt":"清理背景","sources":sources,"aspect_ratio":"1:1","image_size":"2K"}, context)
    assert manifest.status == "partial"
    failed=[asset.id for asset in manifest.assets if asset.status == "failed"]
    retried=retry_batch_edit(manifest.id, failed, context)
    assert retried.status == "succeeded"
    assert len(client.calls) == 3


def test_batch_adaptive_uses_each_source_orientation(tmp_path: Path) -> None:
    portrait = tmp_path / "portrait.png"; Image.new("RGB", (300, 400), "red").save(portrait)
    client = FakeClient()
    run_batch_edit({"prompt":"清理背景","sources":[str(portrait)],"aspect_ratio":"Adaptive","image_size":"2K"}, WorkflowContext(client, TaskStore(tmp_path / "tasks")))
    assert client.calls[0]["size"] == "1024x1536"
