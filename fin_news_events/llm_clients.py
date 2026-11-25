from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import requests
import time

ENV_OPENROUTER_PATH = Path(__file__).resolve().parent.parent / ".env.openrouter"

ALLOWED_CATEGORIES = ("MACRO", "TRADFI", "TECH_AI", "POLITICS_REG", "CRYPTO")
ALLOWED_SUBCATEGORIES = {
    "MACRO": ("fed_rates", "inflation_cpi", "employment_nfp", "usd_treasury_liquidity"),
    "TRADFI": ("etf_institutional_flows", "equities_index", "commodities_gold_oil", "banking_credit", "major_financing"),
    "TECH_AI": ("leadership_governance", "earnings_guidance", "product_launch", "valuation_capex"),
    "POLITICS_REG": ("geopolitics_tariffs", "political_statement", "enforcement_lawsuit", "regulation_policy"),
    "CRYPTO": ("liquidation_solvency", "hack_security", "exchange_listing", "stablecoins_onchain", "protocol_milestone", "altcoins_ecosystem", "btc_eth_majors"),
}
SUBCATEGORY_ALIASES = {
    "mining": "protocol_milestone",
    "miner": "protocol_milestone",
    "halving": "protocol_milestone",
    "market_sentiment": "btc_eth_majors",
    "price_action": "btc_eth_majors",
    "bitcoin": "btc_eth_majors",
    "btc": "btc_eth_majors",
    "ethereum": "altcoins_ecosystem",
    "altcoin": "altcoins_ecosystem",
    "listing": "exchange_listing",
    "delisting": "exchange_listing",
    "hack": "hack_security",
    "exploit": "hack_security",
    "security": "hack_security",
    "etf": "etf_institutional_flows",
    "flows": "etf_institutional_flows",
    "institutional": "etf_institutional_flows",
    "fed": "fed_rates",
    "rates": "fed_rates",
    "interest_rate": "fed_rates",
    "cpi": "inflation_cpi",
    "inflation": "inflation_cpi",
    "treasury": "usd_treasury_liquidity",
    "dollar": "usd_treasury_liquidity",
    "dxy": "usd_treasury_liquidity",
    "yield": "usd_treasury_liquidity",
    "jobs": "employment_nfp",
    "nfp": "employment_nfp",
    "gold": "commodities_gold_oil",
    "oil": "commodities_gold_oil",
    "stocks": "equities_index",
    "equity": "equities_index",
    "nasdaq": "equities_index",
    "ceo": "leadership_governance",
    "governance": "leadership_governance",
    "board": "leadership_governance",
    "earnings": "earnings_guidance",
    "guidance": "earnings_guidance",
    "product": "product_launch",
    "chips": "valuation_capex",
    "semiconductor": "valuation_capex",
    "semiconductors": "valuation_capex",
    "capex": "valuation_capex",
    "valuation": "valuation_capex",
    "ai": "valuation_capex",
    "tariff": "geopolitics_tariffs",
    "export_control": "geopolitics_tariffs",
    "election": "political_statement",
    "congress": "political_statement",
    "lawsuit": "enforcement_lawsuit",
    "sec": "regulation_policy",
    "regulation": "regulation_policy",
    "stablecoin": "stablecoins_onchain",
    "liquidation": "liquidation_solvency",
    "bankruptcy": "liquidation_solvency",
}


def normalize_llm_taxonomy(category: str | None, subcategory: str | None) -> tuple[str, str]:
    cat = (category or "TRADFI").upper().strip()
    if cat not in ALLOWED_CATEGORIES:
        cat = "TRADFI"
    raw = (subcategory or "").lower().strip().replace(" ", "_").replace("-", "_")
    allowed = ALLOWED_SUBCATEGORIES[cat]
    if raw in allowed:
        return cat, raw
    # If the subcat belongs to another category, prefer that category
    for c, subs in ALLOWED_SUBCATEGORIES.items():
        if raw in subs:
            return c, raw
    alias = SUBCATEGORY_ALIASES.get(raw)
    if alias:
        for c, subs in ALLOWED_SUBCATEGORIES.items():
            if alias in subs:
                return c, alias
    # Token overlap fallback
    for token in raw.split("_"):
        alias = SUBCATEGORY_ALIASES.get(token)
        if alias:
            for c, subs in ALLOWED_SUBCATEGORIES.items():
                if alias in subs:
                    return c, alias
    fallback = {"MACRO": "usd_treasury_liquidity", "TRADFI": "equities_index", "TECH_AI": "valuation_capex", "POLITICS_REG": "political_statement", "CRYPTO": "btc_eth_majors"}[cat]
    return cat, fallback



def load_openrouter_env(env_path: Path = ENV_OPENROUTER_PATH) -> bool:
    """Silently load key/base_url from .env.openrouter into os.environ without printing values."""
    if not env_path.exists():
        return False
    loaded = False
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k = k.replace("export ", "").strip()
        v = v.strip().strip('"').strip("'")
        if k and v:
            os.environ.setdefault(k, v)
            loaded = True
    return loaded


@dataclass
class LLMExtractionResult:
    status: str  # "OK" | "SKIPPED_NO_KEY" | "AUTH_ERROR_401" | "ERROR"
    model: str
    category: Optional[str] = None
    subcategory: Optional[str] = None
    direction: Optional[str] = None
    confidence: Optional[float] = None
    is_relevant: Optional[bool] = None
    materiality_score: Optional[float] = None
    summary: str = ""
    rationale: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    raw_error: str = ""


class LiteLLMClient:
    """OpenAI-compatible structured JSON extractor supporting OpenRouter, LiteLLM, and OpenAI."""

    def __init__(self, model_override: Optional[str] = None):
        load_openrouter_env()
        self.api_key = (
            os.environ.get("LITELLM_API_KEY")
            or os.environ.get("OPENROUTER_API_KEY")
            or os.environ.get("OPENAI_API_KEY")
            or ""
        ).strip()
        self.base_url = (
            os.environ.get("LITELLM_BASE_URL")
            or os.environ.get("OPENROUTER_BASE_URL")
            or os.environ.get("OPENAI_BASE_URL")
            or "https://api.openai.com/v1"
        ).rstrip("/")
        default_model = (
            "google/gemini-2.5-flash-lite"
            if "openrouter.ai" in self.base_url
            else "gpt-4o-mini"
        )
        self.model = (
            model_override
            or os.environ.get("LITELLM_MODEL")
            or os.environ.get("OPENROUTER_MODEL")
            or os.environ.get("OPENAI_MODEL")
            or default_model
        ).strip()

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)

    def check_health(self) -> tuple[bool, int, str]:
        if not self.api_key:
            return False, 0, "NO_API_KEY"
        if "openrouter.ai" in self.base_url:
            try:
                r = requests.get(
                    f"{self.base_url}/auth/key",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    timeout=10,
                )
                if r.status_code == 200:
                    return True, 200, "OK"
                return False, r.status_code, r.text[:160]
            except Exception as exc:
                return False, 0, str(exc)
        return True, 200, "KEY_SET"

    def extract_event(self, headline: str, summary: str, target_symbol: str, retrieval_layer: str) -> LLMExtractionResult:
        if not self.api_key:
            return LLMExtractionResult(
                status="SKIPPED_NO_KEY",
                model=self.model,
                rationale="LITELLM_API_KEY / OPENROUTER_API_KEY / OPENAI_API_KEY not set",
            )

        allowed_subs = "; ".join(
            f"{cat}: {', '.join(subs)}" for cat, subs in ALLOWED_SUBCATEGORIES.items()
        )
        system_prompt = (
            "You are a quantitative financial news event extractor. Return strictly ONE JSON object with keys: "
            "is_relevant (bool; true if this news is material enough to send to a trading-signal LLM / human research timeline for the target asset), "
            "category (exactly one of MACRO|TRADFI|TECH_AI|POLITICS_REG|CRYPTO), "
            "subcategory (MUST be one of the allowed snake_case values listed below), "
            "direction (BULLISH|BEARISH|NEUTRAL|MIXED for the target asset), "
            "confidence (0.0-1.0), materiality_score (0-100), summary (1 sentence), rationale (short). "
            f"Allowed subcategories: {allowed_subs}. "
            "Do not invent new subcategory names."
        )
        user_prompt = (
            f"Target Asset: {target_symbol}\n"
            f"Retrieval Layer: {retrieval_layer}\n"
            f"Headline: {headline}\n"
            f"Snippet: {summary[:500]}"
        )
        last_err = ""
        for attempt in range(4):
            try:
                resp = requests.post(
                    f"{self.base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                    json={
                        "model": self.model,
                        "temperature": 0.1,
                        "max_tokens": 400,
                        "response_format": {"type": "json_object"},
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt},
                        ],
                    },
                    timeout=(5, 20),
                )
                if resp.status_code == 401:
                    return LLMExtractionResult(
                        status="AUTH_ERROR_401",
                        model=self.model,
                        raw_error=resp.text[:160],
                    )
                if resp.status_code == 429 or resp.status_code >= 500:
                    last_err = f"HTTP {resp.status_code}"
                    time.sleep(1.5 * (attempt + 1))
                    continue
                resp.raise_for_status()
                data = resp.json()
                usage = data.get("usage", {})
                content = data["choices"][0]["message"]["content"]
                parsed = json.loads(content)
                cat, sub = normalize_llm_taxonomy(parsed.get("category"), parsed.get("subcategory"))
                direction = str(parsed.get("direction", "NEUTRAL")).upper()
                if direction not in ("BULLISH", "BEARISH", "NEUTRAL", "MIXED"):
                    direction = "NEUTRAL"
                return LLMExtractionResult(
                    status="OK",
                    model=self.model,
                    category=cat,
                    subcategory=sub,
                    direction=direction,
                    confidence=float(parsed.get("confidence", 0.7)),
                    is_relevant=bool(parsed.get("is_relevant", True)),
                    materiality_score=float(parsed.get("materiality_score", 50.0)),
                    summary=str(parsed.get("summary", "")),
                    rationale=str(parsed.get("rationale", "")),
                    prompt_tokens=int(usage.get("prompt_tokens", 0)),
                    completion_tokens=int(usage.get("completion_tokens", 0)),
                )
            except Exception as exc:
                last_err = str(exc)
                time.sleep(1.2 * (attempt + 1))
        return LLMExtractionResult(status="ERROR", model=self.model, raw_error=last_err[:200])

    def attribute_price_move(self, user_payload: str) -> "AttributionLLMResult":
        """One-sentence Chinese attribution of an already-observed price move. Never forecasts prices."""
        if not self.api_key:
            return AttributionLLMResult(status="SKIPPED_NO_KEY", model=self.model, raw_error="no api key")
        system_prompt = (
            "You are a financial move-attribution assistant. The price move already happened; "
            "do NOT predict future prices. Return strictly ONE JSON object with keys: "
            "attribution_zh (one Chinese sentence), confidence (0.0-1.0), "
            "verdict (exactly one of ATTRIBUTED, EX_POST_REPORT, NO_CLEAR_NEWS, MIXED). "
            "Rules: only use the provided candidate news; never invent facts, numbers, or sources. "
            "If news was published after the jump start, treat it as a after-the-fact report and say so. "
            "If evidence is weak or only technical/liquidity explanations fit, set verdict to NO_CLEAR_NEWS "
            "and write: 未找到明确新闻，可能为流动性/清算/技术面. Do not force a story."
        )
        last_err = ""
        for attempt in range(4):
            try:
                resp = requests.post(
                    f"{self.base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                    json={
                        "model": self.model,
                        "temperature": 0.1,
                        "max_tokens": 220,
                        "response_format": {"type": "json_object"},
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_payload[:6000]},
                        ],
                    },
                    timeout=(5, 20),
                )
                if resp.status_code == 401:
                    return AttributionLLMResult(status="AUTH_ERROR_401", model=self.model, raw_error=resp.text[:160])
                if resp.status_code == 429 or resp.status_code >= 500:
                    last_err = f"HTTP {resp.status_code}"
                    time.sleep(1.5 * (attempt + 1))
                    continue
                resp.raise_for_status()
                data = resp.json()
                usage = data.get("usage", {})
                parsed = json.loads(data["choices"][0]["message"]["content"])
                verdict = str(parsed.get("verdict", "NO_CLEAR_NEWS")).upper()
                if verdict not in ("ATTRIBUTED", "EX_POST_REPORT", "NO_CLEAR_NEWS", "MIXED"):
                    verdict = "NO_CLEAR_NEWS"
                conf = float(parsed.get("confidence", 0.0))
                conf = max(0.0, min(1.0, conf))
                text = str(parsed.get("attribution_zh", "")).strip()
                if verdict == "NO_CLEAR_NEWS" and not text:
                    text = "未找到明确新闻，可能为流动性/清算/技术面"
                return AttributionLLMResult(
                    status="OK",
                    model=self.model,
                    attribution_zh=text,
                    confidence=conf,
                    verdict=verdict,
                    prompt_tokens=int(usage.get("prompt_tokens", 0)),
                    completion_tokens=int(usage.get("completion_tokens", 0)),
                )
            except Exception as exc:
                last_err = str(exc)
                time.sleep(1.2 * (attempt + 1))
        return AttributionLLMResult(status="ERROR", model=self.model, raw_error=last_err[:200])


@dataclass
class AttributionLLMResult:
    status: str
    model: str
    attribution_zh: str = ""
    confidence: float = 0.0
    verdict: str = "NO_CLEAR_NEWS"
    prompt_tokens: int = 0
    completion_tokens: int = 0
    raw_error: str = ""


@dataclass
class FactCheckResult:
    status: str  # "VERIFIED" | "DISPUTED" | "UNCONFIRMED" | "SKIPPED_NO_KEY" | "ERROR"
    model: str
    summary: str = ""
    citations: list[str] | None = None
    raw_error: str = ""


class PerplexityFactChecker:
    """Optional Perplexity Sonar multi-source fact-checking client for high-sensitivity claims (e.g. CEO changes)."""

    def __init__(self):
        load_openrouter_env()
        self.api_key = os.environ.get("PERPLEXITY_API_KEY", "").strip()
        self.model = os.environ.get("PERPLEXITY_MODEL", "sonar").strip()

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)

    def verify_claim(self, headline: str, target_symbol: str) -> FactCheckResult:
        if not self.api_key:
            return FactCheckResult(
                status="SKIPPED_NO_KEY",
                model=self.model,
                summary="PERPLEXITY_API_KEY not set; multi-source web fact-check skipped",
                citations=[],
            )
        prompt = (
            f"Fact-check this financial/corporate claim regarding {target_symbol}: '{headline}'. "
            "Respond in JSON with keys: status (VERIFIED|DISPUTED|UNCONFIRMED), summary (concise)."
        )
        try:
            resp = requests.post(
                "https://api.perplexity.ai/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                json={
                    "model": self.model,
                    "temperature": 0.1,
                    "messages": [{"role": "user", "content": prompt}],
                },
                timeout=20,
            )
            resp.raise_for_status()
            data = resp.json()
            text = data["choices"][0]["message"]["content"]
            citations = data.get("citations", [])
            parsed: dict[str, Any] = {}
            try:
                parsed = json.loads(text)
            except Exception:
                pass
            return FactCheckResult(
                status=str(parsed.get("status", "UNCONFIRMED")).upper(),
                model=self.model,
                summary=str(parsed.get("summary", text[:300])),
                citations=citations,
            )
        except Exception as exc:
            return FactCheckResult(status="ERROR", model=self.model, raw_error=str(exc), citations=[])
