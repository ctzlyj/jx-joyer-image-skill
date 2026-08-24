from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from ..images import bytes_to_image_file
from ..models import OutputAsset, TaskManifest
from ..prompts.common import build_derivative_prompt
from ..storage import TaskStore


class ModelClient(Protocol):
    def generate_text(self, *, instructions: str, input_text: str) -> str: ...
    def generate_image(self, *, prompt: str, size: str) -> bytes: ...
    def edit_image(self, *, prompt: str, images: list[Path], size: str) -> bytes: ...


@dataclass
class WorkflowContext:
    client: ModelClient
    store: TaskStore


def _references(values: list[str]) -> list[Path]:
    references = [Path(value).expanduser().resolve() for value in values]
    for reference in references:
        if not reference.is_file():
            raise FileNotFoundError(f"reference image not found: {reference}")
    return references


def _save_image(manifest: TaskManifest, context: WorkflowContext, data: bytes, *, name: str, prompt: str, kind: str) -> TaskManifest:
    task_dir = context.store.directory(manifest.id)
    relative = f"outputs/{name}.png"
    bytes_to_image_file(data, task_dir / relative)
    manifest.assets.append(OutputAsset(id=name, kind=kind, status="succeeded", path=relative, prompt=prompt))
    manifest.status = "succeeded"
    context.store.save(manifest)
    return manifest


def _fail(manifest: TaskManifest, context: WorkflowContext, error: Exception) -> None:
    manifest.status = "failed"
    manifest.errors.append(str(error)[:500])
    context.store.save(manifest)


def run_copy(request: dict[str, Any], context: WorkflowContext) -> TaskManifest:
    manifest = context.store.create("copy", {"instructions": str(request.get("instructions", "")), "input": str(request.get("input", ""))})
    manifest.status = "running"
    manifest.text_requests = 1
    context.store.save(manifest)
    try:
        result = context.client.generate_text(instructions=manifest.request["instructions"], input_text=manifest.request["input"])
        manifest.request["result"] = result
        manifest.status = "succeeded"
        context.store.save(manifest)
        return manifest
    except Exception as error:
        _fail(manifest, context, error)
        raise


def run_generate(request: dict[str, Any], context: WorkflowContext) -> TaskManifest:
    prompt = str(request.get("prompt", "")).strip()
    if not prompt:
        raise ValueError("prompt is required")
    size = str(request.get("size", "1024x1024"))
    manifest = context.store.create("generate", {"prompt": prompt, "size": size})
    manifest.status = "running"
    manifest.image_requests = 1
    context.store.save(manifest)
    try:
        data = context.client.generate_image(prompt=prompt, size=size)
        return _save_image(manifest, context, data, name="generated-1", prompt=prompt, kind="generated")
    except Exception as error:
        _fail(manifest, context, error)
        raise


def run_edit(request: dict[str, Any], context: WorkflowContext) -> TaskManifest:
    prompt = str(request.get("prompt", "")).strip()
    if not prompt:
        raise ValueError("prompt is required")
    references = _references(list(request.get("references", [])))
    if not references:
        raise ValueError("at least one reference image is required")
    size = str(request.get("size", "1024x1024"))
    manifest = context.store.create("edit", {"prompt": prompt, "references": [str(path) for path in references], "size": size})
    manifest.status = "running"
    manifest.image_requests = 1
    context.store.save(manifest)
    try:
        data = context.client.edit_image(prompt=prompt, images=references, size=size)
        return _save_image(manifest, context, data, name="edited-1", prompt=prompt, kind="edited")
    except Exception as error:
        _fail(manifest, context, error)
        raise


def run_derive(request: dict[str, Any], context: WorkflowContext) -> TaskManifest:
    source = Path(str(request.get("source", ""))).expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(f"source image not found: {source}")
    instruction = str(request.get("instruction", "")).strip()
    aspect_ratio = str(request.get("aspect_ratio", "1:1"))
    prompt = build_derivative_prompt(instruction, aspect_ratio=aspect_ratio)
    size = str(request.get("size", "1024x1024"))
    manifest = context.store.create("derive", {"source": str(source), "instruction": instruction, "aspect_ratio": aspect_ratio, "size": size})
    manifest.status = "running"
    manifest.image_requests = 1
    context.store.save(manifest)
    try:
        data = context.client.edit_image(prompt=prompt, images=[source], size=size)
        return _save_image(manifest, context, data, name="derived-1", prompt=prompt, kind="derived")
    except Exception as error:
        _fail(manifest, context, error)
        raise

