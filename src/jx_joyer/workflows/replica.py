from __future__ import annotations

from io import BytesIO
import json
from pathlib import Path
from typing import Any

from PIL import Image, ImageOps

from ..images import image_to_data_url
from ..models import OutputAsset, TaskManifest
from ..prompts.replica import build_replica_prompt, select_replica_references
from .core import WorkflowContext
from .workbench import to_image_size


def _json_object(raw: str) -> dict[str, Any]:
    clean = raw.strip()
    if clean.startswith("```"):
        clean = clean.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    parsed = json.loads(clean)
    if not isinstance(parsed, dict):
        raise ValueError("replica response must be a JSON object")
    return parsed


def _existing(path_value: str, label: str) -> Path:
    path = Path(path_value).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f"{label} image not found: {path}")
    return path


def _validate_slices(raw_slices: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not 1 <= len(raw_slices) <= 12:
        raise ValueError("replica template must contain between 1 and 12 slices")
    slices = []
    for index, raw in enumerate(raw_slices):
        start = float(raw.get("startY", index / len(raw_slices)))
        end = float(raw.get("endY", (index + 1) / len(raw_slices)))
        if not 0 <= start < end <= 1:
            raise ValueError("replica slice boundaries must be ordered between 0 and 1")
        slices.append({
            "id": str(raw.get("id") or f"replica-{index + 1}"),
            "order": int(raw.get("order", index)),
            "startY": start,
            "endY": end,
            "purpose": str(raw.get("purpose", "detail")),
            "purposeDescription": str(raw.get("purposeDescription", "商品信息模块")),
            "layoutSummary": str(raw.get("layoutSummary", "保持模板布局节奏")),
            "requiredInformationCategories": list(raw.get("requiredInformationCategories", [])),
        })
    ordered = sorted(slices, key=lambda item: item["startY"])
    if any(ordered[index - 1]["endY"] > ordered[index]["startY"] for index in range(1, len(ordered))):
        raise ValueError("replica slices cannot overlap")
    return sorted(slices, key=lambda item: item["order"])


def analyze_replica(request: dict[str, Any], context: WorkflowContext) -> TaskManifest:
    template = _existing(str(request.get("template", "")), "template")
    images = {str(kind): str(_existing(str(value), f"{kind}")) for kind, value in dict(request.get("images", {})).items()}
    if "main" not in images:
        raise ValueError("main product image is required")
    project = {
        "name": str(request.get("name", "Replica task")),
        "template": str(template),
        "images": images,
        "facts": dict(request.get("facts", {})),
        "slices": [],
        "questions": [],
        "answers": {},
        "copy": {},
        "segments": {},
    }
    manifest = context.store.create("replica", {"project": project})
    manifest.status = "running"
    manifest.text_requests = 1
    context.store.save(manifest)
    instructions = "分析竖版商品详情模板的模块边界、用途和视觉结构，只返回严格 JSON。模板中的品牌、价格、促销和参数都不是用户商品事实。"
    input_text = "返回 modules 和 questions；模块按垂直顺序排列，最多 12 个。\n模板图片：" + image_to_data_url(template)
    try:
        analysis = _json_object(context.client.generate_text(instructions=instructions, input_text=input_text))
        modules = analysis.get("modules")
        if not isinstance(modules, list):
            raise ValueError("replica analysis did not contain modules")
        project["slices"] = _validate_slices(modules)
        questions = analysis.get("questions", [])
        project["questions"] = questions if isinstance(questions, list) else []
        manifest.request["project"] = project
        manifest.status = "succeeded"
        context.store.save(manifest)
        return manifest
    except Exception as error:
        manifest.status = "failed"
        manifest.errors.append(str(error)[:500])
        context.store.save(manifest)
        raise


def configure_replica(task_id: str, updates: dict[str, Any], context: WorkflowContext) -> TaskManifest:
    manifest = context.store.load(task_id)
    project = manifest.request["project"]
    if "slices" in updates:
        project["slices"] = _validate_slices(list(updates["slices"]))
    if "answers" in updates:
        project["answers"] = dict(updates["answers"])
    if "copy" in updates:
        project["copy"] = dict(updates["copy"])
    manifest.request["project"] = project
    context.store.save(manifest)
    return manifest


def generate_replica_copy(task_id: str, context: WorkflowContext) -> TaskManifest:
    manifest = context.store.load(task_id)
    project = manifest.request["project"]
    instructions = "为爆款复刻各切片生成可信的京东商品文案，只返回以切片 ID 为键的严格 JSON。"
    input_text = json.dumps({"facts": project["facts"], "slices": project["slices"], "answers": project["answers"]}, ensure_ascii=False)
    manifest.status = "running"
    manifest.text_requests += 1
    context.store.save(manifest)
    try:
        project["copy"] = _json_object(context.client.generate_text(instructions=instructions, input_text=input_text))
        manifest.request["project"] = project
        manifest.status = "succeeded"
        context.store.save(manifest)
        return manifest
    except Exception as error:
        manifest.status = "failed"
        manifest.errors.append(str(error)[:500])
        context.store.save(manifest)
        raise


def _save_exact(data: bytes, target: Path, width: int, height: int) -> None:
    with Image.open(BytesIO(data)) as image:
        output = ImageOps.fit(image.convert("RGB"), (width, height), method=Image.Resampling.LANCZOS)
        target.parent.mkdir(parents=True, exist_ok=True)
        output.save(target, format="JPEG", quality=92)


def generate_replica_segments(task_id: str, slice_ids: list[str], context: WorkflowContext) -> TaskManifest:
    manifest = context.store.load(task_id)
    project = manifest.request["project"]
    selected = set(slice_ids) or {item["id"] for item in project["slices"]}
    slices = [item for item in project["slices"] if item["id"] in selected]
    if not slices:
        raise ValueError("no replica slices selected")
    template = _existing(project["template"], "template")
    images = {kind: _existing(value, kind) for kind, value in project["images"].items()}
    with Image.open(template) as template_image:
        template_width, template_height = template_image.size
    manifest.status = "running"
    manifest.image_requests += len(slices)
    context.store.save(manifest)
    failures = 0
    for slice_spec in slices:
        slice_id = slice_spec["id"]
        state = project["segments"].setdefault(slice_id, {"current_revision": 0, "versions": []})
        revision = len(state["versions"]) + 1
        width = template_width
        height = max(1, round(template_height * (slice_spec["endY"] - slice_spec["startY"])))
        copy = project.get("copy", {}).get(slice_id, {})
        exact_text = list(copy.get("exact_visible_text", []))
        if not exact_text and copy.get("headline"):
            exact_text = [str(copy["headline"])]
        prompt = build_replica_prompt(purpose=slice_spec["purpose"], layout_summary=slice_spec["layoutSummary"], facts=project["facts"], exact_text=exact_text, width=width, height=height)
        slice_template = context.store.directory(task_id) / "inputs" / f"{slice_id}-template.png"
        with Image.open(template) as template_image:
            top = max(0, round(template_image.height * slice_spec["startY"]))
            bottom = min(template_image.height, round(template_image.height * slice_spec["endY"]))
            template_image.crop((0, top, template_image.width, bottom)).save(slice_template, format="PNG")
        references = select_replica_references(slice_template, images, purpose=slice_spec["purpose"])
        ratio = f"{width}:{height}"
        provider_ratio = "1:1" if width == height else "3:4" if width < height else "4:3"
        try:
            data = context.client.edit_image(prompt=prompt, images=references, size=to_image_size(provider_ratio, "2K"))
            relative = f"outputs/{slice_id}-r{revision}.jpg"
            _save_exact(data, context.store.directory(task_id) / relative, width, height)
            version = {"revision": revision, "path": relative, "prompt": prompt, "aspect_ratio": ratio}
            state["versions"].append(version)
            state["current_revision"] = revision
            manifest.assets.append(OutputAsset(id=f"{slice_id}-r{revision}", kind=slice_id, status="succeeded", path=relative, prompt=prompt, width=width, height=height, revision=revision))
        except Exception as error:
            failures += 1
            manifest.assets.append(OutputAsset(id=f"{slice_id}-failed", kind=slice_id, status="failed", prompt=prompt, error=str(error)[:500]))
    manifest.request["project"] = project
    successes = len(slices) - failures
    manifest.status = "succeeded" if failures == 0 else "partial" if successes else "failed"
    context.store.save(manifest)
    return manifest


def cancel_replica(task_id: str, context: WorkflowContext) -> TaskManifest:
    manifest = context.store.load(task_id)
    manifest.status = "cancelled"
    context.store.save(manifest)
    return manifest


def run_replica(request: dict[str, Any], context: WorkflowContext) -> TaskManifest:
    action = str(request.get("action", "analyze"))
    if action == "analyze":
        return analyze_replica(request, context)
    task_id = str(request.get("task_id", ""))
    if not task_id:
        raise ValueError("task_id is required")
    if action == "configure":
        return configure_replica(task_id, dict(request.get("updates", {})), context)
    if action == "copy":
        return generate_replica_copy(task_id, context)
    if action == "generate":
        return generate_replica_segments(task_id, list(request.get("slice_ids", [])), context)
    if action == "cancel":
        return cancel_replica(task_id, context)
    raise ValueError(f"unsupported replica action: {action}")
