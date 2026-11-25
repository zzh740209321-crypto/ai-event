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

GNEWS_RSS_URL = "https://news.google.com/rss/search"

PUBLISHER_DOMAIN_MAP = {
    "reuters": "reuters.com",
    "associated press": "apnews.com",
    "ap news": "apnews.com",
    "cnbc": "cnbc.com",
    "bloomberg": "bloomberg.com",
    "the wall street journal": "wsj.com",
    "wall street journal": "wsj.com",
    "wsj": "wsj.com",
    "financial times": "ft.com",
    "the new york times": "nytimes.com",
    "new york times": "nytimes.com",
    "marketwatch": "marketwatch.com",
    "barron's": "barrons.com",
    "barrons": "barrons.com",
    "investopedia": "investopedia.com",
    "investor's business daily": "investors.com",
    "yahoo finance": "finance.yahoo.com",
    "nbc news": "nbcnews.com",
    "abc news": "abcnews.go.com",
    "bbc": "bbc.com",
    "bbc news": "bbc.com",
    "coindesk": "coindesk.com",
    "the block": "theblock.co",
    "cointelegraph": "cointelegraph.com",
    "decrypt": "decrypt.co",
    "the motley fool": "fool.com",
    "fortune": "fortune.com",
    "cnn": "cnn.com",
    "the washington post": "washingtonpost.com",
    "the hill": "thehill.com",
    "kiplinger": "kiplinger.com",
}


def _clean_html(raw: str) -> str:
    if not raw:
        return ""
    txt = BeautifulSoup(raw, "lxml").get_text(" ", strip=True)
    return re.sub(r"\s+", " ", txt).strip()


def _resolve_publisher_domain(publisher: str, publisher_url: str, link: str) -> str:
    domain = extract_domain(publisher_url) if publisher_url else extract_domain(link)
    if domain in ("unknown", "news.google.com", "") and publisher:
        mapped = PUBLISHER_DOMAIN_MAP.get(publisher.strip().lower())
        if mapped:
            return mapped
    return domain


def fetch_google_news_rss(
    client: ConditionalHTTPClient,
    query: str,
    retrieval_layer: str,
    query_tag: str,
    start_dt: datetime,
    end_dt: datetime,
    conditional: bool = False,
) -> tuple[list[RawNewsItem], SourceFetchStats]:
    """Fetch Google News RSS using after:/before: date bounds or when:Nd."""
    now = datetime.now(timezone.utc)
    span_days = max(1, int((end_dt - start_dt).total_seconds() // 86400) + 1)
    if (now - end_dt).total_seconds() > 3600 * 6 or span_days > 2:
        after_s = (start_dt - timedelta(days=1)).strftime("%Y-%m-%d")
        before_s = (end_dt + timedelta(days=1)).strftime("%Y-%m-%d")
        full_q = f"{query} after:{after_s} before:{before_s}"
    else:
        full_q = f"{query} when:1d"

    params = {"q": full_q, "hl": "en-US", "gl": "US", "ceid": "US:en"}
    items: list[RawNewsItem] = []
    try:
        resp, dt_ms, not_modified = client.get(GNEWS_RSS_URL, params=params, conditional=conditional)
        if not_modified:
            return [], SourceFetchStats(
                source_name=f"GoogleNewsRSS[{query_tag}]",
                status="NOT_MODIFIED",
                http_code=304,
                fetch_latency_ms=round(dt_ms, 1),
                typical_update_lag_desc="1–10 min",
                historical_window_desc="after:/before: supports months–years (older items may snap to 08:00 UTC)",
            )
        if resp.status_code != 200:
            return [], SourceFetchStats(
                source_name=f"GoogleNewsRSS[{query_tag}]",
                status="ERROR",
                http_code=resp.status_code,
                fetch_latency_ms=round(dt_ms, 1),
            )
        ingested_at = datetime.now(timezone.utc)
        root = ET.fromstring(resp.content)
        for el in root.findall(".//item"):
            raw_title = (el.findtext("title") or "").strip()
            link = (el.findtext("link") or "").strip()
            pub_dt = parse_dt_safe(el.findtext("pubDate"))
            if not raw_title or not pub_dt:
                continue
            if pub_dt < start_dt or pub_dt > end_dt + timedelta(hours=12):
                continue
            src_el = el.find("source")
            publisher = (src_el.text or "").strip() if src_el is not None and src_el.text else ""
            publisher_url = src_el.attrib.get("url", "") if src_el is not None else ""
            title = raw_title
            if publisher and title.endswith(f" - {publisher}"):
                title = title[: -(len(publisher) + 3)].strip()
            domain = _resolve_publisher_domain(publisher, publisher_url, link)
            desc = _clean_html(el.findtext("description") or "")
            items.append(
                RawNewsItem(
                    item_id=make_item_id(link, title),
                    title=title,
                    summary=desc[:500],
                    url=link,
                    source_name=publisher or domain or "Google News",
                    source_feed="google_news_rss",
                    source_domain=domain,
                    published_at=pub_dt,
                    ingested_at=ingested_at,
                    fetch_latency_ms=round(dt_ms, 1),
                    retrieval_layer=retrieval_layer,
                    query_tag=query_tag,
                    is_primary_official=False,
                )
            )
        return items, SourceFetchStats(
            source_name=f"GoogleNewsRSS[{query_tag}]",
            status="OK",
            http_code=200,
            items_fetched=len(items),
            fetch_latency_ms=round(dt_ms, 1),
            typical_update_lag_desc="1–10 min",
            historical_window_desc="after:/before: multi-month/year (100 items/query cap)",
        )
    except Exception as exc:
        return [], SourceFetchStats(
            source_name=f"GoogleNewsRSS[{query_tag}]",
            status="ERROR",
            note=str(exc),
        )
