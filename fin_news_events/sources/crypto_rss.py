from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

from bs4 import BeautifulSoup

from fin_news_events.models import RawNewsItem
from fin_news_events.sources.base import (
    ConditionalHTTPClient,
    SourceFetchStats,
    extract_domain,
    make_item_id,
    parse_dt_safe,
)

CRYPTO_FEEDS = [
    ("CoinDesk", "coindesk_rss", "https://www.coindesk.com/arc/outboundfeeds/rss/", "1–5 min"),
    ("Cointelegraph", "cointelegraph_rss", "https://cointelegraph.com/rss", "1–5 min"),
    ("Decrypt", "decrypt_rss", "https://decrypt.co/feed", "2–10 min"),
    ("The Block", "theblock_rss", "https://www.theblock.co/rss.xml", "1–5 min"),
    ("Kraken Blog", "kraken_rss", "https://blog.kraken.com/feed", "5–30 min"),
]


def _clean(txt: str) -> str:
    if not txt:
        return ""
    s = BeautifulSoup(txt, "lxml").get_text(" ", strip=True)
    return re.sub(r"\s+", " ", s).strip()


def fetch_crypto_rss(
    client: ConditionalHTTPClient,
    start_dt: datetime,
    end_dt: datetime,
    conditional: bool = False,
) -> tuple[list[RawNewsItem], list[SourceFetchStats]]:
    all_items: list[RawNewsItem] = []
    stats: list[SourceFetchStats] = []
    for name, feed_id, url, lag_desc in CRYPTO_FEEDS:
        try:
            resp, dt_ms, not_modified = client.get(url, conditional=conditional)
            if not_modified:
                stats.append(
                    SourceFetchStats(
                        source_name=name,
                        status="NOT_MODIFIED",
                        http_code=304,
                        fetch_latency_ms=round(dt_ms, 1),
                        typical_update_lag_desc=lag_desc,
                        historical_window_desc="Latest ~20–40 items only (requires self-hosted archive)",
                    )
                )
                continue
            if resp.status_code != 200:
                stats.append(
                    SourceFetchStats(
                        source_name=name,
                        status="ERROR",
                        http_code=resp.status_code,
                        fetch_latency_ms=round(dt_ms, 1),
                    )
                )
                continue
            ingested_at = datetime.now(timezone.utc)
            root = ET.fromstring(resp.content)
            count = 0
            for el in root.findall(".//item"):
                title = _clean(el.findtext("title") or "")
                link = (el.findtext("link") or "").strip()
                pub_dt = parse_dt_safe(el.findtext("pubDate"))
                if not title or not pub_dt:
                    continue
                if pub_dt < start_dt or pub_dt > end_dt + timedelta(hours=12):
                    continue
                desc = _clean(el.findtext("description") or "")
                all_items.append(
                    RawNewsItem(
                        item_id=make_item_id(link, title),
                        title=title,
                        summary=desc[:500],
                        url=link,
                        source_name=name,
                        source_feed=feed_id,
                        source_domain=extract_domain(link),
                        published_at=pub_dt,
                        ingested_at=ingested_at,
                        fetch_latency_ms=round(dt_ms, 1),
                        retrieval_layer="CROSS_MARKET",
                        query_tag="crypto_specialized_rss",
                        is_primary_official=(name == "Kraken Blog"),
                    )
                )
                count += 1
            stats.append(
                SourceFetchStats(
                    source_name=name,
                    status="OK",
                    http_code=200,
                    items_fetched=count,
                    fetch_latency_ms=round(dt_ms, 1),
                    typical_update_lag_desc=lag_desc,
                    historical_window_desc="Latest ~20–40 items only (requires self-hosted archive)",
                )
            )
        except Exception as exc:
            stats.append(SourceFetchStats(source_name=name, status="ERROR", note=str(exc)))
    return all_items, stats
