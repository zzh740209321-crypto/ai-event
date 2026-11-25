from __future__ import annotations

import time
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Optional

from fin_news_events.classifier import BaseEventClassifier, get_classifier
from fin_news_events.dedup_cluster import ActiveCluster, IncrementalClusterer
from fin_news_events.entity_mapper import TargetProfile, extract_matched_entities, resolve_target
from fin_news_events.evaluator import evaluate_run
from fin_news_events.market_data import (
    attach_market_reaction,
    compute_hourly_vol,
    fetch_binance_klines,
    fetch_yahoo_bars,
)
from fin_news_events.models import EventCluster, RawNewsItem, to_myt_str, to_utc_iso
from fin_news_events.scorer import score_event
from fin_news_events.sources import (
    ConditionalHTTPClient,
    SourceFetchStats,
    fetch_binance_announcements,
    fetch_crypto_rss,
    fetch_cryptopanic_plugin,
    fetch_gdelt_doc,
    fetch_google_news_rss,
    fetch_nvidia_newsroom_rss,
    fetch_sec_company_filings,
    fetch_yahoo_ticker_rss,
)

CROSS_MARKET_TAGS = [
    ("macro_fed", "(Federal Reserve OR FOMC OR Jerome Powell OR interest rate OR CPI OR inflation OR Treasury yield OR US dollar)"),
    ("tradfi_flows", "(S&P 500 OR Nasdaq OR gold price OR crude oil OR Bitcoin ETF OR institutional flows)"),
    ("tech_ai", "(AI valuation OR OpenAI OR Anthropic OR TSMC OR semiconductor OR hyperscaler OR Nvidia)"),
    ("politics_reg", "(midterm election OR Congress OR Trump OR SEC OR CFTC OR tariff OR export controls)"),
]


def _is_relevant_to_target(item: RawNewsItem, matched_entities: list[str], layer: str, profile: TargetProfile) -> bool:
    if item.is_primary_official:
        return True
    if layer == "DIRECT":
        return True
    # Cross-market items must mention at least one relevant macro/TradFi/AI/policy/crypto entity
    if not matched_entities:
        return False
    # For equities, drop pure minor altcoin-only fluff unless macro/AI/crypto-beta
    if profile.asset_class == "EQUITY" and item.source_feed in ("coindesk_rss", "cointelegraph_rss", "decrypt_rss", "theblock_rss", "kraken_rss", "binance_cms"):
        # Keep only if it links to AI, equities, macro, or Fed/SEC/election
        keep_tags = {"Fed/FOMC", "Inflation/CPI", "US Treasury/DXY", "Equities/Nasdaq/S&P", "AI/Semis", "Politics/Tariffs/SEC"}
        return any(e in keep_tags for e in matched_entities)
    return True


def collect_two_layer_news(
    profile: TargetProfile,
    start_dt: datetime,
    end_dt: datetime,
    client: ConditionalHTTPClient,
    conditional: bool = False,
    include_gdelt: bool = True,
    extra_queries: list[tuple[str, str]] | None = None,
) -> tuple[list[RawNewsItem], list[SourceFetchStats]]:
    all_items: list[RawNewsItem] = []
    stats: list[SourceFetchStats] = []

    # Layer 1: Direct target queries via Google News RSS (sliced if span > 10 days to avoid 100-item cap)
    span_days = max(1, (end_dt - start_dt).days)
    windows: list[tuple[datetime, datetime]] = []
    if span_days > 10:
        cur = start_dt
        while cur < end_dt:
            nxt = min(end_dt, cur + timedelta(days=7))
            windows.append((cur, nxt))
            cur = nxt
    else:
        windows.append((start_dt, end_dt))

    for w_idx, (w_start, w_end) in enumerate(windows):
        for q_idx, q in enumerate(profile.direct_queries):
            items, st = fetch_google_news_rss(
                client,
                query=q,
                retrieval_layer="DIRECT",
                query_tag=f"direct_{q_idx}_w{w_idx}",
                start_dt=w_start,
                end_dt=w_end,
                conditional=conditional,
            )
            all_items.extend(items)
            stats.append(st)

        # Layer 2: Cross-market global pool
        for tag, q in CROSS_MARKET_TAGS:
            items, st = fetch_google_news_rss(
                client,
                query=q,
                retrieval_layer="CROSS_MARKET",
                query_tag=f"{tag}_w{w_idx}",
                start_dt=w_start,
                end_dt=w_end,
                conditional=conditional,
            )
            all_items.extend(items)
            stats.append(st)

        if extra_queries:
            for tag, q in extra_queries:
                items, st = fetch_google_news_rss(
                    client,
                    query=q,
                    retrieval_layer="CROSS_MARKET",
                    query_tag=f"{tag}_w{w_idx}",
                    start_dt=w_start,
                    end_dt=w_end,
                    conditional=conditional,
                )
                all_items.extend(items)
                stats.append(st)

    # Yahoo Finance Ticker RSS (recent)
    if profile.yahoo_rss_tickers:
        items, st = fetch_yahoo_ticker_rss(
            client,
            tickers=profile.yahoo_rss_tickers,
            retrieval_layer="DIRECT",
            query_tag="yahoo_direct",
            start_dt=start_dt,
            end_dt=end_dt,
            conditional=conditional,
        )
        all_items.extend(items)
        stats.append(st)

    # Macro Yahoo RSS (SPY, QQQ, Gold, Oil)
    m_items, m_st = fetch_yahoo_ticker_rss(
        client,
        tickers=["SPY", "QQQ", "GC=F", "CL=F"],
        retrieval_layer="CROSS_MARKET",
        query_tag="yahoo_macro",
        start_dt=start_dt,
        end_dt=end_dt,
        conditional=conditional,
    )
    all_items.extend(m_items)
    stats.append(m_st)

    # Official equity filings & newsroom
    if profile.sec_cik:
        sec_items, sec_st = fetch_sec_company_filings(
            client, profile.sec_cik, profile.canonical_symbol, start_dt, end_dt, conditional=conditional
        )
        all_items.extend(sec_items)
        stats.append(sec_st)

    if profile.canonical_symbol == "NVDA":
        nv_items, nv_st = fetch_nvidia_newsroom_rss(client, start_dt, end_dt, conditional=conditional)
        all_items.extend(nv_items)
        stats.append(nv_st)

    # Crypto specialized RSS & Binance Official CMS
    c_items, c_stats = fetch_crypto_rss(client, start_dt, end_dt, conditional=conditional)
    all_items.extend(c_items)
    stats.extend(c_stats)

    b_items, b_st = fetch_binance_announcements(client, start_dt, end_dt, conditional=conditional)
    all_items.extend(b_items)
    stats.append(b_st)

    # Optional GDELT DOC API (3-month rolling window)
    if include_gdelt and (datetime.now(timezone.utc) - start_dt).days <= 95:
        g_q = " OR ".join(profile.direct_aliases[:2])
        g_items, g_st = fetch_gdelt_doc(client, g_q, "DIRECT", "gdelt_direct", start_dt, end_dt, max_records=40)
        all_items.extend(g_items)
        stats.append(g_st)

    # Optional API-key plugin stub (CryptoPanic)
    if profile.asset_class == "CRYPTO":
        cp_items, cp_st = fetch_cryptopanic_plugin(client, profile.canonical_symbol.split("/")[0], start_dt, end_dt)
        all_items.extend(cp_items)
        stats.append(cp_st)

    return all_items, stats


def build_event_from_cluster(
    cluster: ActiveCluster,
    profile: TargetProfile,
    classifier: BaseEventClassifier,
    recent_subcats: Counter[str],
    t_cluster_start: float,
) -> EventCluster:
    combined_text = f"{cluster.rep_title}. " + " ".join(it.summary[:200] for it in cluster.items[:2] if it.summary)
    matched_entities, layer = extract_matched_entities(combined_text, profile)
    if any(it.retrieval_layer == "DIRECT" for it in cluster.items) and layer == "DIRECT":
        final_layer = "DIRECT"
    elif layer == "DIRECT":
        final_layer = "DIRECT"
    else:
        final_layer = "CROSS_MARKET"

    clf = classifier.classify(combined_text, profile.canonical_symbol, final_layer)
    sc = score_event(
        cluster=cluster,
        clf=clf,
        profile=profile,
        retrieval_layer=final_layer,
        recent_same_subcat_count=recent_subcats.get(clf.subcategory, 0),
    )
    recent_subcats[clf.subcategory] += 1

    pub_dt = cluster.first_seen or datetime.now(timezone.utc)
    ing_dt = cluster.latest_ingested or datetime.now(timezone.utc)
    pushed_dt = datetime.now(timezone.utc)
    e2e_ms = round((time.perf_counter() - t_cluster_start) * 1000.0, 2)
    pub_to_ing = round((ing_dt - pub_dt).total_seconds(), 1)

    sources_list = []
    seen_urls: set[str] = set()
    for it in sorted(cluster.items, key=lambda x: x.published_at):
        if it.url in seen_urls:
            continue
        seen_urls.add(it.url)
        from fin_news_events.scorer import get_source_credibility
        sources_list.append(
            {
                "name": it.source_name,
                "feed": it.source_feed,
                "domain": it.source_domain,
                "url": it.url,
                "published_at_myt": to_myt_str(it.published_at),
                "credibility": round(get_source_credibility(it.source_name, it.source_domain), 2),
                "is_primary_official": it.is_primary_official,
            }
        )

    best_summary = next((it.summary for it in cluster.items if it.summary), "")
    return EventCluster(
        event_id=cluster.cluster_id,
        target_symbol=profile.canonical_symbol,
        retrieval_layer=final_layer,
        published_at_utc=to_utc_iso(pub_dt),
        published_at_myt=to_myt_str(pub_dt),
        last_updated_utc=to_utc_iso(cluster.last_seen or pub_dt),
        ingested_at_utc=to_utc_iso(ing_dt),
        pushed_at_utc=to_utc_iso(pushed_dt),
        e2e_pipeline_latency_ms=e2e_ms,
        source_publish_to_ingest_sec=pub_to_ing,
        headline=cluster.rep_title,
        summary=best_summary[:350],
        category=clf.category,
        subcategory=clf.subcategory,
        matched_entities=matched_entities,
        transmission_path=sc.transmission_path,
        transmission_weight=sc.transmission_weight,
        direction=clf.direction,
        confidence=clf.confidence,
        impact_score=sc.impact_score,
        score_breakdown=sc.breakdown,
        verification_status=sc.verification_status,
        verification_detail=sc.verification_detail,
        novelty=sc.novelty,
        source_credibility=sc.source_credibility,
        source_count=len(sources_list),
        unique_domains=sorted({s["domain"] for s in sources_list if s["domain"]}),
        sources=sources_list,
        classifier_mode=clf.classifier_mode,
    )


def run_batch_pipeline(
    symbol: str,
    start_dt: datetime,
    end_dt: datetime,
    classifier_mode: str = "auto",
    include_gdelt: bool = True,
    extra_queries: list[tuple[str, str]] | None = None,
    sim_threshold: float = 0.42,
) -> dict:
    profile = resolve_target(symbol)
    client = ConditionalHTTPClient()
    classifier = get_classifier(classifier_mode)

    raw_items, source_stats = collect_two_layer_news(
        profile=profile,
        start_dt=start_dt,
        end_dt=end_dt,
        client=client,
        conditional=False,
        include_gdelt=include_gdelt,
        extra_queries=extra_queries,
    )

    # Filter & annotate relevance
    filtered_items: list[RawNewsItem] = []
    for it in raw_items:
        ents, layer = extract_matched_entities(f"{it.title} {it.summary}", profile)
        if _is_relevant_to_target(it, ents, layer, profile):
            if layer == "DIRECT":
                it.retrieval_layer = "DIRECT"
            filtered_items.append(it)

    clusterer = IncrementalClusterer(sim_threshold=sim_threshold, window_hours=48)
    clusters = clusterer.cluster_batch(filtered_items)

    # Fetch market data with buffer (-48h before start, +36h after end)
    mkt_start = start_dt - timedelta(days=3)
    mkt_end = min(datetime.now(timezone.utc), end_dt + timedelta(days=2))
    span_days = (mkt_end - mkt_start).days

    if profile.asset_class == "CRYPTO":
        target_df = fetch_binance_klines(profile.market_symbol, mkt_start, mkt_end, interval="1h")
        bench_df = fetch_binance_klines(profile.benchmark_symbol, mkt_start, mkt_end, interval="1h")
        sec_bench_df = None
    else:
        interval = "1h" if span_days <= 180 and (datetime.now(timezone.utc) - mkt_start).days <= 700 else "1d"
        target_df = fetch_yahoo_bars(profile.market_symbol, mkt_start, mkt_end, interval=interval)
        bench_df = fetch_yahoo_bars(profile.benchmark_symbol, mkt_start, mkt_end, interval=interval)
        sec_bench_df = (
            fetch_yahoo_bars(profile.secondary_benchmark, mkt_start, mkt_end, interval=interval)
            if profile.secondary_benchmark
            else None
        )

    hourly_vol = compute_hourly_vol(target_df)

    recent_subcats: Counter[str] = Counter()
    events: list[EventCluster] = []
    for c in clusters:
        t0 = time.perf_counter()
        evt = build_event_from_cluster(c, profile, classifier, recent_subcats, t0)
        pub_dt = c.first_seen or start_dt
        evt.market_reaction = attach_market_reaction(
            pub_dt=pub_dt,
            target_df=target_df,
            bench_df=bench_df,
            benchmark_symbol=profile.benchmark_symbol,
            hourly_vol=hourly_vol,
            sec_bench_df=sec_bench_df,
            sec_bench_symbol=profile.secondary_benchmark,
        )
        events.append(evt)

    # Sort newest first for timeline display, or keep chronological and sort in exporter
    eval_summary = evaluate_run(
        target_symbol=profile.canonical_symbol,
        raw_count=len(filtered_items),
        exact_dedup_count=clusterer.exact_dedup_count,
        events=events,
        source_stats=source_stats,
    )
    eval_summary["raw_unfiltered_fetched"] = len(raw_items)
    eval_summary["market_bars_loaded"] = {
        profile.market_symbol: len(target_df),
        profile.benchmark_symbol: len(bench_df),
        "hourly_vol_pct": round(hourly_vol * 100, 3),
    }

    return {
        "profile": profile,
        "events": events,
        "evaluation": eval_summary,
        "classifier_mode": getattr(classifier, "mode_name", "unknown"),
    }
