import os
import unittest
from datetime import date, datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pandas as pd

from fin_news_events.hotlist import (
    AttributionConfig,
    aggregate_candidate_causes,
    detect_sessions,
    detect_windows,
    news_heat,
    relevance_score,
    score_candidates,
    verification_label,
)
from fin_news_events.llm_clients import PerplexityFactChecker
from fin_news_events.models import MYT
from fin_news_events.scorer import compute_authority_verification
from fin_news_events.sources.market_rss import build_targeted_attribution_queries


class TestHotlist(unittest.TestCase):
    def test_verification_and_heat(self):
        self.assertIn("未核实", verification_label("UNVERIFIED_OR_RUMOR"))
        self.assertIn("多源", verification_label("MULTI_SOURCE_CONFIRMED"))
        h1 = news_heat(1, 1, AttributionConfig())
        h3 = news_heat(3, 5, AttributionConfig())
        self.assertGreater(h1, 0)
        self.assertGreater(h3, h1)

    def test_detect_windows_finds_jump(self):
        start = datetime(2026, 11, 24, 0, 0, tzinfo=MYT)
        idx = [start + timedelta(minutes=15 * i) for i in range(200)]
        close = [100.0] * 80 + [100.0, 106.0] + [106.2] * 118
        vol = [10.0] * 80 + [80.0, 40.0] + [12.0] * 118
        idx_utc = [t.astimezone(timezone.utc) for t in idx]
        df = pd.DataFrame({"close": close, "volume": vol}, index=pd.DatetimeIndex(idx_utc))
        day_start, day_end = start, start + timedelta(days=1)
        wins = detect_windows(df, "15m", day_start, day_end, AttributionConfig())
        self.assertTrue(wins, "expected a jump window")
        self.assertEqual(wins[0]["direction"], "UP")
        self.assertGreater(wins[0]["cum_ret_pct"], 4)

    def test_ex_post_news_is_flagged_and_downweighted(self):
        jump = datetime(2026, 11, 24, 10, 0, tzinfo=MYT)
        before = {
            "event_id": "a",
            "headline": "Fed hikes rates",
            "category": "MACRO",
            "subcategory": "fed_rates",
            "direction": "BEARISH",
            "impact_score": 80,
            "target_symbol": "BTC/USDT",
            "retrieval_layer": "CROSS_MARKET",
            "published_at_utc": (jump - timedelta(hours=1)).astimezone(timezone.utc).isoformat(),
            "published_at_myt": "2026-11-24 09:00 UTC+8",
            "source_count": 3,
            "unique_domains": ["reuters.com", "cnbc.com", "wsj.com"],
            "sources": [{"name": "Reuters", "domain": "reuters.com", "url": "https://reuters.com/1"}],
            "verification_status": "MULTI_SOURCE_CONFIRMED",
            "_pub_dt": jump - timedelta(hours=1),
        }
        after = dict(before)
        after["event_id"] = "b"
        after["headline"] = "Bitcoin falls after Fed hike, analysts say"
        after["_pub_dt"] = jump + timedelta(hours=0.5)
        after["published_at_utc"] = after["_pub_dt"].astimezone(timezone.utc).isoformat()
        after["source_count"] = 1
        after["unique_domains"] = ["blog.example"]
        after["sources"] = [{"name": "Blog", "domain": "blog.example", "url": "https://blog.example/1"}]
        after["verification_status"] = "UNVERIFIED_OR_RUMOR"
        scored = score_candidates([before, after], jump, "DOWN", "BTC/USDT", AttributionConfig())
        self.assertEqual(scored[0]["event_id"], "a")
        post = next(s for s in scored if s["event_id"] == "b")
        self.assertTrue(post["ex_post"])
        self.assertEqual(post["timing"], "事后解释/报道")
        self.assertLess(post["attr_score"], scored[0]["attr_score"])

    def test_detect_sessions_dst_aware_et(self):
        # Day 1: Oct 30 2026 (EDT UTC-4 -> 09:30 ET = 13:30 UTC = 21:30 UTC+8)
        # Day 2: Nov 24 2026 (EST UTC-5 -> 09:30 ET = 14:30 UTC = 22:30 UTC+8)
        bars = [
            ("2026-10-30T13:30:00Z", 100.0, 101.0),
            ("2026-10-30T19:30:00Z", 101.0, 102.0),
            ("2026-11-24T14:30:00Z", 100.0, 96.0),
            ("2026-11-24T20:30:00Z", 96.0, 95.0),
        ]
        idx = pd.DatetimeIndex([datetime.fromisoformat(t.replace("Z", "+00:00")) for t, _, _ in bars])
        df = pd.DataFrame({"open": [o for _, o, _ in bars], "close": [c for _, _, c in bars]}, index=idx)
        recs = detect_sessions(df)
        self.assertEqual(len(recs), 2)
        self.assertEqual(recs[0]["session_date_et"], "2026-10-30")
        self.assertIn("21:30 UTC+8", recs[0]["open_myt"])
        self.assertEqual(recs[1]["session_date_et"], "2026-11-24")
        self.assertIn("22:30 UTC+8", recs[1]["open_myt"])
        self.assertAlmostEqual(recs[1]["ret_incl_gap"], 95.0 / 102.0 - 1.0, places=5)

    def test_targeted_queries_and_crypto_noise_filter(self):
        qs = build_targeted_attribution_queries(["NVDA", "SMH", "QQQ"], "us", date(2026, 11, 24))
        q_str = " ".join(q for _, _, q in qs)
        self.assertIn("site:reuters.com", q_str)
        self.assertIn("Nvidia shares", q_str)
        self.assertIn("chip stocks", q_str)
        self.assertIn("stock market today", q_str)

        crypto_etf = {
            "headline": "Bitcoin ETFs see $570 million net outflows as BTC dips below $60K",
            "summary": "Spot bitcoin ETF flows",
            "category": "TRADFI",
            "retrieval_layer": "CROSS_MARKET",
            "target_symbol": "NVDA",
        }
        self.assertLessEqual(relevance_score(crypto_etf, "NVDA"), 0.2)

    def test_authority_verification_and_cause_aggregation(self):
        off = compute_authority_verification(
            [{"name": "NVIDIA Newsroom", "domain": "nvidianews.nvidia.com", "is_primary_official": True}],
            "OFFICIAL_PRIMARY",
        )
        self.assertEqual(off["verification_tier"], "confirmed")
        self.assertTrue(off["has_official"])

        multi = compute_authority_verification(
            [
                {"name": "Reuters", "domain": "reuters.com"},
                {"name": "CNBC", "domain": "cnbc.com"},
            ]
        )
        self.assertEqual(multi["verification_tier"], "confirmed")
        self.assertEqual(multi["independent_sources_count"], 2)

        single = compute_authority_verification([{"name": "Reuters", "domain": "reuters.com"}])
        self.assertEqual(single["verification_tier"], "single_source")

        rumor = compute_authority_verification([{"name": "RandomBlog", "domain": "randomblog.xyz"}])
        self.assertEqual(rumor["verification_tier"], "unverified")

        cands = [
            {
                "headline": "Nvidia rally unwinds ahead of open",
                "attr_score": 0.78,
                "authority_score": 0.88,
                "ex_post": False,
                "hours_vs_jump": -1.2,
                "published_at_myt": "2026-11-24 21:18 UTC+8",
                "relevance": 0.9,
                "sources": [{"name": "Barron's", "domain": "barrons.com", "url": "https://barrons.com/1"}],
            },
            {
                "headline": "Nasdaq, S&P 500 close lower, giving up Nvidia-fueled gains",
                "attr_score": 0.72,
                "authority_score": 0.95,
                "ex_post": True,
                "hours_vs_jump": 7.4,
                "published_at_myt": "2026-11-25 05:56 UTC+8",
                "relevance": 0.9,
                "sources": [{"name": "Reuters", "domain": "reuters.com", "url": "https://reuters.com/2"}],
            },
        ]
        causes = aggregate_candidate_causes(cands, asset_class="equity")
        self.assertEqual(len(causes), 1)
        self.assertEqual(causes[0]["verification_tier"], "confirmed")
        self.assertEqual(causes[0]["independent_sources_count"], 2)
        self.assertIn("事前", causes[0]["timing"])

    def test_factchecker_skip_and_openrouter_fallback(self):
        with patch.dict(os.environ, {}, clear=True), patch("fin_news_events.llm_clients.load_openrouter_env", return_value=False):
            fc = PerplexityFactChecker(prefer_openrouter_online=False)
            res = fc.verify_claim("Test claim", "NVDA")
            self.assertEqual(res.status, "SKIPPED_NO_KEY")

        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_resp.json.return_value = {
            "choices": [{
                "message": {
                    "content": '```json\n{"status":"VERIFIED","independent_sources_count":3,"authority_tier":"official","key_sources":["NVIDIA Newsroom","SEC","Reuters"],"summary":"已确认。"}\n```',
                    "annotations": [
                        {"type": "url_citation", "url_citation": {"url": "https://nvidianews.nvidia.com/1"}},
                        {"type": "url_citation", "url_citation": {"url": "https://www.reuters.com/1"}},
                    ],
                }
            }],
            "usage": {"prompt_tokens": 50, "completion_tokens": 40, "cost": 0.0051},
        }
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "sk-or-test", "OPENROUTER_BASE_URL": "https://openrouter.ai/api/v1"}, clear=True), \
             patch("fin_news_events.llm_clients.load_openrouter_env", return_value=False), \
             patch("fin_news_events.llm_clients.requests.post", return_value=mock_resp):
            fc2 = PerplexityFactChecker(prefer_openrouter_online=True)
            self.assertEqual(fc2.provider, "openrouter")
            r2 = fc2.verify_claim("Huang reinstated", "NVDA", "2026-11-23")
            self.assertEqual(r2.status, "VERIFIED")
            self.assertEqual(r2.verification_tier, "confirmed")
            self.assertEqual(len(r2.citations), 2)
            self.assertAlmostEqual(r2.cost_usd, 0.0051, places=4)


if __name__ == "__main__":
    unittest.main()
