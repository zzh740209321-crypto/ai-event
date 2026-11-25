from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from typing import Optional

import numpy as np
import pandas as pd
import requests

from fin_news_events.models import MarketReaction, to_myt_str, to_utc_iso

BINANCE_KLINES_URL = "https://api.binance.com/api/v3/klines"
YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
HEADERS = {"User-Agent": "FinNewsEventsMVP/0.2"}


def fetch_binance_klines(symbol: str, start_dt: datetime, end_dt: datetime, interval: str = "1h") -> pd.DataFrame:
    """Fetch OHLCV bars from Binance public spot API with pagination."""
    start_ms = int(start_dt.timestamp() * 1000)
    end_ms = int(end_dt.timestamp() * 1000)
    rows: list[list] = []
    cur = start_ms
    while cur < end_ms:
        resp = requests.get(
            BINANCE_KLINES_URL,
            params={"symbol": symbol, "interval": interval, "startTime": cur, "endTime": end_ms, "limit": 1000},
            timeout=12,
        )
        resp.raise_for_status()
        batch = resp.json()
        if not batch:
            break
        rows.extend(batch)
        last_open = int(batch[-1][0])
        if last_open <= cur or len(batch) < 1000:
            break
        step_ms = {
            "1m": 60_000, "3m": 180_000, "5m": 300_000, "15m": 900_000,
            "30m": 1_800_000, "1h": 3_600_000, "2h": 7_200_000, "4h": 14_400_000,
            "1d": 86_400_000,
        }.get(interval, 3_600_000)
        cur = last_open + step_ms
    if not rows:
        return pd.DataFrame(columns=["ts", "open", "high", "low", "close", "volume"]).set_index("ts")
    df = pd.DataFrame(
        [
            {
                "ts": datetime.fromtimestamp(r[0] / 1000.0, tz=timezone.utc),
                "open": float(r[1]),
                "high": float(r[2]),
                "low": float(r[3]),
                "close": float(r[4]),
                "volume": float(r[5]),
            }
            for r in rows
        ]
    )
    df = df.drop_duplicates(subset=["ts"]).sort_values("ts").set_index("ts")
    return df


def fetch_yahoo_bars(symbol: str, start_dt: datetime, end_dt: datetime, interval: str = "1h") -> pd.DataFrame:
    """Fetch OHLCV bars from Yahoo Finance public Chart API (1h up to ~730d, 1d for older history)."""
    p1 = int(start_dt.timestamp())
    p2 = int(end_dt.timestamp())
    resp = requests.get(
        YAHOO_CHART_URL.format(symbol=symbol),
        params={"interval": interval, "period1": p1, "period2": p2},
        headers=HEADERS,
        timeout=12,
    )
    if resp.status_code != 200 and interval == "1h":
        resp = requests.get(
            YAHOO_CHART_URL.format(symbol=symbol),
            params={"interval": "1d", "period1": p1, "period2": p2},
            headers=HEADERS,
            timeout=12,
        )
    resp.raise_for_status()
    result = resp.json().get("chart", {}).get("result")
    if not result:
        return pd.DataFrame(columns=["ts", "open", "high", "low", "close", "volume"]).set_index("ts")
    res = result[0]
    ts_list = res.get("timestamp", [])
    quote = res.get("indicators", {}).get("quote", [{}])[0]
    opens = quote.get("open", [])
    highs = quote.get("high", [])
    lows = quote.get("low", [])
    closes = quote.get("close", [])
    vols = quote.get("volume", [])
    records = []
    for i, ts in enumerate(ts_list):
        c = closes[i] if i < len(closes) else None
        if c is None:
            continue
        records.append(
            {
                "ts": datetime.fromtimestamp(ts, tz=timezone.utc),
                "open": float(opens[i]) if i < len(opens) and opens[i] is not None else float(c),
                "high": float(highs[i]) if i < len(highs) and highs[i] is not None else float(c),
                "low": float(lows[i]) if i < len(lows) and lows[i] is not None else float(c),
                "close": float(c),
                "volume": float(vols[i]) if i < len(vols) and vols[i] is not None else 0.0,
            }
        )
    if not records:
        return pd.DataFrame(columns=["ts", "open", "high", "low", "close", "volume"]).set_index("ts")
    df = pd.DataFrame(records).drop_duplicates(subset=["ts"]).sort_values("ts").set_index("ts")
    return df


def _lookup_price_at_or_after(df: pd.DataFrame, target_dt: datetime, max_lag_hours: float = 72.0) -> tuple[Optional[datetime], Optional[float]]:
    if df.empty:
        return None, None
    idx = df.index
    pos = idx.searchsorted(target_dt)
    if pos >= len(idx):
        return None, None
    bar_ts = idx[pos].to_pydatetime()
    if (bar_ts - target_dt).total_seconds() > max_lag_hours * 3600:
        return None, None
    return bar_ts, float(df.iloc[pos]["close"])


def _calc_forward_return(df: pd.DataFrame, anchor_ts: datetime, anchor_price: float, hours: int) -> Optional[float]:
    if df.empty or anchor_price <= 0:
        return None
    target_dt = anchor_ts + timedelta(hours=hours)
    # Find closest bar at or after target_dt (within tolerance)
    pos = df.index.searchsorted(target_dt)
    if pos >= len(df.index):
        return None
    bar_ts = df.index[pos].to_pydatetime()
    # Allow up to 72h gap for weekend equity gaps on 24h checks, tighter for 1h/4h
    max_gap_h = 4 if hours <= 4 else 72
    if (bar_ts - target_dt).total_seconds() > max_gap_h * 3600:
        return None
    fwd_price = float(df.iloc[pos]["close"])
    return (fwd_price - anchor_price) / anchor_price


def compute_hourly_vol(df: pd.DataFrame) -> float:
    if df.empty or len(df) < 5:
        return 0.01
    rets = df["close"].pct_change().dropna()
    # Estimate typical step in hours
    diffs = df.index.to_series().diff().dropna().dt.total_seconds() / 3600.0
    med_h = float(diffs.median()) if len(diffs) else 1.0
    med_h = max(1.0, med_h)
    std_step = float(rets.std())
    if not math.isfinite(std_step) or std_step <= 1e-6:
        return 0.01
    return std_step / math.sqrt(med_h)


def attach_market_reaction(
    pub_dt: datetime,
    target_df: pd.DataFrame,
    bench_df: pd.DataFrame,
    benchmark_symbol: str,
    hourly_vol: float,
    sec_bench_df: Optional[pd.DataFrame] = None,
    sec_bench_symbol: Optional[str] = None,
) -> Optional[MarketReaction]:
    if target_df.empty:
        return None
    anchor_ts, anchor_price = _lookup_price_at_or_after(target_df, pub_dt, max_lag_hours=72.0)
    if anchor_ts is None or anchor_price is None:
        return None

    lag_hours = (anchor_ts - pub_dt).total_seconds() / 3600.0
    note_parts = []
    if lag_hours > 2.0:
        note_parts.append(f"aligned_next_bar(+{lag_hours:.1f}h)")

    r1 = _calc_forward_return(target_df, anchor_ts, anchor_price, 1)
    r4 = _calc_forward_return(target_df, anchor_ts, anchor_price, 4)
    r24 = _calc_forward_return(target_df, anchor_ts, anchor_price, 24)

    b_ts, b_price = _lookup_price_at_or_after(bench_df, anchor_ts, max_lag_hours=4.0) if not bench_df.empty else (None, None)
    b1 = _calc_forward_return(bench_df, b_ts, b_price, 1) if (b_ts and b_price) else None
    b4 = _calc_forward_return(bench_df, b_ts, b_price, 4) if (b_ts and b_price) else None
    b24 = _calc_forward_return(bench_df, b_ts, b_price, 24) if (b_ts and b_price) else None

    ab1 = (r1 - b1) if (r1 is not None and b1 is not None) else None
    ab4 = (r4 - b4) if (r4 is not None and b4 is not None) else None
    ab24 = (r24 - b24) if (r24 is not None and b24 is not None) else None

    z1 = (r1 / (hourly_vol * math.sqrt(1))) if (r1 is not None and hourly_vol > 0) else None
    z4 = (r4 / (hourly_vol * math.sqrt(4))) if (r4 is not None and hourly_vol > 0) else None
    z24 = (r24 / (hourly_vol * math.sqrt(24))) if (r24 is not None and hourly_vol > 0) else None

    sec_ab24 = None
    if sec_bench_df is not None and not sec_bench_df.empty:
        sb_ts, sb_price = _lookup_price_at_or_after(sec_bench_df, anchor_ts, max_lag_hours=4.0)
        if sb_ts and sb_price:
            sb24 = _calc_forward_return(sec_bench_df, sb_ts, sb_price, 24)
            if r24 is not None and sb24 is not None:
                sec_ab24 = r24 - sb24

    if r24 is None:
        note_parts.append("24h_window_pending")

    return MarketReaction(
        anchor_time_utc=to_utc_iso(anchor_ts),
        anchor_time_myt=to_myt_str(anchor_ts),
        anchor_price=round(anchor_price, 4),
        benchmark_symbol=benchmark_symbol,
        ret_1h=round(r1 * 100, 3) if r1 is not None else None,
        ret_4h=round(r4 * 100, 3) if r4 is not None else None,
        ret_24h=round(r24 * 100, 3) if r24 is not None else None,
        bench_ret_1h=round(b1 * 100, 3) if b1 is not None else None,
        bench_ret_4h=round(b4 * 100, 3) if b4 is not None else None,
        bench_ret_24h=round(b24 * 100, 3) if b24 is not None else None,
        abnormal_ret_1h=round(ab1 * 100, 3) if ab1 is not None else None,
        abnormal_ret_4h=round(ab4 * 100, 3) if ab4 is not None else None,
        abnormal_ret_24h=round(ab24 * 100, 3) if ab24 is not None else None,
        vol_zscore_1h=round(z1, 2) if z1 is not None else None,
        vol_zscore_4h=round(z4, 2) if z4 is not None else None,
        vol_zscore_24h=round(z24, 2) if z24 is not None else None,
        secondary_benchmark_symbol=sec_bench_symbol,
        secondary_abnormal_ret_24h=round(sec_ab24 * 100, 3) if sec_ab24 is not None else None,
        data_note="; ".join(note_parts) if note_parts else "OK",
    )
