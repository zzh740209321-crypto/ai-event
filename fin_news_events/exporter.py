from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from fin_news_events.models import EventCluster


def export_results(
    slug: str,
    events: list[EventCluster],
    evaluation: dict[str, Any],
    output_dir: str = "outputs",
) -> dict[str, str]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    events_sorted = sorted(events, key=lambda e: e.published_at_utc, reverse=True)

    timeline_json_path = out / f"timeline_{slug}.json"
    timeline_csv_path = out / f"timeline_{slug}.csv"
    signals_jsonl_path = out / f"signals_{slug}.jsonl"
    eval_json_path = out / f"eval_{slug}.json"

    with timeline_json_path.open("w", encoding="utf-8") as f:
        json.dump([e.to_dict() for e in events_sorted], f, ensure_ascii=False, indent=2)

    with signals_jsonl_path.open("w", encoding="utf-8") as f:
        for e in sorted(events, key=lambda x: x.published_at_utc):
            f.write(json.dumps(e.to_signal_bus_payload(), ensure_ascii=False) + "\n")

    with eval_json_path.open("w", encoding="utf-8") as f:
        json.dump(evaluation, f, ensure_ascii=False, indent=2)

    csv_cols = [
        "event_id", "target_symbol", "published_at_myt", "retrieval_layer",
        "category", "subcategory", "impact_score", "direction", "confidence",
        "verification_status", "transmission_weight", "transmission_path",
        "novelty", "source_credibility", "source_count", "headline",
        "primary_source", "primary_url", "anchor_price",
        "ret_1h_pct", "ret_4h_pct", "ret_24h_pct",
        "abnormal_ret_1h_pct", "abnormal_ret_4h_pct", "abnormal_ret_24h_pct",
        "vol_zscore_24h", "e2e_pipeline_latency_ms", "classifier_mode",
    ]
    with timeline_csv_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=csv_cols)
        w.writeheader()
        for e in events_sorted:
            mr = e.market_reaction
            w.writerow(
                {
                    "event_id": e.event_id,
                    "target_symbol": e.target_symbol,
                    "published_at_myt": e.published_at_myt,
                    "retrieval_layer": e.retrieval_layer,
                    "category": e.category,
                    "subcategory": e.subcategory,
                    "impact_score": e.impact_score,
                    "direction": e.direction,
                    "confidence": e.confidence,
                    "verification_status": e.verification_status,
                    "transmission_weight": e.transmission_weight,
                    "transmission_path": e.transmission_path,
                    "novelty": e.novelty,
                    "source_credibility": e.source_credibility,
                    "source_count": e.source_count,
                    "headline": e.headline,
                    "primary_source": e.sources[0]["name"] if e.sources else "",
                    "primary_url": e.sources[0]["url"] if e.sources else "",
                    "anchor_price": mr.anchor_price if mr else "",
                    "ret_1h_pct": mr.ret_1h if mr else "",
                    "ret_4h_pct": mr.ret_4h if mr else "",
                    "ret_24h_pct": mr.ret_24h if mr else "",
                    "abnormal_ret_1h_pct": mr.abnormal_ret_1h if mr else "",
                    "abnormal_ret_4h_pct": mr.abnormal_ret_4h if mr else "",
                    "abnormal_ret_24h_pct": mr.abnormal_ret_24h if mr else "",
                    "vol_zscore_24h": mr.vol_zscore_24h if mr else "",
                    "e2e_pipeline_latency_ms": e.e2e_pipeline_latency_ms,
                    "classifier_mode": e.classifier_mode,
                }
            )

    return {
        "timeline_json": str(timeline_json_path),
        "timeline_csv": str(timeline_csv_path),
        "signals_jsonl": str(signals_jsonl_path),
        "eval_json": str(eval_json_path),
    }
