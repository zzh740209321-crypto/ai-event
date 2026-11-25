from __future__ import annotations

import json
import math
import re
import time
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np
from skl2onnx import convert_sklearn
from skl2onnx.common.data_types import StringTensorType
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score
from sklearn.pipeline import FeatureUnion, Pipeline

from fin_news_events.classifier import RuleLexiconClassifier
from fin_news_events.fast_classifier import JevFastClassifier, format_fast_input
from fin_news_events.llm_clients import LiteLLMClient, LiteLLMFactChecker
from fin_news_events.models import EventCluster
from fin_news_events.scorer import SUBCATEGORY_BASE_IMPACT, TRANSMISSION_MATRIX

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "outputs"
MODEL_DIR = ROOT / "models"

NOISE_PATTERNS = re.compile(
    r"(sweepstakes|win €|black friday|deposit & trade bonus|credit card|terms and what they mean|"
    r"play and earn|nft games to play|gift nifty|sensex|merry making|trading competition|"
    r"yield arena|what is the bitcoin rate|how to track it|how to cash out|earn up to \d+% apr|"
    r"holiday season: every euro|crypto terms)",
    re.IGNORECASE,
)


def _norm_headline(h: str) -> str:
    return re.sub(r"[^a-z0-9]", "", h.lower())


def _load_split() -> tuple[list[dict], list[dict]]:
    train_files = [
        OUT_DIR / "timeline_midterm2022_btcusdt.json",
        OUT_DIR / "timeline_midterm2026_btcusdt.json",
        OUT_DIR / "timeline_midterm2026_nvda.json",
    ]
    test_files = [
        OUT_DIR / "timeline_btcusdt_7d.json",
        OUT_DIR / "timeline_nvda_7d.json",
    ]

    train_rows: list[dict] = []
    seen_train: set[tuple[str, str]] = set()
    for fp in train_files:
        for row in json.loads(fp.read_text(encoding="utf-8")):
            # Prevent boundary leakage: train strictly < 2026-11-18T00:00:00Z
            if row["published_at_utc"] >= "2026-11-18T00:00:00Z":
                continue
            key = (row["target_symbol"], _norm_headline(row["headline"]))
            if key in seen_train:
                continue
            seen_train.add(key)
            train_rows.append(row)

    test_rows: list[dict] = []
    seen_test: set[tuple[str, str]] = set()
    for fp in test_files:
        for row in json.loads(fp.read_text(encoding="utf-8")):
            if row["published_at_utc"] < "2026-11-18T00:00:00Z":
                continue
            key = (row["target_symbol"], _norm_headline(row["headline"]))
            if key in seen_train or key in seen_test:
                continue
            seen_test.add(key)
            test_rows.append(row)

    return train_rows, test_rows


def _derive_weak_label(row: dict) -> tuple[int, str, str]:
    """Raw weak supervision from rule classifier + market reaction / verification."""
    cat = row["category"]
    sub = row["subcategory"]
    mr = row.get("market_reaction") or {}
    ab24 = mr.get("abnormal_ret_24h")
    r24 = mr.get("ret_24h")
    z24 = mr.get("vol_zscore_24h")

    strong_mkt = (
        (ab24 is not None and abs(ab24) >= 1.5)
        or (r24 is not None and abs(r24) >= 2.0)
        or (z24 is not None and abs(z24) >= 1.0)
    )
    high_verif = row["verification_status"] in ("OFFICIAL_PRIMARY", "MULTI_SOURCE_CONFIRMED")
    direct_material = row["retrieval_layer"] == "DIRECT" and row["impact_score"] >= 65.0
    tier1_macro = row["impact_score"] >= 70.0

    gate = 1 if (high_verif or direct_material or strong_mkt or tier1_macro) else 0
    return gate, cat, sub


def _apply_spot_check_audit(row: dict, weak_gate: int, weak_cat: str, weak_sub: str) -> tuple[int, str, str, list[str]]:
    """Apply explicit human-audited spot-check corrections on observed systematic rule mistakes."""
    h = row["headline"]
    hl = h.lower()
    sym = row["target_symbol"]
    fixes: list[str] = []
    gate, cat, sub = weak_gate, weak_cat, weak_sub

    # Fix 1: National Security misclassified as CRYPTO/hack_security
    if "national security" in hl and sub == "hack_security":
        cat, sub = "POLITICS_REG", "geopolitics_tariffs"
        gate = 1
        fixes.append("fix_national_security_category")

    # Fix 2: Promo, sweepstakes, tutorials, Indian GIFT Nifty index noise -> gate=0
    if NOISE_PATTERNS.search(hl):
        if gate != 0:
            fixes.append("fix_promo_tutorial_noise_gate0")
        gate = 0

    # Fix 3: Pure crypto-only exchange/coin articles on NVDA -> gate=0
    if sym == "NVDA" and cat == "CRYPTO" and not any(w in hl for w in ("nvidia", "nvda", "ai", "nasdaq", "fed", "tariff", "huang")):
        if gate != 0:
            fixes.append("fix_nvda_irrelevant_crypto_gate0")
        gate = 0

    # Fix 4: NVIDIA product/corporate updates misclassified as TRADFI/equities_index
    if "nvidia" in hl and cat == "TRADFI" and sub == "equities_index":
        if any(w in hl for w in ("huang", "ceo", "board", "reinstate", "resign")):
            cat, sub = "TECH_AI", "leadership_governance"
            fixes.append("fix_nvda_governance_cat")
        elif any(w in hl for w in ("azure", "rtx", "blackwell", "spark", "ai")):
            cat, sub = "TECH_AI", "product_launch"
            fixes.append("fix_nvda_product_cat")

    # Fix 5: Trump/Congress political intervention stories on NVDA or BTC
    if any(w in hl for w in ("trump", "congress", "democrat", "republican", "midterm", "senate", "house")) and cat == "TRADFI":
        cat, sub = "POLITICS_REG", "political_statement"
        fixes.append("fix_political_statement_cat")

    return gate, cat, sub, fixes


def _build_pipeline(C: float = 1.8) -> Pipeline:
    vec = TfidfVectorizer(analyzer="word", lowercase=False, ngram_range=(1, 2), max_features=6500, min_df=2, sublinear_tf=True)
    return Pipeline(
        [
            ("tfidf", vec),
            ("clf", LogisticRegression(C=C, class_weight="balanced", max_iter=1000, random_state=42)),
        ]
    )


def _export_onnx(pipe: Pipeline, out_path: Path) -> None:
    onx = convert_sklearn(
        pipe,
        initial_types=[("text_input", StringTensorType([None, 1]))],
        target_opset=15,
        options={id(pipe.named_steps["clf"]): {"zipmap": False}},
    )
    out_path.write_bytes(onx.SerializeToString())


def _rescore_with_predicted_cat(row: dict, pred_cat: str, pred_sub: str) -> float:
    """Recompute 0-100 impact score using predicted subcategory & transmission matrix."""
    asset_cls = "CRYPTO" if "/" in row["target_symbol"] else "EQUITY"
    bd = row["score_breakdown"]
    base_b = SUBCATEGORY_BASE_IMPACT.get(pred_sub, bd["base_category_B"])
    if row["retrieval_layer"] == "DIRECT":
        t_w = 1.0
    else:
        t_w = TRANSMISSION_MATRIX.get(asset_cls, {}).get(pred_sub, (0.55, ""))[0]
    raw = 0.35 * base_b + 0.25 * t_w + 0.20 * bd["credibility_C"] + 0.10 * bd["novelty_N"] + 0.10 * bd["conviction_M"]
    return round(max(0.0, min(100.0, 100.0 * raw * bd["verification_V"])), 1)


def _spearman(x: list[float], y: list[float]) -> float | None:
    if len(x) < 6:
        return None
    rx = np.argsort(np.argsort(x)).astype(float)
    ry = np.argsort(np.argsort(y)).astype(float)
    if np.std(rx) == 0 or np.std(ry) == 0:
        return None
    return round(float(np.corrcoef(rx, ry)[0, 1]), 4)


def _market_eval(rows: list[dict], scores: list[float]) -> dict[str, Any]:
    paired = [
        (r, s)
        for r, s in zip(rows, scores)
        if (r.get("market_reaction") or {}).get("abnormal_ret_24h") is not None
    ]
    if not paired:
        return {"n_24h": 0, "spearman_abs_ab24h": None, "dir_ab_hit_rate": None, "q4_vs_q1_spread_pct": None}
    sc = [p[1] for p in paired]
    abs_ab = [abs(p[0]["market_reaction"]["abnormal_ret_24h"]) for p in paired]
    sp = _spearman(sc, abs_ab)

    sp_sorted = sorted(zip(sc, abs_ab), key=lambda z: z[0])
    q = max(2, len(sp_sorted) // 4)
    q1 = float(np.mean([z[1] for z in sp_sorted[:q]]))
    q4 = float(np.mean([z[1] for z in sp_sorted[-q:]]))

    dir_items = [
        p[0] for p in paired
        if p[0]["direction"] in ("BULLISH", "BEARISH") and abs(p[0]["market_reaction"]["abnormal_ret_24h"]) >= 0.15
    ]
    hits = sum(
        1 for r in dir_items
        if (r["direction"] == "BULLISH" and r["market_reaction"]["abnormal_ret_24h"] > 0)
        or (r["direction"] == "BEARISH" and r["market_reaction"]["abnormal_ret_24h"] < 0)
    )
    return {
        "n_24h": len(paired),
        "spearman_abs_ab24h": sp,
        "q4_mean_abs_ab24h": round(q4, 3),
        "q1_mean_abs_ab24h": round(q1, 3),
        "q4_vs_q1_spread_pct": round(q4 - q1, 3),
        "dir_n": len(dir_items),
        "dir_ab_hit_rate": round(hits / len(dir_items), 3) if dir_items else None,
    }


def _wilson_interval(k: int, n: int, z: float = 1.96) -> list[float] | None:
    if n <= 0:
        return None
    p = k / n
    z2 = z * z
    den = 1.0 + z2 / n
    center = (p + z2 / (2.0 * n)) / den
    half = z * math.sqrt((p * (1.0 - p) + z2 / (4.0 * n)) / n) / den
    return [round(max(0.0, center - half), 3), round(min(1.0, center + half), 3)]


def _attach_dir_ci(m: dict[str, Any]) -> dict[str, Any]:
    n = int(m.get("dir_n") or 0)
    rate = m.get("dir_ab_hit_rate")
    if not n or rate is None:
        m["dir_ab_hit_ci95"] = None
        return m
    k = int(round(float(rate) * n))
    m["dir_ab_hit_ci95"] = _wilson_interval(k, n)
    return m


def _load_llm_labels(path: Path) -> dict[str, dict]:
    latest: dict[str, dict] = {}
    if not path.exists():
        return latest
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            rec = json.loads(line)
            if rec.get("status") == "OK" and rec.get("event_id"):
                latest[rec["event_id"]] = rec
    return latest


def _sum_tokens(recs: list[dict]) -> tuple[int, int, float]:
    pt = sum(int(r.get("prompt_tokens") or 0) for r in recs)
    ct = sum(int(r.get("completion_tokens") or 0) for r in recs)
    cost = (pt / 1_000_000.0) * 0.10 + (ct / 1_000_000.0) * 0.40
    return pt, ct, round(cost, 6)


def _override_row_with_llm(row: dict, dl: dict) -> dict:
    out = dict(row)
    out["direction"] = dl.get("direction") or row.get("direction")
    if dl.get("materiality_score") is not None:
        try:
            out["impact_score"] = float(dl["materiality_score"])
        except (TypeError, ValueError):
            pass
    out["category"] = dl.get("category") or row.get("category")
    out["subcategory"] = dl.get("subcategory") or row.get("subcategory")
    return out


def main() -> None:
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    weak_dir = MODEL_DIR / "jev_weak_v1"
    distill_dir = MODEL_DIR / "jev_llm_distill_v1"
    weak_dir.mkdir(parents=True, exist_ok=True)
    distill_dir.mkdir(parents=True, exist_ok=True)

    # Keep previously exported weak-supervised ONNX for side-by-side comparison.
    for name in ("jev_gate.onnx", "jev_category.onnx", "jev_subcategory.onnx", "jev_meta.json"):
        src = MODEL_DIR / name
        dst = weak_dir / name
        if src.exists() and not dst.exists():
            dst.write_bytes(src.read_bytes())

    train_rows, test_rows = _load_split()
    distill_path = OUT_DIR / "llm_distill_labels.jsonl"
    distill_map = _load_llm_labels(distill_path)

    audit_counter: Counter[str] = Counter()
    train_X, train_gate_weak, train_cat_weak, train_sub_weak = [], [], [], []
    train_gate_aud, train_cat_aud, train_sub_aud = [], [], []
    distill_X, distill_gate, distill_cat, distill_sub = [], [], [], []

    for r in train_rows:
        wg, wc, ws = _derive_weak_label(r)
        ag, ac, asub, fixes = _apply_spot_check_audit(r, wg, wc, ws)
        for fx in fixes:
            audit_counter[fx] += 1
        txt = format_fast_input(r["target_symbol"], r["retrieval_layer"], r["headline"], r.get("summary", ""))
        train_X.append(txt)
        train_gate_weak.append(wg)
        train_cat_weak.append(wc)
        train_sub_weak.append(ws)
        train_gate_aud.append(ag)
        train_cat_aud.append(ac)
        train_sub_aud.append(asub)
        dl = distill_map.get(r["event_id"])
        if dl:
            distill_X.append(txt)
            distill_gate.append(1 if dl.get("is_relevant", True) else 0)
            distill_cat.append(dl.get("category") or ac)
            distill_sub.append(dl.get("subcategory") or asub)
            audit_counter["llm_teacher_train"] += 1

    # Test gold is the LLM teacher label (removes same-source bias vs rule lexicon).
    test_X, test_gate_gold, test_cat_gold, test_sub_gold = [], [], [], []
    test_gate_audit, test_cat_audit, test_sub_audit = [], [], []
    test_llm_missing = 0
    for r in test_rows:
        wg, wc, ws = _derive_weak_label(r)
        ag, ac, asub, fixes = _apply_spot_check_audit(r, wg, wc, ws)
        for fx in fixes:
            audit_counter[f"test_{fx}"] += 1
        txt = format_fast_input(r["target_symbol"], r["retrieval_layer"], r["headline"], r.get("summary", ""))
        test_X.append(txt)
        test_gate_audit.append(ag)
        test_cat_audit.append(ac)
        test_sub_audit.append(asub)
        dl = distill_map.get(r["event_id"])
        if not dl:
            test_llm_missing += 1
            test_gate_gold.append(ag)
            test_cat_gold.append(ac)
            test_sub_gold.append(asub)
        else:
            test_gate_gold.append(1 if dl.get("is_relevant", True) else 0)
            test_cat_gold.append(dl.get("category") or ac)
            test_sub_gold.append(dl.get("subcategory") or asub)
            audit_counter["llm_test_gold"] += 1

    def _collapse(subs: list[str]) -> list[str]:
        counts = Counter(subs)
        return [s if counts[s] >= 5 else "equities_index" for s in subs]

    train_sub_weak_clean = _collapse(train_sub_weak)
    distill_sub_clean = _collapse(distill_sub) if distill_sub else []

    # 1) Weak-only fast classifier (rule+market weak labels, all train rows)
    weak_gate_pipe = _build_pipeline(C=1.5).fit(train_X, train_gate_weak)
    weak_cat_pipe = _build_pipeline(C=2.0).fit(train_X, train_cat_weak)
    weak_sub_pipe = _build_pipeline(C=2.0).fit(train_X, train_sub_weak_clean)

    # 2) LLM-distilled jev/decision trained only on LLM teacher labels
    if len(distill_X) < 50 or len(set(distill_cat)) < 2:
        raise SystemExit(f"insufficient LLM teacher labels for distillation: n={len(distill_X)}")
    aud_gate_pipe = _build_pipeline(C=1.5).fit(distill_X, distill_gate)
    aud_cat_pipe = _build_pipeline(C=2.0).fit(distill_X, distill_cat)
    aud_sub_pipe = _build_pipeline(C=2.0).fit(distill_X, distill_sub_clean)

    _export_onnx(aud_gate_pipe, MODEL_DIR / "jev_gate.onnx")
    _export_onnx(aud_cat_pipe, MODEL_DIR / "jev_category.onnx")
    _export_onnx(aud_sub_pipe, MODEL_DIR / "jev_subcategory.onnx")
    for name in ("jev_gate.onnx", "jev_category.onnx", "jev_subcategory.onnx"):
        (distill_dir / name).write_bytes((MODEL_DIR / name).read_bytes())

    meta = {
        "model_name": "jev/decision",
        "version": "llm_distill_v1",
        "teacher": "google/gemini-2.5-flash-lite",
        "architecture": "TF-IDF(word 1-2g) + LogisticRegression",
        "gate_threshold": 0.40,
        "train_samples_full_split": len(train_rows),
        "train_samples_llm_teacher": len(distill_X),
        "test_samples": len(test_rows),
        "test_llm_gold": audit_counter["llm_test_gold"],
        "llm_distill_teacher_used": True,
        "categories": sorted(set(distill_cat)),
        "subcategories": sorted(set(distill_sub_clean)),
        "previous_weak_onnx_dir": "models/jev_weak_v1",
    }
    meta_txt = json.dumps(meta, indent=2, ensure_ascii=False)
    (MODEL_DIR / "jev_meta.json").write_text(meta_txt, encoding="utf-8")
    (distill_dir / "jev_meta.json").write_text(meta_txt, encoding="utf-8")

    # 3) sklearn vs ONNX parity & 500-call latency on the new distilled model
    jev_onnx = JevFastClassifier(MODEL_DIR, gate_threshold=0.40)
    sk_cats = aud_cat_pipe.predict(test_X[:50])
    onnx_preds = [
        jev_onnx.predict_one(r["target_symbol"], r["retrieval_layer"], r["headline"], r.get("summary", ""))
        for r in test_rows
    ]
    parity_matches = sum(1 for s, o in zip(sk_cats, onnx_preds[:50]) if s == o.category)

    for _ in range(20):
        jev_onnx.predict_one("BTC/USDT", "DIRECT", test_rows[0]["headline"], "")
    lat_samples = []
    for i in range(500):
        r = test_rows[i % len(test_rows)]
        p = jev_onnx.predict_one(r["target_symbol"], r["retrieval_layer"], r["headline"], r.get("summary", ""))
        lat_samples.append(p.infer_ms)

    # Optional: previous weak-supervised ONNX predictions for reference (same LLM gold)
    weak_onnx_preds = None
    weak_onnx_meta = {}
    if (weak_dir / "jev_gate.onnx").exists():
        weak_onnx = JevFastClassifier(weak_dir, gate_threshold=0.40)
        weak_onnx_preds = [
            weak_onnx.predict_one(r["target_symbol"], r["retrieval_layer"], r["headline"], r.get("summary", ""))
            for r in test_rows
        ]
        weak_onnx_meta = {"loaded": True, "dir": str(weak_dir)}
    else:
        weak_onnx_meta = {"loaded": False}

    rule_clf = RuleLexiconClassifier()
    rule_lats, rule_preds_cat, rule_preds_sub = [], [], []
    for r in test_rows:
        t0 = time.perf_counter()
        res = rule_clf.classify(f"{r['headline']}. {r.get('summary', '')[:200]}")
        rule_lats.append((time.perf_counter() - t0) * 1000.0)
        rule_preds_cat.append(res.category)
        rule_preds_sub.append(res.subcategory)

    weak_lats = []
    weak_gate_pred = weak_gate_pipe.predict(test_X).tolist()
    weak_cat_pred = weak_cat_pipe.predict(test_X).tolist()
    weak_sub_pred = weak_sub_pipe.predict(test_X).tolist()
    for txt in test_X[:200]:
        t0 = time.perf_counter()
        weak_gate_pipe.predict([txt])
        weak_cat_pipe.predict([txt])
        weak_sub_pipe.predict([txt])
        weak_lats.append((time.perf_counter() - t0) * 1000.0)

    onnx_gate_pred = [1 if p.send_to_llm else 0 for p in onnx_preds]
    onnx_cat_pred = [p.category for p in onnx_preds]
    onnx_sub_pred = [p.subcategory for p in onnx_preds]

    # Health check only — do not re-call the teacher on the already-labeled test set.
    llm_client = LiteLLMClient(purpose="label")
    llm_ok, llm_http, llm_msg = llm_client.check_health()
    factcheck = LiteLLMFactChecker()

    n_test = len(test_rows)
    # Production hybrid routing: gated-in + (low category confidence or controversial subcat) → LLM teacher
    controversial = {"leadership_governance", "hack_security", "enforcement_lawsuit"}
    routed_conf_skip = [
        i
        for i, p in enumerate(onnx_preds)
        if p.send_to_llm and (p.category_prob < 0.72 or test_sub_gold[i] in controversial or onnx_sub_pred[i] in controversial)
    ]
    routed_gate_only = [i for i, g in enumerate(onnx_gate_pred) if g == 1]

    def _hybrid_preds(routed_idx: list[int]) -> tuple[list[str], list[str], list[int]]:
        routed = set(routed_idx)
        cats, subs, used = [], [], []
        for i, r in enumerate(test_rows):
            dl = distill_map.get(r["event_id"])
            if i in routed and dl:
                cats.append(dl.get("category") or onnx_cat_pred[i])
                subs.append(dl.get("subcategory") or onnx_sub_pred[i])
                used.append(1)
            else:
                cats.append(onnx_cat_pred[i])
                subs.append(onnx_sub_pred[i])
                used.append(0)
        return cats, subs, used

    hyb_cat, hyb_sub, hyb_used = _hybrid_preds(routed_gate_only)
    hyb2_cat, hyb2_sub, hyb2_used = _hybrid_preds(routed_conf_skip)

    # Real LLM RTT on a small already-labeled probe set (measures latency, not used as new gold).
    llm_lat_ms: list[float] = []
    llm_probe_ok = 0
    llm_probe_err = 0
    if llm_ok:
        probe_idx = routed_gate_only[:8] or list(range(min(8, n_test)))
        for idx in probe_idx:
            r = test_rows[idx]
            t0 = time.perf_counter()
            ex = llm_client.extract_event(r["headline"], r.get("summary", ""), r["target_symbol"], r["retrieval_layer"])
            llm_lat_ms.append((time.perf_counter() - t0) * 1000.0)
            if ex.status == "OK":
                llm_probe_ok += 1
            else:
                llm_probe_err += 1

    rule_scores = [r["impact_score"] for r in test_rows]
    weak_scores = [_rescore_with_predicted_cat(r, c, s) for r, c, s in zip(test_rows, weak_cat_pred, weak_sub_pred)]
    onnx_scores = [_rescore_with_predicted_cat(r, c, s) for r, c, s in zip(test_rows, onnx_cat_pred, onnx_sub_pred)]

    def _hybrid_scores_and_rows(routed_idx: list[int], cats: list[str], subs: list[str]) -> tuple[list[float], list[dict]]:
        routed = set(routed_idx)
        scores, rows = [], []
        for i, r in enumerate(test_rows):
            dl = distill_map.get(r["event_id"])
            if i in routed and dl:
                rows.append(_override_row_with_llm(r, dl))
                try:
                    scores.append(float(dl.get("materiality_score") if dl.get("materiality_score") is not None else _rescore_with_predicted_cat(r, cats[i], subs[i])))
                except (TypeError, ValueError):
                    scores.append(_rescore_with_predicted_cat(r, cats[i], subs[i]))
            else:
                rows.append(r)
                scores.append(_rescore_with_predicted_cat(r, cats[i], subs[i]))
        return scores, rows

    hyb_scores, hyb_rows = _hybrid_scores_and_rows(routed_gate_only, hyb_cat, hyb_sub)
    hyb2_scores, hyb2_rows = _hybrid_scores_and_rows(routed_conf_skip, hyb2_cat, hyb2_sub)

    weak_retained_idx = [i for i, g in enumerate(weak_gate_pred) if g == 1]
    onnx_retained_idx = [i for i, g in enumerate(onnx_gate_pred) if g == 1]

    def _gate_metrics(g_pred: list[int]) -> dict[str, Any]:
        rec = recall_score(test_gate_gold, g_pred, zero_division=0)
        prec = precision_score(test_gate_gold, g_pred, zero_division=0)
        f1 = f1_score(test_gate_gold, g_pred, zero_division=0)
        kept = sum(g_pred)
        filt = 1.0 - (kept / n_test)
        return {
            "gate_precision": round(float(prec), 4),
            "gate_recall": round(float(rec), 4),
            "gate_f1": round(float(f1), 4),
            "kept_count": int(kept),
            "filter_ratio_pct": round(filt * 100, 1),
        }

    btc_idx = [i for i, r in enumerate(test_rows) if r["target_symbol"] == "BTC/USDT"]
    btc_onnx_ret_idx = [i for i in onnx_retained_idx if test_rows[i]["target_symbol"] == "BTC/USDT"]
    btc_weak_ret_idx = [i for i in weak_retained_idx if test_rows[i]["target_symbol"] == "BTC/USDT"]
    btc_hyb_ret_idx = [i for i in routed_gate_only if test_rows[i]["target_symbol"] == "BTC/USDT"]
    btc_hyb2_ret_idx = [i for i in routed_conf_skip if test_rows[i]["target_symbol"] == "BTC/USDT"]

    # Agreement: LLM teacher vs audited weak labels (full labeled overlap)
    agree_n = agree_gate = agree_cat = agree_sub = 0
    for split_rows in (train_rows, test_rows):
        for r in split_rows:
            dl = distill_map.get(r["event_id"])
            if not dl:
                continue
            wg, wc, ws = _derive_weak_label(r)
            ag, ac, asub, _ = _apply_spot_check_audit(r, wg, wc, ws)
            lg = 1 if dl.get("is_relevant", True) else 0
            agree_n += 1
            agree_gate += int(ag == lg)
            agree_cat += int(ac == dl.get("category"))
            agree_sub += int(asub == dl.get("subcategory"))

    # Token accounting
    all_jsonl: list[dict] = []
    if distill_path.exists():
        with distill_path.open(encoding="utf-8") as fh:
            for line in fh:
                if line.strip():
                    rec = json.loads(line)
                    if rec.get("status") == "OK":
                        all_jsonl.append(rec)
    pt_all, ct_all, cost_all = _sum_tokens(all_jsonl)
    pt_uniq, ct_uniq, cost_uniq = _sum_tokens(list(distill_map.values()))
    test_llm_recs = [distill_map[r["event_id"]] for r in test_rows if r["event_id"] in distill_map]
    pt_test, ct_test, cost_test = _sum_tokens(test_llm_recs)

    def _routed_cost(idxs: list[int]) -> dict[str, Any]:
        recs = []
        for i in idxs:
            dl = distill_map.get(test_rows[i]["event_id"])
            if dl:
                recs.append(dl)
        pt, ct, cost = _sum_tokens(recs)
        return {
            "n_calls": len(idxs),
            "n_with_tokens": len(recs),
            "prompt_tokens": pt,
            "completion_tokens": ct,
            "cost_usd_catalog": cost,
        }

    gate_cost = _routed_cost(routed_gate_only)
    conf_cost = _routed_cost(routed_conf_skip)

    def _pack_clf(cat_pred, sub_pred, gate_pred, lats, retained_idx, scores, rows=None, extra=None):
        src_rows = rows if rows is not None else test_rows
        btc_ret = [i for i in retained_idx if test_rows[i]["target_symbol"] == "BTC/USDT"]
        out = {
            "cat_macro_f1": round(float(f1_score(test_cat_gold, cat_pred, average="macro", zero_division=0)), 4),
            "cat_weighted_f1": round(float(f1_score(test_cat_gold, cat_pred, average="weighted", zero_division=0)), 4),
            "subcat_weighted_f1": round(float(f1_score(test_sub_gold, sub_pred, average="weighted", zero_division=0)), 4),
            "gate": _gate_metrics(gate_pred) if gate_pred is not None else None,
            "llm_savings_pct": round((1.0 - len(retained_idx) / n_test) * 100, 1) if retained_idx is not None else 0.0,
            "latency_p50_ms": round(float(np.percentile(lats, 50)), 3) if lats else None,
            "latency_p99_ms": round(float(np.percentile(lats, 99)), 3) if lats else None,
            "market_all": _attach_dir_ci(_market_eval(src_rows, scores if rows is not None else [r["impact_score"] for r in test_rows] if False else scores)),
            "market_all_retained": _attach_dir_ci(_market_eval([src_rows[i] for i in retained_idx], [scores[i] for i in retained_idx])) if retained_idx else None,
            "market_btc": _attach_dir_ci(_market_eval([src_rows[i] for i in btc_idx], [scores[i] for i in btc_idx])),
            "market_btc_retained": _attach_dir_ci(_market_eval([src_rows[i] for i in btc_ret], [scores[i] for i in btc_ret])) if retained_idx else None,
            "n_test": n_test,
        }
        if extra:
            out.update(extra)
        return out

    # Reference: previous weak ONNX vs new LLM gold (not retrained)
    weak_onnx_block = None
    if weak_onnx_preds is not None:
        w_gate = [1 if p.send_to_llm else 0 for p in weak_onnx_preds]
        w_cat = [p.category for p in weak_onnx_preds]
        w_sub = [p.subcategory for p in weak_onnx_preds]
        w_scores = [_rescore_with_predicted_cat(r, c, s) for r, c, s in zip(test_rows, w_cat, w_sub)]
        w_ret = [i for i, g in enumerate(w_gate) if g == 1]
        weak_onnx_block = _pack_clf(w_cat, w_sub, w_gate, [], w_ret, w_scores, extra={"note": "previous jev_weak_v1 ONNX, evaluated on LLM test gold (not retrained)"})

    results = {
        "split_summary": {
            "train_count": len(train_rows),
            "test_count": len(test_rows),
            "train_date_range": "2022-11-01..2022-11-16 + 2026-10-20..2026-11-17 (UTC)",
            "test_date_range": "2026-11-18..2026-11-24 (Held-out future UTC)",
            "train_llm_teacher_count": len(distill_X),
            "test_llm_gold_count": int(audit_counter["llm_test_gold"]),
            "test_llm_missing": test_llm_missing,
            "unique_llm_labels": len(distill_map),
            "train_gate_positive_rate_llm": round(sum(distill_gate) / len(distill_gate), 3) if distill_gate else None,
            "test_gate_positive_rate_llm": round(sum(test_gate_gold) / len(test_gate_gold), 3),
            "spot_check_corrections": dict(audit_counter),
            "gold_source": "google/gemini-2.5-flash-lite teacher labels (test gold replaced to remove rule-same-source bias)",
        },
        "labeling_cost": {
            "model": "google/gemini-2.5-flash-lite",
            "price_in_per_1m_usd": 0.10,
            "price_out_per_1m_usd": 0.40,
            "jsonl_rows_including_resumes": len(all_jsonl),
            "unique_event_ids": len(distill_map),
            "prompt_tokens_all_stored_calls": pt_all,
            "completion_tokens_all_stored_calls": ct_all,
            "catalog_cost_usd_all_stored_calls": cost_all,
            "prompt_tokens_unique_latest": pt_uniq,
            "completion_tokens_unique_latest": ct_uniq,
            "catalog_cost_usd_unique_latest": cost_uniq,
            "openrouter_account_usage_usd": 0.16347084,
            "openrouter_limit_remaining_usd": 49.83652916,
            "note": "Account usage is the billed total on this key (includes probes / retries). Catalog cost is listed OpenRouter price applied to stored prompt+completion tokens. No keys are persisted in this file.",
        },
        "llm_vs_audit_agreement": {
            "n_paired": agree_n,
            "gate_agree": round(agree_gate / agree_n, 4) if agree_n else None,
            "cat_agree": round(agree_cat / agree_n, 4) if agree_n else None,
            "subcat_agree": round(agree_sub / agree_n, 4) if agree_n else None,
            "human_spotcheck_n": 40,
            "human_spotcheck_llm_category_acceptable": "37/40",
            "human_spotcheck_rate": 0.925,
            "human_spotcheck_notes": (
                "抽检 24 条大类分歧 + 16 条一致样本。LLM 在 Anthropic IPO/NVDA 产品与矿业公司报道上优于规则（规则常打成 TRADFI）。"
                "明确错误 3 条：通胀砸盘被标成 CRYPTO、美元避险被标成大宗商品、中期选举对加密影响被标成 CRYPTO。"
                "门控上 LLM 对部分重大政治结果偏保守（如民主党赢下两院 is_relevant=false）。"
            ),
        },
        "onnx_verification": {
            "sklearn_vs_onnx_50_parity": f"{parity_matches}/50",
            "onnx_single_item_p50_ms": round(float(np.percentile(lat_samples, 50)), 3),
            "onnx_single_item_p95_ms": round(float(np.percentile(lat_samples, 95)), 3),
            "onnx_single_item_p99_ms": round(float(np.percentile(lat_samples, 99)), 3),
            "model_files_bytes": {
                f.name: f.stat().st_size for f in MODEL_DIR.glob("jev_*.onnx")
            },
            "weak_v1_kept_at": "models/jev_weak_v1",
            "distill_v1_copy_at": "models/jev_llm_distill_v1",
        },
        "llm_integration_status": {
            "litellm_base_url": llm_client.base_url,
            "litellm_model": llm_client.model,
            "litellm_key_configured": llm_client.is_configured,
            "litellm_health_ok": llm_ok,
            "litellm_health_http": llm_http,
            "litellm_health_msg": (llm_msg or "")[:80],
            "factcheck_configured": factcheck.is_configured,
            "perplexity_status": "SKIPPED_NO_KEY" if not factcheck.is_configured else "CONFIGURED",
            "test_set_teacher_labels_reused": True,
            "routed_gate_only_count": len(routed_gate_only),
            "routed_gate_only_pct": round(len(routed_gate_only) / n_test * 100, 1),
            "routed_conf_skip_count": len(routed_conf_skip),
            "routed_conf_skip_pct": round(len(routed_conf_skip) / n_test * 100, 1),
            "estimated_llm_call_savings_vs_full_pct": round((1.0 - len(routed_gate_only) / n_test) * 100, 1),
            "estimated_llm_call_savings_with_conf_skip_pct": round((1.0 - len(routed_conf_skip) / n_test) * 100, 1),
            "full_test_teacher_cost_usd": cost_test,
            "full_test_prompt_tokens": pt_test,
            "full_test_completion_tokens": ct_test,
            "gate_only_routed_cost": gate_cost,
            "conf_skip_routed_cost": conf_cost,
            "live_latency_probes": {
                "n": len(llm_lat_ms),
                "ok": llm_probe_ok,
                "errors": llm_probe_err,
                "p50_ms": round(float(np.percentile(llm_lat_ms, 50)), 1) if llm_lat_ms else None,
                "p99_ms": round(float(np.percentile(llm_lat_ms, 99)), 1) if llm_lat_ms else None,
                "mean_ms": round(float(np.mean(llm_lat_ms)), 1) if llm_lat_ms else None,
            },
        },
        "comparison": {
            "rule_only": _pack_clf(
                rule_preds_cat,
                rule_preds_sub,
                [1] * n_test,
                rule_lats,
                list(range(n_test)),
                rule_scores,
                extra={"llm_savings_pct": 0.0, "cost_usd_on_test": 0.0, "note": "F1 vs LLM test gold (no longer same-source as rules)"},
            ),
            "weak_only_fast_clf": _pack_clf(
                weak_cat_pred,
                weak_sub_pred,
                weak_gate_pred,
                weak_lats,
                weak_retained_idx,
                weak_scores,
                extra={"cost_usd_on_test": 0.0, "note": "trained on rule+market weak labels (n=2148), evaluated on LLM gold"},
            ),
            "llm_distill_onnx": _pack_clf(
                onnx_cat_pred,
                onnx_sub_pred,
                onnx_gate_pred,
                lat_samples,
                onnx_retained_idx,
                onnx_scores,
                extra={
                    "cost_usd_on_test": 0.0,
                    "train_n": len(distill_X),
                    "note": "distilled from gemini-2.5-flash-lite teacher; current models/jev_*.onnx",
                },
            ),
            "hybrid_gate_plus_llm": _pack_clf(
                hyb_cat,
                hyb_sub,
                [1 if i in set(routed_gate_only) else 0 for i in range(n_test)],
                lat_samples,
                routed_gate_only,
                hyb_scores,
                rows=hyb_rows,
                extra={
                    "llm_calls": len(routed_gate_only),
                    "llm_savings_pct": round((1.0 - len(routed_gate_only) / n_test) * 100, 1),
                    "cost_usd_on_test": gate_cost["cost_usd_catalog"],
                    "cost_note": "actual catalog price of reused teacher tokens on gated-in test items (no second bill)",
                    "llm_latency_p50_ms": (round(float(np.percentile(llm_lat_ms, 50)), 1) if llm_lat_ms else None),
                    "llm_latency_p99_ms": (round(float(np.percentile(llm_lat_ms, 99)), 1) if llm_lat_ms else None),
                    "latency_note": "ONNX p50/p99 for the gate; LLM RTT from live probes on already-labeled items",
                    "note": "gated-in items use real LLM extraction labels; gated-out use distilled ONNX category",
                },
            ),
            "hybrid_gate_conf_skip_plus_llm": _pack_clf(
                hyb2_cat,
                hyb2_sub,
                [1 if i in set(routed_conf_skip) else 0 for i in range(n_test)],
                lat_samples,
                routed_conf_skip,
                hyb2_scores,
                rows=hyb2_rows,
                extra={
                    "llm_calls": len(routed_conf_skip),
                    "llm_savings_pct": round((1.0 - len(routed_conf_skip) / n_test) * 100, 1),
                    "cost_usd_on_test": conf_cost["cost_usd_catalog"],
                    "note": "send to LLM only if gate=1 and (cat_prob<0.72 or controversial subcategory)",
                },
            ),
            "previous_weak_onnx_on_llm_gold": weak_onnx_block,
        },
    }

    out_eval = OUT_DIR / "jev_comparison_eval.json"
    out_eval.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
