from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Optional

import requests


@dataclass
class ClassificationResult:
    category: str  # MACRO | TRADFI | TECH_AI | POLITICS_REG | CRYPTO
    subcategory: str
    direction: str  # BULLISH | BEARISH | NEUTRAL | MIXED
    confidence: float
    classifier_mode: str
    rationale: str = ""
    send_to_llm: bool = True
    fast_gate_prob: Optional[float] = None
    fast_infer_ms: Optional[float] = None


CATEGORY_RULES: list[tuple[str, str, str, float]] = [
    ("POLITICS_REG", "enforcement_lawsuit", r"\b(subpoena|lawsuit|sued|indict|indictment|criminal|crackdown|europol|doj|sec charges|enforcement|settlement|fine|probe|investigation)\b", 1.5),
    ("POLITICS_REG", "geopolitics_tariffs", r"\b(tariff|tariffs|sanction|sanctions|export control|export controls|chip ban|trade war|geopolitic|national security)\b", 1.5),
    ("POLITICS_REG", "political_statement", r"\b(midterm|election|congress|senate|house|democrat|democrats|republican|republicans|gop|trump|white house|biden|lawmaker|legislation)\b", 1.3),
    ("POLITICS_REG", "regulation_policy", r"\b(sec |cftc|no-action|regulatory|regulation|bill|act|policy|license|approval|approved)\b", 1.2),
    ("TECH_AI", "leadership_governance", r"\b(ceo|reinstate|reinstates|reinstated|rehire|resign|step down|oust|board|governance|apologizes|therapy|chief executive|successor|fired)\b", 1.8),
    ("TECH_AI", "earnings_guidance", r"\b(earnings|revenue|eps|guidance|quarter|q1|q2|q3|q4|annual loss|profit|beat|miss|10-q|10-k|8-k|form 4|sec form)\b", 1.7),
    ("TECH_AI", "product_launch", r"\b(blackwell|rubin|h100|h200|b200|rtx|gpu|ai chip|ai chips|release|launch|unveil|ai agent|claude|gpt|cuda)\b", 1.3),
    ("TECH_AI", "valuation_capex", r"\b(valuation|capex|ai trade|data center|hyperscaler|bubble|ai retreat|ai stocks|semiconductor|foundry|tsmc|openai|anthropic)\b", 1.1),
    ("MACRO", "fed_rates", r"\b(fed|federal reserve|fomc|powell|waller|rate cut|rate hike|interest rate|hawkish|dovish|central bank|monetary policy)\b", 1.6),
    ("MACRO", "inflation_cpi", r"\b(cpi|pce|inflation|deflation|consumer price|producer price|ppi)\b", 1.6),
    ("MACRO", "employment_nfp", r"\b(payroll|nonfarm|nfp|unemployment|jobless|jobs report|labor market)\b", 1.5),
    ("MACRO", "usd_treasury_liquidity", r"\b(treasury|yield|yields|10-year|bond|dxy|dollar|liquidity|qt|qe|deficit|fiscal)\b", 1.3),
    ("CRYPTO", "hack_security", r"\b(hack|hacked|exploit|vulnerability|flaw|breach|stolen|drain|phishing|attack|coldcard|cybersecurity)\b", 1.7),
    ("CRYPTO", "liquidation_solvency", r"\b(liquidat|insolvency|bankrupt|bankruptcy|contagion|depeg|outage|halt|withdrawal freeze|solvency|margin call)\b", 1.7),
    ("CRYPTO", "exchange_listing", r"\b(binance|coinbase|kraken|perpetual|futures|listing|delist|collateral|margin|spot trading|options on)\b", 1.4),
    ("CRYPTO", "stablecoins_onchain", r"\b(stablecoin|tether|usdt|usdc|circle|on-chain|whale|wallet|exchange inflow|exchange outflow|cbdc)\b", 1.4),
    ("CRYPTO", "protocol_milestone", r"\b(upgrade|fork|mainnet|testnet|layer 2|l2|halving|staking|hashrate|miner|mining|taproot)\b", 1.3),
    ("CRYPTO", "altcoins_ecosystem", r"\b(ethereum|eth|solana|sol|xrp|cardano|dogecoin|altcoin|defi|nft)\b", 1.0),
    ("CRYPTO", "btc_eth_majors", r"\b(bitcoin|btc|btcusdt|satoshi|digital gold)\b", 0.9),
    ("TRADFI", "etf_institutional_flows", r"\b(etf|ibit|gbtc|fbtc|blackrock|fidelity|inflow|outflow|institutional|asset-management|custody|fund)\b", 1.4),
    ("TRADFI", "commodities_gold_oil", r"\b(gold|silver|crude|oil|brent|wti|diesel|commodity|commodities)\b", 1.2),
    ("TRADFI", "banking_credit", r"\b(bank|banking|credit|loan|lending|jpmorgan|goldman|morgan stanley|citigroup|credit card)\b", 1.2),
    ("TRADFI", "major_financing", r"\b(ipo|merger|acquisition|buyback|raise|funding|series [a-d]|billion deal)\b", 1.3),
    ("TRADFI", "equities_index", r"\b(s&p 500|nasdaq|dow jones|stock|stocks|equities|wall street|rally|sell-off)\b", 0.9),
]

BULLISH_WORDS = {
    "rise", "rises", "rising", "surge", "surges", "rally", "rallies", "jump", "jumps",
    "gain", "gains", "rebound", "recovery", "recover", "beat", "beats", "strong",
    "approve", "approved", "approval", "relief", "inflow", "inflows", "launch", "launches",
    "collaborates", "partnership", "rehire", "reinstate", "reinstates", "reinstated",
    "skyrocket", "skyrockets", "soar", "soars", "deal", "bullish", "record high",
    "drop criminal", "dismiss", "win", "wins", "growth", "boost", "optimism", "expand",
}

BEARISH_WORDS = {
    "fall", "falls", "falling", "slip", "slips", "drop", "drops", "plunge", "plunges",
    "sink", "sinks", "slump", "retreat", "sell-off", "selloff", "loss", "losses",
    "crash", "hack", "hacked", "exploit", "flaw", "subpoena", "lawsuit", "criminal",
    "crackdown", "tariff", "tariffs", "ban", "restrict", "warning", "fear", "fears",
    "risk", "crisis", "outflow", "outflows", "bankrupt", "liquidation", "decline",
    "declines", "miss", "misses", "cut", "turmoil", "wanes", "two-year low", "probe",
    "fizzles", "pull back", "pulls back", "delist", "hawkish", "tighter",
}


class BaseEventClassifier:
    def classify(self, text: str, target_symbol: str = "BTC/USDT", retrieval_layer: str = "DIRECT") -> ClassificationResult:
        raise NotImplementedError


class RuleLexiconClassifier(BaseEventClassifier):
    """Zero-key deterministic classifier using 5-category taxonomy + financial lexicon."""

    mode_name = "rule_lexicon_fallback"

    def classify(self, text: str, target_symbol: str = "BTC/USDT", retrieval_layer: str = "DIRECT") -> ClassificationResult:
        lower = text.lower()
        matched_cat = "TRADFI"
        matched_sub = "equities_index"
        hits = 0
        best_score = 0.0
        for cat, sub, pat, prio in CATEGORY_RULES:
            matches = re.findall(pat, lower)
            if matches:
                weight = len(matches) * prio
                if weight > best_score:
                    best_score = weight
                    matched_cat = cat
                    matched_sub = sub
                    hits = len(matches)

        bull_hits = sum(1 for w in BULLISH_WORDS if re.search(rf"\b{re.escape(w)}\b", lower))
        bear_hits = sum(1 for w in BEARISH_WORDS if re.search(rf"\b{re.escape(w)}\b", lower))

        if "rate hike" in lower or "hawkish" in lower:
            bear_hits += 1
        if any(p in lower for p in ("dollar rises", "dollar firmer", "yields rise", "inflation rises", "fewer rate cuts")):
            bear_hits += 2
        if "rate cut" in lower or "dovish" in lower:
            bull_hits += 1

        if bull_hits > bear_hits:
            direction = "BULLISH"
        elif bear_hits > bull_hits:
            direction = "BEARISH"
        elif bull_hits > 0 and bear_hits > 0:
            direction = "MIXED"
        else:
            direction = "NEUTRAL"

        conf = min(0.92, 0.52 + 0.08 * min(hits, 3) + 0.06 * abs(bull_hits - bear_hits))
        return ClassificationResult(
            category=matched_cat,
            subcategory=matched_sub,
            direction=direction,
            confidence=round(conf, 3),
            classifier_mode=self.mode_name,
            rationale=f"rule_hits={hits}, bull={bull_hits}, bear={bear_hits}",
        )


class OpenAICompatibleClassifier(BaseEventClassifier):
    """Pluggable LLM classifier via the LiteLLM gateway (LITELLM_MODEL_LABEL)."""

    def __init__(self):
        from fin_news_events.llm_clients import LiteLLMClient
        self.client = LiteLLMClient(purpose="label")
        self.mode_name = f"openai_compatible:{self.client.model}"
        self._fallback = RuleLexiconClassifier()

    def classify(self, text: str, target_symbol: str = "BTC/USDT", retrieval_layer: str = "DIRECT") -> ClassificationResult:
        res = self.client.extract_event(text[:300], text[300:], target_symbol, retrieval_layer)
        if res.status == "OK" and res.category:
            return ClassificationResult(
                category=res.category,
                subcategory=res.subcategory or "equities_index",
                direction=res.direction or "NEUTRAL",
                confidence=res.confidence or 0.7,
                classifier_mode=self.mode_name,
                rationale=res.rationale,
            )
        return self._fallback.classify(text, target_symbol, retrieval_layer)


class JevHybridClassifier(BaseEventClassifier):
    """Two-stage classifier: jev/decision ONNX milliseconds filter -> optional LiteLLM gateway."""

    def __init__(self, use_llm: bool = False):
        from fin_news_events.fast_classifier import JevFastClassifier
        from fin_news_events.llm_clients import LiteLLMClient
        self.fast = JevFastClassifier()
        self.use_llm = use_llm
        self.llm = LiteLLMClient(purpose="label") if use_llm else None
        self.llm_healthy = self.llm.check_health()[0] if (self.llm and self.llm.is_configured) else False
        self.rule_dir = RuleLexiconClassifier()
        self.mode_name = "jev_onnx+litellm" if (use_llm and self.llm_healthy) else "jev_decision_onnx"

    def classify(self, text: str, target_symbol: str = "BTC/USDT", retrieval_layer: str = "DIRECT") -> ClassificationResult:
        headline, _, summary = text.partition(". ")
        pred = self.fast.predict_one(target_symbol, retrieval_layer, headline, summary)
        rule_res = self.rule_dir.classify(text, target_symbol, retrieval_layer)

        if self.use_llm and self.llm_healthy and pred.send_to_llm and pred.category_prob < 0.72:
            ex = self.llm.extract_event(headline, summary, target_symbol, retrieval_layer)
            if ex.status == "OK" and ex.category:
                return ClassificationResult(
                    category=ex.category,
                    subcategory=ex.subcategory or pred.subcategory,
                    direction=ex.direction or rule_res.direction,
                    confidence=ex.confidence or pred.category_prob,
                    classifier_mode=f"jev_onnx+litellm:{self.llm.model}",
                    rationale=ex.rationale,
                    send_to_llm=True,
                    fast_gate_prob=pred.gate_prob,
                    fast_infer_ms=pred.infer_ms,
                )

        return ClassificationResult(
            category=pred.category,
            subcategory=pred.subcategory,
            direction=rule_res.direction,
            confidence=pred.category_prob,
            classifier_mode=self.mode_name,
            rationale=f"gate_p={pred.gate_prob:.3f}, cat_p={pred.category_prob:.3f}",
            send_to_llm=pred.send_to_llm,
            fast_gate_prob=pred.gate_prob,
            fast_infer_ms=pred.infer_ms,
        )


def get_classifier(mode: str = "auto") -> BaseEventClassifier:
    from fin_news_events.fast_classifier import JevFastClassifier
    from fin_news_events.llm_clients import LiteLLMClient

    if mode == "rule":
        return RuleLexiconClassifier()
    if mode == "jev_onnx":
        return JevHybridClassifier(use_llm=False)
    if mode == "hybrid":
        return JevHybridClassifier(use_llm=True)
    if mode == "openai":
        c = LiteLLMClient(purpose="label")
        if c.is_configured:
            return OpenAICompatibleClassifier()
        return RuleLexiconClassifier()
    # auto: prefer jev_onnx when trained models exist, else rule fallback
    if JevFastClassifier.is_available():
        return JevHybridClassifier(use_llm=False)
    return RuleLexiconClassifier()
