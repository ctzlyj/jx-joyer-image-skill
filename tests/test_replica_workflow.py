from io import BytesIO
import json
from pathlib import Path

from PIL import Image

from jx_joyer.storage import TaskStore
from jx_joyer.workflows.core import WorkflowContext
from jx_joyer.workflows.replica import analyze_replica, cancel_replica, configure_replica, generate_replica_copy, generate_replica_segments


def png_bytes(color="red", size=(800,1000)):
    buffer=BytesIO(); Image.new("RGB", size, color).save(buffer, format="PNG"); return buffer.getvalue()


class FakeClient:
    def __init__(self): self.calls=[]; self.text_index=0
    def generate_text(self, **kwargs):
        self.calls.append(("text", kwargs)); self.text_index += 1
        if self.text_index == 1:
            return json.dumps({"modules":[{"id":"replica-1","order":0,"startY":0,"endY":1,"purpose":"detail","purposeDescription":"细节展示","layoutSummary":"左图右文","requiredInformationCategories":["材质"]}],"questions":[]}, ensure_ascii=False)
        return json.dumps({"replica-1":{"headline":"品质之选","exact_visible_text":["品质之选"],"bullets":[]}}, ensure_ascii=False)
    def edit_image(self, **kwargs): self.calls.append(("edit", kwargs)); return png_bytes("blue")


def setup(tmp_path: Path):
    template=tmp_path/"template.png"; template.write_bytes(png_bytes())
    product=tmp_path/"product.png"; product.write_bytes(png_bytes("green"))
    client=FakeClient(); context=WorkflowContext(client, TaskStore(tmp_path/"tasks"))
    manifest=analyze_replica({"name":"复刻任务","template":str(template),"images":{"main":str(product)},"facts":{"材质":"棉"}}, context)
    return client, context, manifest


def test_replica_analysis_and_copy(tmp_path: Path) -> None:
    client, context, manifest=setup(tmp_path)
    assert manifest.request["project"]["slices"][0]["id"] == "replica-1"
    assert "data:image/png;base64," in client.calls[0][1]["input_text"]
    copied=generate_replica_copy(manifest.id, context)
    assert copied.request["project"]["copy"]["replica-1"]["headline"] == "品质之选"


def test_replica_generate_revision_and_cancel(tmp_path: Path) -> None:
    client, context, manifest=setup(tmp_path)
    configured=configure_replica(manifest.id, {"copy":{"replica-1":{"exact_visible_text":["新品上市"]}}}, context)
    generated=generate_replica_segments(configured.id, [], context)
    assert generated.status == "succeeded"
    assert generated.request["project"]["segments"]["replica-1"]["current_revision"] == 1
    refs=next(call for call in client.calls if call[0] == "edit")[1]["images"]
    assert Path(refs[0]).name == "replica-1-template.png"
    with Image.open(refs[0]) as template_slice:
        assert template_slice.size == (800, 1000)
    assert Path(refs[1]).name == "product.png"
    cancelled=cancel_replica(manifest.id, context)
    assert cancelled.status == "cancelled"
