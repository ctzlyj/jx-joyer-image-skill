import json

from jx_joyer.cli import main


def test_help_lists_core_commands(capsys) -> None:
    assert main(["--help"]) == 0
    output = capsys.readouterr().out
    for command in ("doctor", "copy", "generate", "edit", "derive", "history"):
        assert command in output


def test_doctor_does_not_require_key_or_call_model(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.delenv("JD_LLM_API_KEY", raising=False)
    assert main(["--output-dir", str(tmp_path), "doctor"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["key_present"] is False
    assert payload["live_request_performed"] is False


def test_model_commands_require_explicit_yes(tmp_path, capsys) -> None:
    code = main(["--output-dir", str(tmp_path), "generate", "--prompt", "测试"])
    assert code == 2
    message = capsys.readouterr().err
    assert "--yes" in message
    assert "request count" not in message.lower()
    assert "user confirmation" not in message.lower()


def test_help_lists_business_commands(capsys) -> None:
    assert main(["--help"]) == 0
    output = capsys.readouterr().out
    for command in ("ecommerce", "workbench", "batch-edit", "detail", "replica"):
        assert command in output


def test_estimate_does_not_require_key(tmp_path, monkeypatch, capsys) -> None:
    task_file = tmp_path / "task.json"
    task_file.write_text(json.dumps({"workflow":"ecommerce","image_types":["main","scene"],"copy_fields":["shortTitle"],"product_copy":{"selling_points":["a","b","c"],"long_title":"x","short_title":""}}), encoding="utf-8")
    monkeypatch.delenv("JD_LLM_API_KEY", raising=False)
    assert main(["estimate", "--task-file", str(task_file)]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload == {"workflow":"ecommerce","text_requests":1,"image_requests":2}
