#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone

from fin_news_events.exporter import export_results
from fin_news_events.hotlist import run_hotlist
from fin_news_events.label_llm import run_label_with_llm
from fin_news_events.pipeline import run_batch_pipeline
from fin_news_events.streaming import run_polling_stream


def _parse_date(s: str, end_of_day: bool = False) -> datetime:
    dt = datetime.strptime(s.strip(), "%Y-%m-%d").replace(tzinfo=timezone.utc)
    if end_of_day:
        dt = dt.replace(hour=23, minute=59, second=59)
    return dt


def main() -> None:
    parser = argparse.ArgumentParser(description="AI Financial News Event System MVP")
    parser.add_argument("--symbol", required=False, default="BTC/USDT", help="Trading pair or equity ticker, e.g. BTC/USDT or NVDA")
    parser.add_argument("--days", type=int, default=7, help="Rolling lookback days (default: 7)")
    parser.add_argument("--start", type=str, default=None, help="Historical backfill start date YYYY-MM-DD (UTC)")
    parser.add_argument("--end", type=str, default=None, help="Historical backfill end date YYYY-MM-DD (UTC)")
    parser.add_argument("--output-dir", type=str, default="outputs", help="Directory for JSON/CSV/JSONL outputs")
    parser.add_argument("--slug", type=str, default=None, help="Optional filename slug override")
    parser.add_argument(
        "--classifier",
        choices=["auto", "rule", "openai", "jev_onnx", "hybrid"],
        default="auto",
        help="Classifier backend (jev_onnx = ONNX fast filter, hybrid = ONNX + LiteLLM/OpenRouter)",
    )
    parser.add_argument("--no-gdelt", action="store_true", help="Skip GDELT DOC API call")
    parser.add_argument("--extra-query", action="append", default=[], help="Extra query as tag::query")
    # Real-time streaming polling mode
    parser.add_argument("--poll", action="store_true", help="Run in low-latency polling & push mode")
    parser.add_argument("--interval", type=int, default=60, help="Polling interval in seconds (default: 60)")
    parser.add_argument("--cycles", type=int, default=2, help="Number of poll cycles before exit (default: 2)")
    parser.add_argument("--webhook", type=str, default=None, help="Optional webhook URL for Signal Bus push")
    parser.add_argument("--stream-out", type=str, default="outputs/signal_stream.jsonl", help="JSONL stream output path")
    # LLM labeling for distillation
    parser.add_argument("--label-with-llm", action="store_true", help="Annotate events using LiteLLM/OpenRouter for distillation")
    parser.add_argument("--label-input", type=str, default="outputs/timeline_btcusdt_7d.json", help="Timeline JSON input for --label-with-llm")
    parser.add_argument("--label-out", type=str, default="outputs/llm_distill_labels.jsonl", help="Distillation JSONL output path")
    parser.add_argument("--label-limit", type=int, default=2000, help="Max events to label in --label-with-llm")
    parser.add_argument("--label-workers", type=int, default=8, help="Concurrent LLM labeling workers")
    parser.add_argument("--label-build-pool", action="store_true", help="Build a time-split train+test labeling pool (all test + stratified train)")
    parser.add_argument("--label-use-gate", action="store_true", help="Only label events the ONNX gate would send to LLM")
    parser.add_argument("--llm-model", type=str, default=None, help="Optional LLM model override")
    parser.add_argument("--hotlist", action="store_true", help="Build UTC+8 move-attribution board (and auxiliary news hotlist)")
    parser.add_argument("--date", type=str, default=None, help="Hotlist date YYYY-MM-DD in UTC+8 (default: last 3 calendar days)")
    parser.add_argument("--hotlist-days", type=int, default=3, help="If --date is omitted, number of recent UTC+8 days to include")

    args = parser.parse_args()

    if args.label_with_llm:
        res = run_label_with_llm(
            input_json=None if args.label_build_pool else args.label_input,
            out_jsonl=args.label_out,
            limit=args.label_limit,
            use_gate=args.label_use_gate,
            model_override=args.llm_model,
            workers=args.label_workers,
            build_pool=args.label_build_pool,
        )
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return

    if args.hotlist:
        from datetime import date as date_cls
        from fin_news_events.models import MYT

        today = datetime.now(MYT).date()
        if args.date:
            d0 = datetime.strptime(args.date.strip(), "%Y-%m-%d").date()
            if args.start and args.end:
                d0 = datetime.strptime(args.start.strip(), "%Y-%m-%d").date()
                d1 = datetime.strptime(args.end.strip(), "%Y-%m-%d").date()
                days = []
                cur = d0
                while cur <= d1:
                    days.append(cur)
                    cur += timedelta(days=1)
            else:
                days = [d0]
        elif args.start and args.end:
            d0 = datetime.strptime(args.start.strip(), "%Y-%m-%d").date()
            d1 = datetime.strptime(args.end.strip(), "%Y-%m-%d").date()
            days = []
            cur = d0
            while cur <= d1:
                days.append(cur)
                cur += timedelta(days=1)
        else:
            n = max(1, int(args.hotlist_days))
            days = [today - timedelta(days=i) for i in range(n - 1, -1, -1)]
        res = run_hotlist(days, output_dir=args.output_dir, model_override=args.llm_model)
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return

    if args.poll:
        signals = run_polling_stream(
            symbol=args.symbol,
            interval_sec=args.interval,
            cycles=args.cycles,
            stream_out=args.stream_out,
            webhook_url=args.webhook,
            classifier_mode=args.classifier,
        )
        print(f"Polling finished. Emitted {len(signals)} SignalEvent(s) to {args.stream_out}")
        return

    now = datetime.now(timezone.utc)
    if args.start and args.end:
        start_dt = _parse_date(args.start, end_of_day=False)
        end_dt = _parse_date(args.end, end_of_day=True)
    elif args.start:
        start_dt = _parse_date(args.start, end_of_day=False)
        end_dt = now
    else:
        end_dt = now
        start_dt = now - timedelta(days=args.days)

    extra_q = []
    for raw_q in args.extra_query:
        if "::" in raw_q:
            t, q = raw_q.split("::", 1)
            extra_q.append((t.strip(), q.strip()))
        else:
            extra_q.append(("custom", raw_q.strip()))

    res = run_batch_pipeline(
        symbol=args.symbol,
        start_dt=start_dt,
        end_dt=end_dt,
        classifier_mode=args.classifier,
        include_gdelt=not args.no_gdelt,
        extra_queries=extra_q or None,
    )

    clean_slug = args.slug or f"{res['profile'].market_symbol.lower()}_{args.days}d"
    if args.start:
        clean_slug = args.slug or f"{res['profile'].market_symbol.lower()}_{args.start}_to_{args.end or 'now'}"

    paths = export_results(clean_slug, res["events"], res["evaluation"], output_dir=args.output_dir)
    ev = res["evaluation"]
    print(f"=== {res['profile'].canonical_symbol} | classifier={res['classifier_mode']} ===")
    print(
        f"Raw={ev['raw_items_fetched']} (unfiltered={ev['raw_unfiltered_fetched']}) -> "
        f"Clusters={ev['event_clusters_output']} (compression={ev['dedup_compression_ratio']:.1%})"
    )
    print(f"Layers={ev['layer_breakdown']} | Categories={ev['category_breakdown']}")
    print(f"Verification={ev['verification_breakdown']}")
    print(f"Market Validation={ev['market_validation']}")
    print("Outputs:", paths)


if __name__ == "__main__":
    main()
