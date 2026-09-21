from __future__ import annotations

from pathlib import Path
from hashlib import sha256
import shutil
from typing import Any

from PIL import Image

from ..images import bytes_to_image_file
from ..models import OutputAsset, TaskManifest
from ..prompts.workbench import build_workbench_prompt
from .core import WorkflowContext

RATIOS = ("1:1", "16:9", "21:9", "4:3", "3:2", "5:4", "2:1", "3:4", "2:3", "4:5", "9:16")
FOUR_K = {
    "1:1": "2880x2880", "16:9": "3840x2160", "21:9": "3840x1648", "4:3": "3264x2448",
    "3:2": "3504x2336", "5:4": "3200x2560", "2:1": "3840x1920", "3:4": "2448x3264",
    "2:3": "2336x3504", "4:5": "2560x3200", "9:16": "2160x3840",
}


def to_image_size(aspect_ratio: str, image_size: str) -> str:
    if image_size == "4K":
        return "3840x2160" if aspect_ratio == "Adaptive" else FOUR_K[aspect_ratio]
    if aspect_ratio in {"Adaptive", "1:1"}:
        return "1024x1024"
    if aspect_ratio in {"16:9", "21:9", "4:3", "3:2", "5:4", "2:1"}:
        return "1536x1024"
    if aspect_ratio in {"3:4", "2:3", "4:5", "9:16"}:
        return "1024x1536"
    raise ValueError(f"unsupported aspect ratio: {aspect_ratio}")


def nearest_ratio(path: Path) -> str:
    with Image.open(path) as image:
        ratio = image.width / image.height
    return min(RATIOS, key=lambda item: abs((int(item.split(":")[0]) / int(item.split(":")[1])) - ratio))


def _paths(values: list[str]) -> list[Path]:
    paths = [Path(value).expanduser().resolve() for value in values]
    for path in paths:
        if not path.is_file():
            raise FileNotFoundError(f"reference image not found: {path}")
    return paths


def create_generation_plan(request: dict[str, Any]) -> list[dict[str, Any]]:
    prompt = str(request.get("prompt", "")).strip()
    if not prompt:
        raise ValueError("prompt is required")
    references = _paths(list(request.get("references", [])))
    prompt_mode = str(request.get("prompt_mode", "count"))
    reference_mode = str(request.get("reference_mode", "shared"))
    requested_ratio = str(request.get("aspect_ratio", "Adaptive"))
    if requested_ratio not in (*RATIOS, "Adaptive") or request.get("image_size", "2K") not in {"1K", "2K", "4K"}:
        raise ValueError("unsupported aspect ratio or image size")
    if prompt_mode not in {"count", "queue"} or reference_mode not in {"shared", "per-image"}:
        raise ValueError("unsupported prompt or reference mode")
    if prompt_mode == "queue" and reference_mode == "per-image":
        raise ValueError("queue mode uses shared references; use per-image mode with one instruction")
    if prompt_mode == "queue":
        normalized = prompt.replace("\r\n", "\n")
        separator = "\n---\n" if "\n---\n" in normalized else "\n"
        prompts = [part.strip() for part in normalized.split(separator) if part.strip()][:10]
    elif reference_mode == "per-image":
        prompts = [prompt] * len(references)
    else:
        prompts = [prompt] * max(1, min(int(request.get("count", 1)), 10))
    if reference_mode == "per-image" and not references:
        raise ValueError("per-image mode requires reference images")
    plan = []
    for index, item_prompt in enumerate(prompts):
        item_refs = [references[index]] if reference_mode == "per-image" else references
        ratio = requested_ratio
        if requested_ratio == "Adaptive" and item_refs:
            ratio = nearest_ratio(item_refs[0])
        plan.append({"id": f"image-{index + 1}", "prompt": item_prompt, "aspect_ratio": ratio, "references": item_refs})
    return plan


def _execute(manifest: TaskManifest, plan: list[dict[str, Any]], context: WorkflowContext) -> TaskManifest:
    manifest.status = "running"
    context.store.save(manifest)
    for item in plan:
        index = next(index for index, asset in enumerate(manifest.assets) if asset.id == item["id"])
        manifest.assets[index] = OutputAsset(id=item["id"], kind="workbench", status="running", prompt=item["prompt"])
        manifest.image_requests += 1
        context.store.save(manifest)
        try:
            references = [context.store.file_path(manifest.id, reference["path"]) for reference in item["references"]]
            if references:
                data = context.client.edit_image(prompt=item["prompt"], images=references, size=item["size"])
            else:
                data = context.client.generate_image(prompt=item["prompt"], size=item["size"])
            relative = f"outputs/{item['id']}.png"
            output = context.store.file_path(manifest.id, relative)
            bytes_to_image_file(data, output)
            with Image.open(output) as image:
                width, height = image.size
            manifest.assets[index] = OutputAsset(id=item["id"], kind="workbench", status="succeeded", path=relative, prompt=item["prompt"], width=width, height=height)
        except Exception as error:
            manifest.assets[index] = OutputAsset(id=item["id"], kind="workbench", status="failed", prompt=item["prompt"], error=str(error)[:500])
        context.store.save(manifest)
    succeeded = sum(asset.status == "succeeded" for asset in manifest.assets)
    manifest.status = "succeeded" if succeeded == len(manifest.assets) else "partial" if succeeded else "failed"
    context.store.save(manifest)
    return manifest


def run_workbench(request: dict[str, Any], context: WorkflowContext) -> TaskManifest:
    plan = create_generation_plan(request)
    safe_request = dict(request)
    safe_request.pop("generation_snapshot", None)
    safe_request["references"] = [str(path) for path in _paths(list(request.get("references", [])))]
    manifest = context.store.create("workbench", safe_request)
    with context.store.execution_lock(manifest.id):
        copied: dict[Path, dict[str, str]] = {}
        snapshot = []
        try:
            for item in plan:
                references = []
                for source in item["references"]:
                    if source not in copied:
                        relative = f"inputs/reference-{len(copied) + 1}{source.suffix.lower()}"
                        target = context.store.file_path(manifest.id, relative)
                        shutil.copyfile(source, target)
                        copied[source] = {"path": relative, "sha256": sha256(target.read_bytes()).hexdigest()}
                    references.append(copied[source])
                roles = ["商品"] + ["补充参考"] * (len(references) - 1) if references else []
                prompt = build_workbench_prompt(item["prompt"], ratio=item["aspect_ratio"], reference_roles=roles)
                snapshot.append({"id": item["id"], "prompt": prompt, "size": to_image_size(item["aspect_ratio"], str(request.get("image_size", "2K"))), "references": references})
            manifest.request["generation_snapshot"] = {"version": 1, "items": snapshot}
            manifest.assets = [OutputAsset(id=item["id"], kind="workbench", prompt=item["prompt"]) for item in snapshot]
            return _execute(manifest, snapshot, context)
        except Exception:
            manifest.status = "failed"
            context.store.save(manifest)
            raise


def retry_workbench(task_id: str, asset_ids: list[str], context: WorkflowContext) -> TaskManifest:
    with context.store.execution_lock(task_id):
        manifest = context.store.load(task_id)
        if manifest.kind != "workbench":
            raise ValueError("task is not a workbench task")
        if manifest.status in {"draft", "running"} or any(asset.status in {"pending", "running"} for asset in manifest.assets):
            raise ValueError("task is running or incomplete; reconcile its outcome before retrying")
        failed = {asset.id for asset in manifest.assets if asset.status == "failed"}
        selected = set(asset_ids) or failed
        if selected - failed:
            raise ValueError("only existing failed images may be retried")
        if not selected:
            return manifest
        snapshot = manifest.request.get("generation_snapshot", {})
        if not isinstance(snapshot, dict) or snapshot.get("version") != 1:
            raise ValueError("original generation snapshot is unavailable; do not replay this task")
        items = snapshot.get("items")
        if not isinstance(items, list) or any(not isinstance(item, dict) or not isinstance(item.get("id"), str) for item in items):
            raise ValueError("generation snapshot items are invalid")
        plan = [item for item in items if item["id"] in selected]
        if len(plan) != len(selected) or {item["id"] for item in plan} != selected:
            raise ValueError("generation snapshot does not match failed images")
        for item in plan:
            if not isinstance(item.get("prompt"), str) or not item["prompt"].strip() or item.get("size") not in (*FOUR_K.values(), "1024x1024", "1536x1024", "1024x1536") or not isinstance(item.get("references"), list):
                raise ValueError("generation snapshot parameters are incomplete")
            for reference in item["references"]:
                if not isinstance(reference, dict) or not isinstance(reference.get("path"), str) or not isinstance(reference.get("sha256"), str):
                    raise ValueError("reference snapshot parameters are incomplete")
                path = context.store.file_path(task_id, reference["path"])
                if not path.is_file() or sha256(path.read_bytes()).hexdigest() != reference["sha256"]:
                    raise ValueError("reference snapshot is missing or changed; do not replay this task")
        return _execute(manifest, plan, context)
