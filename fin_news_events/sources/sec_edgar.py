from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fin_news_events.models import RawNewsItem
from fin_news_events.sources.base import ConditionalHTTPClient, SourceFetchStats, make_item_id, parse_dt_safe


def fetch_sec_company_filings(
    client: ConditionalHTTPClient,
    cik: str,
    symbol: str,
    start_dt: datetime,
    end_dt: datetime,
    conditional: bool = False,
) -> tuple[list[RawNewsItem], SourceFetchStats]:
    """Fetch official SEC EDGAR filings (8-K, 10-Q, 10-K, Form 4, 144) for a CIK."""
    cik_padded = cik.zfill(10)
    url = f"https://data.sec.gov/submissions/CIK{cik_padded}.json"
    try:
        resp, dt_ms, not_modified = client.get(url, conditional=conditional)
        if not_modified:
            return [], SourceFetchStats(
                source_name=f"SEC_EDGAR[{symbol}]",
                status="NOT_MODIFIED",
                http_code=304,
                fetch_latency_ms=round(dt_ms, 1),
                typical_update_lag_desc="Seconds–2 min after acceptanceDateTime",
                historical_window_desc="Full EDGAR history (since ~1994/2001)",
            )
        if resp.status_code != 200:
            return [], SourceFetchStats(
                source_name=f"SEC_EDGAR[{symbol}]",
                status="ERROR",
                http_code=resp.status_code,
                fetch_latency_ms=round(dt_ms, 1),
            )
        data = resp.json()
        recent = data.get("filings", {}).get("recent", {})
        forms = recent.get("form", [])
        acc_dts = recent.get("acceptanceDateTime", [])
        filing_dates = recent.get("filingDate", [])
        accs = recent.get("accessionNumber", [])
        primary_docs = recent.get("primaryDocument", [])
        descs = recent.get("primaryDocDescription", [])
        items_field = recent.get("items", [])

        ingested_at = datetime.now(timezone.utc)
        out: list[RawNewsItem] = []
        cik_int = str(int(cik))
        for i in range(min(len(forms), 120)):
            form = forms[i]
            if form not in ("8-K", "8-K/A", "10-Q", "10-K", "4", "144", "SC 13D", "SC 13G"):
                continue
            dt_str = acc_dts[i] if i < len(acc_dts) and acc_dts[i] else filing_dates[i]
            pub_dt = parse_dt_safe(dt_str)
            if not pub_dt:
                continue
            if pub_dt < start_dt or pub_dt > end_dt + timedelta(hours=12):
                continue
            acc_no = accs[i].replace("-", "")
            pdoc = primary_docs[i] if i < len(primary_docs) else ""
            doc_url = f"https://www.sec.gov/Archives/edgar/data/{cik_int}/{acc_no}/{pdoc}" if pdoc else f"https://www.sec.gov/edgar/browse/?CIK={cik_padded}"
            desc = descs[i] if i < len(descs) else ""
            item_codes = items_field[i] if i < len(items_field) else ""
            title = f"{symbol} SEC Form {form} Filing" + (f" (Items: {item_codes})" if item_codes else "")
            summary = f"Official SEC EDGAR filing Form {form} accepted {pub_dt.strftime('%Y-%m-%d %H:%M:%S UTC')}. {desc}".strip()
            out.append(
                RawNewsItem(
                    item_id=make_item_id(doc_url, title + dt_str),
                    title=title,
                    summary=summary,
                    url=doc_url,
                    source_name="SEC EDGAR",
                    source_feed="sec_edgar",
                    source_domain="sec.gov",
                    published_at=pub_dt,
                    ingested_at=ingested_at,
                    fetch_latency_ms=round(dt_ms, 1),
                    retrieval_layer="DIRECT",
                    query_tag="sec_edgar_filing",
                    is_primary_official=True,
                )
            )
        return out, SourceFetchStats(
            source_name=f"SEC_EDGAR[{symbol}]",
            status="OK",
            http_code=200,
            items_fetched=len(out),
            fetch_latency_ms=round(dt_ms, 1),
            typical_update_lag_desc="Seconds–2 min after EDGAR acceptance",
            historical_window_desc="Full EDGAR electronic archive (since ~1994/2001)",
        )
    except Exception as exc:
        return [], SourceFetchStats(source_name=f"SEC_EDGAR[{symbol}]", status="ERROR", note=str(exc))
