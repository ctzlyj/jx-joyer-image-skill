from __future__ import annotations

from pathlib import Path
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
    if prompt_mode == "queue":
        prompts = [part.strip() for part in prompt.replace("\r\n", "\n").split("\n---\n") if part.strip()][:10]
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


def run_workbench(request: dict[str, Any], context: WorkflowContext) -> TaskManifest:
    plan = create_generation_plan(request)
    image_size = str(request.get("image_size", "2K"))
    safe_request = dict(request)
    safe_request["references"] = [str(path) for path in _paths(list(request.get("references", [])))]
    manifest = context.store.create("workbench", safe_request)
    manifest.status = "running"
    manifest.image_requests = len(plan)
    context.store.save(manifest)
    for item in plan:
        roles = [] if not item["references"] else ["商品"] + ["补充参考"] * max(0, len(item["references"]) - 1)
        prompt = build_workbench_prompt(item["prompt"], ratio=item["aspect_ratio"], reference_roles=roles)
        try:
            if item["references"]:
                data = context.client.edit_image(prompt=prompt, images=item["references"], size=to_image_size(item["aspect_ratio"], image_size))
            else:
                data = context.client.generate_image(prompt=prompt, size=to_image_size(item["aspect_ratio"], image_size))
            relative = f"outputs/{item['id']}.png"
            bytes_to_image_file(data, context.store.directory(manifest.id) / relative)
            manifest.assets.append(OutputAsset(id=item["id"], kind="workbench", status="succeeded", path=relative, prompt=prompt))
        except Exception as error:
            manifest.assets.append(OutputAsset(id=item["id"], kind="workbench", status="failed", prompt=prompt, error=str(error)[:500]))
    succeeded = sum(asset.status == "succeeded" for asset in manifest.assets)
    manifest.status = "succeeded" if succeeded == len(manifest.assets) else "partial" if succeeded else "failed"
    context.store.save(manifest)
    return manifest

