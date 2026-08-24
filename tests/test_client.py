import base64
import json
from pathlib import Path

import httpx
import pytest

from jx_joyer.client import OxygenClient
from jx_joyer.errors import OxygenApiError


def make_client(handler, *, sleeps=None) -> OxygenClient:
    recorded = sleeps if sleeps is not None else []
    return OxygenClient(
        api_key="test-key",
        transport=httpx.MockTransport(handler),
        sleep=recorded.append,
        random_value=lambda: 0.0,
    )


def test_generate_text_uses_responses_endpoint_and_fixed_model() -> None:
    requests = []
    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, request=request, json={"output": [{"content": [{"text": "文案"}]}]})
    client = make_client(handler)
    try:
        assert client.generate_text(instructions="系统", input_text="用户") == "文案"
    finally:
        client.close()
    payload = json.loads(requests[0].content)
    assert requests[0].url.path.endswith("/responses")
    assert payload == {"model": "GPT-5.6-Sol-joybuilder", "instructions": "系统", "input": "用户", "stream": False}


def test_generate_image_uses_generations_without_image_field() -> None:
    requests = []
    expected = b"generated"
    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, request=request, json={"data": [{"b64_json": base64.b64encode(expected).decode()}]})
    client = make_client(handler)
    try:
        assert client.generate_image(prompt="商品主图", size="1024x1024") == expected
    finally:
        client.close()
    payload = json.loads(requests[0].content)
    assert requests[0].url.path.endswith("/images/generations")
    assert payload == {"model": "GPT-image-2-joybuilder", "prompt": "商品主图", "size": "1024x1024"}


def test_edit_image_uses_edits_with_data_url_array(tmp_path: Path) -> None:
    requests = []
    source_a = tmp_path / "a.png"
    source_b = tmp_path / "b.jpg"
    source_a.write_bytes(b"png")
    source_b.write_bytes(b"jpg")
    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, request=request, json={"data": [{"b64Json": base64.b64encode(b"edited").decode()}]})
    client = make_client(handler)
    try:
        assert client.edit_image(prompt="编辑", images=[source_a, source_b], size="1152x1536") == b"edited"
    finally:
        client.close()
    payload = json.loads(requests[0].content)
    assert requests[0].url.path.endswith("/images/edits")
    assert len(payload["image"]) == 2
    assert payload["image"][0].startswith("data:image/png;base64,")
    assert payload["image"][1].startswith("data:image/jpeg;base64,")


def test_429_honors_retry_after() -> None:
    attempts = 0
    sleeps = []
    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(429, request=request, headers={"Retry-After": "2"}, json={"error": {"message": "busy"}})
        return httpx.Response(200, request=request, json={"output_text": "ok"})
    client = make_client(handler, sleeps=sleeps)
    try:
        assert client.generate_text(instructions="a", input_text="b") == "ok"
    finally:
        client.close()
    assert attempts == 2
    assert 2.0 in sleeps


def test_non_retryable_error_is_sanitized() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, request=request, json={"error": {"message": "invalid secret-key-value"}})
    client = make_client(handler)
    try:
        with pytest.raises(OxygenApiError) as caught:
            client.generate_text(instructions="a", input_text="b")
    finally:
        client.close()
    assert caught.value.status_code == 401
    assert "test-key" not in str(caught.value)
    assert "Bearer" not in str(caught.value)


def test_client_requires_environment_key(monkeypatch) -> None:
    monkeypatch.delenv("JD_LLM_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="JD_LLM_API_KEY"):
        OxygenClient.from_environment()


def test_error_redacts_runtime_key_and_data_url() -> None:
    secret = "runtime-secret-value-123456"
    encoded = "data:image/png;base64," + ("A" * 80)
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, request=request, json={"error": {"message": f"bad {secret} {encoded}"}})
    client = OxygenClient(api_key=secret, transport=httpx.MockTransport(handler), sleep=lambda _: None)
    try:
        with pytest.raises(OxygenApiError) as caught:
            client.generate_text(instructions="a", input_text="b")
    finally:
        client.close()
    message = str(caught.value)
    assert secret not in message
    assert "base64," not in message
    assert "[REDACTED]" in message
