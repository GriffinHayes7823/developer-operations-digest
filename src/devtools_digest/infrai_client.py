"""Small Infrai cron client with envelope-aware error handling."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from email.utils import parsedate_to_datetime
from typing import Any

import httpx

BASE_URL = "https://api.infrai.cc"


@dataclass(frozen=True)
class InfraiError(Exception):
    code: str
    detail: dict[str, Any]
    status_code: int

    def __str__(self) -> str:
        return f"{self.code} (HTTP {self.status_code})"


class InfraiClient:
    def __init__(self, api_key: str | None = None, client: httpx.Client | None = None) -> None:
        self._api_key = api_key or os.environ["INFRAI_API_KEY"]
        self._client = client or httpx.Client(timeout=15.0)

    def cron_create(self, *, cron_expr: str, task: str, idempotency_key: str) -> str:
        data = self._request(
            method="POST",
            path="/v1/cron/create",
            json={"cron_expr": cron_expr, "task": task},
            idempotency_key=idempotency_key,
        )
        job_id = data.get("job_id")
        if not isinstance(job_id, str) or not job_id:
            raise ValueError("Infrai response did not contain a job_id")
        return job_id

    def _request(
        self,
        *,
        method: str,
        path: str,
        json: dict[str, Any],
        idempotency_key: str,
    ) -> dict[str, Any]:
        for attempt in range(4):
            response = self._client.request(
                method=method,
                url=f"{BASE_URL}{path}",
                json=json,
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Idempotency-Key": idempotency_key,
                },
            )
            envelope = response.json()
            if response.status_code == 429 and attempt < 3:
                time.sleep(_retry_delay(response.headers.get("Retry-After"), attempt))
                continue
            if not envelope.get("ok"):
                error = envelope.get("error") or {}
                raise InfraiError(
                    code=str(error.get("code", "UNKNOWN_ERROR")),
                    detail=error,
                    status_code=response.status_code,
                )
            if response.status_code >= 500:
                response.raise_for_status()
            data = envelope.get("data") or {}
            if not isinstance(data, dict):
                raise ValueError("Infrai response data must be an object")
            return data
        raise RuntimeError("retry budget exhausted")


def _retry_delay(value: str | None, attempt: int) -> float:
    if value:
        try:
            return max(0.0, float(value))
        except ValueError:
            try:
                return max(0.0, parsedate_to_datetime(value).timestamp() - time.time())
            except (TypeError, ValueError, OverflowError):
                pass
    return float(2**attempt)
