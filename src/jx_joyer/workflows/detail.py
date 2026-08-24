from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..images import bytes_to_image_file, concatenate_vertical, resize_for_ratio
from ..models import OutputAsset, TaskManifest
from ..prompts.common import build_derivative_prompt
from ..prompts.detail import build_detail_prompt
from .core import WorkflowContext

CORE_SEGMENTS = ("hero", "product", "benefits", "experience", "proof", "service")
EXTRA_SEGMENTS = ("brandStory", "dimensions", "comparison", "specTable", "craftProcess", "accessories", "seriesShowcase", "ingredients", "afterSales", "usageTips")
ALL_SEGMENTS = CORE_SEGMENTS + EXTRA_SEGMENTS


def _paths(values: list[str]) -> list[Path]:
    paths = [Path(value).expanduser().resolve() for value in values]
    for path in paths:
        if not path.is_file():
            raise FileNotFoundError(f"detail reference image not found: {path}")
    return paths


def _parse_json_object(raw: str) -> dict[str, Any]:
    clean = raw.strip()
    if clean.startswith("```"):
        clean = clean.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    parsed = json.loads(clean)
    if not isinstance(parsed, dict):
        raise ValueError("text response must be a JSON object")
    return parsed


def create_detail_project(request: dict[str, Any], context: WorkflowContext) -> TaskManifest:
    name = str(request.get("name", "")).strip()
    if not name:
        raise ValueError("detail project name is required")
    references = _paths(list(request.get("references", [])))
    segment_order = list(request.get("segments", CORE_SEGMENTS))
    if not segment_order or any(segment not in ALL_SEGMENTS for segment in segment_order):
        raise ValueError("detail segments contain an unsupported module")
    project = {
        "name": name,
        "facts": dict(request.get("facts", {})),
        "references": [str(path) for path in references],
        "creative_direction": str(request.get("creative_direction", "")),
        "copy": dict(request.get("copy", {})),
        "segment_order": segment_order,
        "segments": {},
    }
    return context.store.create("detail", {"project": project})


def generate_detail_copy(task_id: str, context: WorkflowContext) -> TaskManifest:
    manifest = context.store.load(task_id)
    project = manifest.request["project"]
    instructions = "为京东商品详情页生成严格 JSON 文案；只使用已确认事实，不虚构参数、认证或功效。"
    input_text = json.dumps({"facts": project["facts"], "segments": project["segment_order"], "creative_direction": project["creative_direction"]}, ensure_ascii=False)
    manifest.status = "running"
    manifest.text_requests += 1
    context.store.save(manifest)
    try:
        generated = _parse_json_object(context.client.generate_text(instructions=instructions, input_text=input_text))
        current = dict(project.get("copy", {}))
        for segment, copy in generated.items():
            if segment in project["segment_order"] and segment not in current:
                current[segment] = copy
        project["copy"] = current
        manifest.request["project"] = project
        manifest.status = "succeeded"
        context.store.save(manifest)
        return manifest
    except Exception as error:
        manifest.status = "failed"
        manifest.errors.append(str(error)[:500])
        context.store.save(manifest)
        raise


def _generate_segment(manifest: TaskManifest, segment: str, context: WorkflowContext, *, derivative: str | None = None) -> OutputAsset:
    project = manifest.request["project"]
    state = project["segments"].setdefault(segment, {"current_revision": 0, "versions": []})
    revision = len(state["versions"]) + 1
    references = _paths(project["references"])
    if derivative is None:
        prompt = build_detail_prompt(
            segment=segment,
            facts=project["facts"],
            copy=project.get("copy", {}).get(segment, {}),
            creative_direction=project["creative_direction"],
            width=750,
            height=1125,
        )
    else:
        prompt = build_derivative_prompt(derivative, aspect_ratio="2:3")
        current = next((item for item in state["versions"] if item["revision"] == state["current_revision"]), None)
        if current is None:
            raise ValueError(f"segment has no current revision: {segment}")
        references = [context.store.directory(manifest.id) / current["path"]]
    data = context.client.edit_image(prompt=prompt, images=references, size="1024x1536") if references else context.client.generate_image(prompt=prompt, size="1024x1536")
    task_dir = context.store.directory(manifest.id)
    raw = task_dir / "outputs" / f"{segment}-r{revision}-source.png"
    final = task_dir / "outputs" / f"{segment}-r{revision}.jpg"
    bytes_to_image_file(data, raw)
    resize_for_ratio(raw, final, ratio="2:3", max_dimension=1125)
    raw.unlink(missing_ok=True)
    version = {"revision": revision, "path": f"outputs/{segment}-r{revision}.jpg", "prompt": prompt}
    state["versions"].append(version)
    state["current_revision"] = revision
    return OutputAsset(id=f"{segment}-r{revision}", kind=segment, status="succeeded", path=version["path"], prompt=prompt, width=750, height=1125, revision=revision)


def generate_detail_segments(task_id: str, segments: list[str], context: WorkflowContext) -> TaskManifest:
    manifest = context.store.load(task_id)
    project = manifest.request["project"]
    selected = segments or list(project["segment_order"])
    if any(segment not in project["segment_order"] for segment in selected):
        raise ValueError("requested segment is not enabled for this project")
    manifest.status = "running"
    manifest.image_requests += len(selected)
    context.store.save(manifest)
    failures = 0
    for segment in selected:
        try:
            manifest.assets.append(_generate_segment(manifest, segment, context))
        except Exception as error:
            failures += 1
            manifest.assets.append(OutputAsset(id=f"{segment}-failed", kind=segment, status="failed", error=str(error)[:500]))
    manifest.request["project"] = project
    successes = len(selected) - failures
    manifest.status = "succeeded" if failures == 0 else "partial" if successes else "failed"
    context.store.save(manifest)
    return manifest


def derive_detail_segment(task_id: str, segment: str, instruction: str, context: WorkflowContext) -> TaskManifest:
    manifest = context.store.load(task_id)
    manifest.status = "running"
    manifest.image_requests += 1
    context.store.save(manifest)
    try:
        manifest.assets.append(_generate_segment(manifest, segment, context, derivative=instruction))
        manifest.status = "succeeded"
        context.store.save(manifest)
        return manifest
    except Exception as error:
        manifest.status = "failed"
        manifest.errors.append(str(error)[:500])
        context.store.save(manifest)
        raise


def restore_detail_revision(task_id: str, segment: str, revision: int, context: WorkflowContext) -> TaskManifest:
    manifest = context.store.load(task_id)
    state = manifest.request["project"]["segments"].get(segment)
    if state is None or not any(item["revision"] == revision for item in state["versions"]):
        raise ValueError("detail revision not found")
    state["current_revision"] = revision
    context.store.save(manifest)
    return manifest


def export_detail(task_id: str, context: WorkflowContext) -> TaskManifest:
    manifest = context.store.load(task_id)
    project = manifest.request["project"]
    sources: list[Path] = []
    for segment in project["segment_order"]:
        state = project["segments"].get(segment)
        if not state:
            continue
        current = next((item for item in state["versions"] if item["revision"] == state["current_revision"]), None)
        if current:
            sources.append(context.store.directory(task_id) / current["path"])
    if not sources:
        raise ValueError("detail project has no generated segments")
    relative = "outputs/detail-export.jpg"
    concatenate_vertical(sources, context.store.directory(task_id) / relative)
    manifest.assets = [asset for asset in manifest.assets if asset.kind != "detail-export"]
    manifest.assets.append(OutputAsset(id="detail-export", kind="detail-export", status="succeeded", path=relative))
    manifest.status = "succeeded"
    context.store.save(manifest)
    return manifest


def run_detail(request: dict[str, Any], context: WorkflowContext) -> TaskManifest:
    action = str(request.get("action", "create"))
    if action == "create":
        return create_detail_project(request, context)
    task_id = str(request.get("task_id", ""))
    if not task_id:
        raise ValueError("task_id is required")
    if action == "copy":
        return generate_detail_copy(task_id, context)
    if action == "generate":
        return generate_detail_segments(task_id, list(request.get("segments", [])), context)
    if action == "derive":
        return derive_detail_segment(task_id, str(request.get("segment", "")), str(request.get("instruction", "")), context)
    if action == "restore":
        return restore_detail_revision(task_id, str(request.get("segment", "")), int(request.get("revision", 0)), context)
    if action == "export":
        return export_detail(task_id, context)
    raise ValueError(f"unsupported detail action: {action}")
