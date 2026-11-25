from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import requests
import time

ROOT = Path(__file__).resolve().parent.parent

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



ENV_FILE_CANDIDATES = (
    ROOT / ".env",
    ROOT / ".env.litellm",
    ROOT / ".env.openrouter",  # demo-only fallback; never commit secrets
)

# Company LiteLLM friendly aliases. The gateway config maps these to upstream models.
DEFAULT_LITELLM_BASE_URL = "http://127.0.0.1:4000/v1"
DEFAULT_MODEL_ATTRIBUTION = "gemini-flash-lite"
DEFAULT_MODEL_LABEL = "gemini-flash-lite"
DEFAULT_MODEL_FACTCHECK = "perplexity-sonar"

# When the LiteLLM base URL is an OpenRouter-compatible demo endpoint, map aliases
# to OpenRouter model ids. All traffic still goes to {LITELLM_BASE_URL}/chat/completions.
_OPENROUTER_DEMO_MODEL_MAP = {
    "gemini-flash-lite": "google/gemini-2.5-flash-lite",
    "perplexity-sonar": "perplexity/sonar",
}

PURPOSE_MODEL_ENV = {
    "attribution": "LITELLM_MODEL_ATTRIBUTION",
    "label": "LITELLM_MODEL_LABEL",
    "factcheck": "LITELLM_MODEL_FACTCHECK",
}
PURPOSE_MODEL_DEFAULT = {
    "attribution": DEFAULT_MODEL_ATTRIBUTION,
    "label": DEFAULT_MODEL_LABEL,
    "factcheck": DEFAULT_MODEL_FACTCHECK,
}


def load_litellm_env() -> bool:
    """Load LiteLLM settings from .env files into os.environ (setdefault, never prints values)."""
    loaded = False
    for env_path in ENV_FILE_CANDIDATES:
        if not env_path.exists():
            continue
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


def load_openrouter_env(env_path: Path | None = None) -> bool:
    """Backward-compatible alias of load_litellm_env (demo .env.openrouter is already included)."""
    return load_litellm_env()


def _litellm_credentials() -> tuple[str, str]:
    load_litellm_env()
    api_key = (os.environ.get("LITELLM_API_KEY") or os.environ.get("OPENROUTER_API_KEY") or "").strip()
    base_url = (os.environ.get("LITELLM_BASE_URL") or os.environ.get("OPENROUTER_BASE_URL") or DEFAULT_LITELLM_BASE_URL).strip().rstrip("/")
    return api_key, base_url


def resolve_litellm_model(purpose: str = "attribution", model_override: Optional[str] = None) -> str:
    load_litellm_env()
    _, base_url = _litellm_credentials()
    purpose = (purpose or "attribution").strip().lower()
    if purpose not in PURPOSE_MODEL_ENV:
        purpose = "attribution"
    model = (
        (model_override or "").strip()
        or os.environ.get(PURPOSE_MODEL_ENV[purpose], "").strip()
        or os.environ.get("LITELLM_MODEL", "").strip()
        or PURPOSE_MODEL_DEFAULT[purpose]
    )
    if "openrouter.ai" in base_url:
        model = _OPENROUTER_DEMO_MODEL_MAP.get(model, model)
    return model


@dataclass
class LLMExtractionResult:
    status: str  # "OK" | "SKIPPED_NO_KEY" | "AUTH_ERROR_401" | "PAYMENT_REQUIRED" | "TIMEOUT" | "ERROR"
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


@dataclass
class ChatResult:
    ok: bool
    status: str
    http_status: int = 0
    data: dict[str, Any] | None = None
    raw_error: str = ""


class LiteLLMClient:
    """Single OpenAI-compatible client: all model calls go to the LiteLLM gateway /chat/completions."""

    def __init__(self, model_override: Optional[str] = None, purpose: str = "attribution"):
        self.purpose = (purpose or "attribution").strip().lower()
        self.api_key, self.base_url = _litellm_credentials()
        self.model = resolve_litellm_model(self.purpose, model_override)
        self.provider = "litellm"

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key and self.base_url)

    def check_health(self) -> tuple[bool, int, str]:
        if not self.api_key:
            return False, 0, "NO_API_KEY"
        if not self.base_url:
            return False, 0, "NO_BASE_URL"
        try:
            r = requests.get(
                f"{self.base_url}/models",
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=10,
            )
            if r.status_code == 200:
                return True, 200, "OK"
            if r.status_code in (401, 403):
                return False, r.status_code, "AUTH_ERROR"
            if r.status_code == 402:
                return False, 402, "PAYMENT_REQUIRED"
            if r.status_code == 404:
                # Some LiteLLM deployments omit /models; key+URL is enough to attempt calls.
                return True, 404, "MODELS_ENDPOINT_MISSING"
            return False, r.status_code, (r.text or "")[:160]
        except requests.Timeout:
            return False, 0, "TIMEOUT"
        except Exception as exc:
            return False, 0, str(exc)[:160]

    def chat_completions(
        self,
        messages: list[dict[str, str]],
        *,
        max_tokens: int = 400,
        temperature: float = 0.1,
        json_object: bool = True,
        timeout: float | tuple[float, float] = (5, 20),
        retries: int = 3,
        model: Optional[str] = None,
    ) -> ChatResult:
        """POST /chat/completions with graceful 401/402/timeout handling. Never raises to callers."""
        if not self.is_configured:
            return ChatResult(ok=False, status="SKIPPED_NO_KEY", raw_error="LITELLM_API_KEY not set")
        payload: dict[str, Any] = {
            "model": (model or self.model),
            "temperature": temperature,
            "max_tokens": max_tokens,
            "messages": messages,
        }
        if json_object:
            payload["response_format"] = {"type": "json_object"}
        last_err = ""
        last_http = 0
        attempts = max(1, retries)
        for attempt in range(attempts):
            try:
                resp = requests.post(
                    f"{self.base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                    json=payload,
                    timeout=timeout,
                )
                last_http = resp.status_code
                if resp.status_code == 401:
                    return ChatResult(ok=False, status="AUTH_ERROR_401", http_status=401, raw_error=resp.text[:200])
                if resp.status_code == 402:
                    return ChatResult(ok=False, status="PAYMENT_REQUIRED", http_status=402, raw_error=resp.text[:200])
                if resp.status_code == 429 or resp.status_code >= 500:
                    last_err = f"HTTP {resp.status_code}"
                    time.sleep(1.5 * (attempt + 1))
                    continue
                if resp.status_code >= 400:
                    return ChatResult(ok=False, status="ERROR", http_status=resp.status_code, raw_error=resp.text[:200])
                return ChatResult(ok=True, status="OK", http_status=resp.status_code, data=resp.json())
            except requests.Timeout:
                last_err = "TIMEOUT"
                last_http = 0
                time.sleep(1.2 * (attempt + 1))
            except Exception as exc:
                last_err = str(exc)[:200]
                time.sleep(1.2 * (attempt + 1))
        status = "TIMEOUT" if last_err == "TIMEOUT" else "ERROR"
        return ChatResult(ok=False, status=status, http_status=last_http, raw_error=last_err[:200])

    def extract_event(self, headline: str, summary: str, target_symbol: str, retrieval_layer: str) -> LLMExtractionResult:
        if not self.is_configured:
            return LLMExtractionResult(
                status="SKIPPED_NO_KEY",
                model=self.model,
                rationale="LITELLM_API_KEY not set",
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
        chat = self.chat_completions(
            [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
            max_tokens=400,
        )
        if not chat.ok or not chat.data:
            return LLMExtractionResult(status=chat.status, model=self.model, raw_error=chat.raw_error)
        try:
            usage = chat.data.get("usage", {})
            content = chat.data["choices"][0]["message"]["content"]
            parsed = json.loads(_strip_json_fence(content))
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
            return LLMExtractionResult(status="ERROR", model=self.model, raw_error=str(exc)[:200])

    def attribute_price_move(self, user_payload: str) -> "AttributionLLMResult":
        """One-sentence Chinese attribution of an already-observed price move. Never forecasts prices."""
        if not self.is_configured:
            return AttributionLLMResult(status="SKIPPED_NO_KEY", model=self.model, raw_error="LITELLM_API_KEY not set")
        system_prompt = (
            "You are a financial move-attribution assistant. The price move already happened; "
            "do NOT predict future prices. Return strictly ONE JSON object with keys: "
            "attribution_zh (one Chinese sentence), confidence (0.0-1.0), "
            "verdict (exactly one of ATTRIBUTED, EX_POST_REPORT, NO_CLEAR_NEWS, MIXED, CONTRARIAN). "
            "Rules: only use the provided candidate news and market tape/macro context; never invent facts, numbers, or sources. "
            "Distinguish pre-jump drivers (事前) vs post-jump/close market wraps (事后解释). "
            "If the move is a sector/profit-taking giveback of a prior-session surge while other sectors/Dow rose, state that clearly instead of calling it a broad market crash. "
            "When summarizing a common factor, mention every provided candidate cause that cleared the score cutoff "
            "(do not drop secondary drivers such as tariffs just because they are not ranked first). "
            "If the symbol is marked 逆势/contrarian versus the sector common factor, do NOT apply the sector's same-direction narrative to this name; "
            "use only name-specific news consistent with this symbol's daily direction, otherwise set verdict to CONTRARIAN or NO_CLEAR_NEWS. "
            "If evidence is weak or only technical/liquidity explanations fit, set verdict to NO_CLEAR_NEWS "
            "and write: 未找到明确新闻，可能为流动性/清算/技术面. Do not force a story."
        )
        chat = self.chat_completions(
            [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_payload[:8000]}],
            max_tokens=300,
        )
        if not chat.ok or not chat.data:
            return AttributionLLMResult(status=chat.status, model=self.model, raw_error=chat.raw_error)
        try:
            usage = chat.data.get("usage", {})
            raw_c = _strip_json_fence(chat.data["choices"][0]["message"]["content"])
            parsed = json.loads(raw_c)
            verdict = str(parsed.get("verdict", "NO_CLEAR_NEWS")).upper()
            if verdict not in ("ATTRIBUTED", "EX_POST_REPORT", "NO_CLEAR_NEWS", "MIXED", "CONTRARIAN"):
                verdict = "NO_CLEAR_NEWS"
            conf = max(0.0, min(1.0, float(parsed.get("confidence", 0.0))))
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
            return AttributionLLMResult(status="ERROR", model=self.model, raw_error=str(exc)[:200])

    def verify_claim(
        self,
        headline: str,
        target_symbol: str,
        session_date: str | None = None,
    ) -> "FactCheckResult":
        if not self.is_configured:
            return FactCheckResult(
                status="SKIPPED_NO_KEY",
                model=self.model,
                provider="litellm",
                verification_tier="unverified",
                summary="LITELLM_API_KEY not set; multi-source web fact-check skipped",
                citations=[],
            )
        date_hint = f" around {session_date}" if session_date else ""
        prompt = (
            f"Verify this financial/market event or attribution for {target_symbol}{date_hint}: '{headline[:500]}'. "
            "Check official sources (SEC filings, company newsroom) and independent Tier-1 news wires (Reuters, AP, Bloomberg, WSJ, CNBC). "
            "Return strictly ONE JSON object with keys: "
            "status (VERIFIED|DISPUTED|UNCONFIRMED), "
            "independent_sources_count (integer count of distinct authoritative outlets), "
            "authority_tier (official|tier1_multi|single_tier1|unverified), "
            "key_sources (array of up to 4 outlet/source names), "
            "summary (concise 1-2 sentences in Chinese noting what is confirmed and exact move/driver if applicable)."
        )
        chat = self.chat_completions(
            [{"role": "user", "content": prompt}],
            max_tokens=320,
            json_object=False,
            timeout=28,
            retries=2,
        )
        if not chat.ok or not chat.data:
            return FactCheckResult(
                status=chat.status,
                model=self.model,
                provider="litellm",
                verification_tier="unverified",
                raw_error=chat.raw_error,
                citations=[],
            )
        try:
            data = chat.data
            msg = data["choices"][0]["message"]
            text = _strip_json_fence(msg.get("content") or "")
            citations: list[str] = list(data.get("citations") or [])
            for ann in msg.get("annotations") or []:
                if isinstance(ann, dict) and ann.get("type") == "url_citation":
                    u = (ann.get("url_citation") or {}).get("url")
                    if u and u not in citations:
                        citations.append(u)
            parsed: dict[str, Any] = {}
            try:
                parsed = json.loads(text)
            except Exception:
                m_start = text.find("{")
                m_end = text.rfind("}")
                if m_start >= 0 and m_end > m_start:
                    try:
                        parsed = json.loads(text[m_start : m_end + 1])
                    except Exception:
                        parsed = {}
            status = str(parsed.get("status", "UNCONFIRMED")).upper()
            if status not in ("VERIFIED", "DISPUTED", "UNCONFIRMED"):
                status = "UNCONFIRMED"
            ind_cnt = int(parsed.get("independent_sources_count") or len(citations) or 0)
            auth_tier = str(parsed.get("authority_tier") or "").lower()
            if status == "VERIFIED" and (ind_cnt >= 2 or len(citations) >= 2 or auth_tier in ("official", "tier1_multi")):
                v_tier = "confirmed"
            elif status == "VERIFIED":
                v_tier = "single_source"
            else:
                v_tier = "unverified"
            usage = data.get("usage") or {}
            pt = int(usage.get("prompt_tokens", 0))
            ct = int(usage.get("completion_tokens", 0))
            raw_cost = usage.get("cost")
            cost_usd = float(raw_cost) if raw_cost is not None else 0.0
            return FactCheckResult(
                status=status,
                model=self.model,
                provider="litellm",
                verification_tier=v_tier,
                summary=str(parsed.get("summary", text[:320])),
                citations=citations[:8],
                independent_sources_count=ind_cnt,
                key_sources=[str(x) for x in (parsed.get("key_sources") or [])[:5]],
                prompt_tokens=pt,
                completion_tokens=ct,
                cost_usd=round(cost_usd, 6),
            )
        except Exception as exc:
            return FactCheckResult(
                status="ERROR",
                model=self.model,
                provider="litellm",
                verification_tier="unverified",
                raw_error=str(exc)[:220],
                citations=[],
            )


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
    status: str  # "VERIFIED" | "DISPUTED" | "UNCONFIRMED" | "SKIPPED_NO_KEY" | "AUTH_ERROR_401" | "PAYMENT_REQUIRED" | "TIMEOUT" | "ERROR"
    model: str
    provider: str = "litellm"
    verification_tier: str = "unverified"  # "confirmed" | "single_source" | "unverified"
    summary: str = ""
    citations: list[str] | None = None
    independent_sources_count: int = 0
    key_sources: list[str] | None = None
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost_usd: float = 0.0
    raw_error: str = ""


def _strip_json_fence(text: str) -> str:
    s = (text or "").strip()
    if s.startswith("```"):
        lines = s.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        s = "\n".join(lines).strip()
    return s


class LiteLLMFactChecker:
    """Online fact-check via the same LiteLLM gateway (LITELLM_MODEL_FACTCHECK)."""

    def __init__(self, model_override: Optional[str] = None, disabled: bool = False, **_ignored: Any):
        self.disabled = disabled
        self.client = LiteLLMClient(model_override=model_override, purpose="factcheck")
        self.provider = "litellm"
        self.model = self.client.model
        self.api_key = self.client.api_key
        self.base_url = self.client.base_url

    @property
    def is_configured(self) -> bool:
        return (not self.disabled) and self.client.is_configured

    def verify_claim(self, headline: str, target_symbol: str, session_date: str | None = None) -> FactCheckResult:
        if self.disabled:
            return FactCheckResult(
                status="SKIPPED_NO_KEY",
                model=self.model,
                provider="litellm",
                verification_tier="unverified",
                summary="Online fact-check disabled for this run",
                citations=[],
            )
        return self.client.verify_claim(headline, target_symbol, session_date)


# Historical alias: all fact-checks now go through LiteLLM, never a direct Perplexity/OpenRouter SDK.
PerplexityFactChecker = LiteLLMFactChecker
