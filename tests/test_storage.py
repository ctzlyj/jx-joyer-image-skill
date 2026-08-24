import json
from pathlib import Path

import pytest

from jx_joyer.storage import TaskStore


def test_task_store_writes_valid_manifest_without_credentials(tmp_path: Path) -> None:
    store = TaskStore(tmp_path)
    manifest = store.create("generate", {"prompt": "测试"})
    saved = json.loads((tmp_path / manifest.id / "manifest.json").read_text(encoding="utf-8"))
    assert saved["request"] == {"prompt": "测试"}
    assert "api_key" not in json.dumps(saved).lower()


def test_history_lists_newest_tasks_first(tmp_path: Path) -> None:
    store = TaskStore(tmp_path)
    first = store.create("generate", {"prompt": "一"})
    second = store.create("edit", {"prompt": "二"})
    assert [item.id for item in store.list()] == [second.id, first.id]


def test_store_rejects_path_traversal(tmp_path: Path) -> None:
    store = TaskStore(tmp_path)
    with pytest.raises(ValueError, match="task id"):
        store.load("../outside")
