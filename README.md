# AI Financial News Event System (MVP)

An end-to-end, zero-API-key-required MVP for multi-asset financial news ingestion, two-layer (Direct + Cross-Market) entity mapping, incremental deduplication/clustering, pluggable event classification & verification scoring, real-time Signal Bus emission, and post-event market reaction validation (`+1h / +4h / +24h` returns, benchmark abnormal returns, and volatility z-scores).

## 1. Quick Start

```bash
cd /workspace/fin-news-events
pip install -r requirements.txt  # core deps already preinstalled on Python 3.13

# 7-day run for Crypto & US Equity
python3 run.py --symbol BTC/USDT --days 7
python3 run.py --symbol NVDA --days 7

# Historical backfill mode (--start / --end)
python3 run.py --symbol BTC/USDT --start 2026-10-20 --end 2026-11-17 --slug midterm2026_btcusdt
python3 run.py --symbol NVDA --start 2026-10-20 --end 2026-11-17 --slug midterm2026_nvda

# Minute-level polling & Signal Bus push mode (supports ETag/304 & Webhook)
python3 run.py --symbol BTC/USDT --poll --interval 60 --cycles 3 --stream-out outputs/signal_stream.jsonl

# Run unit tests
python3 -m unittest discover -s tests -v
```

## 2. LiteLLM Gateway & Optional Plugins

All model calls (attribution LLM, `--label-with-llm` distillation, and online fact-check) go through a single OpenAI-compatible LiteLLM client (`POST {LITELLM_BASE_URL}/chat/completions`). There is no direct OpenRouter or Perplexity SDK path.

### Connect to the company LiteLLM (usually only these)

Copy `.env.example` to `.env` (or `.env.litellm`) and set:

| Variable | Required | Default | Purpose |
|---|---|---|---|
| `LITELLM_BASE_URL` | yes | `http://127.0.0.1:4000/v1` | Gateway base URL, including `/v1` |
| `LITELLM_API_KEY` | yes | — | Gateway / virtual key |
| `LITELLM_MODEL_ATTRIBUTION` | no | `gemini-flash-lite` | `--hotlist` move attribution |
| `LITELLM_MODEL_LABEL` | no | `gemini-flash-lite` | `--label-with-llm` / classifier extraction |
| `LITELLM_MODEL_FACTCHECK` | no | `perplexity-sonar` | Online multi-source fact-check |
| `LITELLM_MODEL` | no | — | Fallback if a purpose-specific model is unset |

The alias names must exist in the gateway `model_list`. See `configs/litellm_config.yaml` for a local proxy example (`litellm --config configs/litellm_config.yaml --port 4000`). If the company already exposes the same aliases, you only change `LITELLM_BASE_URL` and `LITELLM_API_KEY`.

401 / 402 / timeout errors are recorded on the result (`AUTH_ERROR_401`, `PAYMENT_REQUIRED`, `TIMEOUT`) and the run continues without crashing; fact-check failure does not block attribution.

**Demo only:** if `LITELLM_API_KEY` is empty, `OPENROUTER_API_KEY` may be used, and `.env.openrouter` may still be loaded. When the base URL is an OpenRouter-compatible demo endpoint, aliases are mapped to `google/gemini-2.5-flash-lite` and `perplexity/sonar`. Do not commit real keys.

- **CryptoPanic Plugin (`CRYPTOPANIC_API_KEY`)**: Optional keyed source in `fin_news_events/sources/plugins.py`. When the LiteLLM key is unset, classification automatically uses `RuleLexiconClassifier` (`rule_lexicon_fallback`).

接公司 LiteLLM 时：把 `.env.example` 复制为 `.env`，通常只需改 `LITELLM_BASE_URL` 和 `LITELLM_API_KEY`；若公司网关的模型别名与默认值不同，再改 `LITELLM_MODEL_ATTRIBUTION` / `LITELLM_MODEL_LABEL` / `LITELLM_MODEL_FACTCHECK`。

## 3. Production Go + go-zero Service Mapping

| Python MVP Module | Production Go (`go-zero`) Service | Responsibility |
|---|---|---|
| `sources/*`, `streaming.py` | `ingest-job` + `ingest-rpc` | Low-latency conditional pollers (`ETag`/`304`), rate-limit/circuit breaking, Kafka `raw_news` producer |
| `entity_mapper.py` | `entity-rpc` | Ticker/alias/CIK/ecosystem dictionary (Nacos hot-reload) -> Kafka `normalized_news` |
| `dedup_cluster.py` | `dedup-cluster` (Kafka consumer + RPC) | Redis URL/title Bloom/Set dedup + SimHash/MinHash LSH rolling 48h clustering -> `clustered_events` |
| `classifier.py`, `scorer.py` | `classify-score` (Kafka consumer + LLM RPC) | OpenAI-compatible LLM classification, verification status, cross-market transmission & 0-100 scoring -> `scored_events` |
| `market_data.py` | `price-reaction` (Kafka consumer + cron) | Binance/Market Klines alignment (`+1h/+4h/+24h` abnormal return & z-score) -> TiDB `price_reactions` |
| `exporter.py` | `timeline-api` (go-zero REST API) | Research & post-mortem query API over TiDB + Redis hot cache |
| `streaming.py` (Signal Bus) | `push-gateway` | Consumes `scored_events` for sub-minute Webhook / WebSocket / internal signal bus push |
