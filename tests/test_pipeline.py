import unittest
from datetime import datetime, timedelta, timezone

import pandas as pd

from fin_news_events.classifier import RuleLexiconClassifier
from fin_news_events.dedup_cluster import IncrementalClusterer
from fin_news_events.entity_mapper import extract_matched_entities, resolve_target
from fin_news_events.market_data import attach_market_reaction, compute_hourly_vol
from fin_news_events.models import RawNewsItem
from fin_news_events.scorer import score_event


def _make_item(item_id: str, title: str, source: str, domain: str, ts: datetime, official: bool = False) -> RawNewsItem:
    return RawNewsItem(
        item_id=item_id,
        title=title,
        summary="",
        url=f"https://{domain}/{item_id}",
        source_name=source,
        source_feed="test",
        source_domain=domain,
        published_at=ts,
        ingested_at=ts + timedelta(seconds=5),
        fetch_latency_ms=120.0,
        retrieval_layer="DIRECT",
        query_tag="test",
        is_primary_official=official,
    )


class PipelineUnitTests(unittest.TestCase):
    def test_entity_mapper_two_layers(self):
        btc = resolve_target("BTC/USDT")
        self.assertEqual(btc.canonical_symbol, "BTC/USDT")
        self.assertEqual(btc.market_symbol, "BTCUSDT")
        ents_direct, layer_d = extract_matched_entities("Bitcoin surges above $80k after spot ETF inflows", btc)
        self.assertEqual(layer_d, "DIRECT")
        self.assertIn("Bitcoin", ents_direct)

        ents_macro, layer_m = extract_matched_entities("Federal Reserve signals slower rate cuts as CPI rises", btc)
        self.assertEqual(layer_m, "CROSS_MARKET")
        self.assertIn("Fed/FOMC", ents_macro)

    def test_incremental_clusterer_merges_same_story(self):
        t0 = datetime(2026, 11, 23, 12, 0, tzinfo=timezone.utc)
        c = IncrementalClusterer(sim_threshold=0.34, window_hours=48)
        a = _make_item("1", "NVIDIA Board Reinstates Jensen Huang as CEO", "NVIDIA Newsroom", "nvidianews.nvidia.com", t0, official=True)
        b = _make_item("2", "Nvidia board reinstates Jensen Huang as chief executive", "Reuters", "reuters.com", t0 + timedelta(minutes=10))
        d = _make_item("3", "Federal Reserve holds interest rates steady amid sticky inflation", "CNBC", "cnbc.com", t0 + timedelta(minutes=20))

        c1, new1, dup1 = c.process_item(a)
        c2, new2, dup2 = c.process_item(b)
        c3, new3, dup3 = c.process_item(d)

        self.assertTrue(new1)
        self.assertFalse(new2)
        self.assertFalse(dup2)
        self.assertEqual(c1.cluster_id, c2.cluster_id)
        self.assertTrue(new3)
        self.assertNotEqual(c1.cluster_id, c3.cluster_id)

    def test_verification_and_cross_market_scoring(self):
        t0 = datetime(2026, 11, 20, 10, 0, tzinfo=timezone.utc)
        btc = resolve_target("BTC/USDT")
        clf = RuleLexiconClassifier()
        c = IncrementalClusterer()
        r1 = _make_item("x1", "Hawkish Federal Reserve signals fewer rate cuts, dollar rises", "Reuters", "reuters.com", t0)
        r2 = _make_item("x2", "Hawkish Fed signals fewer rate cuts as dollar and yields rise", "CNBC", "cnbc.com", t0 + timedelta(minutes=5))
        cl, _, _ = c.process_item(r1)
        c.process_item(r2)

        res = clf.classify(cl.rep_title)
        self.assertEqual(res.category, "MACRO")
        self.assertEqual(res.subcategory, "fed_rates")
        self.assertEqual(res.direction, "BEARISH")

        sc = score_event(cl, res, btc, "CROSS_MARKET")
        self.assertEqual(sc.verification_status, "MULTI_SOURCE_CONFIRMED")
        self.assertGreater(sc.impact_score, 75.0)
        self.assertIn("Fed/Rates", sc.transmission_path)

    def test_market_reaction_no_lookahead(self):
        base = datetime(2026, 11, 20, 10, 0, tzinfo=timezone.utc)
        idx = [base + timedelta(hours=i) for i in range(30)]
        prices = [100.0 + i * 0.5 for i in range(30)]
        bench = [50.0 + i * 0.1 for i in range(30)]
        df = pd.DataFrame({"open": prices, "high": prices, "low": prices, "close": prices, "volume": [1000]*30}, index=pd.DatetimeIndex(idx))
        bdf = pd.DataFrame({"open": bench, "high": bench, "low": bench, "close": bench, "volume": [1000]*30}, index=pd.DatetimeIndex(idx))

        vol = compute_hourly_vol(df)
        mr = attach_market_reaction(base + timedelta(minutes=15), df, bdf, "ETHUSDT", vol)
        self.assertIsNotNone(mr)
        self.assertEqual(mr.anchor_price, 100.5)  # 11:00 bar, strictly >= 10:15
        self.assertIsNotNone(mr.ret_1h)
        self.assertIsNotNone(mr.abnormal_ret_24h)


if __name__ == "__main__":
    unittest.main()


class FastClassifierTests(unittest.TestCase):
    def test_onnx_fast_classifier_loads_and_predicts(self):
        from fin_news_events.fast_classifier import JevFastClassifier
        if not JevFastClassifier.is_available():
            self.skipTest("ONNX models not exported yet")
        clf = JevFastClassifier()
        p1 = clf.predict_one("NVDA", "DIRECT", "NVIDIA Board Reinstates Jensen Huang as CEO", "")
        self.assertTrue(p1.send_to_llm)
        self.assertEqual(p1.category, "TECH_AI")
        self.assertLess(p1.infer_ms, 50.0)

        p_noise = clf.predict_one("BTC/USDT", "DIRECT", "Get up to $100 in BTC with our Black Friday Deposit & Trade Bonus", "")
        self.assertLess(p_noise.gate_prob, 0.50)
