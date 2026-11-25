from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class TargetProfile:
    raw_symbol: str
    canonical_symbol: str
    asset_class: str  # "CRYPTO" | "EQUITY"
    market_symbol: str  # e.g., "BTCUSDT" or "NVDA"
    benchmark_symbol: str  # e.g., "ETHUSDT" or "SPY"
    secondary_benchmark: str | None  # e.g., None or "QQQ"
    sec_cik: str | None = None
    yahoo_rss_tickers: list[str] = field(default_factory=list)
    direct_aliases: list[str] = field(default_factory=list)
    ecosystem_entities: list[str] = field(default_factory=list)
    direct_queries: list[str] = field(default_factory=list)
    cross_market_queries: list[str] = field(default_factory=list)


KNOWN_PROFILES: dict[str, dict] = {
    "BTC": {
        "canonical_symbol": "BTC/USDT",
        "asset_class": "CRYPTO",
        "market_symbol": "BTCUSDT",
        "benchmark_symbol": "ETHUSDT",
        "secondary_benchmark": None,
        "yahoo_rss_tickers": ["BTC-USD", "ETH-USD", "IBIT"],
        "direct_aliases": [
            "bitcoin", "btc", "btcusdt", "btc/usdt", "xbt",
        ],
        "ecosystem_entities": [
            "ibit", "gbtc", "fbtc", "bitcoin etf", "spot bitcoin",
            "microstrategy", "strategy", "saylor", "cleanspark", "mara",
            "riot platforms", "coldcard", "lightning network", "halving",
            "satoshi", "tether", "usdt", "binance", "coinbase", "kraken",
        ],
        "direct_queries": [
            "(Bitcoin OR BTC OR BTCUSDT)",
            "(Bitcoin ETF OR IBIT OR MicroStrategy OR Bitcoin miner)",
        ],
    },
    "ETH": {
        "canonical_symbol": "ETH/USDT",
        "asset_class": "CRYPTO",
        "market_symbol": "ETHUSDT",
        "benchmark_symbol": "BTCUSDT",
        "secondary_benchmark": None,
        "yahoo_rss_tickers": ["ETH-USD", "BTC-USD"],
        "direct_aliases": ["ethereum", "eth", "ethusdt", "ether"],
        "ecosystem_entities": [
            "vitalik", "lido", "eigenlayer", "arbitrum", "optimism",
            "base", "ethereum etf", "etha", "solana",
        ],
        "direct_queries": [
            "(Ethereum OR ETH OR ETHUSDT)",
            "(Ethereum ETF OR Vitalik OR Ethereum L2)",
        ],
    },
    "NVDA": {
        "canonical_symbol": "NVDA",
        "asset_class": "EQUITY",
        "market_symbol": "NVDA",
        "benchmark_symbol": "SPY",
        "secondary_benchmark": "QQQ",
        "sec_cik": "0001045810",
        "yahoo_rss_tickers": ["NVDA"],
        "direct_aliases": ["nvidia", "nvda"],
        "ecosystem_entities": [
            "jensen huang", "blackwell", "rubin", "hopper", "h100", "h200",
            "b200", "gb200", "cuda", "geforce", "tsmc", "amd", "broadcom",
            "openai", "anthropic", "hyperscaler", "ai chip", "ai chips",
            "semiconductor", "data center",
        ],
        "direct_queries": [
            "(NVIDIA OR NVDA OR \"Jensen Huang\")",
            "(NVIDIA AI chips OR Blackwell OR NVDA SEC)",
        ],
    },
}

DEFAULT_CROSS_MARKET_QUERIES = [
    ("macro_fed", "(Federal Reserve OR FOMC OR Jerome Powell OR interest rate OR CPI OR inflation OR Treasury yield OR US dollar)"),
    ("tradfi_flows", "(S&P 500 OR Nasdaq OR gold price OR crude oil OR institutional flows OR ETF inflows OR ETF outflows)"),
    ("tech_ai", "(AI valuation OR OpenAI OR Anthropic OR TSMC OR semiconductor export OR hyperscaler capex)"),
    ("politics_reg", "(SEC crypto OR CFTC OR White House tariff OR export controls OR antitrust OR geopolitical sanctions)"),
]


def resolve_target(symbol: str) -> TargetProfile:
    clean = symbol.strip().upper()
    base = clean.split("/")[0].split("-")[0]
    if base.endswith("USDT") and len(base) > 4:
        base = base[:-4]

    if base in KNOWN_PROFILES:
        cfg = KNOWN_PROFILES[base]
        return TargetProfile(
            raw_symbol=symbol,
            canonical_symbol=cfg["canonical_symbol"],
            asset_class=cfg["asset_class"],
            market_symbol=cfg["market_symbol"],
            benchmark_symbol=cfg["benchmark_symbol"],
            secondary_benchmark=cfg["secondary_benchmark"],
            sec_cik=cfg.get("sec_cik"),
            yahoo_rss_tickers=list(cfg["yahoo_rss_tickers"]),
            direct_aliases=list(cfg["direct_aliases"]),
            ecosystem_entities=list(cfg["ecosystem_entities"]),
            direct_queries=list(cfg["direct_queries"]),
            cross_market_queries=[q for _, q in DEFAULT_CROSS_MARKET_QUERIES],
        )

    # Generic fallback for arbitrary equity or crypto pair
    is_crypto = "/" in clean or clean.endswith("USDT") or clean.endswith("-USD")
    if is_crypto:
        mkt = f"{base}USDT"
        canon = f"{base}/USDT"
        return TargetProfile(
            raw_symbol=symbol,
            canonical_symbol=canon,
            asset_class="CRYPTO",
            market_symbol=mkt,
            benchmark_symbol="BTCUSDT" if base != "BTC" else "ETHUSDT",
            secondary_benchmark=None,
            yahoo_rss_tickers=[f"{base}-USD"],
            direct_aliases=[base.lower(), canon.lower(), mkt.lower()],
            ecosystem_entities=["bitcoin", "crypto", "binance", "sec"],
            direct_queries=[f"({base} OR {mkt} OR crypto)"],
            cross_market_queries=[q for _, q in DEFAULT_CROSS_MARKET_QUERIES],
        )
    else:
        return TargetProfile(
            raw_symbol=symbol,
            canonical_symbol=base,
            asset_class="EQUITY",
            market_symbol=base,
            benchmark_symbol="SPY",
            secondary_benchmark="QQQ",
            yahoo_rss_tickers=[base],
            direct_aliases=[base.lower()],
            ecosystem_entities=["earnings", "guidance", "sec", "nasdaq", "s&p 500"],
            direct_queries=[f"({base} stock OR {base} earnings)"],
            cross_market_queries=[q for _, q in DEFAULT_CROSS_MARKET_QUERIES],
        )


def extract_matched_entities(text: str, profile: TargetProfile) -> tuple[list[str], str]:
    """Return (matched_entities, layer_override) where layer is DIRECT if direct alias/ecosystem matched."""
    lower = text.lower()
    matched: list[str] = []

    has_direct = False
    for alias in profile.direct_aliases:
        if re.search(rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])", lower):
            matched.append(alias.upper() if len(alias) <= 5 else alias.title())
            has_direct = True

    has_eco = False
    for ent in profile.ecosystem_entities:
        if re.search(rf"(?<![a-z0-9]){re.escape(ent)}(?![a-z0-9])", lower):
            matched.append(ent.upper() if len(ent) <= 4 else ent.title())
            has_eco = True

    # Global macro / cross-market entities for interpretability
    global_keywords = [
        ("Fed/FOMC", r"\b(fed|federal reserve|fomc|powell|rate cut|rate hike|interest rate)\b"),
        ("Inflation/CPI", r"\b(cpi|pce|inflation|core inflation)\b"),
        ("US Treasury/DXY", r"\b(treasury|yield|bond|10-year|dxy|us dollar|liquidity)\b"),
        ("Equities/Nasdaq/S&P", r"\b(nasdaq|s&p 500|dow jones|equities|stock market)\b"),
        ("Gold/Oil", r"\b(gold|crude oil|oil price|brent|wti)\b"),
        ("ETF/Institutional", r"\b(etf|blackrock|fidelity|institutional|inflow|outflow)\b"),
        ("AI/Semis", r"\b(openai|anthropic|tsmc|amd|broadcom|ai chip|ai trade|capex)\b"),
        ("Politics/Tariffs/SEC", r"\b(trump|white house|sec|cftc|tariff|sanction|export control|europol|doj)\b"),
        ("Crypto Market", r"\b(bitcoin|ethereum|crypto|stablecoin|tether|usdt|usdc|liquidation|exploit|hack)\b"),
    ]
    for label, pat in global_keywords:
        if re.search(pat, lower) and label not in matched:
            matched.append(label)

    # Deduplicate preserving order
    deduped = list(dict.fromkeys(matched))
    if has_direct or (has_eco and len(deduped) > 0):
        # Strictly DIRECT only if direct alias or strong company/coin product is present
        layer = "DIRECT" if has_direct else "CROSS_MARKET"
    else:
        layer = "CROSS_MARKET"
    return deduped, layer
