from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np

MODEL_DIR = Path(__file__).resolve().parent.parent / "models"


@dataclass
class FastPrediction:
    gate_prob: float
    send_to_llm: bool
    category: str
    category_prob: float
    subcategory: str
    subcategory_prob: float
    infer_ms: float
    backend: str  # "onnxruntime" | "sklearn"


def format_fast_input(target_symbol: str, retrieval_layer: str, headline: str, summary: str = "") -> str:
    clean_sum = (summary or "").replace("\n", " ").strip()[:160]
    return f"sym_{target_symbol} layer_{retrieval_layer} {headline} {clean_sum}".lower().strip()


class JevFastClassifier:
    """Milliseconds-level two-head ONNX fast classifier (jev/decision) placed before LLM."""

    def __init__(self, model_dir: Path | str = MODEL_DIR, gate_threshold: float = 0.50):
        self.model_dir = Path(model_dir)
        self.gate_threshold = gate_threshold
        self._meta_path = self.model_dir / "jev_meta.json"
        if not self._meta_path.exists():
            raise FileNotFoundError(f"Missing {self._meta_path}; run train_eval_jev.py first.")
        self.meta = json.loads(self._meta_path.read_text(encoding="utf-8"))
        self.gate_threshold = float(self.meta.get("gate_threshold", gate_threshold))

        import onnxruntime as ort
        opts = ort.SessionOptions()
        opts.intra_op_num_threads = 1
        opts.inter_op_num_threads = 1
        providers = ["CPUExecutionProvider"]

        self.sess_gate = ort.InferenceSession(str(self.model_dir / "jev_gate.onnx"), sess_options=opts, providers=providers)
        self.sess_cat = ort.InferenceSession(str(self.model_dir / "jev_category.onnx"), sess_options=opts, providers=providers)
        self.sess_sub = ort.InferenceSession(str(self.model_dir / "jev_subcategory.onnx"), sess_options=opts, providers=providers)

        self._gate_in = self.sess_gate.get_inputs()[0].name
        self._cat_in = self.sess_cat.get_inputs()[0].name
        self._sub_in = self.sess_sub.get_inputs()[0].name

    @classmethod
    def is_available(cls, model_dir: Path | str = MODEL_DIR) -> bool:
        d = Path(model_dir)
        return (d / "jev_meta.json").exists() and (d / "jev_gate.onnx").exists()

    @staticmethod
    def _extract_pos_prob(prob_out: object) -> float:
        # skl2onnx zipmap=False returns ndarray [N, C]; zipmap=True returns list[dict]
        if isinstance(prob_out, list):
            d = prob_out[0]
            return float(d.get(1, d.get("1", 0.0)))
        arr = np.asarray(prob_out)
        if arr.ndim == 2 and arr.shape[1] >= 2:
            return float(arr[0, 1])
        return float(arr.ravel()[0])

    @staticmethod
    def _extract_top_class(label_out: object, prob_out: object) -> tuple[str, float]:
        lbl = str(np.asarray(label_out).ravel()[0])
        if isinstance(prob_out, list):
            d = prob_out[0]
            best_p = max(float(v) for v in d.values()) if d else 0.0
            return lbl, best_p
        arr = np.asarray(prob_out)
        best_p = float(np.max(arr[0])) if arr.ndim == 2 else float(np.max(arr))
        return lbl, best_p

    def predict_one(self, target_symbol: str, retrieval_layer: str, headline: str, summary: str = "") -> FastPrediction:
        text = format_fast_input(target_symbol, retrieval_layer, headline, summary)
        inp = np.array([[text]], dtype=object)

        t0 = time.perf_counter()
        g_lbl, g_prob_raw = self.sess_gate.run(None, {self._gate_in: inp})
        c_lbl, c_prob_raw = self.sess_cat.run(None, {self._cat_in: inp})
        s_lbl, s_prob_raw = self.sess_sub.run(None, {self._sub_in: inp})
        infer_ms = (time.perf_counter() - t0) * 1000.0

        gate_prob = self._extract_pos_prob(g_prob_raw)
        cat_lbl, cat_prob = self._extract_top_class(c_lbl, c_prob_raw)
        sub_lbl, sub_prob = self._extract_top_class(s_lbl, s_prob_raw)

        return FastPrediction(
            gate_prob=round(gate_prob, 4),
            send_to_llm=gate_prob >= self.gate_threshold,
            category=cat_lbl,
            category_prob=round(cat_prob, 4),
            subcategory=sub_lbl,
            subcategory_prob=round(sub_prob, 4),
            infer_ms=round(infer_ms, 3),
            backend="onnxruntime",
        )
