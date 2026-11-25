from __future__ import annotations

import re
from dataclasses import dataclass

from fin_news_events.classifier import ClassificationResult
from fin_news_events.dedup_cluster import ActiveCluster
from fin_news_events.entity_mapper import TargetProfile

# Source credibility priors [0, 1]
SOURCE_CREDIBILITY: dict[str, float] = {
    "sec.gov": 0.99,
    "sec edgar": 0.99,
    "binance.com": 0.97,
    "binance official": 0.97,
    "nvidianews.nvidia.com": 0.97,
    "nvidia newsroom": 0.97,
    "reuters.com": 0.94,
    "reuters": 0.94,
    "wsj.com": 0.92,
    "wsj": 0.92,
    "bloomberg.com": 0.93,
    "bloomberg": 0.93,
    "ft.com": 0.92,
    "nytimes.com": 0.89,
    "the new york times": 0.89,
    "cnbc.com": 0.87,
    "cnbc": 0.87,
    "apnews.com": 0.90,
    "bbc.com": 0.88,
    "abcnews.go.com": 0.85,
    "nbcnews.com": 0.85,
    "coindesk.com": 0.84,
    "coindesk": 0.84,
    "theblock.co": 0.84,
    "the block": 0.84,
    "barrons.com": 0.85,
    "marketwatch.com": 0.81,
    "time.com": 0.82,
    "fidelity.com": 0.83,
    "cointelegraph.com": 0.76,
    "cointelegraph": 0.76,
    "decrypt.co": 0.76,
    "decrypt": 0.76,
    "finance.yahoo.com": 0.74,
    "yahoo finance": 0.74,
    "kraken.com": 0.84,
    "blog.kraken.com": 0.84,
    "fool.com": 0.65,
    "seekingalpha.com": 0.66,
}

# Base impact magnitude B in [0, 1] by subcategory
SUBCATEGORY_BASE_IMPACT: dict[str, float] = {
    "fed_rates": 0.92,
    "inflation_cpi": 0.88,
    "employment_nfp": 0.84,
    "usd_treasury_liquidity": 0.82,
    "etf_institutional_flows": 0.85,
    "liquidation_solvency": 0.94,
    "hack_security": 0.90,
    "earnings_guidance": 0.90,
    "leadership_governance": 0.88,
    "geopolitics_tariffs": 0.86,
    "enforcement_lawsuit": 0.82,
    "regulation_policy": 0.80,
    "political_statement": 0.76,
    "valuation_capex": 0.78,
    "product_launch": 0.76,
    "exchange_listing": 0.74,
    "stablecoins_onchain": 0.74,
    "banking_credit": 0.78,
    "major_financing": 0.76,
    "commodities_gold_oil": 0.68,
    "equities_index": 0.72,
    "protocol_milestone": 0.70,
    "btc_eth_majors": 0.72,
    "altcoins_ecosystem": 0.55,
}

# Cross-market transmission matrix: (weight, path_label)
TRANSMISSION_MATRIX: dict[str, dict[str, tuple[float, str]]] = {
    "CRYPTO": {
        "fed_rates": (0.88, "Fed/Rates → USD Liquidity & Risk Appetite → BTC"),
        "inflation_cpi": (0.84, "CPI/Inflation → Rate Path Repricing → BTC"),
        "employment_nfp": (0.78, "Labor/NFP → Fed Expectation → BTC"),
        "usd_treasury_liquidity": (0.86, "US10Y/DXY/Liquidity → Crypto Liquidity Beta → BTC"),
        "etf_institutional_flows": (0.90, "Spot ETF & Institutional Flows → Direct BTC Demand"),
        "equities_index": (0.68, "Nasdaq/S&P Risk-On/Off Correlation → BTC"),
        "valuation_capex": (0.62, "AI/Tech Risk Sentiment Spillover → BTC"),
        "commodities_gold_oil": (0.58, "Gold Safe-Haven / Macro Hedge Narrative → BTC"),
        "geopolitics_tariffs": (0.72, "Geopolitics/Tariffs → Risk-Off vs Sovereign Hedge → BTC"),
        "political_statement": (0.76, "US Election/Congress → Crypto Policy & Fiscal Deficit → BTC"),
        "regulation_policy": (0.82, "SEC/CFTC Regulatory Regime → Crypto Market Structure"),
        "enforcement_lawsuit": (0.78, "Enforcement/Crime Crackdown → Crypto Sentiment & Liquidity"),
        "leadership_governance": (0.48, "Mega-Cap Tech Governance Shock → Cross-Asset Volatility → BTC"),
        "earnings_guidance": (0.42, "Mega-Cap Tech Earnings → Nasdaq Risk Beta → BTC"),
        "banking_credit": (0.76, "Banking Stress / Credit Liquidity → BTC Hedge & Risk"),
        "btc_eth_majors": (0.95, "Direct BTC/Major Crypto Market Driver"),
        "hack_security": (0.85, "Crypto Security/Custody Trust Shock"),
        "liquidation_solvency": (0.92, "Leverage Liquidation / Solvency Contagion"),
        "exchange_listing": (0.75, "Exchange Product / Margin / Derivatives Structure"),
        "stablecoins_onchain": (0.84, "Stablecoin & On-Chain Liquidity Channel"),
    },
    "EQUITY": {
        "earnings_guidance": (0.94, "Direct Earnings / SEC Filing / Guidance → NVDA"),
        "leadership_governance": (0.92, "CEO/Board Governance & Political Intervention → NVDA"),
        "valuation_capex": (0.88, "AI Capex / Hyperscaler Demand / Tech Valuation → NVDA"),
        "product_launch": (0.86, "GPU/AI Chip Architecture & Ecosystem Launch → NVDA"),
        "geopolitics_tariffs": (0.88, "US-China Export Controls / Tariffs → NVDA Supply & Demand"),
        "political_statement": (0.78, "Congress/White House Tech & Tax Policy → NVDA"),
        "enforcement_lawsuit": (0.80, "Subpoena / Antitrust / Regulatory Inquiry → NVDA"),
        "regulation_policy": (0.76, "AI & Semiconductor Regulatory Policy → NVDA"),
        "fed_rates": (0.80, "Fed/Rates → Growth Equity Discount Rate → NVDA"),
        "inflation_cpi": (0.76, "Inflation/CPI → Real Yield & Multiple Compression → NVDA"),
        "usd_treasury_liquidity": (0.78, "US10Y/DXY → Long-Duration Tech Multiple → NVDA"),
        "employment_nfp": (0.70, "Labor/Macro Growth → Cyclical/Tech Beta → NVDA"),
        "equities_index": (0.72, "Nasdaq/QQQ/SPY Index Flow Beta → NVDA"),
        "etf_institutional_flows": (0.68, "Institutional Tech/Index Fund Flows → NVDA"),
        "commodities_gold_oil": (0.45, "Energy/Macro Input Cost → Broad Equity Sentiment"),
        "banking_credit": (0.62, "Credit Conditions → Enterprise IT & AI Financing"),
        "major_financing": (0.66, "AI Startup Megadeals → GPU Cluster Demand → NVDA"),
        "btc_eth_majors": (0.25, "Crypto Risk Sentiment Spillover (Low Direct Weight)"),
    },
}

RUMOR_PATTERNS = re.compile(
    r"\b(rumor|rumour|reportedly|allegedly|unconfirmed|sources say|consider issuing|could|may be|speculation)\b",
    re.IGNORECASE,
)


def get_source_credibility(source_name: str, domain: str) -> float:
    for key in (domain.lower(), source_name.lower()):
        if key in SOURCE_CREDIBILITY:
            return SOURCE_CREDIBILITY[key]
        for k, v in SOURCE_CREDIBILITY.items():
            if k in key:
                return v
    return 0.55


def assess_verification(cluster: ActiveCluster, credibilities: list[float]) -> tuple[str, str, float]:
    """Return (verification_status, detail, verification_factor V)."""
    has_primary = any(it.is_primary_official for it in cluster.items)
    unique_domains = sorted({it.source_domain for it in cluster.items if it.source_domain})
    credible_domains = {
        it.source_domain
        for it, c in zip(cluster.items, credibilities)
        if c >= 0.72 and it.source_domain
    }
    has_hedged = bool(RUMOR_PATTERNS.search(cluster.rep_title))

    if has_primary:
        return (
            "OFFICIAL_PRIMARY",
            f"Primary official source ({cluster.items[0].source_name}); {len(unique_domains)} domain(s)",
            1.00,
        )
    if len(credible_domains) >= 2:
        v_factor = 0.92 if has_hedged else 1.00
        return (
            "MULTI_SOURCE_CONFIRMED",
            f"Confirmed across {len(credible_domains)} independent credible domains ({', '.join(sorted(credible_domains)[:3])})",
            v_factor,
        )
    max_cred = max(credibilities) if credibilities else 0.55
    if max_cred >= 0.80 and not has_hedged:
        return (
            "SINGLE_TIER1_REPORTED",
            f"Single Tier-1 outlet ({cluster.items[0].source_name}, cred={max_cred:.2f}); awaiting secondary confirmation",
            0.88,
        )
    reason = "hedged/unconfirmed wording detected" if has_hedged else "single non-Tier-1 source"
    return (
        "UNVERIFIED_OR_RUMOR",
        f"Unconfirmed ({reason}; {len(unique_domains)} domain)",
        0.68,
    )


@dataclass
class ScoreResult:
    impact_score: float
    transmission_weight: float
    transmission_path: str
    source_credibility: float
    novelty: float
    verification_status: str
    verification_detail: str
    breakdown: dict[str, float]


def score_event(
    cluster: ActiveCluster,
    clf: ClassificationResult,
    profile: TargetProfile,
    retrieval_layer: str,
    recent_same_subcat_count: int = 0,
) -> ScoreResult:
    credibilities = [get_source_credibility(it.source_name, it.source_domain) for it in cluster.items]
    max_cred = max(credibilities) if credibilities else 0.55
    multi_boost = min(0.08, 0.03 * max(0, len({it.source_domain for it in cluster.items}) - 1))
    src_cred = min(1.0, max_cred + multi_boost)

    base_b = SUBCATEGORY_BASE_IMPACT.get(clf.subcategory, 0.68)

    if retrieval_layer == "DIRECT":
        t_weight = 1.00
        t_path = f"Direct Asset Exposure → {profile.canonical_symbol}"
    else:
        mat = TRANSMISSION_MATRIX.get(profile.asset_class, {})
        t_weight, t_path = mat.get(
            clf.subcategory,
            (0.55, f"Cross-Market Macro/Risk Spillover → {profile.canonical_symbol}"),
        )

    # Novelty decays with duplicate cluster reports and recent repetitive subcategory coverage
    k = len(cluster.items)
    cluster_novelty = 1.0 / (1.0 + 0.18 * max(0, k - 1))
    subcat_saturation = 1.0 / (1.0 + 0.12 * min(recent_same_subcat_count, 4))
    novelty = max(0.42, round(0.65 * cluster_novelty + 0.35 * subcat_saturation, 3))

    # Directional conviction M
    m_conviction = clf.confidence if clf.direction in ("BULLISH", "BEARISH") else 0.60 * clf.confidence

    v_status, v_detail, v_factor = assess_verification(cluster, credibilities)

    raw_weighted = 0.35 * base_b + 0.25 * t_weight + 0.20 * src_cred + 0.10 * novelty + 0.10 * m_conviction
    impact = round(max(0.0, min(100.0, 100.0 * raw_weighted * v_factor)), 1)

    return ScoreResult(
        impact_score=impact,
        transmission_weight=round(t_weight, 3),
        transmission_path=t_path,
        source_credibility=round(src_cred, 3),
        novelty=novelty,
        verification_status=v_status,
        verification_detail=v_detail,
        breakdown={
            "base_category_B": round(base_b, 3),
            "transmission_T": round(t_weight, 3),
            "credibility_C": round(src_cred, 3),
            "novelty_N": round(novelty, 3),
            "conviction_M": round(m_conviction, 3),
            "verification_V": round(v_factor, 3),
        },
    )
