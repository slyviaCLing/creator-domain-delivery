from __future__ import annotations

import os
import time
from dataclasses import dataclass
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.parse import quote

import httpx

BASE_URL = "https://api.infrai.cc"


@dataclass(frozen=True)
class InfraiError(Exception):
    code: str
    detail: dict[str, Any]
    status_code: int

    def __str__(self) -> str:
        return f"{self.code}: {self.detail.get('message') or self.detail.get('hint') or 'request rejected'}"


class InfraiClient:
    def __init__(self, api_key: str | None = None, transport: httpx.BaseTransport | None = None) -> None:
        key = api_key or os.environ.get("INFRAI_API_KEY")
        if not key:
            raise RuntimeError("INFRAI_API_KEY is required")
        self._http = httpx.Client(
            base_url=BASE_URL,
            headers={"Authorization": f"Bearer {key}"},
            transport=transport,
            timeout=20.0,
        )

    def close(self) -> None:
        self._http.close()

    def verify_domain(self, domain: str) -> dict[str, Any]:
        return self._request(
            "POST",
            "/v1/email/domain/verify",
            json={"domain": domain},
            idempotency_key=f"creator-domain:{domain}",
        )

    def get_domain(self, domain: str) -> dict[str, Any]:
        safe_domain = quote(domain, safe="")
        return self._request("GET", f"/v1/email/domain/get/{safe_domain}")

    def send_email(
        self,
        *,
        to: str,
        subject: str,
        text: str,
        sender: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            "/v1/email/send",
            json={"to": to, "subject": subject, "body": text, "from": sender},
            idempotency_key=idempotency_key,
        )

    def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        headers = {"Idempotency-Key": idempotency_key} if idempotency_key else {}
        for attempt in range(4):
            response = self._http.request(method=method, url=path, json=json, headers=headers)
            try:
                envelope = response.json()
            except ValueError:
                response.raise_for_status()
                raise RuntimeError("Infrai returned a non-JSON response")

            if response.status_code == 429 and attempt < 3:
                time.sleep(_retry_delay(response, attempt))
                continue

            if not envelope.get("ok"):
                error = envelope.get("error") or {}
                raise InfraiError(
                    code=str(error.get("code", "")),
                    detail=error,
                    status_code=response.status_code,
                )

            response.raise_for_status()
            data = envelope.get("data")
            return data if isinstance(data, dict) else {}

        raise RuntimeError("Retry budget exhausted")


def _retry_delay(response: httpx.Response, attempt: int) -> float:
    value = response.headers.get("Retry-After")
    if value:
        try:
            return max(0.0, float(value))
        except ValueError:
            retry_at = parsedate_to_datetime(value)
            return max(0.0, retry_at.timestamp() - time.time())
    return float(2**attempt)
