"""Small JSON-over-HTTP client with retries (standard library only)."""

from __future__ import annotations

import json
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from pathlib import Path

RETRY_STATUS = frozenset({429, 500, 502, 503, 504})
Transport = Callable[[str, dict, float], dict]


def ssl_context() -> ssl.SSLContext:
    """Verify TLS. python.org builds on macOS lack CA certificates, so use the
    system bundle when it exists. Verification is never disabled."""
    bundle = Path("/etc/ssl/cert.pem")
    if bundle.exists():
        return ssl.create_default_context(cafile=str(bundle))
    return ssl.create_default_context()


def urllib_transport(url: str, headers: dict, timeout: float) -> dict:
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(
        request, timeout=timeout, context=ssl_context()
    ) as resp:
        return json.load(resp)


def retry_after_seconds(err: urllib.error.HTTPError) -> float | None:
    """Seconds requested by a Retry-After header, if present and numeric."""
    value = err.headers.get("Retry-After") if err.headers else None
    try:
        return float(value) if value is not None else None
    except ValueError:
        return None


class Client:
    """GET JSON with retries for rate limits, server errors and network errors.

    Error messages contain the URL but never the request headers, so API keys
    passed in headers are not exposed.
    """

    def __init__(
        self,
        headers: dict | None = None,
        transport: Transport = urllib_transport,
        retries: int = 6,
        backoff: float = 5.0,
        timeout: float = 120.0,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.headers = headers or {}
        self.transport = transport
        self.retries = retries
        self.backoff = backoff
        self.timeout = timeout
        self.sleep = sleep
        self.requests_made = 0

    def get_json(self, url: str, params: dict | None = None) -> dict:
        if params:
            url = f"{url}?{urllib.parse.urlencode(params)}"
        last: Exception | None = None
        for attempt in range(self.retries):
            self.requests_made += 1
            try:
                return self.transport(url, self.headers, self.timeout)
            except urllib.error.HTTPError as err:
                if err.code not in RETRY_STATUS:
                    raise
                last = err
                wait = retry_after_seconds(err)
                self.sleep(wait if wait is not None else self.backoff * (attempt + 1))
            except (urllib.error.URLError, TimeoutError, ConnectionError) as err:
                last = err
                self.sleep(self.backoff * (attempt + 1))
        raise RuntimeError(f"Giving up on {url} after {self.retries} attempts: {last}")
