from __future__ import annotations

import base64
from collections import deque
import json
import mimetypes
import os
from pathlib import Path
import random
import re
import threading
import time
from typing import Any, Callable

import httpx

from .constants import BASE_URL, IMAGE_CONCURRENCY, IMAGE_MODEL, IMAGE_STARTS_PER_SECOND, MAX_ATTEMPTS, TEXT_CONCURRENCY, TEXT_MODEL, TIMEOUT_SECONDS
from .errors import OxygenApiError


class SlidingWindowRateLimiter:
    def __init__(self, max_requests: int, period_seconds: float, *, sleep: Callable[[float], None], clock: Callable[[], float] = time.monotonic) -> None:
        self.max_requests = max_requests
        self.period_seconds = period_seconds
        self.sleep = sleep
        self.clock = clock
        self.starts: deque[float] = deque()
        self.lock = threading.Lock()

    def acquire(self) -> None:
        while True:
            with self.lock:
                now = self.clock()
                cutoff = now - self.period_seconds
                while self.starts and self.starts[0] <= cutoff:
                    self.starts.popleft()
                if len(self.starts) < self.max_requests:
                    self.starts.append(now)
                    return
                delay = max(self.starts[0] + self.period_seconds - now, 0.001)
            self.sleep(delay)


def _error_detail(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return (response.text or response.reason_phrase)[:500]
    if isinstance(payload, dict):
        error = payload.get("error")
        if isinstance(error, dict) and error.get("message"):
            return str(error["message"])[:500]
        if payload.get("message"):
            return str(payload["message"])[:500]
    return (response.text or response.reason_phrase)[:500]


def _mime_type(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in {".jpg", ".jpeg"}:
        return "image/jpeg"
    if suffix == ".png":
        return "image/png"
    if suffix == ".webp":
        return "image/webp"
    guessed, _ = mimetypes.guess_type(path.name)
    return guessed or "application/octet-stream"


class OxygenClient:
    def __init__(
        self,
        api_key: str,
        *,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
        random_value: Callable[[], float] = random.random,
        timeout_seconds: float = TIMEOUT_SECONDS,
        max_attempts: int = MAX_ATTEMPTS,
    ) -> None:
        if not api_key.strip():
            raise ValueError("Oxygen API key is required")
        self._api_key = api_key.strip()
        self._sleep = sleep
        self._random = random_value
        self._max_attempts = max_attempts
        self._http = httpx.Client(
            base_url=BASE_URL.rstrip("/") + "/",
            timeout=timeout_seconds,
            follow_redirects=True,
            transport=transport,
            headers={"Authorization": f"Bearer {self._api_key}", "User-Agent": "jx-joyer-image-skill/0.1"},
        )
        self._text_semaphore = threading.BoundedSemaphore(TEXT_CONCURRENCY)
        self._image_semaphore = threading.BoundedSemaphore(IMAGE_CONCURRENCY)
        self._image_limiter = SlidingWindowRateLimiter(IMAGE_STARTS_PER_SECOND, 1.0, sleep=sleep)

    @classmethod
    def from_environment(cls, **kwargs: Any) -> "OxygenClient":
        api_key = os.environ.get("JD_LLM_API_KEY", "").strip()
        if not api_key:
            raise RuntimeError("Set JD_LLM_API_KEY in the process environment before running a model command")
        return cls(api_key, **kwargs)

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> "OxygenClient":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def _request(self, endpoint: str, payload: dict[str, Any], *, image: bool) -> dict[str, Any]:
        semaphore = self._image_semaphore if image else self._text_semaphore
        limiter = self._image_limiter if image else None
        retryable_statuses = {408, 409, 425, 429}
        last_error: OxygenApiError | None = None
        with semaphore:
            for attempt in range(1, self._max_attempts + 1):
                if limiter is not None:
                    limiter.acquire()
                try:
                    response = self._http.post(endpoint.lstrip("/"), json=payload)
                except httpx.TransportError as exc:
                    last_error = OxygenApiError(status_code=None, category="network", detail=str(exc), retryable=True)
                else:
                    retryable = response.status_code in retryable_statuses or response.status_code >= 500
                    if response.status_code < 400:
                        try:
                            parsed = response.json()
                        except ValueError as exc:
                            raise OxygenApiError(status_code=response.status_code, category="invalid_response", detail="response was not valid JSON", retryable=False) from exc
                        if not isinstance(parsed, dict):
                            raise OxygenApiError(status_code=response.status_code, category="invalid_response", detail="response JSON must be an object", retryable=False)
                        return parsed
                    category = "rate_limited" if response.status_code == 429 else "authentication" if response.status_code in {401, 403} else "upstream"
                    detail = _error_detail(response).replace(self._api_key, "[REDACTED]")
                    detail = re.sub(r"data:image/[^;]+;base64,[A-Za-z0-9+/=]+", "[REDACTED_DATA_URL]", detail)
                    error = OxygenApiError(status_code=response.status_code, category=category, detail=detail, retryable=retryable)
                    if not retryable:
                        raise error
                    last_error = error
                    retry_after = 0.0
                    if response.status_code == 429:
                        try:
                            retry_after = float(response.headers.get("Retry-After", "60"))
                        except ValueError:
                            retry_after = 60.0
                if attempt < self._max_attempts:
                    backoff = min(2 ** (attempt - 1) + self._random(), 10.0)
                    self._sleep(max(backoff, locals().get("retry_after", 0.0)))
            assert last_error is not None
            raise last_error

    def generate_text(self, *, instructions: str, input_text: str) -> str:
        payload = self._request("responses", {"model": TEXT_MODEL, "instructions": instructions, "input": input_text, "stream": False}, image=False)
        output_text = payload.get("output_text")
        if isinstance(output_text, str) and output_text.strip():
            return output_text.strip()
        parts: list[str] = []
        for item in payload.get("output", []):
            if not isinstance(item, dict):
                continue
            for content in item.get("content", []):
                if isinstance(content, dict) and isinstance(content.get("text"), str):
                    parts.append(content["text"])
        result = "\n".join(part.strip() for part in parts if part.strip())
        if not result:
            raise OxygenApiError(status_code=200, category="invalid_response", detail="text response did not contain output text", retryable=False)
        return result

    def generate_image(self, *, prompt: str, size: str) -> bytes:
        payload = self._request("images/generations", {"model": IMAGE_MODEL, "prompt": prompt, "size": size}, image=True)
        return self._decode_image(payload)

    def edit_image(self, *, prompt: str, images: list[Path], size: str) -> bytes:
        if not images:
            raise ValueError("at least one reference image is required for image editing")
        data_urls = []
        for path in images:
            source = Path(path)
            encoded = base64.b64encode(source.read_bytes()).decode("ascii")
            data_urls.append(f"data:{_mime_type(source)};base64,{encoded}")
        payload = self._request("images/edits", {"model": IMAGE_MODEL, "prompt": prompt, "size": size, "image": data_urls}, image=True)
        return self._decode_image(payload)

    @staticmethod
    def _decode_image(payload: dict[str, Any]) -> bytes:
        data = payload.get("data")
        if not isinstance(data, list) or not data or not isinstance(data[0], dict):
            raise OxygenApiError(status_code=200, category="invalid_response", detail="image response did not contain data[0]", retryable=False)
        encoded = data[0].get("b64_json") or data[0].get("b64Json")
        if not isinstance(encoded, str) or not encoded:
            raise OxygenApiError(status_code=200, category="invalid_response", detail="image response did not contain base64 image data", retryable=False)
        try:
            return base64.b64decode(encoded, validate=True)
        except ValueError as exc:
            raise OxygenApiError(status_code=200, category="invalid_response", detail="image response base64 was invalid", retryable=False) from exc
