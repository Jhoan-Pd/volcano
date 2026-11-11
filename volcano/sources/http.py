"""HTTP GET with retries, shared by the sources that call public JSON APIs.

Retries on network errors, 5xx and 429 with a linear back-off; a 4xx other than 429 is a client
error and is not retried. An injected `httpx.Client` lets tests replace the network.
"""
import time
from typing import Any

import httpx

from volcano.sources.base import DataSourceError


def get_json(url: str, params: dict[str, Any], *, client: httpx.Client | None = None, timeout: float = 20.0,
             headers: dict[str, str] | None = None, retries: int = 2, backoff_s: float = 0.8,
             source: str = "source") -> Any:
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            if client is not None:
                resp = client.get(url, params=params, headers=headers)
            else:
                with httpx.Client(timeout=timeout) as c:
                    resp = c.get(url, params=params, headers=headers)
            if resp.status_code == 200:
                return resp.json()
            last_error = DataSourceError(f"HTTP {resp.status_code}: {resp.text[:200]}")
            if resp.status_code < 500 and resp.status_code != 429:
                break  # client error: retrying will not help
        except (httpx.HTTPError, ValueError) as exc:
            last_error = exc
        if attempt < retries:
            time.sleep(backoff_s * (attempt + 1))
    raise DataSourceError(f"{source} did not answer: {last_error}")
