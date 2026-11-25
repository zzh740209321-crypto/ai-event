from __future__ import annotations

import json
import random
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Optional

from fin_news_events.fast_classifier import JevFastClassifier
from fin_news_events.llm_clients import LiteLLMClient, PerplexityFactChecker
from fin_news_events.train_eval_jev import _apply_spot_check_audit, _derive_weak_label, _load_split, _norm_headline

# OpenRouter listed prices for google/gemini-2.5-flash-lite (USD per 1M tokens)
PRICE_IN_PER_M = 0.10
PRICE_OUT_PER_M = 0.40


def build_label_pool(limit: int = 2000, seed: int = 42) -> list[dict]:
    """All held-out test events plus a stratified train sample, up to `limit`."""
    train_rows, test_rows = _load_split()
    pool: list[dict] = []
    for r in test_rows:
        item = dict(r)
        item["split"] = "test"
        pool.append(item)

    remaining = max(0, limit - len(pool))
    by_cat: dict[str, list[dict]] = {}
    for r in train_rows:
        by_cat.setdefault(r["category"], []).append(r)
    rng = random.Random(seed)
    for rows in by_cat.values():
        rng.shuffle(rows)

    cats = list(by_cat.keys())
    selected_train: list[dict] = []
    # Round-robin from each category until remaining filled
    idx = {c: 0 for c in cats}
    while len(selected_train) < remaining and any(idx[c] < len(by_cat[c]) for c in cats):
        for c in cats:
            if len(selected_train) >= remaining:
                break
            i = idx[c]
            if i < len(by_cat[c]):
                item = dict(by_cat[c][i])
                item["split"] = "train"
                selected_train.append(item)
                idx[c] = i + 1
    pool.extend(selected_train)
    return pool


def _cost_usd(prompt_tokens: int, completion_tokens: int) -> float:
    return (prompt_tokens / 1_000_000.0) * PRICE_IN_PER_M + (completion_tokens / 1_000_000.0) * PRICE_OUT_PER_M


def run_label_with_llm(
    input_json: str | None = None,
    out_jsonl: str = "outputs/llm_distill_labels.jsonl",
    limit: int = 2000,
    use_gate: bool = False,
    model_override: Optional[str] = None,
    workers: int = 8,
    build_pool: bool = False,
) -> dict:
    """Label events using OpenRouter/LiteLLM (and optional Perplexity) for distillation."""
    if build_pool or not input_json:
        rows = build_label_pool(limit=limit)
    else:
        src = Path(input_json)
        if not src.exists():
            raise FileNotFoundError(f"Input file not found: {src}")
        rows = json.loads(src.read_text(encoding="utf-8"))
        if len(rows) > limit:
            rows = rows[:limit]

    client = LiteLLMClient(model_override=model_override)
    pplx = PerplexityFactChecker()
    ok, http_code, msg = client.check_health()

    summary = {
        "input_file": input_json or "built_time_split_pool",
        "total_rows": len(rows),
        "llm_base_url": client.base_url,
        "llm_model": client.model,
        "llm_health_ok": ok,
        "llm_health_http": http_code,
        "llm_health_msg": "OK" if ok else (msg[:160] if msg else ""),
        "perplexity_configured": pplx.is_configured,
        "labeled_count": 0,
        "error_count": 0,
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "estimated_cost_usd": 0.0,
        "price_in_per_1m_usd": PRICE_IN_PER_M,
        "price_out_per_1m_usd": PRICE_OUT_PER_M,
        "output_file": out_jsonl,
        "workers": workers,
        "use_gate": use_gate,
        "train_in_pool": sum(1 for r in rows if r.get("split") == "train"),
        "test_in_pool": sum(1 for r in rows if r.get("split") == "test"),
    }
    if not ok:
        print(
            f"[label-with-llm] LLM endpoint health check failed: HTTP {http_code}. "
            "No labels were generated or fabricated."
        )
        return summary

    jev = JevFastClassifier() if (use_gate and JevFastClassifier.is_available()) else None
    if jev is not None:
        rows = [
            r
            for r in rows
            if jev.predict_one(r["target_symbol"], r["retrieval_layer"], r["headline"], r.get("summary", "")).send_to_llm
        ]
        summary["after_gate"] = len(rows)

    out_p = Path(out_jsonl)
    out_p.parent.mkdir(parents=True, exist_ok=True)

    # Resume support: skip already labeled event_ids
    done_ids: set[str] = set()
    if out_p.exists():
        for line in out_p.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            rec = json.loads(line)
            if rec.get("status") == "OK" and rec.get("event_id"):
                done_ids.add(rec["event_id"])
    pending = [r for r in rows if r.get("event_id") not in done_ids]
    summary["already_labeled"] = len(done_ids)
    summary["pending"] = len(pending)

    lock = threading.Lock()
    labeled = 0
    errors = 0
    prompt_tokens = 0
    completion_tokens = 0

    def _one(r: dict) -> dict | None:
        res = client.extract_event(r["headline"], r.get("summary", ""), r["target_symbol"], r["retrieval_layer"])
        if res.status != "OK":
            return {"_error": True, "event_id": r.get("event_id"), "status": res.status, "raw_error": res.raw_error}
        fact = None
        if pplx.is_configured and r.get("subcategory") in ("leadership_governance", "enforcement_lawsuit"):
            fc = pplx.verify_claim(r["headline"], r["target_symbol"])
            fact = {"status": fc.status, "summary": fc.summary, "citations": fc.citations}
        return {
            "event_id": r["event_id"],
            "target_symbol": r["target_symbol"],
            "split": r.get("split", ""),
            "published_at_utc": r.get("published_at_utc", ""),
            "headline": r.get("headline", ""),
            "retrieval_layer": r.get("retrieval_layer", ""),
            "status": res.status,
            "model": res.model,
            "is_relevant": res.is_relevant,
            "category": res.category,
            "subcategory": res.subcategory,
            "direction": res.direction,
            "confidence": res.confidence,
            "materiality_score": res.materiality_score,
            "summary": res.summary,
            "rationale": res.rationale,
            "prompt_tokens": res.prompt_tokens,
            "completion_tokens": res.completion_tokens,
            "fact_check": fact,
        }

    with out_p.open("a", encoding="utf-8") as f, ThreadPoolExecutor(max_workers=max(1, workers)) as ex:
        futs = [ex.submit(_one, r) for r in pending]
        for fut in as_completed(futs):
            rec = fut.result()
            if rec is None:
                continue
            with lock:
                if rec.get("_error"):
                    errors += 1
                    summary["last_error"] = rec.get("raw_error", rec.get("status", ""))[:160]
                    continue
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                f.flush()
                labeled += 1
                prompt_tokens += int(rec.get("prompt_tokens") or 0)
                completion_tokens += int(rec.get("completion_tokens") or 0)
                if labeled % 100 == 0:
                    print(f"[label-with-llm] progress {labeled}/{len(pending)} errors={errors}")

    # Recount file (includes resumed rows)
    all_ok = []
    if out_p.exists():
        for line in out_p.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rec = json.loads(line)
                if rec.get("status") == "OK":
                    all_ok.append(rec)
    total_pt = sum(int(r.get("prompt_tokens") or 0) for r in all_ok)
    total_ct = sum(int(r.get("completion_tokens") or 0) for r in all_ok)
    summary["labeled_count"] = len(all_ok)
    summary["error_count"] = errors
    summary["prompt_tokens"] = total_pt
    summary["completion_tokens"] = total_ct
    summary["estimated_cost_usd"] = round(_cost_usd(total_pt, total_ct), 6)
    summary["this_run_new_labels"] = labeled
    return summary


def agreement_spotcheck(labels_path: str = "outputs/llm_distill_labels.jsonl", n: int = 80, seed: int = 7) -> dict:
    """Compare LLM labels vs audited weak-supervision labels on a random sample."""
    train_rows, test_rows = _load_split()
    by_id = {r["event_id"]: r for r in train_rows + test_rows}
    recs = []
    for line in Path(labels_path).read_text(encoding="utf-8").splitlines():
        if line.strip():
            rec = json.loads(line)
            if rec.get("status") == "OK" and rec.get("event_id") in by_id:
                recs.append(rec)
    rng = random.Random(seed)
    sample = recs if len(recs) <= n else rng.sample(recs, n)

    cat_agree = 0
    sub_agree = 0
    gate_agree = 0
    disagreements = []
    for rec in sample:
        src = by_id[rec["event_id"]]
        wg, wc, ws = _derive_weak_label(src)
        ag, ac, asub, _ = _apply_spot_check_audit(src, wg, wc, ws)
        llm_gate = 1 if rec.get("is_relevant") else 0
        if rec.get("category") == ac:
            cat_agree += 1
        if rec.get("subcategory") == asub:
            sub_agree += 1
        if llm_gate == ag:
            gate_agree += 1
        if rec.get("category") != ac or rec.get("subcategory") != asub:
            disagreements.append(
                {
                    "split": rec.get("split"),
                    "headline": src["headline"][:110],
                    "weak": f"{ac}/{asub} gate={ag}",
                    "llm": f"{rec.get('category')}/{rec.get('subcategory')} gate={llm_gate} conf={rec.get('confidence')}",
                }
            )
    n_s = len(sample)
    return {
        "sample_size": n_s,
        "category_agreement": round(cat_agree / n_s, 3) if n_s else None,
        "subcategory_agreement": round(sub_agree / n_s, 3) if n_s else None,
        "gate_agreement": round(gate_agree / n_s, 3) if n_s else None,
        "disagreement_examples": disagreements[:12],
    }
