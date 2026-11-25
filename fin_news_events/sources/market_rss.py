from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta, timezone

from bs4 import BeautifulSoup

from fin_news_events.models import RawNewsItem
from fin_news_events.sources.base import (
    ConditionalHTTPClient,
    SourceFetchStats,
    extract_domain,
    make_item_id,
    parse_dt_safe,
)
from fin_news_events.sources.yahoo_news import fetch_yahoo_ticker_rss

# Verified live US market-wrap & financial news RSS feeds (all return HTTP 200 with fresh items).
MARKET_WRAP_FEEDS: list[tuple[str, str, str, str, str]] = [
    ("CNBC Top News", "cnbc_top_rss", "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100003114", "cnbc.com", "1–5 min"),
    ("CNBC Markets", "cnbc_markets_rss", "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=20910258", "cnbc.com", "1–5 min"),
    ("CNBC Investing", "cnbc_investing_rss", "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=15839069", "cnbc.com", "1–5 min"),
    ("CNBC Finance", "cnbc_finance_rss", "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=10000664", "cnbc.com", "1–5 min"),
    ("CNBC Tech", "cnbc_tech_rss", "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=19854910", "cnbc.com", "1–5 min"),
    ("MarketWatch", "marketwatch_rss", "https://feeds.content.dowjones.io/public/rss/mw_topstories", "marketwatch.com", "2–10 min"),
    ("NBC Business", "nbc_business_rss", "https://feeds.nbcnews.com/nbcnews/public/business", "nbcnews.com", "2–10 min"),
    ("NYT Business", "nyt_business_rss", "https://rss.nytimes.com/services/xml/rss/nyt/Business.xml", "nytimes.com", "2–10 min"),
    ("BBC Business", "bbc_business_rss", "https://feeds.bbci.co.uk/news/business/rss.xml", "bbc.com", "2–10 min"),
]


def _clean(txt: str) -> str:
    if not txt:
        return ""
    s = BeautifulSoup(txt, "lxml").get_text(" ", strip=True)
    return re.sub(r"\s+", " ", s).strip()


def fetch_market_wrap_rss(
    client: ConditionalHTTPClient,
    start_dt: datetime,
    end_dt: datetime,
    conditional: bool = False,
    yahoo_tickers: list[str] | None = None,
) -> tuple[list[RawNewsItem], list[SourceFetchStats]]:
    """Fetch public US market-wrap & financial news RSS feeds plus Yahoo market ticker RSS."""
    all_items: list[RawNewsItem] = []
    stats: list[SourceFetchStats] = []
    for name, feed_id, url, canonical_domain, lag_desc in MARKET_WRAP_FEEDS:
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
                        historical_window_desc="Latest ~10–60 items only (requires self-hosted archive)",
                    )
                )
                continue
            if resp is None or resp.status_code != 200:
                stats.append(
                    SourceFetchStats(
                        source_name=name,
                        status="ERROR",
                        http_code=resp.status_code if resp is not None else None,
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
                dom = extract_domain(link)
                if dom in ("unknown", "feeds.nbcnews.com", "feeds.content.dowjones.io", "search.cnbc.com", "rss.nytimes.com", "feeds.bbci.co.uk"):
                    dom = canonical_domain
                all_items.append(
                    RawNewsItem(
                        item_id=make_item_id(link, title),
                        title=title,
                        summary=desc[:500],
                        url=link,
                        source_name=name,
                        source_feed=feed_id,
                        source_domain=dom or canonical_domain,
                        published_at=pub_dt,
                        ingested_at=ingested_at,
                        fetch_latency_ms=round(dt_ms, 1),
                        retrieval_layer="CROSS_MARKET",
                        query_tag="us_market_wrap_rss",
                        is_primary_official=False,
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
                    historical_window_desc="Latest ~10–60 items only",
                )
            )
        except Exception as exc:
            stats.append(SourceFetchStats(source_name=name, status="ERROR", note=str(exc)))

    tickers = yahoo_tickers or ["^GSPC", "^IXIC", "^DJI", "NVDA", "SMH", "SOXX", "AAPL", "MSFT", "TSLA"]
    y_items, y_st = fetch_yahoo_ticker_rss(
        client,
        tickers=tickers,
        retrieval_layer="CROSS_MARKET",
        query_tag="yahoo_us_market_wrap",
        start_dt=start_dt,
        end_dt=end_dt,
        conditional=conditional,
    )
    all_items.extend(y_items)
    stats.append(y_st)
    return all_items, stats


SYMBOL_TARGETED_QUERIES: dict[str, tuple[str, str, str]] = {
    "NVDA": ("DIRECT", "q_nvda_shares", '("Nvidia shares" OR "Nvidia stock" OR "Jensen Huang" OR NVDA)'),
    "AAPL": ("DIRECT", "q_aapl_shares", '("Apple shares" OR "Apple stock" OR AAPL)'),
    "MSFT": ("DIRECT", "q_msft_shares", '("Microsoft shares" OR "Microsoft stock" OR MSFT)'),
    "TSLA": ("DIRECT", "q_tsla_shares", '("Tesla shares" OR "Tesla stock" OR TSLA)'),
    "SMH": ("DIRECT", "q_chip_stocks", '("chip stocks" OR semiconductor OR chipmakers OR "AI stocks")'),
    "SOXX": ("DIRECT", "q_chip_stocks", '("chip stocks" OR semiconductor OR chipmakers OR "AI stocks")'),
    "QQQ": ("CROSS_MARKET", "q_nasdaq_tech", '("Nasdaq" OR "tech stocks" OR "AI rally" OR "AI selloff")'),
    "SPY": ("CROSS_MARKET", "q_sp500_wrap", '("S&P 500" OR "stock market today" OR "Wall Street")'),
    "DIA": ("CROSS_MARKET", "q_dow_wrap", '("Dow Jones" OR "stock market today" OR "value rotation")'),
}


def build_targeted_attribution_queries(
    anomalous_symbols: list[str],
    market: str,
    session_date: date,
) -> list[tuple[str, str, str]]:
    """Auto-generate targeted Google News RSS queries from anomalous symbols, sectors & date.

    Returns list of (retrieval_layer, query_tag, query_string).
    """
    queries: list[tuple[str, str, str]] = []
    seen_tags: set[str] = set()

    def _add(layer: str, tag: str, q: str) -> None:
        if tag in seen_tags:
            return
        seen_tags.add(tag)
        queries.append((layer, tag, q))

    syms_upper = {s.upper() for s in anomalous_symbols}
    month_abbr = session_date.strftime("%b")
    month_full = session_date.strftime("%B")
    day_num = session_date.day
    year_num = session_date.year
    date_phrase = f'("{month_abbr} {day_num}" OR "{month_full} {day_num}")'

    include_us = market in ("us", "all") or any(not s.endswith("/USDT") for s in syms_upper)
    include_crypto = market in ("crypto", "all") or any(s.endswith("/USDT") for s in syms_upper)

    if include_us:
        # Reuters & AP have no public RSS; query via Google News site: filters
        _add("CROSS_MARKET", "reuters_market", "site:reuters.com (stocks OR Nasdaq OR S&P OR Nvidia OR semiconductor OR tariffs)")
        _add("CROSS_MARKET", "ap_market", "site:apnews.com (stocks OR Nasdaq OR Wall Street OR Nvidia OR tariffs)")
        _add("CROSS_MARKET", "investopedia_wrap", 'site:investopedia.com ("stock market today" OR "5 things" OR Nasdaq OR Nvidia)')
        _add("CROSS_MARKET", "cnbc_wrap", "site:cnbc.com (stocks OR Nasdaq OR S&P OR Nvidia OR semiconductor OR tariffs)")
        _add("CROSS_MARKET", "yahoo_wrap", "site:finance.yahoo.com (stocks OR chipmakers OR Nvidia OR Nasdaq OR tariffs)")
        _add("CROSS_MARKET", "stock_market_today", f'("stock market today" OR "markets today") ({date_phrase} OR {year_num})')
        _add("CROSS_MARKET", "tariffs_macro_us", '(tariffs OR "rate hike" OR PCE OR "data center spending") (stocks OR Nasdaq OR chip)')

        for sym in anomalous_symbols:
            su = sym.upper()
            if su in SYMBOL_TARGETED_QUERIES:
                layer, tag, q = SYMBOL_TARGETED_QUERIES[su]
                _add(layer, tag, q)
        if "NVDA" in syms_upper:
            _add("DIRECT", "q_chip_stocks", '("chip stocks" OR semiconductor OR chipmakers OR "AI stocks")')

    if include_crypto:
        _add("DIRECT", "q_crypto_market", '("Bitcoin" OR "Bitcoin ETF" OR "crypto market")')
        for sym in anomalous_symbols:
            if sym.endswith("/USDT"):
                base = sym.split("/")[0].upper()
                if base != "BTC":
                    _add("DIRECT", f"q_crypto_{base.lower()}", f"({base} crypto OR {base} price)")

    return queries
