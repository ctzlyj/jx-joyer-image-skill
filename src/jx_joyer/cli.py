from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
from typing import Any, Sequence

from .client import OxygenClient
from .prompts.ecommerce import missing_copy_fields
from .storage import TaskStore
from .workflows.core import WorkflowContext, run_copy, run_derive, run_edit, run_generate


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="jx-joyer", description="JD Oxygen ecommerce image workflows")
    parser.add_argument("--output-dir", default="jx-joyer-output")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("doctor", help="Check local readiness without a model call")

    estimate = subparsers.add_parser("estimate", help="Estimate model request counts without a model call")
    estimate.add_argument("--task-file", required=True)

    copy = subparsers.add_parser("copy", help="Generate structured product copy")
    copy.add_argument("--instructions", default="Return concise structured JSON")
    copy.add_argument("--input", required=True)
    copy.add_argument("--yes", action="store_true")

    generate = subparsers.add_parser("generate", help="Generate an image without references")
    generate.add_argument("--prompt", required=True)
    generate.add_argument("--size", default="1024x1024")
    generate.add_argument("--yes", action="store_true")

    edit = subparsers.add_parser("edit", help="Edit using one or more reference images")
    edit.add_argument("--prompt", required=True)
    edit.add_argument("--reference", action="append", required=True)
    edit.add_argument("--size", default="1024x1024")
    edit.add_argument("--yes", action="store_true")

    derive = subparsers.add_parser("derive", help="Apply a follow-up edit to an existing image")
    derive.add_argument("--source", required=True)
    derive.add_argument("--instruction", required=True)
    derive.add_argument("--aspect-ratio", default="1:1")
    derive.add_argument("--size", default="1024x1024")
    derive.add_argument("--yes", action="store_true")

    ecommerce = subparsers.add_parser("ecommerce", help="Generate or revise an ecommerce image set")
    ecommerce.add_argument("--task-file")
    ecommerce.add_argument("--retry")
    ecommerce.add_argument("--asset", action="append", default=[])
    ecommerce.add_argument("--derive")
    ecommerce.add_argument("--instruction")
    ecommerce.add_argument("--yes", action="store_true")

    workbench = subparsers.add_parser("workbench", help="Run free-form generation plans")
    workbench.add_argument("--task-file", required=True)
    workbench.add_argument("--yes", action="store_true")

    batch_edit = subparsers.add_parser("batch-edit", help="Edit multiple source images")
    batch_edit.add_argument("--task-file")
    batch_edit.add_argument("--retry")
    batch_edit.add_argument("--asset", action="append", default=[])
    batch_edit.add_argument("--yes", action="store_true")

    detail = subparsers.add_parser("detail", help="Create and generate product detail sections")
    detail.add_argument("--task-file", required=True)
    detail.add_argument("--yes", action="store_true")

    replica = subparsers.add_parser("replica", help="Analyze and recreate hit-image templates")
    replica.add_argument("--task-file", required=True)
    replica.add_argument("--yes", action="store_true")

    history = subparsers.add_parser("history", help="List local task history")
    history.add_argument("--kind")
    history.add_argument("--limit", type=int, default=20)
    return parser


def _emit(payload: object, *, stream=None) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2, default=str), file=stream or sys.stdout)


def _read_task(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("task file must contain a JSON object")
    return payload


def _workflow_payload(payload: dict[str, Any], expected: str) -> dict[str, Any]:
    workflow = payload.get("workflow")
    if workflow is not None and workflow != expected:
        raise ValueError(f"task workflow must be {expected}")
    return {key: value for key, value in payload.items() if key != "workflow"}


def estimate_task(payload: dict[str, Any], store: TaskStore | None = None) -> dict[str, Any]:
    workflow = str(payload.get("workflow", ""))
    text_requests = 0
    image_requests = 0
    if workflow == "ecommerce":
        image_requests = len(payload.get("image_types", ["main", "scene"]))
        copy = payload.get("product_copy", {})
        missing = missing_copy_fields(
            selected=list(payload.get("copy_fields", [])),
            selling_points=list(copy.get("selling_points", ["", "", ""])),
            long_title=str(copy.get("long_title", "")),
            short_title=str(copy.get("short_title", "")),
        )
        text_requests = 1 if missing else 0
    elif workflow == "workbench":
        if payload.get("reference_mode") == "per-image":
            image_requests = len(payload.get("references", []))
        elif payload.get("prompt_mode") == "queue":
            image_requests = len([part for part in str(payload.get("prompt", "")).replace("\r\n", "\n").split("\n---\n") if part.strip()])
        else:
            image_requests = max(1, min(int(payload.get("count", 1)), 10))
    elif workflow == "batch-edit":
        image_requests = len(payload.get("sources", []))
    elif workflow == "detail":
        action = payload.get("action", "create")
        text_requests = 1 if action == "copy" else 0
        image_requests = len(payload.get("segments", [])) or (6 if action == "generate" else 1 if action == "derive" else 0)
    elif workflow == "replica":
        action = payload.get("action", "analyze")
        text_requests = 1 if action in {"analyze", "copy"} else 0
        image_requests = len(payload.get("slice_ids", [])) if action == "generate" else 0
        if action == "generate" and image_requests == 0 and store is not None and payload.get("task_id"):
            manifest = store.load(str(payload["task_id"]))
            image_requests = len(manifest.request["project"].get("slices", []))
    else:
        raise ValueError("task file workflow must be ecommerce, workbench, batch-edit, detail, or replica")
    return {"workflow": workflow, "text_requests": text_requests, "image_requests": image_requests}


def _requires_model(command: str, payload: dict[str, Any] | None) -> bool:
    if command == "detail":
        return str((payload or {}).get("action", "create")) in {"copy", "generate", "derive"}
    if command == "replica":
        return str((payload or {}).get("action", "analyze")) in {"analyze", "copy", "generate"}
    return command not in {"doctor", "estimate", "history"}


class _NoModelClient:
    def __getattr__(self, name: str):
        raise RuntimeError(f"offline action unexpectedly requested model method: {name}")


def _dispatch(args, context: WorkflowContext, payload: dict[str, Any] | None):
    if args.command == "copy":
        return run_copy({"instructions": args.instructions, "input": args.input}, context)
    if args.command == "generate":
        return run_generate({"prompt": args.prompt, "size": args.size}, context)
    if args.command == "edit":
        return run_edit({"prompt": args.prompt, "references": args.reference, "size": args.size}, context)
    if args.command == "derive":
        return run_derive({"source": args.source, "instruction": args.instruction, "aspect_ratio": args.aspect_ratio, "size": args.size}, context)
    if args.command == "ecommerce":
        from .workflows.ecommerce import derive_ecommerce, retry_ecommerce, run_ecommerce
        if args.retry:
            return retry_ecommerce(args.retry, args.asset, context)
        if args.derive:
            if not args.instruction:
                raise ValueError("--instruction is required with --derive")
            return derive_ecommerce(args.derive, args.asset[0] if args.asset else "main", args.instruction, context)
        if payload is None:
            raise ValueError("ecommerce requires --task-file, --retry, or --derive")
        return run_ecommerce(_workflow_payload(payload, "ecommerce"), context)
    if args.command == "workbench":
        from .workflows.workbench import run_workbench
        return run_workbench(_workflow_payload(payload or {}, "workbench"), context)
    if args.command == "batch-edit":
        from .workflows.batch_edit import retry_batch_edit, run_batch_edit
        if args.retry:
            return retry_batch_edit(args.retry, args.asset, context)
        if payload is None:
            raise ValueError("batch-edit requires --task-file or --retry")
        return run_batch_edit(_workflow_payload(payload, "batch-edit"), context)
    if args.command == "detail":
        from .workflows.detail import run_detail
        return run_detail(_workflow_payload(payload or {}, "detail"), context)
    if args.command == "replica":
        from .workflows.replica import run_replica
        return run_replica(_workflow_payload(payload or {}, "replica"), context)
    raise ValueError(f"unsupported command: {args.command}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(list(argv) if argv is not None else None)
    except SystemExit as error:
        return int(error.code)
    store = TaskStore(Path(args.output_dir))
    if args.command == "doctor":
        _emit({"python": sys.version.split()[0], "key_present": bool(os.environ.get("JD_LLM_API_KEY", "").strip()), "gateway": "http://llm-gw.jd.local/v1", "live_request_performed": False})
        return 0
    if args.command == "history":
        _emit([item.model_dump(mode="json") for item in store.list(kind=args.kind, limit=args.limit)])
        return 0
    try:
        payload = _read_task(args.task_file) if getattr(args, "task_file", None) else None
        if args.command == "estimate":
            _emit(estimate_task(payload or {}, store))
            return 0
        requires_model = _requires_model(args.command, payload)
        if requires_model and not args.yes:
            print("This command performs a live Oxygen request. Rerun with --yes to execute.", file=sys.stderr)
            return 2
        if requires_model:
            with OxygenClient.from_environment() as client:
                manifest = _dispatch(args, WorkflowContext(client=client, store=store), payload)
        else:
            manifest = _dispatch(args, WorkflowContext(client=_NoModelClient(), store=store), payload)
        _emit(manifest.model_dump(mode="json"))
        return 0
    except Exception as error:
        _emit({"error": type(error).__name__, "message": str(error)}, stream=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
