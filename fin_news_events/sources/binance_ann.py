from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fin_news_events.models import RawNewsItem
from fin_news_events.sources.base import ConditionalHTTPClient, SourceFetchStats, make_item_id

BINANCE_CMS_URL = "https://www.binance.com/bapi/composite/v1/public/cms/article/list/query"


def fetch_binance_announcements(
    client: ConditionalHTTPClient,
    start_dt: datetime,
    end_dt: datetime,
    conditional: bool = False,
) -> tuple[list[RawNewsItem], SourceFetchStats]:
    params = {"type": "1", "pageNo": "1", "pageSize": "15"}
    try:
        resp, dt_ms, not_modified = client.get(BINANCE_CMS_URL, params=params, conditional=conditional)
        if not_modified:
            return [], SourceFetchStats(
                source_name="BinanceAnnouncements",
                status="NOT_MODIFIED",
                http_code=304,
                fetch_latency_ms=round(dt_ms, 1),
                typical_update_lag_desc="<1 min (direct CMS API)",
                historical_window_desc="Paginated CMS archive (recent announcements)",
            )
        if resp.status_code != 200:
            return [], SourceFetchStats(
                source_name="BinanceAnnouncements",
                status="ERROR",
                http_code=resp.status_code,
                fetch_latency_ms=round(dt_ms, 1),
            )
        data = resp.json()
        ingested_at = datetime.now(timezone.utc)
        items: list[RawNewsItem] = []
        for cat in data.get("data", {}).get("catalogs", []):
            cat_name = cat.get("catalogName", "")
            # Focus on listings, latest news, delistings, API updates
            if cat_name in ("Latest Activities", "Fiat & P2P Updates"):
                continue
            for art in cat.get("articles", []):
                title = (art.get("title") or "").strip()
                code = (art.get("code") or "").strip()
                rel_ms = art.get("releaseDate")
                if not title or not rel_ms:
                    continue
                pub_dt = datetime.fromtimestamp(rel_ms / 1000.0, tz=timezone.utc)
                if pub_dt < start_dt or pub_dt > end_dt + timedelta(hours=12):
                    continue
                url = f"https://www.binance.com/en/support/announcement/{code}"
                items.append(
                    RawNewsItem(
                        item_id=make_item_id(url, title),
                        title=f"[Binance {cat_name}] {title}",
                        summary=f"Official Binance announcement in catalog '{cat_name}'.",
                        url=url,
                        source_name="Binance Official",
                        source_feed="binance_cms",
                        source_domain="binance.com",
                        published_at=pub_dt,
                        ingested_at=ingested_at,
                        fetch_latency_ms=round(dt_ms, 1),
                        retrieval_layer="CROSS_MARKET",
                        query_tag="exchange_announcement",
                        is_primary_official=True,
                    )
                )
        return items, SourceFetchStats(
            source_name="BinanceAnnouncements",
            status="OK",
            http_code=200,
            items_fetched=len(items),
            fetch_latency_ms=round(dt_ms, 1),
            typical_update_lag_desc="<1 min (direct CMS JSON)",
            historical_window_desc="Paginated CMS archive (hundreds of recent notices)",
        )
    except Exception as exc:
        return [], SourceFetchStats(source_name="BinanceAnnouncements", status="ERROR", note=str(exc))
