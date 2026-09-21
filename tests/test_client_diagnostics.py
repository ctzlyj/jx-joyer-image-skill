import httpx
import pytest

from jx_joyer.client import OxygenClient
from jx_joyer.errors import OxygenApiError


@pytest.mark.parametrize("status,category,attempts", [(400, "invalid_request", 1), (401, "authentication", 1), (403, "permission", 1), (402, "quota", 1), (404, "model_unavailable", 1), (413, "invalid_request", 1), (504, "timeout", 4), (503, "upstream", 4)])
def test_http_classification_and_bounded_attempts(status, category, attempts):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(status, request=request, json={"error": {"message": "private upstream content"}})

    with OxygenClient("fake-test-key", transport=httpx.MockTransport(handler), sleep=lambda delay: None) as client:
        with pytest.raises(OxygenApiError) as caught:
            client.generate_text(instructions="test", input_text="test")
    assert len(calls) == attempts
    assert caught.value.category == category
    assert caught.value.attempt_count == attempts
    assert "private upstream content" not in str(caught.value)


def test_retry_after_does_not_leak_into_next_transport_failure():
    calls = []
    sleeps = []

    def handler(request):
        calls.append(request)
        if len(calls) == 1:
            return httpx.Response(429, headers={"Retry-After": "7"}, request=request)
        if len(calls) == 2:
            raise httpx.ReadTimeout("private timeout text", request=request)
        return httpx.Response(200, json={"output_text": "ok"}, request=request)

    with OxygenClient("fake-test-key", transport=httpx.MockTransport(handler), sleep=sleeps.append, random_value=lambda: 0) as client:
        assert client.generate_text(instructions="test", input_text="test") == "ok"
    assert sleeps == [7, 2]


def test_transport_exception_never_echoes_key_or_input():
    secret = "fake-runtime-key-for-test"

    def handler(request):
        raise httpx.ReadTimeout(secret + " private prompt", request=request)

    with OxygenClient(secret, transport=httpx.MockTransport(handler), sleep=lambda delay: None) as client:
        with pytest.raises(OxygenApiError) as caught:
            client.generate_text(instructions="test", input_text="test")
    assert caught.value.category == "timeout"
    assert caught.value.attempt_count == 4
    assert secret not in str(caught.value)
    assert "private prompt" not in str(caught.value)
