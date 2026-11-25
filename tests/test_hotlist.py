import unittest
from datetime import datetime, timedelta, timezone

import pandas as pd

from fin_news_events.hotlist import (
    AttributionConfig,
    detect_windows,
    news_heat,
    score_candidates,
    verification_label,
)
from fin_news_events.models import MYT


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
            "sources": [],
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
        after["verification_status"] = "UNVERIFIED_OR_RUMOR"
        scored = score_candidates([before, after], jump, "DOWN", "BTC/USDT", AttributionConfig())
        self.assertEqual(scored[0]["event_id"], "a")
        post = next(s for s in scored if s["event_id"] == "b")
        self.assertTrue(post["ex_post"])
        self.assertEqual(post["timing"], "事后解释/报道")
        self.assertLess(post["attr_score"], scored[0]["attr_score"])


if __name__ == "__main__":
    unittest.main()
