from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..images import bytes_to_image_file, normalize_ecommerce_image
from ..models import EcommerceSpec, OutputAsset, ProductCopy, TaskManifest
from ..prompts.common import build_derivative_prompt
from ..prompts.ecommerce import build_copy_prompt, build_ecommerce_prompt, missing_copy_fields
from .core import WorkflowContext


def _parse_copy(raw: str) -> dict[str, Any]:
    clean = raw.strip()
    if clean.startswith("```"):
        clean = clean.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    parsed = json.loads(clean)
    if not isinstance(parsed, dict):
        raise ValueError("copy response must be a JSON object")
    return parsed


def _merge_copy(current: ProductCopy, generated: dict[str, Any]) -> ProductCopy:
    generated_points = generated.get("selling_points")
    if not isinstance(generated_points, list):
        generated_points = []
    existing = list(current.selling_points[:3])
    while len(existing) < 3:
        existing.append("")
    points = [existing[index].strip() or (str(generated_points[index]).strip() if index < len(generated_points) else "") for index in range(3)]
    return ProductCopy(
        selling_points=points,
        long_title=current.long_title.strip() or str(generated.get("long_title", "")).strip(),
        short_title=current.short_title.strip() or str(generated.get("short_title", "")).strip(),
    )


def _generate_asset(manifest: TaskManifest, spec: EcommerceSpec, task_type: str, context: WorkflowContext) -> OutputAsset:
    copy = ProductCopy.model_validate(manifest.request["product_copy"])
    prompt = build_ecommerce_prompt(
        task_type=task_type,
        product_name=spec.product_name,
        user_prompt=spec.prompt,
        selling_points=copy.selling_points,
        long_title=copy.long_title,
        short_title=copy.short_title,
        aspect_ratio=spec.aspect_ratio,
    )
    references = [Path(value).expanduser().resolve() for value in spec.reference_images]
    for reference in references:
        if not reference.is_file():
            raise FileNotFoundError(f"reference image not found: {reference}")
    try:
        data = context.client.edit_image(prompt=prompt, images=references, size=spec.provider_size) if references else context.client.generate_image(prompt=prompt, size=spec.provider_size)
        task_dir = context.store.directory(manifest.id)
        raw = task_dir / "outputs" / f"{task_type}-source.png"
        final = task_dir / "outputs" / f"{task_type}.jpg"
        bytes_to_image_file(data, raw)
        normalize_ecommerce_image(raw, final, aspect_ratio=spec.aspect_ratio)
        raw.unlink(missing_ok=True)
        return OutputAsset(id=task_type, kind=task_type, status="succeeded", path=f"outputs/{task_type}.jpg", prompt=prompt, width=spec.final_size[0], height=spec.final_size[1])
    except Exception as error:
        return OutputAsset(id=task_type, kind=task_type, status="failed", prompt=prompt, error=str(error)[:500])


def _status(assets: list[OutputAsset]) -> str:
    succeeded = sum(asset.status == "succeeded" for asset in assets)
    if succeeded == len(assets):
        return "succeeded"
    if succeeded:
        return "partial"
    return "failed"


def run_ecommerce(request: dict[str, Any], context: WorkflowContext) -> TaskManifest:
    spec = EcommerceSpec.model_validate(request)
    safe_request = spec.model_dump(mode="json")
    manifest = context.store.create("ecommerce", safe_request)
    manifest.status = "running"
    context.store.save(manifest)

    missing = missing_copy_fields(
        selected=list(spec.copy_fields),
        selling_points=spec.product_copy.selling_points,
        long_title=spec.product_copy.long_title,
        short_title=spec.product_copy.short_title,
    )
    if missing:
        manifest.text_requests = 1
        try:
            generated = _parse_copy(context.client.generate_text(instructions="Return strict JSON only", input_text=build_copy_prompt(spec.product_name, missing)))
            spec.product_copy = _merge_copy(spec.product_copy, generated)
            manifest.request["product_copy"] = spec.product_copy.model_dump(mode="json")
        except Exception as error:
            manifest.errors.append(f"copy: {str(error)[:450]}")
    manifest.image_requests = len(spec.image_types)
    for task_type in spec.image_types:
        manifest.assets.append(_generate_asset(manifest, spec, task_type, context))
    manifest.status = _status(manifest.assets)
    context.store.save(manifest)
    return manifest


def retry_ecommerce(task_id: str, asset_ids: list[str], context: WorkflowContext) -> TaskManifest:
    manifest = context.store.load(task_id)
    if manifest.kind != "ecommerce":
        raise ValueError("task is not an ecommerce task")
    spec = EcommerceSpec.model_validate(manifest.request)
    selected = set(asset_ids)
    if not selected:
        selected = {asset.id for asset in manifest.assets if asset.status == "failed"}
    replacement: dict[str, OutputAsset] = {}
    for task_type in spec.image_types:
        if task_type in selected:
            replacement[task_type] = _generate_asset(manifest, spec, task_type, context)
            manifest.image_requests += 1
    manifest.assets = [replacement.get(asset.id, asset) for asset in manifest.assets]
    manifest.status = _status(manifest.assets)
    context.store.save(manifest)
    return manifest


def derive_ecommerce(task_id: str, asset_id: str, instruction: str, context: WorkflowContext) -> TaskManifest:
    source_manifest = context.store.load(task_id)
    if source_manifest.kind != "ecommerce":
        raise ValueError("task is not an ecommerce task")
    source_asset = next((asset for asset in source_manifest.assets if asset.id == asset_id and asset.path), None)
    if source_asset is None:
        raise ValueError(f"ecommerce asset not found: {asset_id}")
    spec = EcommerceSpec.model_validate(source_manifest.request)
    source = context.store.directory(task_id) / source_asset.path
    prompt = build_derivative_prompt(instruction, aspect_ratio=spec.aspect_ratio)
    manifest = context.store.create("ecommerce-derive", {
        "source_task_id": task_id,
        "source_asset_id": asset_id,
        "instruction": instruction,
        "aspect_ratio": spec.aspect_ratio,
        "quality": spec.quality,
    })
    manifest.status = "running"
    manifest.image_requests = 1
    context.store.save(manifest)
    try:
        data = context.client.edit_image(prompt=prompt, images=[source], size=spec.provider_size)
        task_dir = context.store.directory(manifest.id)
        raw = task_dir / "outputs" / "derived-source.png"
        final = task_dir / "outputs" / "derived.jpg"
        bytes_to_image_file(data, raw)
        normalize_ecommerce_image(raw, final, aspect_ratio=spec.aspect_ratio)
        raw.unlink(missing_ok=True)
        manifest.assets = [OutputAsset(id="derived", kind="derived", status="succeeded", path="outputs/derived.jpg", prompt=prompt, width=spec.final_size[0], height=spec.final_size[1])]
        manifest.status = "succeeded"
    except Exception as error:
        manifest.status = "failed"
        manifest.errors.append(str(error)[:500])
        context.store.save(manifest)
        raise
    context.store.save(manifest)
    return manifest
