from __future__ import annotations

import hashlib
import math
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from fin_news_events.models import RawNewsItem

STOPWORDS = {
    "the", "a", "an", "and", "or", "for", "of", "to", "in", "on", "at", "by", "with",
    "from", "as", "is", "are", "was", "were", "be", "been", "this", "that", "it",
    "its", "after", "before", "amid", "over", "into", "about", "says", "said",
    "new", "how", "why", "what", "will", "can", "could", "may", "might", "more",
    "today", "now", "here", "report", "reports", "update", "news", "stock", "price",
}


def normalize_tokens(text: str) -> list[str]:
    clean = re.sub(r"[^a-z0-9\s]", " ", text.lower())
    return [t for t in clean.split() if len(t) > 1 and t not in STOPWORDS]


def token_tf(tokens: list[str]) -> dict[str, float]:
    if not tokens:
        return {}
    cnt = Counter(tokens)
    norm = math.sqrt(sum(v * v for v in cnt.values())) or 1.0
    return {k: v / norm for k, v in cnt.items()}


def cosine_sim(v1: dict[str, float], v2: dict[str, float]) -> float:
    if not v1 or not v2:
        return 0.0
    if len(v1) > len(v2):
        v1, v2 = v2, v1
    return sum(val * v2.get(k, 0.0) for k, val in v1.items())


def jaccard_sim(t1: set[str], t2: set[str]) -> float:
    if not t1 or not t2:
        return 0.0
    inter = len(t1 & t2)
    union = len(t1 | t2)
    return inter / union if union else 0.0


def char_ngrams(text: str, n: int = 4) -> set[str]:
    s = re.sub(r"[^a-z0-9]", "", text.lower())
    if len(s) < n:
        return {s} if s else set()
    return {s[i : i + n] for i in range(len(s) - n + 1)}


@dataclass
class ActiveCluster:
    cluster_id: str
    items: list[RawNewsItem] = field(default_factory=list)
    rep_title: str = ""
    rep_tokens: set[str] = field(default_factory=set)
    rep_ngrams: set[str] = field(default_factory=set)
    centroid_tf: dict[str, float] = field(default_factory=dict)
    first_seen: datetime | None = None
    last_seen: datetime | None = None
    latest_ingested: datetime | None = None

    def add_item(self, item: RawNewsItem, tf_vec: dict[str, float], toks: set[str], ngrams: set[str]) -> None:
        self.items.append(item)
        if self.first_seen is None or item.published_at < self.first_seen:
            self.first_seen = item.published_at
            self.rep_title = item.title
        # Prefer primary official headline as representative if available
        if item.is_primary_official:
            self.rep_title = item.title
        if self.last_seen is None or item.published_at > self.last_seen:
            self.last_seen = item.published_at
        if self.latest_ingested is None or item.ingested_at > self.latest_ingested:
            self.latest_ingested = item.ingested_at
        n = len(self.items)
        merged: dict[str, float] = {}
        keys = set(self.centroid_tf.keys()) | set(tf_vec.keys())
        for k in keys:
            merged[k] = ((self.centroid_tf.get(k, 0.0) * (n - 1)) + tf_vec.get(k, 0.0)) / n
        norm = math.sqrt(sum(v * v for v in merged.values())) or 1.0
        self.centroid_tf = {k: v / norm for k, v in merged.items()}
        self.rep_tokens |= toks
        self.rep_ngrams |= ngrams


class IncrementalClusterer:
    """Online single-pass incremental clustering engine shared by streaming and batch backfill."""

    def __init__(self, sim_threshold: float = 0.34, window_hours: int = 48):
        self.sim_threshold = sim_threshold
        self.window = timedelta(hours=window_hours)
        self.clusters: list[ActiveCluster] = []
        self._seen_item_ids: set[str] = set()
        self._seen_norm_titles: dict[str, ActiveCluster] = {}
        self.exact_dedup_count = 0

    def process_item(self, item: RawNewsItem) -> tuple[ActiveCluster, bool, bool]:
        """Process one RawNewsItem. Returns (cluster, is_new_cluster, is_exact_dup)."""
        if item.item_id in self._seen_item_ids:
            self.exact_dedup_count += 1
            norm_t = re.sub(r"[^a-z0-9]", "", item.title.lower())
            if norm_t in self._seen_norm_titles:
                return self._seen_norm_titles[norm_t], False, True
            for c in reversed(self.clusters):
                if any(x.item_id == item.item_id for x in c.items):
                    return c, False, True

        self._seen_item_ids.add(item.item_id)
        norm_t = re.sub(r"[^a-z0-9]", "", item.title.lower())
        if norm_t in self._seen_norm_titles:
            c = self._seen_norm_titles[norm_t]
            if abs((item.published_at - c.first_seen).total_seconds()) <= self.window.total_seconds():
                self.exact_dedup_count += 1
                toks = set(normalize_tokens(item.title))
                c.add_item(item, token_tf(list(toks)), toks, char_ngrams(item.title))
                return c, False, True

        # Use clean title tokens (avoid noisy RSS aggregator HTML descriptions)
        toks_list = normalize_tokens(item.title)
        title_toks = set(toks_list)
        tf_vec = token_tf(toks_list)
        ngrams = char_ngrams(item.title)

        best_cluster: ActiveCluster | None = None
        best_score = 0.0
        for c in self.clusters:
            if c.last_seen and abs((item.published_at - c.last_seen).total_seconds()) > self.window.total_seconds():
                continue
            cos = cosine_sim(tf_vec, c.centroid_tf)
            jac_tok = jaccard_sim(title_toks, c.rep_tokens)
            jac_ng = jaccard_sim(ngrams, c.rep_ngrams)
            blended = 0.55 * cos + 0.25 * jac_tok + 0.20 * jac_ng
            if blended > best_score:
                best_score = blended
                best_cluster = c

        if best_cluster is not None and best_score >= self.sim_threshold:
            best_cluster.add_item(item, tf_vec, title_toks, ngrams)
            self._seen_norm_titles[norm_t] = best_cluster
            return best_cluster, False, False

        cid_seed = f"{item.published_at.isoformat()}|{item.title}".encode("utf-8", errors="ignore")
        cid = "evt_" + hashlib.sha256(cid_seed).hexdigest()[:12]
        new_c = ActiveCluster(cluster_id=cid, rep_title=item.title)
        new_c.add_item(item, tf_vec, title_toks, ngrams)
        self.clusters.append(new_c)
        self._seen_norm_titles[norm_t] = new_c
        return new_c, True, False

    def cluster_batch(self, items: list[RawNewsItem]) -> list[ActiveCluster]:
        sorted_items = sorted(items, key=lambda x: x.published_at)
        all_clusters: dict[str, ActiveCluster] = {}
        for it in sorted_items:
            c, _, _ = self.process_item(it)
            all_clusters[c.cluster_id] = c
        return sorted(all_clusters.values(), key=lambda c: c.first_seen or datetime.min)
