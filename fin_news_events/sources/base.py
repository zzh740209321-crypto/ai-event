from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Optional
from urllib.parse import urlparse

import requests

from fin_news_events.models import RawNewsItem

DEFAULT_HEADERS = {
    "User-Agent": "FinNewsEventsMVP research@finnewsevents.org"
}


def make_item_id(url: str, title: str) -> str:
    base = (url or "").strip() or (title or "").strip().lower()
    return hashlib.sha256(base.encode("utf-8", errors="ignore")).hexdigest()[:16]


def parse_dt_safe(val: str | None) -> Optional[datetime]:
    if not val:
        return None
    s = val.strip()
    try:
        dt = parsedate_to_datetime(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        pass
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S.%fZ", "%Y%m%dT%H%M%SZ", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(s, fmt).replace(tzinfo=timezone.utc)
            return dt
        except Exception:
            continue
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def extract_domain(url: str) -> str:
    try:
        host = urlparse(url).netloc.lower()
        if host.startswith("www."):
            host = host[4:]
        return host or "unknown"
    except Exception:
        return "unknown"


@dataclass
class SourceFetchStats:
    source_name: str
    status: str  # "OK" | "NOT_MODIFIED" | "RATE_LIMITED" | "ERROR" | "DISABLED"
    http_code: Optional[int] = None
    items_fetched: int = 0
    fetch_latency_ms: float = 0.0
    typical_update_lag_desc: str = ""
    historical_window_desc: str = ""
    note: str = ""


class ConditionalHTTPClient:
    """HTTP client supporting ETag / Last-Modified conditional GET for low-latency polling."""

    def __init__(self, timeout: int = 12):
        self.session = requests.Session()
        self.session.headers.update(DEFAULT_HEADERS)
        self.timeout = timeout
        self._etags: dict[str, str] = {}
        self._last_modified: dict[str, str] = {}

    def get(self, url: str, params: dict | None = None, conditional: bool = False) -> tuple[Optional[requests.Response], float, bool]:
        req_headers = {}
        cache_key = url + (str(sorted(params.items())) if params else "")
        if conditional:
            if cache_key in self._etags:
                req_headers["If-None-Match"] = self._etags[cache_key]
            if cache_key in self._last_modified:
                req_headers["If-Modified-Since"] = self._last_modified[cache_key]
        t0 = time.perf_counter()
        resp = self.session.get(url, params=params, headers=req_headers, timeout=self.timeout)
        dt_ms = (time.perf_counter() - t0) * 1000.0
        if resp.status_code == 304:
            return resp, dt_ms, True
        if resp.status_code == 200:
            if "ETag" in resp.headers:
                self._etags[cache_key] = resp.headers["ETag"]
            if "Last-Modified" in resp.headers:
                self._last_modified[cache_key] = resp.headers["Last-Modified"]
        return resp, dt_ms, False
