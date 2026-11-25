from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

MYT = timezone(timedelta(hours=8))


def to_myt_str(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(MYT).strftime("%Y-%m-%d %H:%M UTC+8")


def to_utc_iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass
class RawNewsItem:
    item_id: str
    title: str
    summary: str
    url: str
    source_name: str
    source_feed: str
    source_domain: str
    published_at: datetime
    ingested_at: datetime
    fetch_latency_ms: float
    retrieval_layer: str  # "DIRECT" | "CROSS_MARKET"
    query_tag: str
    is_primary_official: bool = False
    raw_meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["published_at"] = to_utc_iso(self.published_at)
        d["ingested_at"] = to_utc_iso(self.ingested_at)
        return d


@dataclass
class MarketReaction:
    anchor_time_utc: str
    anchor_time_myt: str
    anchor_price: float
    benchmark_symbol: str
    ret_1h: Optional[float] = None
    ret_4h: Optional[float] = None
    ret_24h: Optional[float] = None
    bench_ret_1h: Optional[float] = None
    bench_ret_4h: Optional[float] = None
    bench_ret_24h: Optional[float] = None
    abnormal_ret_1h: Optional[float] = None
    abnormal_ret_4h: Optional[float] = None
    abnormal_ret_24h: Optional[float] = None
    vol_zscore_1h: Optional[float] = None
    vol_zscore_4h: Optional[float] = None
    vol_zscore_24h: Optional[float] = None
    secondary_benchmark_symbol: Optional[str] = None
    secondary_abnormal_ret_24h: Optional[float] = None
    data_note: str = "OK"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class EventCluster:
    event_id: str
    target_symbol: str
    retrieval_layer: str
    published_at_utc: str
    published_at_myt: str
    last_updated_utc: str
    ingested_at_utc: str
    pushed_at_utc: str
    e2e_pipeline_latency_ms: float
    source_publish_to_ingest_sec: Optional[float]
    headline: str
    summary: str
    category: str
    subcategory: str
    matched_entities: list[str]
    transmission_path: str
    transmission_weight: float
    direction: str
    confidence: float
    impact_score: float
    score_breakdown: dict[str, float]
    verification_status: str
    verification_detail: str
    novelty: float
    source_credibility: float
    source_count: int
    unique_domains: list[str]
    sources: list[dict[str, Any]]
    classifier_mode: str
    market_reaction: Optional[MarketReaction] = None

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        return d

    def to_signal_bus_payload(self) -> dict[str, Any]:
        """Compact schema for the multi-agent trading signal system."""
        return {
            "schema_version": "fin_event.v1",
            "event_id": self.event_id,
            "target_symbol": self.target_symbol,
            "retrieval_layer": self.retrieval_layer,
            "published_at_utc": self.published_at_utc,
            "published_at_myt": self.published_at_myt,
            "ingested_at_utc": self.ingested_at_utc,
            "pushed_at_utc": self.pushed_at_utc,
            "e2e_pipeline_latency_ms": self.e2e_pipeline_latency_ms,
            "category": self.category,
            "subcategory": self.subcategory,
            "headline": self.headline,
            "matched_entities": self.matched_entities,
            "transmission_path": self.transmission_path,
            "transmission_weight": self.transmission_weight,
            "direction": self.direction,
            "impact_score": self.impact_score,
            "confidence": self.confidence,
            "novelty": self.novelty,
            "verification_status": self.verification_status,
            "source_credibility": self.source_credibility,
            "source_count": self.source_count,
            "sources": [
                {"name": s["name"], "url": s["url"], "credibility": s["credibility"]}
                for s in self.sources[:5]
            ],
            "classifier_mode": self.classifier_mode,
        }
