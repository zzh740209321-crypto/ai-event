import os
import unittest
from datetime import date, datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pandas as pd

from fin_news_events.hotlist import (
    AttributionConfig,
    aggregate_candidate_causes,
    annotate_contrarian,
    detect_sessions,
    detect_windows,
    has_symbol_specific_aligned_news,
    infer_news_direction,
    is_crypto_credit_noise,
    is_nonmarket_political,
    news_heat,
    relevance_score,
    score_candidates,
    select_by_score_threshold,
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


    def test_select_by_score_threshold_keeps_near_top(self):
        items = [
            {"headline": "unwind", "attr_score": 0.9246},
            {"headline": "governance", "attr_score": 0.854},
            {"headline": "ai capex", "attr_score": 0.785},
            {"headline": "tariffs", "attr_score": 0.7529},
            {"headline": "weak other", "attr_score": 0.55},
        ]
        kept = select_by_score_threshold(items, min_score=0.70, rel_of_top=0.75, max_n=8)
        heads = [x["headline"] for x in kept]
        self.assertIn("tariffs", heads)
        self.assertNotIn("weak other", heads)
        self.assertEqual(len(kept), 4)
        # cap
        many = [{"headline": str(i), "attr_score": 0.90 - i * 0.01} for i in range(12)]
        self.assertEqual(len(select_by_score_threshold(many, max_n=8)), 8)

    def test_direction_and_contrarian_filtering(self):
        self.assertEqual(
            infer_news_direction({"headline": "Nasdaq futures drop as AI stocks cool after Nvidia-fueled rally", "direction": "NEUTRAL"}),
            "BEARISH",
        )
        self.assertEqual(
            infer_news_direction({"headline": "NVIDIA Board Reinstates Jensen Huang as President, CEO and Board Director", "direction": "BULLISH"}),
            "BULLISH",
        )
        jump = datetime(2026, 11, 24, 22, 30, tzinfo=MYT)
        bear = {
            "event_id": "bear",
            "headline": "Nasdaq futures drop as AI stocks cool after Nvidia-fueled rally",
            "summary": "chip stocks lower",
            "category": "TECH_AI",
            "subcategory": "valuation_capex",
            "direction": "NEUTRAL",
            "impact_score": 85,
            "target_symbol": "NVDA",
            "retrieval_layer": "CROSS_MARKET",
            "published_at_utc": (jump - timedelta(hours=1)).astimezone(timezone.utc).isoformat(),
            "published_at_myt": "2026-11-24 21:30 UTC+8",
            "source_count": 6,
            "unique_domains": ["reuters.com", "cnbc.com"],
            "sources": [{"name": "Reuters", "domain": "reuters.com", "url": "https://reuters.com/1"}],
            "verification_status": "MULTI_SOURCE_CONFIRMED",
            "_pub_dt": jump - timedelta(hours=1),
        }
        apple_up = dict(bear)
        apple_up["event_id"] = "aapl-specific"
        apple_up["headline"] = "Apple shares jump after iPhone upgrade cycle data"
        apple_up["direction"] = "BULLISH"
        down_on_down = score_candidates([bear], jump, "DOWN", "NVDA", AttributionConfig())
        up_on_aapl = score_candidates([bear, apple_up], jump, "UP", "AAPL", AttributionConfig())
        self.assertFalse(down_on_down[0]["direction_mismatch"])
        mismatched = next(s for s in up_on_aapl if s["event_id"] == "bear")
        aligned = next(s for s in up_on_aapl if s["event_id"] == "aapl-specific")
        self.assertTrue(mismatched["direction_mismatch"])
        self.assertLess(mismatched["attr_score"], aligned["attr_score"])
        causes_up = aggregate_candidate_causes(up_on_aapl, asset_class="equity")
        self.assertTrue(any("Apple" in (c.get("headline") or "") for c in causes_up) or not any(c.get("direction_mismatch") for c in causes_up))
        # AAPL-like item with only sector-down news should be tagged CONTRARIAN and lack name-specific news
        aapl_item = {
            "id": "2026-11-24_AAPL",
            "date": "2026-11-24",
            "symbol": "AAPL",
            "asset_class": "equity",
            "daily_ret_pct": 1.25,
            "move_dir": "UP",
            "candidates": [mismatched],
            "top_causes": aggregate_candidate_causes([mismatched], asset_class="equity"),
        }
        nvda_item = {
            "id": "2026-11-24_NVDA",
            "date": "2026-11-24",
            "symbol": "NVDA",
            "asset_class": "equity",
            "daily_ret_pct": -5.94,
            "move_dir": "DOWN",
            "magnitude": 5.9,
        }
        groups = [{
            "kind": "equity_common",
            "date": "2026-11-24",
            "move_dir": "DOWN",
            "symbols": ["NVDA", "SMH"],
            "members": [{"id": nvda_item["id"], "symbol": "NVDA"}],
        }]
        annotate_contrarian([aapl_item, nvda_item], groups)
        self.assertTrue(aapl_item.get("contrarian"))
        self.assertFalse(has_symbol_specific_aligned_news(aapl_item))

    def test_nonmarket_political_and_crypto_credit_downweighted(self):
        political = {
            "headline": "Rep. Jamie Raskin on Howard Lutnick probe: A profound conflict of interest",
            "summary": "",
            "category": "POLITICS_REG",
            "subcategory": "enforcement_lawsuit",
        }
        tariffs = {
            "headline": "US prepares new tariffs on China, EU and other trading partners – WSJ",
            "summary": "stock market today",
            "category": "POLITICS_REG",
            "subcategory": "geopolitics_tariffs",
        }
        crypto_credit = {
            "headline": "Neuberger Berman’s HINC fund brings high-yield credit to Aave’s institutional vaults",
            "summary": "",
            "category": "CRYPTO",
            "subcategory": "major_financing",
        }
        self.assertTrue(is_nonmarket_political(political, "NVDA"))
        self.assertFalse(is_nonmarket_political(tariffs, "NVDA"))
        self.assertTrue(is_crypto_credit_noise(crypto_credit, "AAPL"))
        self.assertLessEqual(relevance_score(political, "NVDA"), 0.15)
        self.assertGreaterEqual(relevance_score(tariffs, "NVDA"), 0.65)
        self.assertLessEqual(relevance_score(crypto_credit, "AAPL"), 0.15)

    def test_aggregate_threshold_includes_tariffs(self):
        cands = [
            {"headline": "Nasdaq futures drop as AI stocks cool after Nvidia-fueled rally", "attr_score": 0.9246, "authority_score": 1.0, "ex_post": False, "hours_vs_jump": -1.0, "published_at_myt": "t1", "relevance": 0.9, "sources": [{"name": "Kitco", "domain": "kitco.com", "url": "https://k/1"}]},
            {"headline": "Jensen Huang Could Still Be Kicked Out, Nvidia Could Still Fall 40%", "attr_score": 0.854, "authority_score": 1.0, "ex_post": False, "hours_vs_jump": -0.4, "published_at_myt": "t2", "relevance": 0.9, "sources": [{"name": "Yahoo", "domain": "finance.yahoo.com", "url": "https://y/1"}]},
            {"headline": "Drops for Nvidia, Anthropic and other AI stocks drag the US market back down", "attr_score": 0.785, "authority_score": 0.76, "ex_post": False, "hours_vs_jump": -2.0, "published_at_myt": "t3", "relevance": 0.8, "sources": [{"name": "Yahoo", "domain": "finance.yahoo.com", "url": "https://y/2"}]},
            {"headline": "US prepares new tariffs on China, EU and other trading partners – WSJ", "attr_score": 0.7529, "authority_score": 0.9, "ex_post": False, "hours_vs_jump": -0.87, "published_at_myt": "t4", "relevance": 0.8, "sources": [{"name": "WSJ", "domain": "wsj.com", "url": "https://wsj.com/1"}]},
            {"headline": "Rep. Jamie Raskin on Howard Lutnick probe: A profound conflict of interest", "attr_score": 0.20, "authority_score": 0.88, "ex_post": False, "hours_vs_jump": -1.0, "published_at_myt": "t5", "relevance": 0.12, "direction_mismatch": False, "sources": [{"name": "CNBC", "domain": "cnbc.com", "url": "https://cnbc.com/1"}]},
        ]
        causes = aggregate_candidate_causes(cands, asset_class="equity")
        labels = " ".join(c["theme_label_zh"] + " " + (c.get("headline") or "") for c in causes)
        self.assertGreaterEqual(len(causes), 4)
        self.assertTrue(any("关税" in (c["theme_label_zh"] or "") for c in causes))
        self.assertFalse(any("Raskin" in (c.get("headline") or "") for c in causes))
        self.assertIn("关税", labels)


if __name__ == "__main__":
    unittest.main()
