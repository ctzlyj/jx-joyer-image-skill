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
    assert payload == {"model": "GPT-Image-2.5-Flare-joybuilder", "prompt": "商品主图", "size": "1024x1024"}


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
    assert payload["model"] == "GPT-Image-2.5-Flare-joybuilder"
    # GPT-Image-2.5 系列按请求尺寸透传，不做就近映射
    assert payload["size"] == "1152x1536"
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
    assert "response content omitted" in message


def test_generate_image_primary_passes_requested_size() -> None:
    requests = []
    expected = b"flare-bytes"

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        requests.append(payload)
        return httpx.Response(200, request=request, json={"data": [{"b64_json": base64.b64encode(expected).decode()}]})

    client = make_client(handler)
    try:
        assert client.generate_image(prompt="商品主图", size="2880x2880") == expected
        assert client.last_image_model == "GPT-Image-2.5-Flare-joybuilder"
    finally:
        client.close()
    # 主模型 GPT-Image-2.5-Flare；4K 尺寸原样透传
    assert requests == [{"model": "GPT-Image-2.5-Flare-joybuilder", "prompt": "商品主图", "size": "2880x2880"}]


def test_generate_image_falls_back_to_sunburst_on_quota_and_keeps_requested_size() -> None:
    requests = []
    expected = b"sunburst-bytes"

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        requests.append(payload)
        if payload["model"] == "GPT-Image-2.5-Flare-joybuilder":
            return httpx.Response(403, request=request, json={"error": {"message": "个人本月预算总额已用尽"}})
        return httpx.Response(200, request=request, json={"data": [{"b64_json": base64.b64encode(expected).decode()}]})

    client = make_client(handler)
    try:
        assert client.generate_image(prompt="商品主图", size="2880x2880") == expected
        assert client.last_image_model == "GPT-Image-2.5-Sunburst-joybuilder"
    finally:
        client.close()
    assert [p["model"] for p in requests] == ["GPT-Image-2.5-Flare-joybuilder", "GPT-Image-2.5-Sunburst-joybuilder"]
    # GPT-Image-2.5 系列按请求尺寸透传，不做就近映射
    assert requests[0]["size"] == "2880x2880"
    assert requests[1]["size"] == "2880x2880"


def test_generate_image_falls_back_to_product_pro_maps_size_and_downloads_url(monkeypatch) -> None:
    models = []
    expected = b"cdn-image-bytes"
    generated_url = "https://img20.360buyimg.com/imgzone/test.png"
    sizes = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        models.append(payload["model"])
        sizes.append(payload["size"])
        if payload["model"] == "Oxygen-Product-Pro":
            return httpx.Response(200, request=request, json={"data": [{"url": generated_url}]})
        # 402/403 属额度/权限类不可重试错误，直接触发模型间降级
        if payload["model"] == "GPT-Image-2.5-Flare-joybuilder":
            return httpx.Response(402, request=request, json={"error": "quota"})
        return httpx.Response(403, request=request, json={"error": "permission"})

    downloads = []
    def fake_get(url, **kwargs):
        downloads.append((url, kwargs))
        return httpx.Response(200, content=expected)

    monkeypatch.setattr("jx_joyer.client.httpx.get", fake_get)
    client = make_client(handler)
    try:
        assert client.generate_image(prompt="场景图", size="2880x2880") == expected
        assert client.last_image_model == "Oxygen-Product-Pro"
    finally:
        client.close()
    assert models == ["GPT-Image-2.5-Flare-joybuilder", "GPT-Image-2.5-Sunburst-joybuilder", "Oxygen-Product-Pro"]
    # GPT 系列透传 4K；末位 Oxygen-Product-Pro 就近映射到实测可用尺寸
    assert sizes == ["2880x2880", "2880x2880", "1024x1024"]
    assert downloads[0][0] == generated_url
    # 下载 CDN 图片时不能携带网关 Authorization 头
    assert "Authorization" not in downloads[0][1].get("headers", {})


def test_generate_image_invalid_request_does_not_fallback() -> None:
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(json.loads(request.content)["model"])
        return httpx.Response(400, request=request, json={"error": "bad request"})

    client = make_client(handler)
    try:
        with pytest.raises(OxygenApiError):
            client.generate_image(prompt="x", size="1024x1024")
    finally:
        client.close()
    assert calls == ["GPT-Image-2.5-Flare-joybuilder"]


def test_edit_image_falls_back_to_sunburst(tmp_path: Path) -> None:
    source = tmp_path / "ref.png"
    source.write_bytes(b"ref")
    models = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        models.append(payload["model"])
        if payload["model"] == "GPT-Image-2.5-Flare-joybuilder":
            return httpx.Response(402, request=request, json={"error": "quota"})
        return httpx.Response(200, request=request, json={"data": [{"b64_json": base64.b64encode(b"edited").decode()}]})

    client = make_client(handler)
    try:
        assert client.edit_image(prompt="编辑", images=[source], size="1024x1024") == b"edited"
        assert client.last_image_model == "GPT-Image-2.5-Sunburst-joybuilder"
    finally:
        client.close()
    assert models == ["GPT-Image-2.5-Flare-joybuilder", "GPT-Image-2.5-Sunburst-joybuilder"]
