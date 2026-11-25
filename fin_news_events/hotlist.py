"""Intraday / daily move detection and news attribution (异动归因榜).

Price moves are the starting point. Impact scores and ranking of candidate
news never use future returns. A news-centered auxiliary list is optional.
"""
from __future__ import annotations

import json
import math
import re
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from fin_news_events.classifier import get_classifier
from fin_news_events.dedup_cluster import IncrementalClusterer
from fin_news_events.entity_mapper import extract_matched_entities, resolve_target
from fin_news_events.llm_clients import LiteLLMClient, PerplexityFactChecker
from fin_news_events.market_data import fetch_binance_klines, fetch_yahoo_bars
from fin_news_events.models import MYT, to_myt_str, to_utc_iso
from fin_news_events.scorer import compute_authority_verification, get_source_credibility, score_event
from fin_news_events.sources import (
    ConditionalHTTPClient,
    build_targeted_attribution_queries,
    fetch_binance_announcements,
    fetch_crypto_rss,
    fetch_google_news_rss,
    fetch_market_wrap_rss,
    fetch_nvidia_newsroom_rss,
    fetch_sec_company_filings,
)

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "outputs"
CACHE_DIR = OUT_DIR / "klines_cache"
ET = ZoneInfo("America/New_York")

CRYPTO_UNIVERSE = [
    ("BTCUSDT", "BTC/USDT", "crypto"),
    ("ETHUSDT", "ETH/USDT", "crypto"),
    ("SOLUSDT", "SOL/USDT", "crypto"),
    ("XRPUSDT", "XRP/USDT", "crypto"),
    ("BNBUSDT", "BNB/USDT", "crypto"),
    ("DOGEUSDT", "DOGE/USDT", "crypto"),
    ("ADAUSDT", "ADA/USDT", "crypto"),
]
EQUITY_UNIVERSE = [
    ("NVDA", "NVDA", "equity"),
    ("SMH", "SMH", "equity"),
    ("SOXX", "SOXX", "equity"),
    ("QQQ", "QQQ", "equity"),
    ("SPY", "SPY", "equity"),
    ("DIA", "DIA", "equity"),
    ("AAPL", "AAPL", "equity"),
    ("MSFT", "MSFT", "equity"),
    ("TSLA", "TSLA", "equity"),
]
MACRO_RATES_UNIVERSE = [
    ("DX-Y.NYB", "DXY", "fx"),
    ("^TNX", "US10Y", "rates"),
    ("^FVX", "US05Y", "rates"),
]

SYMBOL_KEYWORDS = {
    "BTC/USDT": ("bitcoin", "btc", "btc/usdt"),
    "ETH/USDT": ("ethereum", "ether", "eth ", "eth/", "ethusdt"),
    "SOL/USDT": ("solana", " sol ", "sol/"),
    "XRP/USDT": ("ripple", " xrp", "xrp/"),
    "BNB/USDT": ("binance coin", "bnb", "bnb/"),
    "DOGE/USDT": ("dogecoin", "doge"),
    "ADA/USDT": ("cardano", " ada", "ada/"),
    "NVDA": ("nvidia", "nvda", "jensen", "huang", "blackwell", "cuda"),
    "SMH": ("semiconductor", "chip stock", "chip stocks", "chipmaker", "nvidia", "broadcom", "amd", "tsmc", "smh", "ai chip"),
    "SOXX": ("semiconductor", "chip stock", "chip stocks", "chipmaker", "nvidia", "broadcom", "amd", "tsmc", "soxx", "ai chip"),
    "SPY": ("s&p", "s & p", "sp500", "s&p 500", "wall street", "us stocks", "stock market", "stocks "),
    "QQQ": ("nasdaq", "qqq", "tech stocks", "ai trade", "ai rally", "ai sell", "magnificent"),
    "DIA": ("dow jones", "dow ", "value rotation", "wall street", "blue-chip"),
    "AAPL": ("apple", "aapl", "iphone", "tim cook"),
    "MSFT": ("microsoft", "msft", "azure", "satya nadella"),
    "TSLA": ("tesla", "tsla", "elon musk", "ev "),
}

CRYPTO_ONLY_TOKENS = ("bitcoin", "btc", "ethereum", "eth ", "solana", "xrp", "dogecoin", "cardano", "crypto", "binance", "altcoin")
EQUITY_MACRO_TOKENS = (
    "nvidia", "nvda", "jensen", "huang", "nasdaq", "s&p", "dow", "wall street",
    "stock market", "stocks ", "us stocks", "chip", "semiconductor", "ai trade",
    "ai rally", "ai sell", "data center", "tariff", "tariffs", "fed ", "fomc",
    "pce", "cpi", "inflation", "treasury", "yield", "apple", "microsoft", "tesla", "anthropic",
)
MACRO_CATS = {"MACRO", "POLITICS_REG", "TRADFI"}


@dataclass
class AttributionConfig:
    lookback_days: int = 30
    daily_z_min: float = 1.25
    daily_ret_min_pct: float = 2.5
    bar_z_min: float = 2.5
    bar_z_vol_confirm: float = 1.8
    vol_z_min: float = 2.0
    bar_ret_min_pct: float = 1.2
    event_pre_hours: float = 6.0
    event_post_hours: float = 1.0
    us_event_pre_hours: float = 16.0
    us_event_post_hours: float = 9.0
    time_tau_hours: float = 4.0
    w_time: float = 0.30
    w_impact: float = 0.25
    w_heat: float = 0.15
    w_dir: float = 0.15
    w_rel: float = 0.15
    attr_score_min: float = 0.28
    llm_top_k: int = 5
    common_window_hours: float = 2.0
    news_hotlist_top_n: int = 10
    llm_model: str = "google/gemini-2.5-flash-lite"
    max_anomalies_for_llm: int = 10
    max_factchecks_per_day: int = 2
    novelty_lookback_days: int = 3
    news_heat_source_w: float = 1.0
    news_heat_article_w: float = 0.35


def _parse_iso(ts: str) -> datetime:
    s = (ts or "").strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _myt_date(dt: datetime) -> date:
    return dt.astimezone(MYT).date()


def day_bounds(d: date) -> tuple[datetime, datetime]:
    start = datetime(d.year, d.month, d.day, tzinfo=MYT)
    return start, start + timedelta(days=1)


def us_session_bounds_approx(d_et: date) -> tuple[datetime, datetime]:
    """Approximate US regular cash session bounds (09:30–16:00 ET, DST-aware) converted to UTC."""
    open_et = datetime(d_et.year, d_et.month, d_et.day, 9, 30, tzinfo=ET)
    close_et = datetime(d_et.year, d_et.month, d_et.day, 16, 0, tzinfo=ET)
    return open_et.astimezone(timezone.utc), close_et.astimezone(timezone.utc)


def _norm_headline(h: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (h or "").lower())


def verification_label(status: str) -> str:
    return {
        "OFFICIAL_PRIMARY": "官方一手",
        "MULTI_SOURCE_CONFIRMED": "多源确认",
        "SINGLE_TIER1_REPORTED": "单一权威（未交叉核实）",
        "UNVERIFIED_OR_RUMOR": "单源未核实",
    }.get(status or "", status or "未知核验")


def verification_tier_zh(tier: str) -> str:
    return {
        "confirmed": "confirmed（多源/官方确认）",
        "single_source": "single_source（单一权威）",
        "unverified": "unverified（单源未核实）",
    }.get(tier or "", tier or "unverified")


def news_heat(n_domains: int, n_articles: int, cfg: AttributionConfig) -> float:
    num = math.log(1.0 + cfg.news_heat_source_w * max(0, n_domains) + cfg.news_heat_article_w * max(0, n_articles))
    den = math.log(1.0 + cfg.news_heat_source_w * 3.0 + cfg.news_heat_article_w * 5.0)
    return round(num / den if den else 0.0, 4)


def _close_at_or_before(df: pd.DataFrame, ts: datetime) -> tuple[Optional[datetime], Optional[float]]:
    if df is None or df.empty:
        return None, None
    idx = df.index
    pos = idx.searchsorted(ts, side="right") - 1
    if pos < 0:
        return None, None
    return idx[pos].to_pydatetime(), float(df.iloc[pos]["close"])


def _cache_path(symbol: str, interval: str) -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    safe = symbol.replace("/", "").replace("^", "_")
    return CACHE_DIR / f"{safe}_{interval}.csv"


def _load_or_fetch(symbol: str, asset_class: str, interval: str, start: datetime, end: datetime) -> pd.DataFrame:
    path = _cache_path(symbol, interval)
    if path.exists():
        df = pd.read_csv(path, parse_dates=["ts"])
        if not df.empty:
            df["ts"] = pd.to_datetime(df["ts"], utc=True)
            df = df.set_index("ts").sort_index()
            fresh_tol = timedelta(hours=8 if asset_class in ("equity", "fx", "rates") else 2)
            if df.index[0] <= start + timedelta(hours=18) and df.index[-1] >= end - fresh_tol:
                return df[(df.index >= start - timedelta(hours=2)) & (df.index <= end + timedelta(hours=1))]
    if asset_class == "crypto":
        df = fetch_binance_klines(symbol, start, end, interval=interval)
    else:
        df = fetch_yahoo_bars(symbol, start, end, interval=interval)
    if not df.empty:
        df.reset_index().to_csv(path, index=False)
    return df


def fetch_universe_bars(
    cfg: AttributionConfig,
    end_utc: datetime,
    market: str = "all",
) -> dict[str, dict[str, pd.DataFrame]]:
    start = end_utc - timedelta(days=cfg.lookback_days + 8)
    frames: dict[str, dict[str, pd.DataFrame]] = {}
    jobs: list[tuple[str, str, str, str]] = []
    if market in ("crypto", "all"):
        for sym, label, cls in CRYPTO_UNIVERSE:
            jobs.append((sym, label, cls, "1h"))
            jobs.append((sym, label, cls, "15m"))
    if market in ("us", "all"):
        for sym, label, cls in EQUITY_UNIVERSE:
            jobs.append((sym, label, cls, "1h"))
            jobs.append((sym, label, cls, "15m"))
        for sym, label, cls in MACRO_RATES_UNIVERSE:
            jobs.append((sym, label, cls, "1h"))

    def _one(job: tuple[str, str, str, str]) -> tuple[str, str, pd.DataFrame]:
        _sym, label, cls, interval = job
        try:
            df = _load_or_fetch(_sym, cls, interval, start, end_utc + timedelta(hours=2))
        except Exception:
            df = pd.DataFrame()
        return label, interval, df

    with ThreadPoolExecutor(max_workers=6) as ex:
        futs = [ex.submit(_one, j) for j in jobs]
        for fut in as_completed(futs):
            label, interval, df = fut.result()
            frames.setdefault(label, {})[interval] = df
    return frames


def daily_returns_myt(df: pd.DataFrame, start_day: date, end_day: date) -> list[dict[str, Any]]:
    rows = []
    d = start_day
    while d <= end_day:
        start, end = day_bounds(d)
        ts0, px0 = _close_at_or_before(df, start)
        ts1, px1 = _close_at_or_before(df, end)
        complete = end <= datetime.now(timezone.utc)
        ret = (px1 / px0) - 1.0 if (px0 and px1 and px0 > 0 and ts1 and ts0 and ts1 > ts0) else None
        rows.append({
            "date": d.isoformat(),
            "start_px": px0,
            "end_px": px1,
            "start_ts": to_utc_iso(ts0) if ts0 else None,
            "end_ts": to_utc_iso(ts1) if ts1 else None,
            "ret": ret,
            "complete": complete,
        })
        d += timedelta(days=1)
    rets = [r["ret"] for r in rows]
    for i, r in enumerate(rows):
        hist = [x for x in rets[max(0, i - 30):i] if x is not None]
        if r["ret"] is None or len(hist) < 8:
            r["z"] = None
            r["hist_std"] = None
            continue
        std = float(np.std(hist, ddof=1)) if len(hist) > 1 else abs(float(np.mean(np.abs(hist))))
        std = max(std, 1e-4)
        r["z"] = r["ret"] / std
        r["hist_std"] = std
    return rows


def detect_sessions(df: pd.DataFrame, gap_hours: float = 8.0) -> list[dict[str, Any]]:
    """Split US equity bars into regular ET cash sessions (DST-aware EST/EDT)."""
    if df is None or df.empty or len(df) < 3:
        return []
    et_times = [ts.to_pydatetime().astimezone(ET) for ts in df.index]
    reg_mask = [
        (t.hour > 9 or (t.hour == 9 and t.minute >= 25))
        and (t.hour < 16 or (t.hour == 16 and t.minute <= 5))
        for t in et_times
    ]
    sub_df = df[reg_mask] if sum(reg_mask) >= 3 else df
    by_et_date: dict[str, list[int]] = defaultdict(list)
    for pos, ts in enumerate(sub_df.index):
        d_et = ts.to_pydatetime().astimezone(ET).date().isoformat()
        by_et_date[d_et].append(pos)

    recs: list[dict[str, Any]] = []
    for d_et in sorted(by_et_date.keys()):
        seg = sub_df.iloc[by_et_date[d_et]]
        if len(seg) < 2:
            continue
        open_px = float(seg.iloc[0]["open"]) if "open" in seg.columns else float(seg.iloc[0]["close"])
        close_px = float(seg.iloc[-1]["close"])
        open_ts = seg.index[0].to_pydatetime()
        close_ts = seg.index[-1].to_pydatetime()
        recs.append({
            "session_date_et": d_et,
            "open_ts": open_ts,
            "close_ts": close_ts,
            "open_px": open_px,
            "close_px": close_px,
            "ret": (close_px / open_px - 1.0) if open_px else None,
            "open_myt": to_myt_str(open_ts),
            "close_myt": to_myt_str(close_ts),
            "open_date_myt": _myt_date(open_ts).isoformat(),
            "close_date_myt": _myt_date(close_ts).isoformat(),
        })
    for i, r in enumerate(recs):
        if i == 0:
            r["prev_close"] = None
            r["prev_close_ts"] = None
            r["prev_ret_incl_gap"] = None
            r["ret_incl_gap"] = r["ret"]
            r["gap_ret"] = None
        else:
            prev_c = recs[i - 1]["close_px"]
            r["prev_close"] = prev_c
            r["prev_close_ts"] = recs[i - 1]["close_ts"]
            r["prev_ret_incl_gap"] = recs[i - 1].get("ret_incl_gap")
            r["ret_incl_gap"] = (r["close_px"] / prev_c - 1.0) if prev_c else r["ret"]
            r["gap_ret"] = (r["open_px"] / prev_c - 1.0) if prev_c and r["open_px"] else None
    rets = [r.get("ret_incl_gap") for r in recs]
    for i, r in enumerate(recs):
        hist = [x for x in rets[max(0, i - 20):i] if x is not None]
        if r.get("ret_incl_gap") is None or len(hist) < 5:
            r["z"] = None
            r["hist_std"] = None
            continue
        std = float(np.std(hist, ddof=1)) if len(hist) > 1 else max(abs(float(np.mean(np.abs(hist)))), 1e-4)
        std = max(std, 1e-4)
        r["z"] = r["ret_incl_gap"] / std
        r["hist_std"] = std
    return recs


def detect_windows(
    df: pd.DataFrame,
    interval: str,
    day_start: datetime,
    day_end: datetime,
    cfg: AttributionConfig,
) -> list[dict[str, Any]]:
    if df is None or df.empty or len(df) < 30:
        return []
    look = df[df.index >= (day_start - timedelta(days=10))].copy()
    if look.empty:
        return []
    look["ret"] = look["close"].pct_change()
    look["vol"] = look["volume"].astype(float)
    look["ret_std"] = look["ret"].rolling(96 if interval == "15m" else 48, min_periods=20).std().shift(1)
    look["vol_med"] = look["vol"].rolling(96 if interval == "15m" else 48, min_periods=20).median().shift(1)
    look["vol_std"] = look["vol"].rolling(96 if interval == "15m" else 48, min_periods=20).std().shift(1)

    day = look[(look.index >= day_start) & (look.index < day_end)]
    flags = []
    for ts, row in day.iterrows():
        ret = row["ret"]
        if ret is None or (isinstance(ret, float) and not math.isfinite(ret)):
            continue
        rstd = float(row["ret_std"]) if pd.notna(row["ret_std"]) else None
        rz = (float(ret) / rstd) if rstd and rstd > 1e-6 else None
        vstd = float(row["vol_std"]) if pd.notna(row["vol_std"]) else None
        vmed = float(row["vol_med"]) if pd.notna(row["vol_med"]) else None
        vz = None
        if vstd and vstd > 0 and pd.notna(row["vol"]):
            base = vmed if vmed is not None else 0.0
            vz = (float(row["vol"]) - base) / vstd
        hit = False
        if rz is not None and abs(rz) >= cfg.bar_z_min:
            hit = True
        elif rz is not None and vz is not None and abs(rz) >= cfg.bar_z_vol_confirm and vz >= cfg.vol_z_min:
            hit = True
        elif abs(float(ret) * 100.0) >= cfg.bar_ret_min_pct:
            hit = True
        if hit:
            flags.append({
                "ts": ts.to_pydatetime(),
                "ret_pct": float(ret) * 100.0,
                "ret_z": rz,
                "vol_z": vz,
                "close": float(row["close"]),
                "volume": float(row["vol"]) if pd.notna(row["vol"]) else None,
            })
    if not flags:
        return []

    windows: list[list[dict[str, Any]]] = []
    gap = timedelta(minutes=20 if interval == "15m" else 70)
    cur = [flags[0]]
    for bar in flags[1:]:
        if bar["ts"] - cur[-1]["ts"] <= gap:
            cur.append(bar)
        else:
            windows.append(cur)
            cur = [bar]
    windows.append(cur)

    out = []
    for bars in windows:
        peak = max(bars, key=lambda b: abs(b["ret_z"] or 0.0))
        start = bars[0]
        end = bars[-1]
        first_ts = start["ts"]
        ret0 = start["ret_pct"] / 100.0
        start_px = start["close"] / (1.0 + ret0) if abs(1.0 + ret0) > 1e-9 else start["close"]
        end_px = end["close"]
        cum = (end_px / start_px - 1.0) * 100.0 if start_px else start["ret_pct"]
        out.append({
            "interval": interval,
            "jump_start_utc": to_utc_iso(first_ts),
            "jump_start_myt": to_myt_str(first_ts),
            "window_end_utc": to_utc_iso(end["ts"]),
            "window_end_myt": to_myt_str(end["ts"]),
            "peak_bar_myt": to_myt_str(peak["ts"]),
            "n_bars": len(bars),
            "peak_ret_pct": round(peak["ret_pct"], 3),
            "peak_ret_z": round(peak["ret_z"], 2) if peak["ret_z"] is not None else None,
            "peak_vol_z": round(peak["vol_z"], 2) if peak["vol_z"] is not None else None,
            "cum_ret_pct": round(cum, 3),
            "direction": "UP" if cum >= 0 else "DOWN",
        })
    out.sort(key=lambda w: abs(w.get("peak_ret_z") or 0.0), reverse=True)
    return out


def load_event_corpus(extra_files: list[Path] | None = None) -> list[dict[str, Any]]:
    files = [
        OUT_DIR / "timeline_btcusdt_7d.json",
        OUT_DIR / "timeline_nvda_7d.json",
        OUT_DIR / "timeline_smoke_jev_1d.json",
        OUT_DIR / "timeline_midterm2026_btcusdt.json",
        OUT_DIR / "timeline_midterm2026_nvda.json",
    ]
    if extra_files:
        files.extend(extra_files)
    by_id: dict[str, dict] = {}
    for fp in files:
        if not fp.exists():
            continue
        for row in json.loads(fp.read_text(encoding="utf-8")):
            eid = row.get("event_id")
            if not eid:
                continue
            prev = by_id.get(eid)
            if prev is None or int(row.get("source_count") or 0) >= int(prev.get("source_count") or 0):
                try:
                    row = dict(row)
                    row["_pub_dt"] = _parse_iso(row["published_at_utc"])
                except Exception:
                    continue
                by_id[eid] = row
    return list(by_id.values())


def merge_event_pools(*pools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    for pool in pools:
        for row in pool:
            eid = row.get("event_id")
            if not eid:
                continue
            row = dict(row)
            if "_pub_dt" not in row:
                try:
                    row["_pub_dt"] = _parse_iso(row["published_at_utc"])
                except Exception:
                    continue
            prev = by_id.get(eid)
            if prev is None or int(row.get("source_count") or 0) >= int(prev.get("source_count") or 0):
                by_id[eid] = row
    return list(by_id.values())


def collect_attribution_news(
    anomalous_symbols: list[str],
    market: str,
    target_dates: list[date],
    win_lo: datetime,
    win_hi: datetime,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Automatically fetch market-wrap RSS + official feeds + targeted Google News queries and cluster/score."""
    http = ConditionalHTTPClient(timeout=12)
    raw_items = []
    stats = []

    include_us = market in ("us", "all") or any(not s.endswith("/USDT") for s in anomalous_symbols)
    include_crypto = market in ("crypto", "all") or any(s.endswith("/USDT") for s in anomalous_symbols)

    if include_us:
        mw_items, mw_stats = fetch_market_wrap_rss(http, win_lo, win_hi, conditional=False)
        raw_items.extend(mw_items)
        stats.extend(mw_stats)

        nv_items, nv_st = fetch_nvidia_newsroom_rss(http, win_lo, win_hi, conditional=False)
        raw_items.extend(nv_items)
        stats.append(nv_st)

        sec_items, sec_st = fetch_sec_company_filings(http, "0001045810", "NVDA", win_lo, win_hi, conditional=False)
        raw_items.extend(sec_items)
        stats.append(sec_st)

    if include_crypto:
        c_items, c_stats = fetch_crypto_rss(http, win_lo, win_hi, conditional=False)
        raw_items.extend(c_items)
        stats.extend(c_stats)

        b_items, b_st = fetch_binance_announcements(http, win_lo, win_hi, conditional=False)
        raw_items.extend(b_items)
        stats.append(b_st)

    ref_date = max(target_dates)
    queries = build_targeted_attribution_queries(anomalous_symbols, market, ref_date)
    for layer, tag, q in queries:
        q_items, q_st = fetch_google_news_rss(
            http,
            query=q,
            retrieval_layer=layer,
            query_tag=tag,
            start_dt=win_lo,
            end_dt=win_hi,
            conditional=False,
        )
        raw_items.extend(q_items)
        stats.append(q_st)

    clusterer = IncrementalClusterer(sim_threshold=0.34, window_hours=48)
    clusters = clusterer.cluster_batch(raw_items)
    clf_backend = get_classifier("auto")
    primary_sym = "NVDA" if market == "us" else "BTC/USDT"
    profile = resolve_target(primary_sym)

    recent_subcats: Counter[str] = Counter()
    events_out: list[dict[str, Any]] = []
    for c in clusters:
        combined = f"{c.rep_title}. " + " ".join(it.summary[:200] for it in c.items[:2] if it.summary)
        matched, layer = extract_matched_entities(combined, profile)
        if any(it.retrieval_layer == "DIRECT" for it in c.items) and layer == "DIRECT":
            final_layer = "DIRECT"
        elif layer == "DIRECT":
            final_layer = "DIRECT"
        else:
            final_layer = "CROSS_MARKET"

        clf = clf_backend.classify(combined, profile.canonical_symbol, final_layer)
        sc = score_event(
            cluster=c,
            clf=clf,
            profile=profile,
            retrieval_layer=final_layer,
            recent_same_subcat_count=recent_subcats.get(clf.subcategory, 0),
        )
        recent_subcats[clf.subcategory] += 1
        pub_dt = c.first_seen or datetime.now(timezone.utc)
        sources_list = []
        seen_urls: set[str] = set()
        for it in sorted(c.items, key=lambda x: x.published_at):
            if it.url in seen_urls:
                continue
            seen_urls.add(it.url)
            sources_list.append({
                "name": it.source_name,
                "feed": it.source_feed,
                "domain": it.source_domain,
                "url": it.url,
                "published_at_myt": to_myt_str(it.published_at),
                "credibility": round(get_source_credibility(it.source_name, it.source_domain), 2),
                "is_primary_official": it.is_primary_official,
            })
        unique_domains = sorted({s["domain"] for s in sources_list if s.get("domain")})
        best_summary = next((it.summary for it in c.items if it.summary), "")
        ev_dict = {
            "event_id": c.cluster_id,
            "target_symbol": profile.canonical_symbol,
            "retrieval_layer": final_layer,
            "published_at_utc": to_utc_iso(pub_dt),
            "published_at_myt": to_myt_str(pub_dt),
            "category": clf.category,
            "subcategory": clf.subcategory,
            "headline": c.rep_title,
            "summary": best_summary,
            "matched_entities": matched,
            "direction": clf.direction,
            "impact_score": sc.impact_score,
            "confidence": round(clf.confidence, 3),
            "novelty": sc.novelty,
            "verification_status": sc.verification_status,
            "source_credibility": sc.source_credibility,
            "source_count": len(sources_list),
            "unique_domains": unique_domains,
            "sources": sources_list,
            "classifier_mode": getattr(clf_backend, "mode_name", "auto"),
            "_pub_dt": pub_dt,
        }
        events_out.append(ev_dict)

    meta = {
        "raw_items_fetched": len(raw_items),
        "clusters_created": len(events_out),
        "queries_run": [tag for _, tag, _ in queries],
        "source_stats": [
            {"source": st.source_name, "status": st.status, "items": st.items_fetched}
            for st in stats
        ],
    }
    return events_out, meta


def _n_domains(row: dict) -> int:
    doms = row.get("unique_domains") or []
    if isinstance(doms, list) and doms:
        return len({str(d).lower() for d in doms if str(d).lower() not in ("unknown", "news.google.com")}) or 1
    return 1 if row.get("source_count") else 0


def relevance_score(row: dict, symbol: str) -> float:
    hl = f"{row.get('headline','')} {row.get('summary','')}".lower()
    is_crypto_target = symbol.endswith("/USDT")
    has_crypto_only = any(t in hl for t in CRYPTO_ONLY_TOKENS)
    has_eq_macro = any(t in hl for t in EQUITY_MACRO_TOKENS)

    if not is_crypto_target and has_crypto_only and not has_eq_macro:
        return 0.15

    keys = SYMBOL_KEYWORDS.get(symbol, ())
    if any(k.strip() and k in hl for k in keys):
        return 1.0 if row.get("retrieval_layer") == "DIRECT" or symbol in (row.get("target_symbol") or "") else 0.90
    if symbol in (row.get("target_symbol") or "") and row.get("retrieval_layer") == "DIRECT" and has_eq_macro:
        return 0.90
    if not is_crypto_target and has_eq_macro:
        cat = row.get("category") or ""
        if cat in MACRO_CATS or cat == "TECH_AI":
            return 0.80
    cat = row.get("category") or ""
    if cat in MACRO_CATS:
        return 0.72 if is_crypto_target else 0.65
    if is_crypto_target and cat == "CRYPTO":
        return 0.32
    if not is_crypto_target and cat == "TECH_AI":
        return 0.68 if symbol in ("NVDA", "SMH", "SOXX") else 0.50
    return 0.18


def direction_align(event_dir: str, move_dir: str) -> float:
    ed = (event_dir or "NEUTRAL").upper()
    if ed in ("NEUTRAL", "MIXED", ""):
        return 0.45
    if move_dir == "UP":
        return 1.0 if ed == "BULLISH" else 0.0
    return 1.0 if ed == "BEARISH" else 0.0


def score_candidates(
    events: list[dict],
    jump_start: datetime,
    move_dir: str,
    symbol: str,
    cfg: AttributionConfig,
    pre_hours: Optional[float] = None,
    post_hours: Optional[float] = None,
) -> list[dict[str, Any]]:
    pre_h = pre_hours if pre_hours is not None else cfg.event_pre_hours
    post_h = post_hours if post_hours is not None else cfg.event_post_hours
    lo = jump_start - timedelta(hours=pre_h)
    hi = jump_start + timedelta(hours=post_h)
    scored = []
    for ev in events:
        pub = ev.get("_pub_dt")
        if pub is None:
            continue
        if pub < lo or pub > hi:
            continue
        dt_h = (pub - jump_start).total_seconds() / 3600.0
        ex_post = dt_h > 0.05
        decay = math.exp(-abs(dt_h) / cfg.time_tau_hours)
        time_prox = (0.45 * decay) if ex_post else decay
        heat = news_heat(_n_domains(ev), int(ev.get("source_count") or 1), cfg)
        impact = float(ev.get("impact_score") or 0.0) / 100.0
        rel = relevance_score(ev, symbol)
        d_al = direction_align(str(ev.get("direction") or ""), move_dir)
        score = (
            cfg.w_time * time_prox
            + cfg.w_impact * impact
            + cfg.w_heat * heat
            + cfg.w_dir * d_al
            + cfg.w_rel * rel
        )
        srcs = [
            {
                "name": s.get("name"),
                "url": s.get("url"),
                "domain": s.get("domain"),
                "is_primary_official": bool(s.get("is_primary_official")),
            }
            for s in (ev.get("sources") or [])[:6]
        ]
        auth = compute_authority_verification(srcs, str(ev.get("verification_status") or ""))
        scored.append({
            "event_id": ev.get("event_id"),
            "headline": ev.get("headline"),
            "category": ev.get("category"),
            "subcategory": ev.get("subcategory"),
            "direction": ev.get("direction"),
            "impact_score": ev.get("impact_score"),
            "target_symbol": ev.get("target_symbol"),
            "retrieval_layer": ev.get("retrieval_layer"),
            "published_at_myt": ev.get("published_at_myt") or to_myt_str(pub),
            "published_at_utc": ev.get("published_at_utc"),
            "source_count": ev.get("source_count"),
            "unique_domains": ev.get("unique_domains") or [],
            "sources": srcs,
            "verification_status": ev.get("verification_status"),
            "verification_label": verification_label(ev.get("verification_status") or ""),
            "verification_tier": auth["verification_tier"],
            "independent_sources_count": auth["independent_sources_count"],
            "authority_score": auth["authority_score"],
            "hours_vs_jump": round(dt_h, 2),
            "timing": "事后解释/报道" if ex_post else "事前或同步",
            "ex_post": ex_post,
            "time_prox": round(time_prox, 4),
            "heat": heat,
            "relevance": round(rel, 3),
            "dir_align": d_al,
            "attr_score": round(score, 4),
        })
    scored.sort(key=lambda x: x["attr_score"], reverse=True)
    return scored


CAUSE_THEME_RULES: list[tuple[str, str, re.Pattern[str]]] = [
    ("rally_unwind", "回吐前一日暴涨 / 获利了结", re.compile(r"\b(fizzl\w*|unwind\w*|gave back|giving up|retreat\w*|fad\w*|profit[- ]taking|cool\w*|after.*rally|fueled rally|fueled gains|slips? back|pullback|rebound.*fades)", re.I)),
    ("huang_reinstatement", "黄仁勋复职与董事会/治理风波", re.compile(r"\b(reinstat\w*|jensen huang|board reversal|code of conduct|succession|town hall|apologiz\w*|sidestep\w*|doj probe|comeback|rehired)", re.I)),
    ("tariffs_trade", "关税与贸易摩擦预期", re.compile(r"\b(tariff\w*|import duties|excess.*capacity|trade probe|export control\w*)", re.I)),
    ("ai_capex_valuation", "AI 资本开支回报与估值/个股情绪", re.compile(r"\b(capex|data center spending|ai debt|ai trade|valuation|anthropic|analog devices|ipo|chip stocks (?:fall|lower|slide|drop))", re.I)),
    ("fed_inflation_rates", "美联储利率 / PCE / 通胀预期", re.compile(r"\b(fed|rate hike|rate cut|pce|cpi|inflation|consumer confidence|treasury|yield)", re.I)),
    ("crypto_etf_flows", "比特币现货 ETF 资金流出与加密原生因素", re.compile(r"\b(etf.*outflow\w*|outflow\w*.*etf|net outflow\w*|hash rate|liquidat\w*|binance)", re.I)),
]


def _cause_theme(headline: str) -> tuple[str, str]:
    for key, label, pat in CAUSE_THEME_RULES:
        if pat.search(headline or ""):
            return key, label
    return "other_" + _norm_headline(headline)[:24], headline[:60]


def aggregate_candidate_causes(
    candidates: list[dict[str, Any]],
    max_causes: int = 5,
    asset_class: str = "equity",
) -> list[dict[str, Any]]:
    """Group candidate articles into distinct ranked causes with cross-source verification."""
    if not candidates:
        return []
    pool = candidates
    if asset_class == "equity":
        eq_pool = [c for c in candidates if c.get("relevance", 0) >= 0.40]
        if eq_pool:
            pool = eq_pool

    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for c in pool:
        tkey, _tlabel = _cause_theme(c.get("headline") or "")
        buckets[tkey].append(c)

    causes: list[dict[str, Any]] = []
    for tkey, items in buckets.items():
        items_sorted = sorted(
            items,
            key=lambda x: (
                x.get("attr_score", 0.0) + 0.06 * x.get("authority_score", 0.0) + (0.04 if not x.get("ex_post") else 0.0)
            ),
            reverse=True,
        )
        rep = items_sorted[0]
        all_srcs: list[dict[str, Any]] = []
        seen_urls: set[str] = set()
        for it in items_sorted:
            for s in it.get("sources") or []:
                u = s.get("url") or ""
                if u and u in seen_urls:
                    continue
                if u:
                    seen_urls.add(u)
                all_srcs.append(s)
        auth = compute_authority_verification(all_srcs)
        has_pre = any(not it.get("ex_post") for it in items)
        has_post = any(it.get("ex_post") for it in items)
        if has_pre and has_post:
            timing_label = "含事前驱动 + 盘中/收盘跟进"
        elif has_pre:
            timing_label = "事前或同步"
        else:
            timing_label = "事后解释/报道"
        earliest = min(items, key=lambda x: x.get("hours_vs_jump", 0.0))
        _, theme_zh = _cause_theme(rep.get("headline") or "")
        causes.append({
            "theme_key": tkey,
            "theme_label_zh": theme_zh,
            "headline": rep.get("headline"),
            "attr_score": rep.get("attr_score"),
            "earliest_published_at_myt": earliest.get("published_at_myt"),
            "earliest_hours_vs_jump": earliest.get("hours_vs_jump"),
            "timing": timing_label,
            "ex_post_only": not has_pre,
            "independent_sources_count": auth["independent_sources_count"],
            "credible_sources_count": auth["credible_sources_count"],
            "independent_domains": auth["independent_domains"],
            "authority_score": auth["authority_score"],
            "verification_tier": auth["verification_tier"],
            "verification_tier_zh": verification_tier_zh(auth["verification_tier"]),
            "article_count": len(items),
            "top_sources": all_srcs[:5],
        })
    causes.sort(
        key=lambda c: (
            c.get("attr_score", 0.0) + 0.08 * min(c.get("credible_sources_count", 0), 3) * 0.33 + 0.05 * c.get("authority_score", 0.0)
        ),
        reverse=True,
    )
    return causes[:max_causes]


def is_anomalous_daily(row: dict, cfg: AttributionConfig) -> bool:
    if row.get("ret") is None:
        return False
    z = row.get("z")
    ret_pct = abs(row["ret"]) * 100.0
    if z is not None and abs(z) >= cfg.daily_z_min:
        return True
    if ret_pct >= cfg.daily_ret_min_pct:
        return True
    return False


def _anomaly_magnitude(daily: dict, windows: list[dict]) -> float:
    mag = 0.0
    if daily.get("z") is not None:
        mag = max(mag, abs(float(daily["z"])))
    if daily.get("ret") is not None:
        mag = max(mag, abs(float(daily["ret"])) * 100.0 / 2.5)
    if windows:
        mag = max(mag, abs(float(windows[0].get("peak_ret_z") or 0.0)))
    return mag


def _llm_payload(
    item: dict,
    candidates: list[dict],
    top_causes: list[dict] | None = None,
    macro_snapshot: dict[str, Any] | None = None,
    session_tape: list[dict[str, Any]] | None = None,
) -> str:
    lines = [
        f"标的或组合: {item['symbol']}",
        "若为 cross_asset_spillover：区分公司/指数自身新闻与风险偏好向加密的溢出，不要把只解释 NVDA 的新闻硬套到山寨币。",
        f"日期: {item['date']} (输出时间均为 UTC+8)",
        f"当日涨跌: {item.get('daily_ret_pct')}%  z={item.get('daily_z')}  前一日涨跌={item.get('prev_session_ret_pct')}%  对前一日涨幅回吐={item.get('giveback_pct')}%  完整会话={item.get('day_complete')}",
        f"异动窗口: {item.get('primary_window')}",
        f"窗口累计涨跌: {item.get('window_cum_ret_pct')}%  方向={item.get('move_dir')}",
    ]
    if session_tape:
        tape_s = "，".join(f"{t['symbol']} {t['ret_pct']:+.2f}%" for t in session_tape if t.get("ret_pct") is not None)
        if tape_s:
            lines.append(f"同会话板块/大盘行情切片: {tape_s}")
    if macro_snapshot:
        ms = []
        for k, v in macro_snapshot.items():
            if isinstance(v, dict) and v.get("ret_pct") is not None:
                ms.append(f"{k} {v['close']:.3f} ({v['ret_pct']:+.2f}% vs 上日美股收盘)")
        if ms:
            lines.append(f"同会话宏观/利率: {'；'.join(ms)}")
    if top_causes:
        lines.append("已聚合去重的候选原因（含独立来源数、权威度与事前/事后标记）:")
        for i, tc in enumerate(top_causes[:5], 1):
            doms = ",".join((tc.get("independent_domains") or [])[:4])
            lines.append(
                f"{i}. [{tc['timing']}] 主题={tc['theme_label_zh']} | 核验={tc['verification_tier']} "
                f"(独立源={tc['independent_sources_count']} [{doms}], 权威={tc['authority_score']}) "
                f"归因分={tc['attr_score']} | {tc['headline']}"
            )
    lines.append("原始候选新闻 Top:")
    if not candidates:
        lines.append("（窗口前后未检索到事件簇）")
    for i, c in enumerate(candidates[:5], 1):
        lines.append(
            f"{i}. [{c['timing']}] {c['published_at_myt']} | {c['category']}/{c['subcategory']} | "
            f"核验={c.get('verification_tier')} 权威={c.get('authority_score')} 归因分={c['attr_score']} | {c['headline']}"
        )
    return "\n".join(lines)


def _apply_llm(
    client: LiteLLMClient,
    item: dict,
    cfg: AttributionConfig,
    macro_snapshot: dict[str, Any] | None = None,
    session_tape: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    cands = item.get("candidates") or []
    top = cands[: cfg.llm_top_k]
    top_causes = item.get("top_causes") or []
    weak = (not top) or (top[0]["attr_score"] < cfg.attr_score_min)
    if weak:
        return {
            "attribution_zh": "未找到明确新闻，可能为流动性/清算/技术面",
            "confidence": 0.0,
            "verdict": "NO_CLEAR_NEWS",
            "llm_status": "SKIPPED_WEAK_EVIDENCE",
            "prompt_tokens": 0,
            "completion_tokens": 0,
        }
    res = client.attribute_price_move(_llm_payload(item, top, top_causes, macro_snapshot, session_tape))
    return {
        "attribution_zh": res.attribution_zh or "未找到明确新闻，可能为流动性/清算/技术面",
        "confidence": res.confidence,
        "verdict": res.verdict if res.status == "OK" else "NO_CLEAR_NEWS",
        "llm_status": res.status,
        "prompt_tokens": res.prompt_tokens,
        "completion_tokens": res.completion_tokens,
        "llm_error": res.raw_error or "",
    }


def group_common_factors(items: list[dict], cfg: AttributionConfig) -> list[dict[str, Any]]:
    """Cluster overlapping windows within the same asset class."""
    def _jump(it: dict) -> datetime | None:
        pw = it.get("primary_window") or {}
        if pw.get("jump_start_utc"):
            return _parse_iso(pw["jump_start_utc"])
        return None

    def _cluster(subset: list[dict]) -> list[list[dict]]:
        unused = list(subset)
        clusters: list[list[dict]] = []
        while unused:
            a = unused.pop(0)
            ja = _jump(a)
            if ja is None:
                continue
            members = [a]
            rest = []
            for b in unused:
                jb = _jump(b)
                if jb is None:
                    continue
                if abs((ja - jb).total_seconds()) <= cfg.common_window_hours * 3600 and a["move_dir"] == b["move_dir"]:
                    members.append(b)
                else:
                    rest.append(b)
            unused = rest
            if len(members) >= 2:
                clusters.append(members)
        return clusters

    def _shared_candidates(members: list[dict], min_share: int) -> list[dict]:
        count_hl: dict[str, dict] = {}
        for m in members:
            seen = set()
            for c in m.get("candidates") or []:
                key = _norm_headline(c["headline"])
                if not key or key in seen:
                    continue
                seen.add(key)
                rec = count_hl.get(key) or {"n": 0, "cand": c, "symbols": []}
                rec["n"] += 1
                rec["symbols"].append(m["symbol"])
                if c["attr_score"] > rec["cand"]["attr_score"]:
                    rec["cand"] = c
                count_hl[key] = rec
        shared = []
        for rec in sorted(count_hl.values(), key=lambda x: (x["n"], x["cand"]["attr_score"]), reverse=True):
            if rec["n"] < min_share and rec["cand"].get("category") not in MACRO_CATS:
                continue
            c = dict(rec["cand"])
            c["shared_by"] = rec["symbols"]
            c["share_n"] = rec["n"]
            shared.append(c)
        shared.sort(key=lambda c: (c.get("share_n") or 0, c["attr_score"]), reverse=True)
        return shared[:12]

    def _pack(members: list[dict], kind: str) -> dict[str, Any]:
        members = sorted(members, key=lambda m: m["magnitude"], reverse=True)
        symbols = [m["symbol"] for m in members]
        js = next((_jump(m) for m in members if _jump(m) is not None), None)
        shared = _shared_candidates(members, min_share=2 if len(members) >= 3 else 1)
        cls_kind = "equity" if kind == "equity_common" else "crypto"
        return {
            "id": "grp_" + kind + "_" + "_".join(s.replace("/", "") for s in symbols[:6]),
            "kind": kind,
            "date": members[0]["date"],
            "symbols": symbols,
            "move_dir": members[0]["move_dir"],
            "jump_start_myt": to_myt_str(js) if js else members[0].get("primary_window", {}).get("jump_start_myt"),
            "members": [
                {"id": m["id"], "symbol": m["symbol"], "daily_ret_pct": m.get("daily_ret_pct"), "daily_z": m.get("daily_z")}
                for m in members
            ],
            "candidates": shared,
            "top_causes": aggregate_candidate_causes(shared, max_causes=5, asset_class=cls_kind),
        }

    cryptos = [it for it in items if it["asset_class"] == "crypto"]
    equities = [it for it in items if it["asset_class"] == "equity"]
    groups: list[dict[str, Any]] = []
    for cl in _cluster(cryptos):
        if len(cl) >= 2:
            groups.append(_pack(cl, "crypto_common"))
    for cl in _cluster(equities):
        if len(cl) >= 2:
            groups.append(_pack(cl, "equity_common"))

    for cg in [g for g in groups if g["kind"] == "crypto_common"]:
        for eg in [g for g in groups if g["kind"] == "equity_common"]:
            if cg["move_dir"] != eg["move_dir"]:
                continue
            c_ids = {m["id"] for m in cg["members"]}
            e_ids = {m["id"] for m in eg["members"]}
            c_items = [it for it in items if it["id"] in c_ids]
            e_items = [it for it in items if it["id"] in e_ids]
            jc = [_jump(x) for x in c_items if _jump(x)]
            je = [_jump(x) for x in e_items if _jump(x)]
            if not jc or not je:
                continue
            if min(abs((a - b).total_seconds()) for a in jc for b in je) <= cfg.common_window_hours * 3600:
                link = _pack(c_items + e_items, "cross_asset_spillover")
                link["candidates"] = [
                    c for c in link["candidates"]
                    if c.get("category") in MACRO_CATS or c.get("share_n", 0) >= 3
                    or any(k in (c.get("headline") or "").lower() for k in ("crypto", "bitcoin", "nasdaq", "stock", "risk", "ai trade", "nvidia"))
                ][:8]
                link["top_causes"] = aggregate_candidate_causes(link["candidates"], max_causes=4, asset_class="crypto")
                groups.append(link)
    return groups


def auxiliary_news_hotlist(events: list[dict], day: date, prev_headlines: list[str], cfg: AttributionConfig) -> list[dict[str, Any]]:
    start, end = day_bounds(day)
    day_ev = [e for e in events if e.get("_pub_dt") and start <= e["_pub_dt"] < end]
    buckets: dict[str, list[dict]] = defaultdict(list)
    for e in day_ev:
        buckets[_norm_headline(e.get("headline") or "") or e["event_id"]].append(e)
    prev_norms = [_norm_headline(h) for h in prev_headlines if h]
    items = []
    for key, evs in buckets.items():
        evs.sort(key=lambda x: (-float(x.get("impact_score") or 0), -int(x.get("source_count") or 0)))
        ev = evs[0]
        nov = 1.0
        if key and key in prev_norms:
            nov = 0.35
        else:
            toks = set(re.findall(r"[a-z0-9]{3,}", (ev.get("headline") or "").lower()))
            best = 0.0
            for h in prev_headlines:
                ot = set(re.findall(r"[a-z0-9]{3,}", h.lower()))
                if toks and ot:
                    best = max(best, len(toks & ot) / len(toks | ot))
            if best >= 0.6:
                nov = 0.5
            elif best >= 0.4:
                nov = 0.75
        heat = news_heat(_n_domains(ev), int(ev.get("source_count") or 1), cfg)
        cred = float(ev.get("source_credibility") or 0.55)
        impact = float(ev.get("impact_score") or 0.0)
        hot = impact * heat * nov * cred
        srcs = [
            {"name": s.get("name"), "url": s.get("url"), "domain": s.get("domain")}
            for s in (ev.get("sources") or [])[:4]
        ]
        auth = compute_authority_verification(srcs, str(ev.get("verification_status") or ""))
        items.append({
            "event_id": ev.get("event_id"),
            "headline": ev.get("headline"),
            "category": ev.get("category"),
            "subcategory": ev.get("subcategory"),
            "hot_score": round(hot, 3),
            "impact_score": impact,
            "heat": heat,
            "novelty": nov,
            "credibility": cred,
            "published_at_myt": ev.get("published_at_myt"),
            "verification_label": verification_label(ev.get("verification_status") or ""),
            "verification_status": ev.get("verification_status"),
            "verification_tier": auth["verification_tier"],
            "sources": srcs,
            "related_symbols": sorted({e.get("target_symbol") for e in evs if e.get("target_symbol")}),
            "price_reaction_display": {
                e.get("target_symbol"): _fmt_price(e.get("market_reaction"))
                for e in evs
                if e.get("target_symbol")
            },
            "note": "价格反应仅事后展示，不参与本辅助热榜排序",
        })
    items.sort(key=lambda x: x["hot_score"], reverse=True)
    return items[: cfg.news_hotlist_top_n]


def _fmt_price(mr: Optional[dict]) -> str:
    if not mr:
        return "暂无对齐行情"
    r24 = mr.get("ret_24h")
    ab = mr.get("abnormal_ret_24h")
    px = mr.get("anchor_price")
    note = mr.get("data_note") or ""
    if r24 is None:
        return f"24h 窗口未结束（锚定 {px}，{note or '待窗口'}）"
    parts = [f"24h {r24:+.2f}%"]
    if ab is not None:
        parts.append(f"Ab24h {ab:+.2f}%")
    if px is not None:
        parts.append(f"锚定 {px}")
    parts.append("仅展示，不参与排序")
    return " | ".join(parts)


def compute_us_macro_snapshot(
    frames: dict[str, dict[str, pd.DataFrame]],
    sess_open_ts: datetime,
    sess_close_ts: datetime,
    prev_close_ts: Optional[datetime],
) -> dict[str, Any]:
    """Compute DXY and Treasury yield changes aligned to the exact US equity cash session."""
    snap: dict[str, Any] = {}
    for _sym, label, _cls in MACRO_RATES_UNIVERSE:
        df1 = frames.get(label, {}).get("1h")
        if df1 is None or df1.empty:
            continue
        t_close, p_close = _close_at_or_before(df1, sess_close_ts + timedelta(minutes=10))
        t_ref = prev_close_ts or (sess_open_ts - timedelta(hours=1))
        t_prev, p_prev = _close_at_or_before(df1, t_ref + timedelta(minutes=10))
        t_open, p_open = _close_at_or_before(df1, sess_open_ts + timedelta(minutes=10))
        ret_vs_prev = ((p_close / p_prev - 1.0) * 100.0) if (p_close and p_prev) else None
        ret_intraday = ((p_close / p_open - 1.0) * 100.0) if (p_close and p_open) else None
        snap[label] = {
            "symbol": _sym,
            "prev_close": round(p_prev, 4) if p_prev is not None else None,
            "open": round(p_open, 4) if p_open is not None else None,
            "close": round(p_close, 4) if p_close is not None else None,
            "ret_pct": round(ret_vs_prev, 3) if ret_vs_prev is not None else None,
            "intraday_ret_pct": round(ret_intraday, 3) if ret_intraday is not None else None,
            "close_myt": to_myt_str(t_close) if t_close else None,
        }
    return snap


def build_day_anomalies(
    day: date,
    frames: dict[str, dict[str, pd.DataFrame]],
    daily_map: dict[str, list[dict]],
    events: list[dict],
    cfg: AttributionConfig,
    market: str = "all",
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    start, end = day_bounds(day)
    items = []
    session_tape: list[dict[str, Any]] = []
    macro_snapshot: dict[str, Any] = {}
    equity_sessions: dict[str, list[dict]] = {}
    if market in ("us", "all"):
        for _s, lab, _cls in EQUITY_UNIVERSE:
            equity_sessions[lab] = detect_sessions(frames.get(lab, {}).get("1h"))

    ref_sess = None
    for lab in ("SPY", "QQQ", "NVDA"):
        ref_sess = next((s for s in equity_sessions.get(lab, []) if s["session_date_et"] == day.isoformat()), None)
        if ref_sess:
            break
    if ref_sess:
        macro_snapshot = compute_us_macro_snapshot(
            frames, ref_sess["open_ts"], ref_sess["close_ts"], ref_sess.get("prev_close_ts")
        )

    universe = []
    if market in ("crypto", "all"):
        universe.extend(CRYPTO_UNIVERSE)
    if market in ("us", "all"):
        universe.extend(EQUITY_UNIVERSE)

    for _sym, label, cls in universe:
        df1 = frames.get(label, {}).get("1h")
        df15 = frames.get(label, {}).get("15m")
        session_note = None
        win_start, win_end = start, end
        prev_ret_pct = None
        giveback_pct = None
        gap_pct = None
        if cls == "equity":
            sess = next((s for s in equity_sessions.get(label, []) if s["session_date_et"] == day.isoformat()), None)
            if sess is None:
                continue
            start_px = sess.get("prev_close") if sess.get("prev_close") else sess["open_px"]
            ret_val = sess.get("ret_incl_gap") if sess.get("ret_incl_gap") is not None else sess["ret"]
            daily = {
                "date": day.isoformat(),
                "start_px": start_px,
                "end_px": sess["close_px"],
                "open_px": sess["open_px"],
                "ret": ret_val,
                "z": sess.get("z"),
                "hist_std": sess.get("hist_std"),
                "complete": sess["close_ts"] <= datetime.now(timezone.utc),
            }
            if sess.get("prev_ret_incl_gap") is not None:
                prev_ret_pct = round(sess["prev_ret_incl_gap"] * 100.0, 3)
                if sess["prev_ret_incl_gap"] >= 0.03 and ret_val is not None and ret_val <= -0.005:
                    giveback_pct = round((-ret_val / sess["prev_ret_incl_gap"]) * 100.0, 1)
            if sess.get("gap_ret") is not None:
                gap_pct = round(sess["gap_ret"] * 100.0, 3)
            win_start, win_end = sess["open_ts"], sess["close_ts"] + timedelta(minutes=1)
            session_note = f"美股 ET {day.isoformat()} 会话（{sess['open_myt']} → {sess['close_myt']}，含隔夜跳空，自动兼容夏令时）"
            session_tape.append({
                "symbol": label,
                "prev_close": round(start_px, 4) if start_px else None,
                "open_px": round(sess["open_px"], 4) if sess.get("open_px") else None,
                "close_px": round(sess["close_px"], 4),
                "gap_pct": gap_pct,
                "ret_pct": round(ret_val * 100.0, 3) if ret_val is not None else None,
                "z": round(sess["z"], 2) if sess.get("z") is not None else None,
                "prev_ret_pct": prev_ret_pct,
                "giveback_pct": giveback_pct,
                "open_myt": sess["open_myt"],
                "close_myt": sess["close_myt"],
            })
        else:
            dailies = daily_map.get(label) or []
            daily = next((r for r in dailies if r["date"] == day.isoformat()), None)
            if daily and daily.get("ret") is not None:
                session_tape.append({
                    "symbol": label,
                    "ret_pct": round(daily["ret"] * 100.0, 3),
                    "z": round(daily["z"], 2) if daily.get("z") is not None else None,
                })

        w15 = detect_windows(df15, "15m", win_start, win_end, cfg) if df15 is not None and not df15.empty else []
        w1h = detect_windows(df1, "1h", win_start, win_end, cfg) if df1 is not None and not df1.empty else []
        windows = w15 or w1h
        daily_ok = is_anomalous_daily(daily, cfg) if daily else False
        strong_windows = [
            w for w in windows
            if abs(w.get("peak_ret_z") or 0) >= cfg.bar_z_min
            or abs(w.get("cum_ret_pct") or 0) >= 2.0
            or abs(w.get("peak_ret_pct") or 0) >= 2.0
        ]
        if not daily_ok and not strong_windows:
            continue
        windows = strong_windows or windows
        primary = windows[0] if windows else None
        if primary:
            jump = _parse_iso(primary["jump_start_utc"])
            move_dir = primary["direction"]
        else:
            move_dir = "UP" if (daily and (daily.get("ret") or 0) >= 0) else "DOWN"
            jump = win_start
            if df1 is not None and not df1.empty:
                dayb = df1[(df1.index >= win_start) & (df1.index < win_end)].copy()
                if len(dayb) >= 2:
                    dayb["ret"] = dayb["close"].pct_change()
                    peak = dayb["ret"].abs().idxmax()
                    if pd.notna(peak):
                        jump = peak.to_pydatetime()
                        move_dir = "UP" if float(dayb.loc[peak, "ret"]) >= 0 else "DOWN"
            primary = {
                "interval": "1h",
                "jump_start_utc": to_utc_iso(jump),
                "jump_start_myt": to_myt_str(jump),
                "window_end_utc": to_utc_iso(min(win_end, datetime.now(timezone.utc))),
                "window_end_myt": to_myt_str(min(win_end, datetime.now(timezone.utc))),
                "peak_bar_myt": to_myt_str(jump),
                "n_bars": None,
                "peak_ret_pct": None,
                "peak_ret_z": None,
                "peak_vol_z": None,
                "cum_ret_pct": round((daily["ret"] or 0) * 100, 3) if daily and daily.get("ret") is not None else None,
                "direction": move_dir,
                "note": "未检出显著分钟级跳变，使用会话/日度异动作为窗口",
            }
        pre_h = cfg.us_event_pre_hours if cls == "equity" else cfg.event_pre_hours
        post_h = cfg.us_event_post_hours if cls == "equity" else cfg.event_post_hours
        cands = score_candidates(events, jump, move_dir, label, cfg, pre_hours=pre_h, post_hours=post_h)
        top_causes = aggregate_candidate_causes(cands, max_causes=5, asset_class=cls)
        ret_pct = round(daily["ret"] * 100, 3) if daily and daily.get("ret") is not None else None
        item = {
            "id": f"{day.isoformat()}_{label}",
            "date": day.isoformat(),
            "symbol": label,
            "asset_class": cls,
            "daily_ret_pct": ret_pct,
            "daily_z": round(daily["z"], 2) if daily and daily.get("z") is not None else None,
            "daily_std": round(daily["hist_std"], 5) if daily and daily.get("hist_std") is not None else None,
            "prev_session_ret_pct": prev_ret_pct,
            "giveback_pct": giveback_pct,
            "gap_pct": gap_pct,
            "day_complete": bool(daily["complete"]) if daily else False,
            "start_px": daily.get("start_px") if daily else None,
            "end_px": daily.get("end_px") if daily else None,
            "move_dir": move_dir,
            "primary_window": primary,
            "other_windows": windows[1:3],
            "window_cum_ret_pct": primary.get("cum_ret_pct") if primary else ret_pct,
            "candidates": cands[:12],
            "top_causes": top_causes,
            "magnitude": _anomaly_magnitude(daily or {}, windows),
            "session_note": session_note,
        }
        items.append(item)
    items.sort(key=lambda x: x["magnitude"], reverse=True)
    return items, session_tape, macro_snapshot


def render_markdown(reports: list[dict], cfg: AttributionConfig) -> str:
    lines = [
        "# 异动归因榜（以价格异动为起点反查新闻）",
        "",
        "加密默认日界为 **UTC+8（Asia/Kuala_Lumpur）**；美股按 **美东（America/New_York，自动兼容 EST/EDT 夏令时）常规会话** 切日（含隔夜跳空），所有输出时间戳统一标注为 **UTC+8**。",
        "价格反应与当日涨跌只作为已发生的事实展示；新闻影响分与候选排序不使用未来收益。",
        "",
        "排序/候选公式：",
        "",
        "`attr_score = 0.30·时间贴近度 + 0.25·影响分 + 0.15·多源热度 + 0.15·方向一致性 + 0.15·标的相关性`",
        "",
        f"加密窗口取跳变起点前 {cfg.event_pre_hours:.0f}h 至后 {cfg.event_post_hours:.0f}h；美股窗口取前 {cfg.us_event_pre_hours:.0f}h 至后 {cfg.us_event_post_hours:.0f}h；晚于跳变的新闻均标记为「事后解释/报道」并降低时间权。",
        "",
    ]
    for rep in reports:
        day = rep["date"]
        mkt_tag = rep.get("market", "all")
        partial = "（交易日未完结）" if not rep.get("all_complete") else ""
        lines += [f"## {day}（market={mkt_tag}，输出时间 UTC+8）{partial}", ""]
        if rep.get("generated_at_myt"):
            lines.append(f"生成时间：{rep['generated_at_myt']}")
            lines.append("")

        tape = rep.get("session_tape") or []
        if tape:
            lines += [
                "### 会话行情切片（含非异动对照）",
                "",
                "| 标的 | 开盘 (UTC+8) | 收盘 (UTC+8) | 隔夜跳空 | 会话涨跌 | z | 上一会话涨跌 / 回吐 |",
                "| --- | --- | --- | ---: | ---: | ---: | --- |",
            ]
            for t in tape:
                gap_s = f"{t['gap_pct']:+.2f}%" if t.get("gap_pct") is not None else "—"
                ret_s = f"{t['ret_pct']:+.2f}%" if t.get("ret_pct") is not None else "—"
                z_s = f"{t['z']:+.2f}" if t.get("z") is not None else "—"
                prev_s = f"{t['prev_ret_pct']:+.2f}%" if t.get("prev_ret_pct") is not None else "—"
                if t.get("giveback_pct") is not None:
                    prev_s += f"（回吐约 {t['giveback_pct']:.1f}%）"
                lines.append(
                    f"| {t['symbol']} | {t.get('open_myt') or '—'} | {t.get('close_myt') or '—'} | {gap_s} | {ret_s} | {z_s} | {prev_s} |"
                )
            lines.append("")

        macro = rep.get("macro_snapshot") or {}
        if macro:
            lines.append("### 同会话宏观/利率（相对上日美股收盘）")
            lines.append("")
            for k, v in macro.items():
                if isinstance(v, dict) and v.get("ret_pct") is not None:
                    lines.append(f"- **{k}**（`{v.get('symbol')}`）：{v.get('prev_close')} → {v.get('close')}（{v['ret_pct']:+.2f}%，盘中 {v.get('intraday_ret_pct'):+.2f}%）")
            lines.append("")

        groups = rep.get("common_factors") or []
        if groups:
            lines += ["### 共同因子", ""]
            for g in groups:
                mem = "、".join(f"{m['symbol']} {m.get('daily_ret_pct'):+.2f}%" if m.get("daily_ret_pct") is not None else m["symbol"] for m in g["members"])
                lines.append(f"- **{g['kind']}**（{g.get('jump_start_myt') or ''}，方向 {g['move_dir']}）：{mem}")
                attr = g.get("attribution_zh") or ""
                conf = g.get("confidence")
                verd = g.get("verdict")
                if attr:
                    lines.append(f"  - 归因：{attr}（置信度 {conf}，判定 {verd}）")
                fc = g.get("fact_check")
                if fc and fc.get("status") != "SKIPPED_NO_KEY":
                    cits = ", ".join((fc.get("citations") or [])[:3])
                    lines.append(
                        f"  - 在线核查（`{fc.get('provider')}/{fc.get('model')}`）：**{fc.get('verification_tier')}** ({fc.get('status')}) — {fc.get('summary')} "
                        + (f"[来源: {cits}]" if cits else "")
                    )
                for tc in (g.get("top_causes") or [])[:4]:
                    srcs = " / ".join(f"[{s.get('name')}]({s.get('url')})" for s in (tc.get("top_sources") or [])[:2] if s.get("url"))
                    lines.append(
                        f"  - 候选原因：**{tc['theme_label_zh']}**（{tc['timing']}，归因分 {tc['attr_score']}，**{tc['verification_tier']}**，"
                        f"独立源 {tc['independent_sources_count']}，权威 {tc['authority_score']}）— {tc['headline']} {srcs}"
                    )
            lines.append("")

        lines += [
            "### 标的异动（按异动程度）",
            "",
            "| 标的 | 当日涨跌 / z | 异动窗口 (UTC+8) | 主因归因 | 置信度 | 时效 | 自动核验 (tier / 独立源 / 权威) |",
            "| --- | --- | --- | --- | --- | --- | --- |",
        ]
        for it in rep.get("anomalies") or []:
            z = it.get("daily_z")
            ret = it.get("daily_ret_pct")
            ret_s = f"{ret:+.2f}%" if ret is not None else "—"
            z_s = f"{z:+.2f}" if z is not None else "—"
            pw = it.get("primary_window") or {}
            win = pw.get("jump_start_myt") or "—"
            if pw.get("cum_ret_pct") is not None:
                win += f"  窗口 {pw['cum_ret_pct']:+.2f}%"
            attr = it.get("attribution_zh") or ""
            conf = it.get("confidence")
            conf_s = f"{conf:.2f}" if conf is not None else "—"
            timing = "—"
            ver = "—"
            if it.get("top_causes"):
                tc0 = it["top_causes"][0]
                timing = tc0.get("timing") or "—"
                ver = f"{tc0.get('verification_tier')} (n={tc0.get('independent_sources_count')}, {tc0.get('authority_score')})"
            elif it.get("candidates"):
                c0 = it["candidates"][0]
                timing = c0.get("timing") or "—"
                ver = f"{c0.get('verification_tier')} (n={c0.get('independent_sources_count')}, {c0.get('authority_score')})"
            if it.get("verdict") == "NO_CLEAR_NEWS":
                timing = "无明显新闻"
                ver = "unverified"
            lines.append(f"| {it['symbol']} | {ret_s} / {z_s} | {win} | {attr} | {conf_s} | {timing} | {ver} |")

        lines += ["", "### 辅助：新闻中心热榜 Top 10（价格不参与排序）", ""]
        news = rep.get("news_hotlist") or []
        if not news:
            lines.append("当日无可用事件簇。")
        else:
            lines += [
                "| 排名 | 标题 | 分类 | 热度分 | 核验 | 首发 (UTC+8) | 价格反应（仅展示） |",
                "| --- | --- | --- | --- | --- | --- | --- |",
            ]
            for i, n in enumerate(news, 1):
                pr = n.get("price_reaction_display") or {}
                pr_s = "；".join(f"{k}: {v}" for k, v in list(pr.items())[:2]) or "—"
                hl = (n.get("headline") or "").replace("|", "/")
                lines.append(
                    f"| {i} | {hl} | {n.get('category')} | {n.get('hot_score')} | {n.get('verification_tier')} / {n.get('verification_label')} | {n.get('published_at_myt')} | {pr_s} |"
                )
        lines.append("")

    if reports:
        lines += [
            "## 花费与局限",
            "",
            f"- 归因 LLM：`{cfg.llm_model}`，仅对上榜异动/共同因子的 Top 候选调用。",
        ]
    return "\n".join(lines) + "\n"


def run_hotlist(
    dates: list[date],
    output_dir: str | Path = "outputs",
    cfg: Optional[AttributionConfig] = None,
    model_override: Optional[str] = None,
    market: str = "all",
    fetch_news: bool = True,
    verify_online: bool = True,
) -> dict[str, Any]:
    cfg = cfg or AttributionConfig()
    if model_override:
        cfg.llm_model = model_override
    market = (market or "all").lower()
    if market not in ("all", "us", "crypto"):
        market = "all"

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc)
    frames = fetch_universe_bars(cfg, now, market=market)

    first = min(dates) - timedelta(days=cfg.lookback_days + 1)
    last = max(dates)
    daily_map: dict[str, list[dict]] = {}
    if market in ("crypto", "all"):
        for _sym, label, _cls in CRYPTO_UNIVERSE:
            df = frames.get(label, {}).get("1h")
            daily_map[label] = daily_returns_myt(df, first, last) if df is not None and not df.empty else []

    base_events = load_event_corpus()
    anomalous_syms: set[str] = set()
    for day in dates:
        its, _tape, _macro = build_day_anomalies(day, frames, daily_map, [], cfg, market=market)
        for it in its:
            anomalous_syms.add(it["symbol"])

    ingest_meta: dict[str, Any] = {"enabled": fetch_news}
    fresh_events: list[dict[str, Any]] = []
    if fetch_news:
        if market in ("us", "all"):
            s_lo, _ = us_session_bounds_approx(min(dates))
            _, s_hi = us_session_bounds_approx(max(dates))
            win_lo = s_lo - timedelta(hours=24)
            win_hi = s_hi + timedelta(hours=8)
        else:
            win_lo, _ = day_bounds(min(dates) - timedelta(days=1))
            _, win_hi = day_bounds(max(dates))
            win_hi = win_hi + timedelta(hours=6)

        fresh_events, ingest_meta = collect_attribution_news(
            sorted(anomalous_syms) or (["NVDA", "SPY", "QQQ"] if market == "us" else ["BTC/USDT"]),
            market=market,
            target_dates=dates,
            win_lo=win_lo,
            win_hi=win_hi,
        )
        snap_path = out_dir / f"hotlist_news_{'_'.join(d.isoformat() for d in dates)}_{market}.json"
        serializable = [{k: v for k, v in ev.items() if k != "_pub_dt"} for ev in fresh_events]
        snap_path.write_text(json.dumps(serializable, ensure_ascii=False, indent=2), encoding="utf-8")
        ingest_meta["snapshot_path"] = str(snap_path)

    events = merge_event_pools(base_events, fresh_events)

    client = LiteLLMClient(model_override=cfg.llm_model)
    health_ok, health_http, health_msg = client.check_health()
    fact_checker = PerplexityFactChecker(prefer_openrouter_online=True) if verify_online else PerplexityFactChecker(prefer_openrouter_online=False)

    reports = []
    all_pt = all_ct = 0
    llm_calls = 0
    fc_calls = 0
    fc_pt = fc_ct = 0
    fc_cost_usd = 0.0

    seed_start, _ = day_bounds(min(dates) - timedelta(days=cfg.novelty_lookback_days))
    first_start, _ = day_bounds(min(dates))
    prev_news_headlines = [
        e.get("headline") or ""
        for e in events
        if e.get("_pub_dt") and seed_start <= e["_pub_dt"] < first_start
    ]

    for day in dates:
        items, session_tape, macro_snapshot = build_day_anomalies(day, frames, daily_map, events, cfg, market=market)
        groups = group_common_factors(items, cfg)

        fc_budget = cfg.max_factchecks_per_day if (verify_online and fact_checker.is_configured) else 0
        fc_targets: list[dict[str, Any]] = []
        for g in groups:
            if g.get("kind") != "cross_asset_spillover":
                fc_targets.append(g)
        if not fc_targets and items:
            fc_targets.append(items[0])

        for obj in fc_targets[:fc_budget]:
            top_c = obj.get("top_causes") or obj.get("candidates") or []
            if not top_c:
                continue
            c0 = top_c[0]
            sym_str = ",".join(obj.get("symbols") or [obj.get("symbol", "")])
            claim = f"{sym_str} moved {obj.get('move_dir')} on {day.isoformat()} (ET/session); candidate driver: {c0.get('headline')}"
            if len(top_c) > 1:
                claim += f"; secondary: {top_c[1].get('headline')}"
            fc_res = fact_checker.verify_claim(claim, sym_str, session_date=day.isoformat())
            fc_dict = {
                "status": fc_res.status,
                "provider": fc_res.provider,
                "model": fc_res.model,
                "verification_tier": fc_res.verification_tier,
                "summary": fc_res.summary,
                "citations": fc_res.citations or [],
                "independent_sources_count": fc_res.independent_sources_count,
                "key_sources": fc_res.key_sources or [],
                "cost_usd": fc_res.cost_usd,
                "raw_error": fc_res.raw_error,
            }
            obj["fact_check"] = fc_dict
            if fc_res.status != "SKIPPED_NO_KEY":
                fc_calls += 1
                fc_pt += fc_res.prompt_tokens
                fc_ct += fc_res.completion_tokens
                fc_cost_usd += fc_res.cost_usd
            if fc_res.status == "VERIFIED" and fc_res.verification_tier == "confirmed" and obj.get("top_causes"):
                obj["top_causes"][0]["online_verified"] = True
                obj["top_causes"][0]["verification_tier"] = "confirmed"
                obj["top_causes"][0]["verification_tier_zh"] = verification_tier_zh("confirmed")

        llm_targets: list[tuple[str, dict]] = []
        if health_ok:
            covered: set[str] = set()
            for g in groups:
                if g.get("kind") != "cross_asset_spillover":
                    llm_targets.append(("group", g))
                    for m in g["members"]:
                        covered.add(m["id"])
            for g in groups:
                if g.get("kind") == "cross_asset_spillover":
                    llm_targets.append(("group", g))
            for it in items:
                if it["id"] not in covered:
                    llm_targets.append(("item", it))
            llm_targets = llm_targets[: cfg.max_anomalies_for_llm]
            for kind, obj in llm_targets:
                if kind == "group":
                    gkind = obj.get("kind") or "common"
                    lead_sym = (obj.get("members") or [{}])[0].get("symbol")
                    lead_it = next((x for x in items if x["symbol"] == lead_sym), {})
                    fake = {
                        "symbol": f"{gkind}: " + ",".join(obj["symbols"]),
                        "date": obj["date"],
                        "daily_ret_pct": lead_it.get("daily_ret_pct"),
                        "daily_z": lead_it.get("daily_z"),
                        "prev_session_ret_pct": lead_it.get("prev_session_ret_pct"),
                        "giveback_pct": lead_it.get("giveback_pct"),
                        "day_complete": lead_it.get("day_complete", True),
                        "primary_window": {"jump_start_myt": obj.get("jump_start_myt")},
                        "window_cum_ret_pct": lead_it.get("window_cum_ret_pct"),
                        "move_dir": obj["move_dir"],
                        "candidates": obj.get("candidates") or [],
                        "top_causes": obj.get("top_causes") or [],
                    }
                    attr = _apply_llm(client, fake, cfg, macro_snapshot=macro_snapshot, session_tape=session_tape)
                    obj.update(attr)
                else:
                    attr = _apply_llm(client, obj, cfg, macro_snapshot=macro_snapshot, session_tape=session_tape)
                    obj.update(attr)
                all_pt += int(attr.get("prompt_tokens") or 0)
                all_ct += int(attr.get("completion_tokens") or 0)
                if attr.get("llm_status") not in ("SKIPPED_WEAK_EVIDENCE", "SKIPPED_NO_KEY"):
                    llm_calls += 1
        else:
            msg = "未调用 LLM（密钥健康检查未通过）" if not client.is_configured else f"LLM 健康检查失败 HTTP {health_http}"
            for it in items:
                it.update({"attribution_zh": "待大模型归因", "confidence": None, "verdict": "PENDING_LLM", "llm_status": msg})
            for g in groups:
                g.update({"attribution_zh": "待大模型归因", "confidence": None, "verdict": "PENDING_LLM", "llm_status": msg})

        inherit: dict[str, dict] = {}
        for g in groups:
            if g.get("kind") == "cross_asset_spillover":
                continue
            for m in g["members"]:
                inherit[m["id"]] = g
        for it in items:
            if it["id"] in inherit:
                g = inherit[it["id"]]
                it["common_factor_id"] = g["id"]
                if g.get("fact_check"):
                    it["fact_check"] = g["fact_check"]
                if not it.get("attribution_zh") or it.get("llm_status") in (None, "SKIPPED_WEAK_EVIDENCE"):
                    it["attribution_zh"] = g.get("attribution_zh")
                    it["confidence"] = g.get("confidence")
                    it["verdict"] = g.get("verdict")
                    it["inherited_from"] = g["id"]
                    it.setdefault("llm_status", g.get("llm_status"))

        spill = [g for g in groups if g.get("kind") == "cross_asset_spillover"]
        for it in items:
            for g in spill:
                if it["id"] in {m["id"] for m in g["members"]} and g.get("attribution_zh"):
                    it["spillover_note"] = g.get("attribution_zh")
                    it["spillover_confidence"] = g.get("confidence")
                    it["spillover_verdict"] = g.get("verdict")
                    if it.get("verdict") == "NO_CLEAR_NEWS" and g.get("verdict") == "ATTRIBUTED":
                        it["attribution_zh"] = "未找到明确的标的直接新闻；交叉溢出：" + (g.get("attribution_zh") or "")
                        it["confidence"] = g.get("confidence")
                        it["verdict"] = "MIXED"
                        it["inherited_from"] = g["id"]

        news = auxiliary_news_hotlist(events, day, prev_news_headlines, cfg)
        prev_news_headlines = [n["headline"] for n in news] + prev_news_headlines
        all_complete = all(it.get("day_complete") for it in items) if items else True
        if market != "us" and day_bounds(day)[1] > now:
            all_complete = False
        if market == "us" and us_session_bounds_approx(day)[1] > now:
            all_complete = False
        reports.append({
            "date": day.isoformat(),
            "market": market,
            "timezone": "Asia/Kuala_Lumpur (UTC+8)",
            "session_rule": "America/New_York regular cash session (EST/EDT DST-aware)" if market == "us" else "Crypto UTC+8 / US ET session",
            "generated_at_myt": to_myt_str(now),
            "all_complete": all_complete,
            "session_tape": session_tape,
            "macro_snapshot": macro_snapshot,
            "anomalies": items,
            "common_factors": groups,
            "news_hotlist": news,
            "ingest_meta": ingest_meta,
            "universe": {
                "crypto": [x[1] for x in CRYPTO_UNIVERSE] if market in ("crypto", "all") else [],
                "equity": [x[1] for x in EQUITY_UNIVERSE] if market in ("us", "all") else [],
            },
            "params": asdict(cfg),
            "note": "价格异动是归因起点；新闻影响分与候选排序不使用未来收益。",
        })

    llm_cost_usd = (all_pt / 1_000_000.0) * 0.10 + (all_ct / 1_000_000.0) * 0.40
    total_cost_usd = llm_cost_usd + fc_cost_usd
    run_cost = {
        "model": cfg.llm_model,
        "llm_health_ok": health_ok,
        "llm_health_http": health_http,
        "llm_calls": llm_calls,
        "prompt_tokens": all_pt,
        "completion_tokens": all_ct,
        "llm_cost_usd": round(llm_cost_usd, 6),
        "factcheck_provider": fact_checker.provider,
        "factcheck_model": fact_checker.model if fact_checker.is_configured else "none",
        "factcheck_calls": fc_calls,
        "factcheck_prompt_tokens": fc_pt,
        "factcheck_completion_tokens": fc_ct,
        "factcheck_cost_usd": round(fc_cost_usd, 6),
        "catalog_cost_usd": round(total_cost_usd, 6),
    }
    for r in reports:
        r["run_cost"] = run_cost

    paths = {}
    suffix = "" if market == "all" else f"_{market}_auto"
    for r in reports:
        stem = f"attribution_{r['date']}{suffix}"
        jp = out_dir / f"{stem}.json"
        mp = out_dir / f"{stem}.md"
        jp.write_text(json.dumps(r, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        md_single = render_markdown([r], cfg)
        md_single += (
            f"- 归因 LLM 调用 {llm_calls} 次（输入 {all_pt} / 输出 {all_ct} tokens，约 ${llm_cost_usd:.5f}）；"
            f"在线核查（`{fact_checker.provider}/{fact_checker.model if fact_checker.is_configured else 'none'}`）"
            f"调用 {fc_calls} 次（约 ${fc_cost_usd:.5f}），合计 **${total_cost_usd:.5f}**。\n"
            f"- 实时增量采集：{ingest_meta.get('raw_items_fetched', 0)} 条原始新闻 → {ingest_meta.get('clusters_created', 0)} 个簇。\n"
        )
        mp.write_text(md_single, encoding="utf-8")
        paths[r["date"]] = {"json": str(jp), "md": str(mp)}

    combined_stem = "attribution_latest" if market == "all" else f"attribution_latest_{market}_auto"
    combined_json = out_dir / f"{combined_stem}.json"
    combined_md = out_dir / f"{combined_stem}.md"
    combined_json.write_text(json.dumps({"cost": run_cost, "days": reports}, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    md = render_markdown(reports, cfg)
    md += (
        f"- 归因 LLM 调用 {llm_calls} 次（输入 {all_pt} / 输出 {all_ct} tokens，约 ${llm_cost_usd:.5f}）；"
        f"在线核查（`{fact_checker.provider}/{fact_checker.model if fact_checker.is_configured else 'none'}`）"
        f"调用 {fc_calls} 次（约 ${fc_cost_usd:.5f}），合计 **${total_cost_usd:.5f}**。\n"
    )
    combined_md.write_text(md, encoding="utf-8")
    paths["combined"] = {"json": str(combined_json), "md": str(combined_md)}
    return {
        "dates": [d.isoformat() for d in dates],
        "market": market,
        "paths": paths,
        "cost": run_cost,
        "ingest": {k: v for k, v in ingest_meta.items() if k != "source_stats"},
        "health": {"ok": health_ok, "http": health_http, "msg": (health_msg or "")[:80]},
    }
