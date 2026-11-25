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


def _clean(txt: str) -> str:
    if not txt:
        return ""
    return re.sub(r"\s+", " ", BeautifulSoup(txt, "lxml").get_text(" ", strip=True)).strip()


def fetch_yahoo_ticker_rss(
    client: ConditionalHTTPClient,
    tickers: list[str],
    retrieval_layer: str,
    query_tag: str,
    start_dt: datetime,
    end_dt: datetime,
    conditional: bool = False,
) -> tuple[list[RawNewsItem], SourceFetchStats]:
    s_param = ",".join(tickers)
    url = "https://feeds.finance.yahoo.com/rss/2.0/headline"
    params = {"s": s_param, "region": "US", "lang": "en-US"}
    try:
        resp, dt_ms, not_modified = client.get(url, params=params, conditional=conditional)
        if not_modified:
            return [], SourceFetchStats(
                source_name=f"YahooFinanceRSS[{s_param}]",
                status="NOT_MODIFIED",
                http_code=304,
                fetch_latency_ms=round(dt_ms, 1),
                typical_update_lag_desc="1–5 min",
                historical_window_desc="Latest ~15–20 items only (requires self-hosted archive)",
            )
        if resp.status_code != 200:
            return [], SourceFetchStats(
                source_name=f"YahooFinanceRSS[{s_param}]",
                status="ERROR",
                http_code=resp.status_code,
                fetch_latency_ms=round(dt_ms, 1),
            )
        ingested_at = datetime.now(timezone.utc)
        root = ET.fromstring(resp.content)
        items: list[RawNewsItem] = []
        for el in root.findall(".//item"):
            title = _clean(el.findtext("title") or "")
            link = (el.findtext("link") or "").strip()
            pub_dt = parse_dt_safe(el.findtext("pubDate"))
            if not title or not pub_dt:
                continue
            if pub_dt < start_dt or pub_dt > end_dt + timedelta(hours=12):
                continue
            desc = _clean(el.findtext("description") or "")
            items.append(
                RawNewsItem(
                    item_id=make_item_id(link, title),
                    title=title,
                    summary=desc[:500],
                    url=link,
                    source_name="Yahoo Finance",
                    source_feed="yahoo_rss",
                    source_domain=extract_domain(link),
                    published_at=pub_dt,
                    ingested_at=ingested_at,
                    fetch_latency_ms=round(dt_ms, 1),
                    retrieval_layer=retrieval_layer,
                    query_tag=query_tag,
                )
            )
        return items, SourceFetchStats(
            source_name=f"YahooFinanceRSS[{s_param}]",
            status="OK",
            http_code=200,
            items_fetched=len(items),
            fetch_latency_ms=round(dt_ms, 1),
            typical_update_lag_desc="1–5 min",
            historical_window_desc="Latest ~15–20 items only (requires self-hosted archive)",
        )
    except Exception as exc:
        return [], SourceFetchStats(source_name=f"YahooFinanceRSS[{s_param}]", status="ERROR", note=str(exc))


def fetch_nvidia_newsroom_rss(
    client: ConditionalHTTPClient,
    start_dt: datetime,
    end_dt: datetime,
    conditional: bool = False,
) -> tuple[list[RawNewsItem], SourceFetchStats]:
    url = "https://nvidianews.nvidia.com/releases.xml"
    try:
        resp, dt_ms, not_modified = client.get(url, conditional=conditional)
        if not_modified:
            return [], SourceFetchStats(
                source_name="NVIDIA_Newsroom",
                status="NOT_MODIFIED",
                http_code=304,
                fetch_latency_ms=round(dt_ms, 1),
            )
        if resp.status_code != 200:
            return [], SourceFetchStats(source_name="NVIDIA_Newsroom", status="ERROR", http_code=resp.status_code, fetch_latency_ms=round(dt_ms, 1))
        ingested_at = datetime.now(timezone.utc)
        root = ET.fromstring(resp.content)
        items: list[RawNewsItem] = []
        for el in root.findall(".//item"):
            title = _clean(el.findtext("title") or "")
            link = (el.findtext("link") or "").strip()
            pub_dt = parse_dt_safe(el.findtext("pubDate"))
            if not title or not pub_dt:
                continue
            if pub_dt < start_dt or pub_dt > end_dt + timedelta(hours=12):
                continue
            desc = _clean(el.findtext("description") or "")
            items.append(
                RawNewsItem(
                    item_id=make_item_id(link, title),
                    title=title,
                    summary=desc[:500],
                    url=link,
                    source_name="NVIDIA Newsroom",
                    source_feed="nvidia_newsroom_rss",
                    source_domain="nvidianews.nvidia.com",
                    published_at=pub_dt,
                    ingested_at=ingested_at,
                    fetch_latency_ms=round(dt_ms, 1),
                    retrieval_layer="DIRECT",
                    query_tag="nvidia_official_pr",
                    is_primary_official=True,
                )
            )
        return items, SourceFetchStats(
            source_name="NVIDIA_Newsroom",
            status="OK",
            http_code=200,
            items_fetched=len(items),
            fetch_latency_ms=round(dt_ms, 1),
            typical_update_lag_desc="<1–5 min",
            historical_window_desc="Multi-month press release XML feed",
        )
    except Exception as exc:
        return [], SourceFetchStats(source_name="NVIDIA_Newsroom", status="ERROR", note=str(exc))
