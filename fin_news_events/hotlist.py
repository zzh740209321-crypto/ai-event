"""Intraday / daily move detection and news attribution (异动归因榜).

Price moves are the starting point. Impact scores and ranking of candidate
news never use future returns. A news-centered auxiliary list is optional.
"""
from __future__ import annotations

import json
import math
import re
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd

from fin_news_events.llm_clients import LiteLLMClient
from fin_news_events.market_data import fetch_binance_klines, fetch_yahoo_bars
from fin_news_events.models import MYT, to_myt_str, to_utc_iso

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "outputs"
CACHE_DIR = OUT_DIR / "klines_cache"

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
    ("SPY", "SPY", "equity"),
    ("QQQ", "QQQ", "equity"),
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
    "SPY": ("s&p", "s & p", "sp500", "s&p 500", "wall street", "us stocks", "stock market"),
    "QQQ": ("nasdaq", "qqq", "tech stocks", "magnificent"),
}

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
    time_tau_hours: float = 3.0
    w_time: float = 0.30
    w_impact: float = 0.25
    w_heat: float = 0.15
    w_dir: float = 0.15
    w_rel: float = 0.15
    attr_score_min: float = 0.28
    llm_top_k: int = 3
    common_window_hours: float = 2.0
    news_hotlist_top_n: int = 10
    llm_model: str = "google/gemini-2.5-flash-lite"
    max_anomalies_for_llm: int = 10
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


def _norm_headline(h: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (h or "").lower())


def verification_label(status: str) -> str:
    return {
        "OFFICIAL_PRIMARY": "官方一手",
        "MULTI_SOURCE_CONFIRMED": "多源确认",
        "SINGLE_TIER1_REPORTED": "单一权威（未交叉核实）",
        "UNVERIFIED_OR_RUMOR": "单源未核实",
    }.get(status or "", status or "未知核验")


def news_heat(n_domains: int, n_articles: int, cfg: AttributionConfig) -> float:
    num = math.log(1.0 + cfg.news_heat_source_w * max(0, n_domains) + cfg.news_heat_article_w * max(0, n_articles))
    den = math.log(1.0 + cfg.news_heat_source_w * 3.0 + cfg.news_heat_article_w * 5.0)
    return round(num / den if den else 0.0, 4)


def _close_at_or_before(df: pd.DataFrame, ts: datetime) -> tuple[Optional[datetime], Optional[float]]:
    if df.empty:
        return None, None
    idx = df.index
    pos = idx.searchsorted(ts, side="right") - 1
    if pos < 0:
        return None, None
    return idx[pos].to_pydatetime(), float(df.iloc[pos]["close"])


def _cache_path(symbol: str, interval: str) -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    safe = symbol.replace("/", "")
    return CACHE_DIR / f"{safe}_{interval}.csv"


def _load_or_fetch(symbol: str, asset_class: str, interval: str, start: datetime, end: datetime) -> pd.DataFrame:
    path = _cache_path(symbol, interval)
    if path.exists():
        df = pd.read_csv(path, parse_dates=["ts"])
        if not df.empty:
            df["ts"] = pd.to_datetime(df["ts"], utc=True)
            df = df.set_index("ts").sort_index()
            if df.index[0] <= start + timedelta(hours=12) and df.index[-1] >= end - timedelta(hours=2):
                return df[(df.index >= start - timedelta(hours=2)) & (df.index <= end + timedelta(hours=1))]
    if asset_class == "crypto":
        df = fetch_binance_klines(symbol, start, end, interval=interval)
    else:
        df = fetch_yahoo_bars(symbol, start, end, interval=interval)
    if not df.empty:
        out = df.reset_index()
        out.to_csv(path, index=False)
    return df


def fetch_universe_bars(cfg: AttributionConfig, end_utc: datetime) -> dict[str, dict[str, pd.DataFrame]]:
    start = end_utc - timedelta(days=cfg.lookback_days + 8)
    frames: dict[str, dict[str, pd.DataFrame]] = {}
    jobs: list[tuple[str, str, str, str]] = []
    for sym, label, cls in CRYPTO_UNIVERSE + EQUITY_UNIVERSE:
        jobs.append((sym, label, cls, "1h"))
        jobs.append((sym, label, cls, "15m"))

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
        complete = True
        now = datetime.now(timezone.utc)
        if end > now:
            complete = False
        ret = None
        if px0 and px1 and px0 > 0 and ts1 and ts0 and ts1 > ts0:
            ret = (px1 / px0) - 1.0
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
    # rolling z vs prior lookback (exclude current day)
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
    """Split equity 1h bars into regular sessions using overnight/weekend gaps."""
    if df is None or df.empty or len(df) < 3:
        return []
    times = [ts.to_pydatetime() for ts in df.index]
    slices: list[tuple[int, int]] = []
    start_i = 0
    for i in range(1, len(times)):
        if (times[i] - times[i - 1]).total_seconds() >= gap_hours * 3600:
            slices.append((start_i, i))
            start_i = i
    slices.append((start_i, len(times)))
    recs: list[dict[str, Any]] = []
    for a, b in slices:
        seg = df.iloc[a:b]
        if len(seg) < 2:
            continue
        open_px = float(seg.iloc[0]["open"]) if "open" in seg.columns else float(seg.iloc[0]["close"])
        close_px = float(seg.iloc[-1]["close"])
        open_ts = seg.index[0].to_pydatetime()
        close_ts = seg.index[-1].to_pydatetime()
        recs.append({
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
    # Official-style session return includes the overnight gap vs the previous session close.
    for i, r in enumerate(recs):
        if i == 0:
            r["prev_close"] = None
            r["ret_incl_gap"] = r["ret"]
        else:
            prev_c = recs[i - 1]["close_px"]
            r["prev_close"] = prev_c
            r["ret_incl_gap"] = (r["close_px"] / prev_c - 1.0) if prev_c else r["ret"]
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
    # trailing stats use a rolling window excluding the current bar
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
            # absolute jump floor so flat-then-gap days are not missed when trailing std ~ 0
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
        # window cumulative return from open of first bar to close of last
        first_ts = start["ts"]
        # approximate start price as close / (1+ret)
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


def load_event_corpus() -> list[dict[str, Any]]:
    files = [
        OUT_DIR / "timeline_btcusdt_7d.json",
        OUT_DIR / "timeline_nvda_7d.json",
        OUT_DIR / "timeline_smoke_jev_1d.json",
        OUT_DIR / "timeline_midterm2026_btcusdt.json",
        OUT_DIR / "timeline_midterm2026_nvda.json",
    ]
    by_id: dict[str, dict] = {}
    for fp in files:
        if not fp.exists():
            continue
        for row in json.loads(fp.read_text(encoding="utf-8")):
            eid = row.get("event_id")
            if not eid:
                continue
            # Keep the copy with more sources if duplicated
            prev = by_id.get(eid)
            if prev is None or int(row.get("source_count") or 0) >= int(prev.get("source_count") or 0):
                try:
                    row = dict(row)
                    row["_pub_dt"] = _parse_iso(row["published_at_utc"])
                except Exception:
                    continue
                by_id[eid] = row
    return list(by_id.values())


def _n_domains(row: dict) -> int:
    doms = row.get("unique_domains") or []
    if isinstance(doms, list) and doms:
        return len({str(d).lower() for d in doms})
    return 1 if row.get("source_count") else 0


def relevance_score(row: dict, symbol: str) -> float:
    hl = f"{row.get('headline','')} {row.get('summary','')}".lower()
    keys = SYMBOL_KEYWORDS.get(symbol, ())
    if any(k.strip() and k in hl for k in keys):
        return 1.0 if row.get("retrieval_layer") == "DIRECT" or symbol in (row.get("target_symbol") or "") else 0.85
    if symbol in (row.get("target_symbol") or "") and row.get("retrieval_layer") == "DIRECT":
        return 0.9
    cat = row.get("category") or ""
    if cat in MACRO_CATS:
        return 0.72
    if symbol.endswith("/USDT") and cat == "CRYPTO":
        return 0.32
    if symbol in ("NVDA", "SPY", "QQQ") and cat == "TECH_AI":
        return 0.62 if symbol == "NVDA" else 0.45
    return 0.18


def direction_align(event_dir: str, move_dir: str) -> float:
    ed = (event_dir or "NEUTRAL").upper()
    if ed in ("NEUTRAL", "MIXED", ""):
        return 0.4
    if move_dir == "UP":
        return 1.0 if ed == "BULLISH" else 0.0
    return 1.0 if ed == "BEARISH" else 0.0


def score_candidates(
    events: list[dict],
    jump_start: datetime,
    move_dir: str,
    symbol: str,
    cfg: AttributionConfig,
) -> list[dict[str, Any]]:
    lo = jump_start - timedelta(hours=cfg.event_pre_hours)
    hi = jump_start + timedelta(hours=cfg.event_post_hours)
    scored = []
    for ev in events:
        pub = ev.get("_pub_dt")
        if pub is None:
            continue
        if pub < lo or pub > hi:
            continue
        dt_h = (pub - jump_start).total_seconds() / 3600.0
        ex_post = dt_h > 0.05  # published after jump start (3+ min)
        decay = math.exp(-abs(dt_h) / cfg.time_tau_hours)
        time_prox = (0.4 * decay) if ex_post else decay
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
            "sources": [
                {"name": s.get("name"), "url": s.get("url"), "domain": s.get("domain")}
                for s in (ev.get("sources") or [])[:6]
            ],
            "verification_status": ev.get("verification_status"),
            "verification_label": verification_label(ev.get("verification_status") or ""),
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


def _llm_payload(item: dict, candidates: list[dict]) -> str:
    lines = [
        f"标的或组合: {item['symbol']}",
        "若为 cross_asset_spillover：区分公司/指数自身新闻与风险偏好向加密的溢出，不要把只解释 NVDA 的新闻硬套到山寨币。",
        f"日界: {item['date']} (UTC+8)",
        f"当日涨跌: {item.get('daily_ret_pct')}%  z={item.get('daily_z')}  是否完整交易日={item.get('day_complete')}",
        f"异动窗口: {item.get('primary_window')}",
        f"窗口累计涨跌: {item.get('window_cum_ret_pct')}%  方向={item.get('move_dir')}",
        "候选新闻（已按归因分排序，价格不参与该分数）:",
    ]
    if not candidates:
        lines.append("（窗口前后未检索到事件簇）")
    for i, c in enumerate(candidates, 1):
        lines.append(
            f"{i}. [{c['timing']}] {c['published_at_myt']} | {c['category']}/{c['subcategory']} | "
            f"影响分={c['impact_score']} 热度={c['heat']} 相关={c['relevance']} 方向={c['direction']} "
            f"核验={c['verification_label']} 归因分={c['attr_score']} | {c['headline']}"
        )
    return "\n".join(lines)


def _apply_llm(client: LiteLLMClient, item: dict, cfg: AttributionConfig) -> dict[str, Any]:
    cands = item.get("candidates") or []
    top = cands[: cfg.llm_top_k]
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
    res = client.attribute_price_move(_llm_payload(item, top))
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
    """Cluster overlapping windows within the same asset class.

    A cross-asset spillover group is added only when both a crypto cluster and an
    equity cluster overlap in time; it is labeled separately so NVDA-specific news
    is not blindly inherited by alts.
    """
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
        return shared[:8]

    def _pack(members: list[dict], kind: str) -> dict[str, Any]:
        members = sorted(members, key=lambda m: m["magnitude"], reverse=True)
        symbols = [m["symbol"] for m in members]
        js = next((_jump(m) for m in members if _jump(m) is not None), None)
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
            "candidates": _shared_candidates(members, min_share=2 if len(members) >= 3 else 1),
        }

    cryptos = [it for it in items if it["asset_class"] == "crypto"]
    equities = [it for it in items if it["asset_class"] == "equity"]
    groups: list[dict[str, Any]] = []
    crypto_clusters = _cluster(cryptos)
    equity_clusters = _cluster(equities)
    for cl in crypto_clusters:
        if len(cl) >= 2:
            groups.append(_pack(cl, "crypto_common"))
    for cl in equity_clusters:
        if len(cl) >= 2:
            groups.append(_pack(cl, "equity_common"))

    # Optional spillover link: overlapping crypto & equity clusters, same direction
    for cg in [g for g in groups if g["kind"] == "crypto_common"]:
        for eg in [g for g in groups if g["kind"] == "equity_common"]:
            if cg["move_dir"] != eg["move_dir"]:
                continue
            # reuse jump strings
            # find member jumps
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
                # Keep only market-wide / linking headlines for the spillover payload
                link["candidates"] = [
                    c for c in link["candidates"]
                    if c.get("category") in MACRO_CATS or c.get("share_n", 0) >= 3
                    or any(k in (c.get("headline") or "").lower() for k in ("crypto", "bitcoin", "nasdaq", "stock", "risk", "ai trade", "nvidia"))
                ][:6]
                groups.append(link)
    return groups



def auxiliary_news_hotlist(events: list[dict], day: date, prev_headlines: list[str], cfg: AttributionConfig) -> list[dict[str, Any]]:
    start, end = day_bounds(day)
    day_ev = [e for e in events if e.get("_pub_dt") and start <= e["_pub_dt"] < end]
    # merge same headline across symbols
    buckets: dict[str, list[dict]] = defaultdict(list)
    for e in day_ev:
        buckets[_norm_headline(e.get("headline") or "") or e["event_id"]].append(e)
    prev_norms = [_norm_headline(h) for h in prev_headlines if h]
    items = []
    for key, evs in buckets.items():
        evs.sort(key=lambda x: (-float(x.get("impact_score") or 0), -int(x.get("source_count") or 0)))
        ev = evs[0]
        # novelty vs prior days' headlines
        nov = 1.0
        if key and key in prev_norms:
            nov = 0.35
        else:
            # token overlap decay
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
            "sources": [
                {"name": s.get("name"), "url": s.get("url"), "domain": s.get("domain")}
                for s in (ev.get("sources") or [])[:4]
            ],
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


def build_day_anomalies(
    day: date,
    frames: dict[str, dict[str, pd.DataFrame]],
    daily_map: dict[str, list[dict]],
    events: list[dict],
    cfg: AttributionConfig,
) -> list[dict[str, Any]]:
    start, end = day_bounds(day)
    items = []
    equity_sessions: dict[str, list[dict]] = {}
    for _s, lab, cls in EQUITY_UNIVERSE:
        equity_sessions[lab] = detect_sessions(frames.get(lab, {}).get("1h"))

    for _sym, label, cls in CRYPTO_UNIVERSE + EQUITY_UNIVERSE:
        df1 = frames.get(label, {}).get("1h")
        df15 = frames.get(label, {}).get("15m")
        session_note = None
        win_start, win_end = start, end
        if cls == "equity":
            sess = next((s for s in equity_sessions.get(label, []) if s["open_date_myt"] == day.isoformat()), None)
            if sess is None:
                continue
            start_px = sess.get("prev_close") if sess.get("prev_close") else sess["open_px"]
            daily = {
                "date": day.isoformat(),
                "start_px": start_px,
                "end_px": sess["close_px"],
                "ret": sess.get("ret_incl_gap") if sess.get("ret_incl_gap") is not None else sess["ret"],
                "z": sess.get("z"),
                "hist_std": sess.get("hist_std"),
                "complete": sess["close_ts"] <= datetime.now(timezone.utc),
            }
            win_start, win_end = sess["open_ts"], sess["close_ts"] + timedelta(minutes=1)
            session_note = f"美股会话 {sess['open_myt']} → {sess['close_myt']}（按开盘所在 UTC+8 日归属，避免被零点拆分）"
        else:
            dailies = daily_map.get(label) or []
            daily = next((r for r in dailies if r["date"] == day.isoformat()), None)
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
            # synthetic window = the whole day, jump at start of largest 1h bar if any, else day start
            move_dir = "UP" if (daily and (daily.get("ret") or 0) >= 0) else "DOWN"
            jump = start
            if df1 is not None and not df1.empty:
                dayb = df1[(df1.index >= start) & (df1.index < end)].copy()
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
                "window_end_utc": to_utc_iso(min(end, datetime.now(timezone.utc))),
                "window_end_myt": to_myt_str(min(end, datetime.now(timezone.utc))),
                "peak_bar_myt": to_myt_str(jump),
                "n_bars": None,
                "peak_ret_pct": None,
                "peak_ret_z": None,
                "peak_vol_z": None,
                "cum_ret_pct": round((daily["ret"] or 0) * 100, 3) if daily and daily.get("ret") is not None else None,
                "direction": move_dir,
                "note": "未检出显著分钟级跳变，使用日度异动作为窗口",
            }
        cands = score_candidates(events, jump, move_dir, label, cfg)
        ret_pct = round(daily["ret"] * 100, 3) if daily and daily.get("ret") is not None else None
        item = {
            "id": f"{day.isoformat()}_{label}",
            "date": day.isoformat(),
            "symbol": label,
            "asset_class": cls,
            "daily_ret_pct": ret_pct,
            "daily_z": round(daily["z"], 2) if daily and daily.get("z") is not None else None,
            "daily_std": round(daily["hist_std"], 5) if daily and daily.get("hist_std") is not None else None,
            "day_complete": bool(daily["complete"]) if daily else False,
            "start_px": daily.get("start_px") if daily else None,
            "end_px": daily.get("end_px") if daily else None,
            "move_dir": move_dir,
            "primary_window": primary,
            "other_windows": windows[1:3],
            "window_cum_ret_pct": primary.get("cum_ret_pct") if primary else ret_pct,
            "candidates": cands[:8],
            "magnitude": _anomaly_magnitude(daily or {}, windows),
            "session_note": session_note,
        }
        items.append(item)
    items.sort(key=lambda x: x["magnitude"], reverse=True)
    return items


def render_markdown(reports: list[dict], cfg: AttributionConfig) -> str:
    lines = [
        "# 异动归因榜（以价格异动为起点反查新闻）",
        "",
        "日界为 **UTC+8（Asia/Kuala_Lumpur）**。价格反应与当日涨跌只作为已发生的事实展示；新闻影响分与候选排序不使用未来收益。",
        "",
        "排序/候选公式：",
        "",
        "`attr_score = 0.30·时间贴近度 + 0.25·影响分 + 0.15·多源热度 + 0.15·方向一致性 + 0.15·标的相关性`",
        "",
        f"窗口取跳变起点前 {cfg.event_pre_hours:.0f}h 至后 {cfg.event_post_hours:.0f}h；晚于跳变的新闻标记为「事后解释/报道」并降低时间权。",
        "",
    ]
    for rep in reports:
        day = rep["date"]
        partial = "（交易日未完结）" if not rep.get("all_complete") else ""
        lines += [f"## {day} UTC+8 {partial}", ""]
        if rep.get("generated_at_myt"):
            lines.append(f"生成时间：{rep['generated_at_myt']}")
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
                for c in (g.get("candidates") or [])[:3]:
                    lines.append(f"  - 候选：{c['headline']}（{c['timing']}，归因分 {c['attr_score']}，{c['verification_label']}）")
            lines.append("")
        lines += [
            "### 标的异动（按异动程度）",
            "",
            "| 标的 | 当日涨跌 / z | 异动窗口 (UTC+8) | 主因归因 | 置信度 | 时效 | 核验 |",
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
            if it.get("candidates"):
                timing = it["candidates"][0].get("timing") or "—"
                ver = it["candidates"][0].get("verification_label") or "—"
            if it.get("verdict") == "NO_CLEAR_NEWS":
                timing = "无明显新闻"
                ver = "—"
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
                    f"| {i} | {hl} | {n.get('category')} | {n.get('hot_score')} | {n.get('verification_label')} | {n.get('published_at_myt')} | {pr_s} |"
                )
        lines.append("")
    if reports:
        cost = reports[-1].get("run_cost") or reports[0].get("run_cost") or {}
        # prefer attached global cost on last
        lines += [
            "## 花费与局限",
            "",
            f"- LLM 模型：`{cfg.llm_model}`，仅对上榜异动/共同因子的 Top 候选调用。",
        ]
    return "\n".join(lines) + "\n"


def run_hotlist(
    dates: list[date],
    output_dir: str | Path = "outputs",
    cfg: Optional[AttributionConfig] = None,
    model_override: Optional[str] = None,
) -> dict[str, Any]:
    cfg = cfg or AttributionConfig()
    if model_override:
        cfg.llm_model = model_override
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc)
    frames = fetch_universe_bars(cfg, now)
    # daily stats from lookback to last requested date
    first = min(dates) - timedelta(days=cfg.lookback_days + 1)
    last = max(dates)
    daily_map: dict[str, list[dict]] = {}
    for _sym, label, _cls in CRYPTO_UNIVERSE + EQUITY_UNIVERSE:
        df = frames.get(label, {}).get("1h")
        if df is None or df.empty:
            daily_map[label] = []
            continue
        daily_map[label] = daily_returns_myt(df, first, last)

    events = load_event_corpus()
    client = LiteLLMClient(model_override=cfg.llm_model)
    health_ok, health_http, health_msg = client.check_health()

    reports = []
    all_pt = all_ct = 0
    llm_calls = 0
    prev_news_headlines: list[str] = []

    # accumulate prior-day headlines for auxiliary novelty (dates should be sorted)
    # also seed from events before the first date
    seed_start, _ = day_bounds(min(dates) - timedelta(days=cfg.novelty_lookback_days))
    first_start, _ = day_bounds(min(dates))
    prev_news_headlines = [
        e.get("headline") or ""
        for e in events
        if e.get("_pub_dt") and seed_start <= e["_pub_dt"] < first_start
    ]

    for day in dates:
        items = build_day_anomalies(day, frames, daily_map, events, cfg)
        groups = group_common_factors(items, cfg)
        # LLM budget: groups first, then top individuals not fully covered
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
                    # fabricate a payload item
                    kind = obj.get("kind") or "common"
                    fake = {
                        "symbol": f"{kind}: " + ",".join(obj["symbols"]),
                        "date": obj["date"],
                        "daily_ret_pct": None,
                        "daily_z": None,
                        "day_complete": True,
                        "primary_window": {"jump_start_myt": obj.get("jump_start_myt")},
                        "window_cum_ret_pct": None,
                        "move_dir": obj["move_dir"],
                        "candidates": obj.get("candidates") or [],
                    }
                    attr = _apply_llm(client, fake, cfg)
                    obj.update(attr)
                else:
                    attr = _apply_llm(client, obj, cfg)
                    obj.update(attr)
                all_pt += int(attr.get("prompt_tokens") or 0)
                all_ct += int(attr.get("completion_tokens") or 0)
                if attr.get("llm_status") not in ("SKIPPED_WEAK_EVIDENCE", "SKIPPED_NO_KEY"):
                    llm_calls += 1
        else:
            msg = "未调用 LLM（密钥健康检查未通过）" if not client.is_configured else f"LLM 健康检查失败 HTTP {health_http}"
            for it in items:
                it.update({
                    "attribution_zh": "待大模型归因（本条仅完成规则候选排序）",
                    "confidence": None,
                    "verdict": "PENDING_LLM",
                    "llm_status": msg,
                })
            for g in groups:
                g.update({
                    "attribution_zh": "待大模型归因（本条仅完成规则候选排序）",
                    "confidence": None,
                    "verdict": "PENDING_LLM",
                    "llm_status": msg,
                })
        # Inherit only from same-asset-class groups (not cross-asset spillover).
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
                        it["attribution_zh"] = (
                            "未找到明确的标的直接新闻；交叉溢出：" + (g.get("attribution_zh") or "")
                        )
                        it["confidence"] = g.get("confidence")
                        it["verdict"] = "MIXED"
                        it["inherited_from"] = g["id"]

        news = auxiliary_news_hotlist(events, day, prev_news_headlines, cfg)
        prev_news_headlines = [n["headline"] for n in news] + prev_news_headlines
        all_complete = all(it.get("day_complete") for it in items) if items else True
        # if the calendar day is not finished, mark incomplete
        if day_bounds(day)[1] > now:
            all_complete = False
        reports.append({
            "date": day.isoformat(),
            "timezone": "Asia/Kuala_Lumpur (UTC+8)",
            "generated_at_myt": to_myt_str(now),
            "all_complete": all_complete,
            "anomalies": items,
            "common_factors": groups,
            "news_hotlist": news,
            "universe": {
                "crypto": [x[1] for x in CRYPTO_UNIVERSE],
                "equity": [x[1] for x in EQUITY_UNIVERSE],
            },
            "params": asdict(cfg),
            "note": "价格异动是归因起点；新闻影响分与候选排序不使用未来收益。单源未核实已标注。",
        })

    catalog_cost = (all_pt / 1_000_000.0) * 0.10 + (all_ct / 1_000_000.0) * 0.40
    run_cost = {
        "model": cfg.llm_model,
        "llm_health_ok": health_ok,
        "llm_health_http": health_http,
        "llm_calls": llm_calls,
        "prompt_tokens": all_pt,
        "completion_tokens": all_ct,
        "catalog_cost_usd": round(catalog_cost, 6),
        "price_in_per_1m_usd": 0.10,
        "price_out_per_1m_usd": 0.40,
    }
    for r in reports:
        r["run_cost"] = run_cost

    # write per-day + combined
    paths = {}
    for r in reports:
        stem = f"attribution_{r['date']}"
        jp = out_dir / f"{stem}.json"
        mp = out_dir / f"{stem}.md"
        # don't dump full params with unused on every? keep
        slim = dict(r)
        jp.write_text(json.dumps(slim, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        mp.write_text(render_markdown([r], cfg), encoding="utf-8")
        paths[r["date"]] = {"json": str(jp), "md": str(mp)}
    combined_json = out_dir / "attribution_latest.json"
    combined_md = out_dir / "attribution_latest.md"
    combined_json.write_text(json.dumps({"cost": run_cost, "days": reports}, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    # append cost footer
    md = render_markdown(reports, cfg)
    md += (
        f"- 本次调用 {llm_calls} 次，输入 {all_pt} / 输出 {all_ct} tokens，目录价 ${catalog_cost:.4f}。\n"
        "- 事件语料主要来自已跑通的 BTC/USDT 与 NVDA 时间线，山寨币/宽基指数的直接新闻覆盖有限，"
        "无候选或低分时会明确标注「未找到明确新闻」。\n"
        "- 美股以 Yahoo 1h/15m K 线为准；UTC+8 日界下，美股常规交易多在当晚 22:30 开盘、次日 05:00 收盘（EST）。\n"
    )
    combined_md.write_text(md, encoding="utf-8")
    paths["combined"] = {"json": str(combined_json), "md": str(combined_md)}
    return {"dates": [d.isoformat() for d in dates], "paths": paths, "cost": run_cost, "health": {"ok": health_ok, "http": health_http, "msg": (health_msg or "")[:80]}}
