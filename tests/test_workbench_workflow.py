from io import BytesIO
from pathlib import Path

from PIL import Image

from jx_joyer.storage import TaskStore
from jx_joyer.workflows.core import WorkflowContext
from jx_joyer.workflows.workbench import create_generation_plan, run_workbench, to_image_size


def png_bytes(color="red"):
    buffer = BytesIO()
    Image.new("RGB", (320, 240), color).save(buffer, format="PNG")
    return buffer.getvalue()


class FakeClient:
    def __init__(self):
        self.calls = []
    def generate_image(self, **kwargs):
        self.calls.append(("generate", kwargs)); return png_bytes()
    def edit_image(self, **kwargs):
        self.calls.append(("edit", kwargs)); return png_bytes("blue")


def test_workbench_size_mapping_matches_site() -> None:
    assert to_image_size("1:1", "2K") == "1024x1024"
    assert to_image_size("16:9", "2K") == "1536x1024"
    assert to_image_size("3:4", "2K") == "1024x1536"
    assert to_image_size("3:4", "4K") == "2448x3264"


def test_queue_plan_and_zero_reference_generation(tmp_path: Path) -> None:
    plan = create_generation_plan({"prompt": "第一张\n---\n第二张", "prompt_mode": "queue", "aspect_ratio": "1:1", "image_size": "2K", "references": []})
    assert [item["prompt"] for item in plan] == ["第一张", "第二张"]
    client = FakeClient()
    manifest = run_workbench({"prompt": "第一张\n---\n第二张", "prompt_mode": "queue", "aspect_ratio": "1:1", "image_size": "2K", "references": []}, WorkflowContext(client, TaskStore(tmp_path)))
    assert [name for name, _ in client.calls] == ["generate", "generate"]
    assert manifest.status == "succeeded"


def test_per_image_references_are_not_mixed(tmp_path: Path) -> None:
    refs = []
    for index in range(2):
        path = tmp_path / f"{index}.png"; path.write_bytes(png_bytes()); refs.append(str(path))
    client = FakeClient()
    run_workbench({"prompt": "统一修图", "reference_mode": "per-image", "aspect_ratio": "Adaptive", "image_size": "1K", "references": refs}, WorkflowContext(client, TaskStore(tmp_path / "tasks")))
    assert [len(call[1]["images"]) for call in client.calls] == [1, 1]
    assert all(name == "edit" for name, _ in client.calls)


def test_zero_reference_prompt_does_not_claim_reference_roles(tmp_path: Path) -> None:
    client = FakeClient()
    run_workbench({"prompt": "纯文字生成", "count": 1, "aspect_ratio": "1:1", "image_size": "1K", "references": []}, WorkflowContext(client, TaskStore(tmp_path)))
    assert "参考图1" not in client.calls[0][1]["prompt"]
