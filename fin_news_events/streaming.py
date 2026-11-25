from __future__ import annotations

import json
import queue
import time
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import requests

from fin_news_events.classifier import get_classifier
from fin_news_events.dedup_cluster import IncrementalClusterer
from fin_news_events.entity_mapper import extract_matched_entities, resolve_target
from fin_news_events.models import RawNewsItem, to_myt_str
from fin_news_events.pipeline import _is_relevant_to_target, build_event_from_cluster, collect_two_layer_news
from fin_news_events.sources import ConditionalHTTPClient


def run_polling_stream(
    symbol: str,
    interval_sec: int = 60,
    cycles: int = 2,
    stream_out: str = "outputs/signal_stream.jsonl",
    webhook_url: Optional[str] = None,
    classifier_mode: str = "auto",
) -> list[dict]:
    """Single-core dual-exit real-time polling mode with ETag/Last-Modified & incremental clustering."""
    profile = resolve_target(symbol)
    client = ConditionalHTTPClient()
    classifier = get_classifier(classifier_mode)
    clusterer = IncrementalClusterer(sim_threshold=0.42, window_hours=48)
    item_queue: queue.Queue[RawNewsItem] = queue.Queue()
    recent_subcats: Counter[str] = Counter()
    pushed_signals: list[dict] = []

    out_path = Path(stream_out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    seen_ids: set[str] = set()
    for cycle_idx in range(1, cycles + 1):
        now = datetime.now(timezone.utc)
        start_dt = now - timedelta(hours=24)
        print(f"[POLL cycle {cycle_idx}/{cycles}] {to_myt_str(now)} | symbol={profile.canonical_symbol}")

        raw_items, stats = collect_two_layer_news(
            profile=profile,
            start_dt=start_dt,
            end_dt=now,
            client=client,
            conditional=(cycle_idx > 1),
            include_gdelt=False,  # skip 15-min GDELT in sub-minute polling loop
        )
        not_mod = sum(1 for s in stats if s.status == "NOT_MODIFIED")
        new_queued = 0
        for it in sorted(raw_items, key=lambda x: x.published_at):
            if it.item_id in seen_ids:
                continue
            ents, layer = extract_matched_entities(f"{it.title} {it.summary}", profile)
            if not _is_relevant_to_target(it, ents, layer, profile):
                continue
            seen_ids.add(it.item_id)
            item_queue.put(it)
            new_queued += 1

        emitted_this_cycle = 0
        while not item_queue.empty():
            it = item_queue.get()
            t0 = time.perf_counter()
            cluster, is_new, is_exact = clusterer.process_item(it)
            if is_exact:
                continue
            # Emit on new event OR when cluster crosses multi-source confirmation (size == 2)
            if is_new or len(cluster.items) == 2:
                evt = build_event_from_cluster(cluster, profile, classifier, recent_subcats, t0)
                payload = evt.to_signal_bus_payload()
                payload["stream_event_type"] = "EVENT_CREATED" if is_new else "EVENT_CONFIRMED_UPDATE"
                pushed_signals.append(payload)
                with out_path.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(payload, ensure_ascii=False) + "\n")
                if webhook_url:
                    try:
                        requests.post(webhook_url, json=payload, timeout=5)
                    except Exception as exc:
                        print(f"  [WARN] webhook push failed: {exc}")
                emitted_this_cycle += 1

        print(
            f"  fetched={len(raw_items)} not_modified_304={not_mod} queued={new_queued} "
            f"emitted_signals={emitted_this_cycle} total_active_clusters={len(clusterer.clusters)}"
        )
        if cycle_idx < cycles:
            time.sleep(interval_sec)

    return pushed_signals
