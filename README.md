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

The product is **anomaly-first**: session-aware price moves are detected first, then news in the event window is scored and attributed. The system does not forecast prices. Full design (flow, Kafka topics, Redis/TiDB, Nacos including LiteLLM aliases, APIs, mermaid) is in [docs/architecture.md](docs/architecture.md). The interactive report is the same Page: [architecture and measured results](https://cursor.com/canvas/store-a2570073-d912-4e05-bcf0-9f6b2ef5bdfa/6576dd5b-a1a0-422b-9b63-5dc4f17858c8).

Daily attribution CLI:

```bash
python3 run.py --hotlist --market us --date 2026-11-24
python3 run.py --hotlist --market crypto --date 2026-11-24
python3 run.py --hotlist --market all --date 2026-11-23
```

| Python MVP Module | Production Go (`go-zero`) Service | Responsibility |
|---|---|---|
| `sources/*` (incl. `market_rss.py`, `google_news.py`), `streaming.py` | `ingest-job` + `ingest-rpc` | Market-wrap RSS, targeted + auto Google News, SEC/Newsroom/CMS, crypto RSS; ETag/304; Kafka `raw_news` |
| `entity_mapper.py` | `entity-rpc` | Ticker/alias/CIK/ecosystem dictionary (Nacos hot-reload) -> Kafka `normalized_news` |
| `dedup_cluster.py` | `dedup-cluster` | Redis URL/title Bloom + SimHash/MinHash LSH, 48h clustering -> `clustered_events` |
| `classifier.py`, `fast_classifier.py`, `scorer.py`, `llm_clients.py` | `classify-score` | jev/decision ONNX gate, then LiteLLM label alias; verification + transmission score -> event store / `scored_events` |
| `market_data.py`, `hotlist.detect_sessions` | `kline-ingest` + `session-calendar` | Binance/Yahoo klines; US ET regular session + overnight gap; crypto UTC+8 |
| `hotlist` anomaly detection | `anomaly-detect` | Daily return, z-score, 15m/1h jump windows -> Kafka `anomaly_windows`, Redis `anomaly:{date}` |
| `hotlist` scoring / common-factor / contrarian | `attribution-rpc` | Window candidates, rule scores, threshold selection, LiteLLM attribution + fact-check -> `attribution_results` |
| `streaming.py` (Signal Bus) | `push-gateway` | Minute-level Webhook / gRPC Stream / WS of anomalies and attributions |
| `market_data.py`, `evaluator.py` | `price-reaction` | Display-only `+1h/+4h/+24h` abnormal returns (never used in scoring) |
| `exporter.py`, `outputs/attribution_*.md` | `timeline-api` | Research timeline and `GET /v1/attribution` review board |
