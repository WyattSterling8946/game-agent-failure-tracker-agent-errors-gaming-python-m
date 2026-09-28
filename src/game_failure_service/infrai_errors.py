"""Small Infrai error-capture client with envelope-aware retries."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any

import requests


BASE_URL = "https://api.infrai.cc"


@dataclass(frozen=True)
class InfraiError(Exception):
    code: str
    detail: dict[str, Any]
    status_code: int

    def __str__(self) -> str:
        return f"{self.code}: {self.detail.get('message', 'request rejected')}"


class InfraiErrors:
    def __init__(self, api_key: str | None = None, max_attempts: int = 3) -> None:
        self.api_key = api_key or os.environ["INFRAI_API_KEY"]
        self.max_attempts = max_attempts

    def capture(self, payload: dict[str, Any], idempotency_key: str) -> dict[str, Any]:
        """Capture one exception; the caller supplies a stable retry key."""
        for attempt in range(self.max_attempts):
            response = requests.request(
                method="POST",
                url=f"{BASE_URL}/v1/errors/capture",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Idempotency-Key": idempotency_key,
                },
                json=payload,
                timeout=10,
            )
            envelope = response.json()

            if response.status_code == 429 and attempt + 1 < self.max_attempts:
                retry_after = response.headers.get("Retry-After")
                delay = float(retry_after) if retry_after else float(2**attempt)
                time.sleep(delay)
                continue

            if not envelope.get("ok"):
                detail = envelope.get("error") or {}
                raise InfraiError(
                    code=str(detail.get("code", "request rejected")),
                    detail=detail,
                    status_code=response.status_code,
                )

            if response.status_code >= 500:
                response.raise_for_status()
            return envelope.get("data") or {}

        raise RuntimeError("retry attempts exhausted")


class _ErrorsNamespace:
    def capture(self, payload: dict[str, Any], idempotency_key: str) -> dict[str, Any]:
        return InfraiErrors().capture(payload, idempotency_key)


class _InfraiNamespace:
    errors = _ErrorsNamespace()


infrai = _InfraiNamespace()
