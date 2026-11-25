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

## 2. Optional Plugins & LLM Mode

- **LLM Classification (`OPENAI_API_KEY`)**: Set `OPENAI_API_KEY` (and optional `OPENAI_BASE_URL`, `OPENAI_MODEL`) to enable `OpenAICompatibleClassifier`. When unset, the pipeline automatically runs `RuleLexiconClassifier` (`rule_lexicon_fallback`) and records `classifier_mode` on every event.
- **CryptoPanic Plugin (`CRYPTOPANIC_API_KEY`)**: Optional keyed source in `fin_news_events/sources/plugins.py`.

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
