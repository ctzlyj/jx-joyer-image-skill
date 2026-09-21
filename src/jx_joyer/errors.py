from __future__ import annotations


class OxygenApiError(RuntimeError):
    def __init__(self, *, status_code: int | None, category: str, detail: str, retryable: bool, attempt_count: int = 1) -> None:
        self.status_code = status_code
        self.category = category
        self.detail = detail[:500]
        self.retryable = retryable
        self.attempt_count = attempt_count
        prefix = f"HTTP {status_code}" if status_code is not None else "Oxygen request failed"
        super().__init__(f"{prefix} [{category}, attempts={attempt_count}]: {self.detail}")
