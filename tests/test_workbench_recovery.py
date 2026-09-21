from pathlib import Path
import subprocess
import sys
import zipfile

import pytest

from jx_joyer.models import OutputAsset
from jx_joyer.storage import TaskStore
from jx_joyer.workflows.core import WorkflowContext
from jx_joyer.workflows import workbench
from test_workbench_workflow import FakeClient, png_bytes


class PartialClient(FakeClient):
    def generate_image(self, **kwargs):
        self.calls.append(("generate", kwargs))
        if len(self.calls) == 2:
            raise RuntimeError("synthetic failure")
        return png_bytes()


def test_progress_is_persisted_before_each_call(tmp_path):
    store = TaskStore(tmp_path)
    snapshots = []

    class InspectClient(FakeClient):
        def generate_image(self, **kwargs):
            current = store.list()[0]
            snapshots.append([asset.status for asset in current.assets])
            assert current.status == "running"
            return super().generate_image(**kwargs)

    manifest = workbench.run_workbench({"prompt": "商品", "count": 2}, WorkflowContext(InspectClient(), store))
    assert snapshots == [["running", "pending"], ["succeeded", "running"]]
    assert all((asset.width, asset.height) == (320, 240) for asset in manifest.assets)


def test_retry_preserves_success_and_rejects_successful_selection(tmp_path):
    client = PartialClient()
    context = WorkflowContext(client, TaskStore(tmp_path))
    manifest = workbench.run_workbench({"prompt": "商品", "count": 2}, context)
    original = manifest.assets[0].model_dump()
    original_bytes = (context.store.directory(manifest.id) / manifest.assets[0].path).read_bytes()
    with pytest.raises(ValueError, match="failed"):
        workbench.retry_workbench(manifest.id, ["image-1"], context)
    assert len(client.calls) == 2
    retried = workbench.retry_workbench(manifest.id, ["image-2"], context)
    assert retried.status == "succeeded"
    assert retried.assets[0].model_dump() == original
    assert (context.store.directory(manifest.id) / retried.assets[0].path).read_bytes() == original_bytes
    assert len(client.calls) == 3
    assert retried.image_requests == 3
    assert workbench.retry_workbench(manifest.id, [], context).status == "succeeded"
    assert len(client.calls) == 3


def test_retry_uses_saved_reference_not_modified_source(tmp_path):
    source = tmp_path / "original.png"
    source.write_bytes(png_bytes())

    class EditClient(FakeClient):
        def edit_image(self, **kwargs):
            self.calls.append(("edit", kwargs))
            if len(self.calls) == 1:
                raise RuntimeError("synthetic failure")
            assert kwargs["images"][0].read_bytes() == png_bytes()
            return png_bytes()

    client = EditClient()
    context = WorkflowContext(client, TaskStore(tmp_path / "tasks"))
    manifest = workbench.run_workbench({"prompt": "保留商品", "references": [str(source)]}, context)
    source.write_bytes(png_bytes("blue"))
    assert workbench.retry_workbench(manifest.id, [], context).status == "succeeded"


def test_missing_or_changed_snapshot_is_not_replayed(tmp_path):
    context = WorkflowContext(PartialClient(), TaskStore(tmp_path))
    legacy = context.store.create("workbench", {"prompt": "旧任务"})
    legacy.status = "failed"
    legacy.assets = [OutputAsset(id="image-1", kind="workbench", status="failed")]
    context.store.save(legacy)
    with pytest.raises(ValueError, match="snapshot"):
        workbench.retry_workbench(legacy.id, [], context)
    source = tmp_path / "source.png"
    source.write_bytes(png_bytes())

    class FailedEdit(FakeClient):
        def edit_image(self, **kwargs):
            self.calls.append(("edit", kwargs))
            raise RuntimeError("synthetic failure")

    context.client = FailedEdit()
    manifest = workbench.run_workbench({"prompt": "参考", "references": [str(source)]}, context)
    snapshot = next((context.store.directory(manifest.id) / "inputs").glob("*"))
    snapshot.write_bytes(png_bytes("blue"))
    with pytest.raises(ValueError, match="snapshot"):
        workbench.retry_workbench(manifest.id, [], context)
    assert len(context.client.calls) == 1


def test_task_lock_and_running_status_prevent_retry(tmp_path):
    context = WorkflowContext(PartialClient(), TaskStore(tmp_path))
    manifest = workbench.run_workbench({"prompt": "商品", "count": 2}, context)
    with context.store.execution_lock(manifest.id):
        with pytest.raises(RuntimeError, match="executing"):
            workbench.retry_workbench(manifest.id, [], context)
    manifest.status = "running"
    context.store.save(manifest)
    with pytest.raises(ValueError, match="running"):
        workbench.retry_workbench(manifest.id, [], context)
    assert len(context.client.calls) == 2


def test_task_lock_blocks_another_process_and_releases(tmp_path):
    store = TaskStore(tmp_path)
    manifest = store.create("workbench", {})
    source = "\n".join([
        "import sys",
        "from jx_joyer.storage import TaskStore",
        "try:",
        "    with TaskStore(sys.argv[1]).execution_lock(sys.argv[2]): pass",
        "except RuntimeError:",
        "    sys.exit(17)",
    ])
    command = [sys.executable, "-c", source, str(tmp_path), manifest.id]
    with store.execution_lock(manifest.id):
        assert subprocess.run(command, capture_output=True, timeout=15).returncode == 17
    assert subprocess.run(command, capture_output=True, timeout=15).returncode == 0


@pytest.mark.parametrize("field", ["prompt", "size", "references"])
def test_incomplete_snapshot_does_not_change_status_or_call_model(tmp_path, field):
    context = WorkflowContext(PartialClient(), TaskStore(tmp_path))
    manifest = workbench.run_workbench({"prompt": "商品", "count": 2}, context)
    del manifest.request["generation_snapshot"]["items"][1][field]
    context.store.save(manifest)
    with pytest.raises(ValueError, match="snapshot"):
        workbench.retry_workbench(manifest.id, [], context)
    assert context.store.load(manifest.id).status == "partial"
    assert len(context.client.calls) == 2


def test_zip_all_and_selected_excludes_failed_and_private_inputs(tmp_path):
    context = WorkflowContext(PartialClient(), TaskStore(tmp_path))
    manifest = workbench.run_workbench({"prompt": "不进压缩包的提示词", "count": 3}, context)
    from jx_joyer.exports import export_task
    archive = export_task(context.store, manifest.id, [])
    with zipfile.ZipFile(archive) as result:
        assert len(result.namelist()) == 2
        assert all(name.endswith(".png") and "/" not in name for name in result.namelist())
    selected = export_task(context.store, manifest.id, ["image-3"])
    with zipfile.ZipFile(selected) as result:
        assert len(result.namelist()) == 1
    for selection in (["image-2"], ["unknown"]):
        with pytest.raises(ValueError):
            export_task(context.store, manifest.id, selection)


def test_zip_rejects_path_escape(tmp_path):
    from jx_joyer.exports import export_task
    store = TaskStore(tmp_path)
    manifest = store.create("workbench", {})
    manifest.assets = [OutputAsset(id="image-1", kind="workbench", status="succeeded", path="../outside.png")]
    store.save(manifest)
    with pytest.raises(ValueError):
        export_task(store, manifest.id, [])


@pytest.mark.parametrize("relative", ["inputs/reference.png", "manifest.json", "outputs/notes.txt"])
def test_zip_cannot_export_input_or_metadata(tmp_path, relative):
    from jx_joyer.exports import export_task
    store = TaskStore(tmp_path)
    manifest = store.create("workbench", {})
    manifest.assets = [OutputAsset(id="image-1", kind="workbench", status="succeeded", path=relative)]
    if relative != "manifest.json":
        (store.directory(manifest.id) / relative).write_bytes(png_bytes())
    store.save(manifest)
    with pytest.raises(ValueError):
        export_task(store, manifest.id, [])


def test_queue_supports_web_lines_and_legacy_multiline_separator():
    assert len(workbench.create_generation_plan({"prompt": "第一张\n第二张", "prompt_mode": "queue"})) == 2
    plan = workbench.create_generation_plan({"prompt": "第一张\n详细要求\n---\n第二张", "prompt_mode": "queue"})
    assert [item["prompt"] for item in plan] == ["第一张\n详细要求", "第二张"]


@pytest.mark.parametrize("options", [{"aspect_ratio": "unknown"}, {"image_size": "unknown"}, {"prompt_mode": "unknown"}, {"reference_mode": "per-image", "prompt_mode": "queue"}])
def test_invalid_plan_fails_before_creating_task(tmp_path, options):
    context = WorkflowContext(FakeClient(), TaskStore(tmp_path))
    with pytest.raises(ValueError):
        workbench.run_workbench({"prompt": "商品", **options}, context)
    assert context.store.list() == []
    assert not context.client.calls
