import json

from jx_joyer.cli import main
from jx_joyer.storage import TaskStore
from jx_joyer.workflows.core import WorkflowContext
from jx_joyer.workflows.workbench import run_workbench
from test_workbench_recovery import PartialClient


def test_retry_cli_and_offline_export_history(tmp_path, monkeypatch, capsys):
    client = PartialClient()
    store = TaskStore(tmp_path)
    manifest = run_workbench({"prompt": "商品", "count": 2}, WorkflowContext(client, store))
    monkeypatch.delenv("JD_LLM_API_KEY", raising=False)

    def forbidden(*args, **kwargs):
        raise AssertionError("offline command must not initialize a model")

    monkeypatch.setattr("jx_joyer.cli.OxygenClient.from_environment", forbidden)
    prefix = ["--output-dir", str(tmp_path)]
    assert main([*prefix, "history", "--task", manifest.id]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "partial"
    assert main([*prefix, "export", "--task", manifest.id, "--asset", "image-1"]) == 0
    assert json.loads(capsys.readouterr().out)["archive"].endswith(".zip")
    assert main([*prefix, "workbench", "--retry", manifest.id]) == 2
    capsys.readouterr()

    class ClientContext:
        def __enter__(self):
            return client

        def __exit__(self, *args):
            return None

    monkeypatch.setattr("jx_joyer.cli.OxygenClient.from_environment", lambda: ClientContext())
    assert main([*prefix, "workbench", "--retry", manifest.id, "--asset", "image-2", "--yes"]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "succeeded"
    assert len(client.calls) == 3


def test_workbench_task_and_retry_are_mutually_exclusive(tmp_path):
    assert main(["--output-dir", str(tmp_path), "workbench", "--task-file", "unused.json", "--retry", "task-example"]) == 2
