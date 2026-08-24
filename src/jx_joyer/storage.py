from __future__ import annotations

import json
from pathlib import Path
import re
import shutil
from typing import Any

from .models import TaskManifest, utc_now


_SAFE_TASK_ID = re.compile(r"^[A-Za-z0-9._-]+$")


class TaskStore:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _task_dir(self, task_id: str) -> Path:
        if not _SAFE_TASK_ID.fullmatch(task_id):
            raise ValueError("invalid task id")
        path = (self.root / task_id).resolve()
        if path.parent != self.root:
            raise ValueError("invalid task id")
        return path

    def create(self, kind: str, request: dict[str, Any]) -> TaskManifest:
        manifest = TaskManifest(kind=kind, request=request)
        task_dir = self._task_dir(manifest.id)
        task_dir.mkdir(parents=False, exist_ok=False)
        (task_dir / "inputs").mkdir()
        (task_dir / "outputs").mkdir()
        (task_dir / "previews").mkdir()
        self.save(manifest)
        return manifest

    def load(self, task_id: str) -> TaskManifest:
        path = self._task_dir(task_id) / "manifest.json"
        if not path.is_file():
            raise FileNotFoundError(f"task not found: {task_id}")
        return TaskManifest.model_validate_json(path.read_text(encoding="utf-8"))

    def save(self, manifest: TaskManifest) -> None:
        task_dir = self._task_dir(manifest.id)
        task_dir.mkdir(parents=True, exist_ok=True)
        manifest.updated_at = utc_now()
        target = task_dir / "manifest.json"
        temporary = task_dir / "manifest.json.tmp"
        temporary.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
        temporary.replace(target)

    def list(self, *, kind: str | None = None, limit: int = 20) -> list[TaskManifest]:
        if limit < 1:
            return []
        manifests: list[TaskManifest] = []
        for path in self.root.glob("*/manifest.json"):
            try:
                manifest = TaskManifest.model_validate_json(path.read_text(encoding="utf-8"))
            except (ValueError, OSError):
                continue
            if kind is None or manifest.kind == kind:
                manifests.append(manifest)
        manifests.sort(key=lambda item: (item.created_at, item.id), reverse=True)
        return manifests[:limit]

    def delete(self, task_id: str) -> None:
        task_dir = self._task_dir(task_id)
        if task_dir.exists():
            shutil.rmtree(task_dir)

    def directory(self, task_id: str) -> Path:
        path = self._task_dir(task_id)
        if not path.is_dir():
            raise FileNotFoundError(f"task not found: {task_id}")
        return path
