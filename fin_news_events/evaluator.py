from __future__ import annotations

import math
from collections import Counter
from typing import Any

import numpy as np

from fin_news_events.models import EventCluster
from fin_news_events.sources.base import SourceFetchStats


def _spearman_corr(x: list[float], y: list[float]) -> float | None:
    if len(x) < 4:
        return None
    rx = np.argsort(np.argsort(x)).astype(float)
    ry = np.argsort(np.argsort(y)).astype(float)
    if np.std(rx) == 0 or np.std(ry) == 0:
        return None
    return round(float(np.corrcoef(rx, ry)[0, 1]), 4)


def evaluate_run(
    target_symbol: str,
    raw_count: int,
    exact_dedup_count: int,
    events: list[EventCluster],
    source_stats: list[SourceFetchStats],
) -> dict[str, Any]:
    clusters_count = len(events)
    compression_ratio = round(1.0 - (clusters_count / raw_count), 4) if raw_count else 0.0

    cat_counts = Counter(e.category for e in events)
    layer_counts = Counter(e.retrieval_layer for e in events)
    verif_counts = Counter(e.verification_status for e in events)
    dir_counts = Counter(e.direction for e in events)

    e2e_ms = [e.e2e_pipeline_latency_ms for e in events]
    fetch_ms = [s.fetch_latency_ms for s in source_stats if s.fetch_latency_ms > 0]
    pub_to_ing = [
        e.source_publish_to_ingest_sec
        for e in events
        if e.source_publish_to_ingest_sec is not None and 0 <= e.source_publish_to_ingest_sec <= 86400
    ]

    # Market reaction evaluation (24h window & 4h window)
    eval_24 = [e for e in events if e.market_reaction and e.market_reaction.ret_24h is not None]
    eval_4 = [e for e in events if e.market_reaction and e.market_reaction.ret_4h is not None]

    scores_24 = [e.impact_score for e in eval_24]
    abs_ret_24 = [abs(e.market_reaction.ret_24h) for e in eval_24]
    abs_ab_24 = [
        abs(e.market_reaction.abnormal_ret_24h)
        for e in eval_24
        if e.market_reaction.abnormal_ret_24h is not None
    ]
    scores_ab_24 = [
        e.impact_score
        for e in eval_24
        if e.market_reaction.abnormal_ret_24h is not None
    ]

    corr_raw_24 = _spearman_corr(scores_24, abs_ret_24)
    corr_ab_24 = _spearman_corr(scores_ab_24, abs_ab_24)

    # Top vs bottom quantile |abnormal_ret_24h|
    top_q_ab = None
    bot_q_ab = None
    if len(scores_ab_24) >= 8:
        paired = sorted(zip(scores_ab_24, abs_ab_24), key=lambda p: p[0])
        q = max(2, len(paired) // 4)
        bot_q_ab = round(float(np.mean([p[1] for p in paired[:q]])), 3)
        top_q_ab = round(float(np.mean([p[1] for p in paired[-q:]])), 3)

    # Directional hit rate on directional predictions (exclude NEUTRAL/MIXED, require |ret| >= 0.15%)
    dir_eval = [
        e for e in eval_24
        if e.direction in ("BULLISH", "BEARISH") and abs(e.market_reaction.ret_24h) >= 0.15
    ]
    raw_hits = sum(
        1 for e in dir_eval
        if (e.direction == "BULLISH" and e.market_reaction.ret_24h > 0)
        or (e.direction == "BEARISH" and e.market_reaction.ret_24h < 0)
    )
    ab_dir_eval = [
        e for e in dir_eval
        if e.market_reaction.abnormal_ret_24h is not None and abs(e.market_reaction.abnormal_ret_24h) >= 0.15
    ]
    ab_hits = sum(
        1 for e in ab_dir_eval
        if (e.direction == "BULLISH" and e.market_reaction.abnormal_ret_24h > 0)
        or (e.direction == "BEARISH" and e.market_reaction.abnormal_ret_24h < 0)
    )

    return {
        "target_symbol": target_symbol,
        "raw_items_fetched": raw_count,
        "exact_duplicates_removed": exact_dedup_count,
        "event_clusters_output": clusters_count,
        "dedup_compression_ratio": compression_ratio,
        "layer_breakdown": dict(layer_counts),
        "category_breakdown": dict(cat_counts),
        "verification_breakdown": dict(verif_counts),
        "direction_breakdown": dict(dir_counts),
        "latency_metrics": {
            "source_fetch_median_ms": round(float(np.median(fetch_ms)), 1) if fetch_ms else None,
            "source_fetch_p95_ms": round(float(np.percentile(fetch_ms, 95)), 1) if fetch_ms else None,
            "pipeline_e2e_median_ms": round(float(np.median(e2e_ms)), 2) if e2e_ms else None,
            "pipeline_e2e_p95_ms": round(float(np.percentile(e2e_ms, 95)), 2) if e2e_ms else None,
            "recent_24h_publish_to_ingest_median_sec": round(float(np.median(pub_to_ing)), 1) if pub_to_ing else None,
        },
        "market_validation": {
            "events_with_4h_reaction": len(eval_4),
            "events_with_24h_reaction": len(eval_24),
            "spearman_score_vs_abs_ret_24h": corr_raw_24,
            "spearman_score_vs_abs_abnormal_ret_24h": corr_ab_24,
            "top_quartile_mean_abs_abnormal_ret_24h_pct": top_q_ab,
            "bottom_quartile_mean_abs_abnormal_ret_24h_pct": bot_q_ab,
            "directional_eval_count": len(dir_eval),
            "directional_raw_hit_rate": round(raw_hits / len(dir_eval), 3) if dir_eval else None,
            "directional_abnormal_eval_count": len(ab_dir_eval),
            "directional_abnormal_hit_rate": round(ab_hits / len(ab_dir_eval), 3) if ab_dir_eval else None,
        },
        "source_status": [
            {
                "source": s.source_name,
                "status": s.status,
                "http_code": s.http_code,
                "items": s.items_fetched,
                "latency_ms": s.fetch_latency_ms,
                "update_lag": s.typical_update_lag_desc,
                "historical_window": s.historical_window_desc,
                "note": s.note,
            }
            for s in source_stats
        ],
    }
