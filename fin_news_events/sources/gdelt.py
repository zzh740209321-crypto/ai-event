from __future__ import annotations

import time
from datetime import datetime, timezone

from fin_news_events.models import RawNewsItem
from fin_news_events.sources.base import (
    ConditionalHTTPClient,
    SourceFetchStats,
    extract_domain,
    make_item_id,
    parse_dt_safe,
)

GDELT_DOC_URL = "https://api.gdeltproject.org/api/v2/doc/doc"
_LAST_GDELT_CALL = 0.0


def fetch_gdelt_doc(
    client: ConditionalHTTPClient,
    query: str,
    retrieval_layer: str,
    query_tag: str,
    start_dt: datetime,
    end_dt: datetime,
    max_records: int = 50,
) -> tuple[list[RawNewsItem], SourceFetchStats]:
    """Query GDELT DOC 2.0 API (3-month rolling window, 1 req / 5s limit)."""
    global _LAST_GDELT_CALL
    now_mono = time.monotonic()
    wait = 5.2 - (now_mono - _LAST_GDELT_CALL)
    if wait > 0:
        time.sleep(wait)
    _LAST_GDELT_CALL = time.monotonic()

    params = {
        "query": f"{query} sourcelang:english",
        "mode": "ArtList",
        "maxrecords": str(max_records),
        "format": "json",
        "startdatetime": start_dt.astimezone(timezone.utc).strftime("%Y%m%d%H%M%S"),
        "enddatetime": end_dt.astimezone(timezone.utc).strftime("%Y%m%d%H%M%S"),
    }
    try:
        resp, dt_ms, _ = client.get(GDELT_DOC_URL, params=params, conditional=False)
        if resp.status_code == 429:
            return [], SourceFetchStats(
                source_name=f"GDELT_DOC[{query_tag}]",
                status="RATE_LIMITED",
                http_code=429,
                fetch_latency_ms=round(dt_ms, 1),
                typical_update_lag_desc="15 min",
                historical_window_desc="~3 months rolling (raw GDELT 2.0 files / BigQuery since 2015-02)",
                note="HTTP 429 rate-limited (shared IP 1 req/5s limit); gracefully skipped",
            )
        if resp.status_code != 200:
            return [], SourceFetchStats(
                source_name=f"GDELT_DOC[{query_tag}]",
                status="ERROR",
                http_code=resp.status_code,
                fetch_latency_ms=round(dt_ms, 1),
                note=resp.text[:120],
            )
        data = resp.json()
        ingested_at = datetime.now(timezone.utc)
        items: list[RawNewsItem] = []
        for art in data.get("articles", []):
            title = (art.get("title") or "").strip()
            url = (art.get("url") or "").strip()
            pub_dt = parse_dt_safe(art.get("seendate"))
            if not title or not url or not pub_dt:
                continue
            domain = art.get("domain") or extract_domain(url)
            items.append(
                RawNewsItem(
                    item_id=make_item_id(url, title),
                    title=title,
                    summary="",
                    url=url,
                    source_name=domain,
                    source_feed="gdelt_doc",
                    source_domain=domain,
                    published_at=pub_dt,
                    ingested_at=ingested_at,
                    fetch_latency_ms=round(dt_ms, 1),
                    retrieval_layer=retrieval_layer,
                    query_tag=query_tag,
                )
            )
        return items, SourceFetchStats(
            source_name=f"GDELT_DOC[{query_tag}]",
            status="OK",
            http_code=200,
            items_fetched=len(items),
            fetch_latency_ms=round(dt_ms, 1),
            typical_update_lag_desc="15 min",
            historical_window_desc="~3 months rolling (raw GDELT 2.0 / BigQuery since 2015-02)",
        )
    except Exception as exc:
        return [], SourceFetchStats(
            source_name=f"GDELT_DOC[{query_tag}]",
            status="ERROR",
            note=str(exc),
        )
