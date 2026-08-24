from __future__ import annotations

from pathlib import Path
from typing import Any

from ..images import bytes_to_image_file
from ..models import OutputAsset, TaskManifest
from ..prompts.workbench import build_workbench_prompt
from .core import WorkflowContext
from .workbench import nearest_ratio, to_image_size


def _paths(values: list[str], label: str) -> list[Path]:
    paths = [Path(value).expanduser().resolve() for value in values]
    for path in paths:
        if not path.is_file():
            raise FileNotFoundError(f"{label} image not found: {path}")
    return paths


def _edit_item(manifest: TaskManifest, asset_id: str, source: Path, common: list[Path], request: dict[str, Any], context: WorkflowContext) -> OutputAsset:
    requested_ratio = str(request.get("aspect_ratio", "Adaptive"))
    ratio = nearest_ratio(source) if requested_ratio == "Adaptive" else requested_ratio
    image_size = str(request.get("image_size", "2K"))
    prompt = build_workbench_prompt(str(request.get("prompt", "")), ratio=ratio, reference_roles=["待修改源图"] + ["公共参考"] * len(common))
    try:
        data = context.client.edit_image(prompt=prompt, images=[source, *common], size=to_image_size(ratio, image_size))
        relative = f"outputs/{asset_id}.png"
        bytes_to_image_file(data, context.store.directory(manifest.id) / relative)
        return OutputAsset(id=asset_id, kind="batch-edit", status="succeeded", path=relative, prompt=prompt)
    except Exception as error:
        return OutputAsset(id=asset_id, kind="batch-edit", status="failed", prompt=prompt, error=str(error)[:500])


def _finish(manifest: TaskManifest, context: WorkflowContext) -> TaskManifest:
    succeeded = sum(asset.status == "succeeded" for asset in manifest.assets)
    manifest.status = "succeeded" if succeeded == len(manifest.assets) else "partial" if succeeded else "failed"
    context.store.save(manifest)
    return manifest


def run_batch_edit(request: dict[str, Any], context: WorkflowContext) -> TaskManifest:
    sources = _paths(list(request.get("sources", [])), "source")
    if not sources:
        raise ValueError("at least one source image is required")
    if len(sources) > 10:
        raise ValueError("batch editing supports at most 10 source images")
    common = _paths(list(request.get("common_references", [])), "common reference")
    if len(common) > 3:
        raise ValueError("batch editing supports at most 3 common references")
    safe_request = dict(request)
    safe_request["sources"] = [str(path) for path in sources]
    safe_request["common_references"] = [str(path) for path in common]
    manifest = context.store.create("batch-edit", safe_request)
    manifest.status = "running"
    manifest.image_requests = len(sources)
    context.store.save(manifest)
    for index, source in enumerate(sources):
        manifest.assets.append(_edit_item(manifest, f"source-{index + 1}", source, common, safe_request, context))
    return _finish(manifest, context)


def retry_batch_edit(task_id: str, asset_ids: list[str], context: WorkflowContext) -> TaskManifest:
    manifest = context.store.load(task_id)
    if manifest.kind != "batch-edit":
        raise ValueError("task is not a batch-edit task")
    sources = _paths(list(manifest.request.get("sources", [])), "source")
    common = _paths(list(manifest.request.get("common_references", [])), "common reference")
    selected = set(asset_ids) or {asset.id for asset in manifest.assets if asset.status == "failed"}
    replacements: dict[str, OutputAsset] = {}
    for index, source in enumerate(sources):
        asset_id = f"source-{index + 1}"
        if asset_id in selected:
            replacements[asset_id] = _edit_item(manifest, asset_id, source, common, manifest.request, context)
            manifest.image_requests += 1
    manifest.assets = [replacements.get(asset.id, asset) for asset in manifest.assets]
    return _finish(manifest, context)

