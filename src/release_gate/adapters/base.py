"""Shared HTTP adapter with retries and UNKNOWN-friendly errors."""

from __future__ import annotations

import time
from typing import Any

import httpx

from release_gate.config import ApiConfig


class AdapterError(Exception):
    def __init__(self, message: str, *, transient: bool = False, status_code: int | None = None):
        super().__init__(message)
        self.transient = transient
        self.status_code = status_code


class HttpAdapter:
    name = "http"

    def __init__(self, config: ApiConfig, *, dry_run: bool = False):
        self.config = config
        self.dry_run = dry_run
        self._client: httpx.Client | None = None

    @property
    def configured(self) -> bool:
        return bool(self.config.base_url)

    def _auth(self) -> httpx.Auth | tuple[str, str] | None:
        if self.config.token:
            return None
        if self.config.username:
            return (self.config.username, self.config.password)
        return None

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json", "Content-Type": "application/json"}
        if self.config.token:
            headers["Authorization"] = f"Bearer {self.config.token}"
        return headers

    def client(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(
                base_url=self.config.base_url.rstrip("/"),
                headers=self._headers(),
                auth=self._auth(),
                timeout=self.config.timeout_seconds,
            )
        return self._client

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None

    def request(self, method: str, path: str, **kwargs: Any) -> Any:
        if not self.configured:
            raise AdapterError(f"{self.name} is not configured (missing BASE_URL)", transient=False)
        if self.dry_run and method.upper() in {"POST", "PUT", "DELETE"}:
            return {"dry_run": True, "method": method, "path": path, "kwargs": kwargs}

        last_error: Exception | None = None
        attempts = max(1, self.config.max_retries + 1)
        for attempt in range(attempts):
            try:
                response = self.client().request(method, path, **kwargs)
                if response.status_code >= 500:
                    raise AdapterError(
                        f"{self.name} {method} {path} -> {response.status_code}",
                        transient=True,
                        status_code=response.status_code,
                    )
                if response.status_code >= 400:
                    raise AdapterError(
                        f"{self.name} {method} {path} -> {response.status_code}: {response.text[:300]}",
                        transient=False,
                        status_code=response.status_code,
                    )
                if response.status_code == 204 or not response.content:
                    return None
                return response.json()
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                last_error = AdapterError(str(exc), transient=True)
            except AdapterError as exc:
                if not exc.transient:
                    raise
                last_error = exc
            if attempt + 1 < attempts:
                time.sleep(0.5 * (attempt + 1))
        raise last_error or AdapterError(f"{self.name} request failed", transient=True)
