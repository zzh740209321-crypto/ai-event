from __future__ import annotations

import os
from datetime import datetime, timezone

from fin_news_events.models import RawNewsItem
from fin_news_events.sources.base import ConditionalHTTPClient, SourceFetchStats, extract_domain, make_item_id, parse_dt_safe


def fetch_cryptopanic_plugin(
    client: ConditionalHTTPClient,
    currencies: str,
    start_dt: datetime,
    end_dt: datetime,
) -> tuple[list[RawNewsItem], SourceFetchStats]:
    """Optional key-gated plugin for CryptoPanic API v1."""
    api_key = os.environ.get("CRYPTOPANIC_API_KEY", "").strip()
    if not api_key:
        return [], SourceFetchStats(
            source_name="CryptoPanic[OptionalPlugin]",
            status="DISABLED",
            typical_update_lag_desc="<1 min (paid/keyed)",
            historical_window_desc="API pagination window",
            note="CRYPTOPANIC_API_KEY not set; optional plugin skipped",
        )
    url = "https://cryptopanic.com/api/v1/posts/"
    params = {"auth_token": api_key, "currencies": currencies, "public": "true"}
    try:
        resp, dt_ms, _ = client.get(url, params=params)
        if resp.status_code != 200:
            return [], SourceFetchStats(source_name="CryptoPanic[OptionalPlugin]", status="ERROR", http_code=resp.status_code, fetch_latency_ms=round(dt_ms, 1))
        ingested_at = datetime.now(timezone.utc)
        items: list[RawNewsItem] = []
        for post in resp.json().get("results", []):
            title = (post.get("title") or "").strip()
            link = (post.get("url") or "").strip()
            pub_dt = parse_dt_safe(post.get("published_at"))
            if not title or not pub_dt or pub_dt < start_dt or pub_dt > end_dt:
                continue
            dom = post.get("domain") or extract_domain(link)
            items.append(
                RawNewsItem(
                    item_id=make_item_id(link, title),
                    title=title,
                    summary="",
                    url=link,
                    source_name=post.get("source", {}).get("title") or dom,
                    source_feed="cryptopanic_plugin",
                    source_domain=dom,
                    published_at=pub_dt,
                    ingested_at=ingested_at,
                    fetch_latency_ms=round(dt_ms, 1),
                    retrieval_layer="DIRECT",
                    query_tag="cryptopanic",
                )
            )
        return items, SourceFetchStats(source_name="CryptoPanic[OptionalPlugin]", status="OK", http_code=200, items_fetched=len(items), fetch_latency_ms=round(dt_ms, 1))
    except Exception as exc:
        return [], SourceFetchStats(source_name="CryptoPanic[OptionalPlugin]", status="ERROR", note=str(exc))
