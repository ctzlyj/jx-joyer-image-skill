from pathlib import Path
from uuid import uuid4
from zipfile import ZipFile, ZIP_DEFLATED

from PIL import Image

from .storage import TaskStore


def export_task(store: TaskStore, task_id: str, asset_ids: list[str]) -> Path:
    manifest = store.load(task_id)
    selected = set(asset_ids) or {asset.id for asset in manifest.assets if asset.status == "succeeded" and asset.path}
    assets = [asset for asset in manifest.assets if asset.id in selected]
    if not assets or len(assets) != len(selected) or any(asset.status != "succeeded" or not asset.path for asset in assets):
        raise ValueError("select existing successful images for export")
    sources = [store.file_path(task_id, asset.path) for asset in assets]
    output_directory = store.file_path(task_id, "outputs")
    if any(not source.is_relative_to(output_directory) or source.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp"} for source in sources):
        raise ValueError("only task output images can be exported")
    if any(not source.is_file() for source in sources):
        raise FileNotFoundError("export image is missing; no model request was made")
    for source in sources:
        with Image.open(source) as image:
            image.verify()
    archive = store.file_path(task_id, f"exports/images-{uuid4().hex}.zip")
    archive.parent.mkdir(parents=True, exist_ok=True)
    try:
        with ZipFile(archive, "x", compression=ZIP_DEFLATED) as output:
            for index, source in enumerate(sources, 1):
                output.write(source, arcname=f"{index:03d}-{source.name}")
    except Exception:
        archive.unlink(missing_ok=True)
        raise
    return archive
