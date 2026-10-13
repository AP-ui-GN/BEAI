"""Shared HTTP client: timeout, bounded retries, per-host spacing, and a file cache.

RCSB asks callers to start at a handful of requests per second and to back off
on HTTP 429 (https://www.rcsb.org/docs/programmatic-access/web-apis-overview,
read 2026-10-13). UniProt does not publish a hard limit and says to honour
Retry-After. This client spaces requests to the same host at least 0.25 s apart
and retries at most three times.
"""

from __future__ import annotations

import hashlib
import json
import threading
import time
from pathlib import Path
from urllib.parse import urlparse

import httpx

from backend.app.core.errors import ExternalServiceError

_CACHE_TTL_SECONDS = 24 * 60 * 60
_MIN_INTERVAL_SECONDS = 0.25


class ExternalHttp:
    """Blocking client. Tests pass an httpx transport."""

    def __init__(self, cache_dir: Path, timeout: float = 20.0, transport: httpx.BaseTransport | None = None) -> None:
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._client = httpx.Client(
            transport=transport,
            timeout=timeout,
            follow_redirects=True,
            headers={"User-Agent": "BEAI/0.1 (local research)"},
        )
        self._lock = threading.Lock()
        self._next_allowed: dict[str, float] = {}

    def close(self) -> None:
        self._client.close()

    def get_bytes(self, url: str) -> bytes:
        cached = self._read_cache(url)
        if cached is not None:
            return cached
        body = self._request(url)
        self._write_cache(url, body)
        return body

    def get_json(self, url: str) -> dict:
        body = self.get_bytes(url)
        try:
            parsed = json.loads(body)
        except json.JSONDecodeError as exc:
            raise ExternalServiceError(f"{_host(url)} returned a response that was not JSON.") from exc
        if not isinstance(parsed, dict):
            raise ExternalServiceError(f"{_host(url)} returned JSON that was not an object.")
        return parsed

    def _request(self, url: str) -> bytes:
        last_status: int | None = None
        for attempt in range(3):
            self._throttle(url)
            try:
                response = self._client.get(url)
            except httpx.HTTPError as exc:
                last_status = None
                if attempt == 2:
                    name = exc.__class__.__name__
                    raise ExternalServiceError(f"The request to {_host(url)} failed ({name}).") from exc
                time.sleep(0.2 * (2**attempt))
                continue
            if response.status_code == 429 or response.status_code >= 500:
                last_status = response.status_code
                retry_after = response.headers.get("Retry-After")
                delay = float(retry_after) if retry_after and retry_after.isdigit() else 0.2 * (2**attempt)
                time.sleep(delay)
                continue
            if response.status_code >= 400:
                raise ExternalServiceError(f"{_host(url)} returned HTTP {response.status_code}.")
            return response.content
        status = last_status if last_status is not None else "unknown"
        raise ExternalServiceError(f"{_host(url)} failed after retries (last status {status}).")

    def _throttle(self, url: str) -> None:
        host = _host(url)
        with self._lock:
            wait = self._next_allowed.get(host, 0.0) - time.monotonic()
            self._next_allowed[host] = max(time.monotonic(), self._next_allowed.get(host, 0.0)) + _MIN_INTERVAL_SECONDS
        if wait > 0:
            time.sleep(wait)

    def _path(self, url: str) -> Path:
        digest = hashlib.sha256(url.encode("utf-8")).hexdigest()
        return self.cache_dir / digest

    def _read_cache(self, url: str) -> bytes | None:
        path = self._path(url)
        if not path.is_file():
            return None
        age = time.time() - path.stat().st_mtime
        if age > _CACHE_TTL_SECONDS:
            return None
        return path.read_bytes()

    def _write_cache(self, url: str, body: bytes) -> None:
        path = self._path(url)
        temporary = path.with_suffix(".tmp")
        temporary.write_bytes(body)
        temporary.replace(path)


def _host(url: str) -> str:
    return urlparse(url).netloc or "the external service"
