import os
import unittest
from unittest.mock import MagicMock, patch

import requests

from fin_news_events.llm_clients import (
    LiteLLMClient,
    LiteLLMFactChecker,
    resolve_litellm_model,
)


def _env(data: dict):
    return patch.dict(os.environ, data, clear=True)


def _no_dotenv():
    return patch("fin_news_events.llm_clients.load_litellm_env", return_value=False)


class TestLiteLLMClient(unittest.TestCase):
    def test_skip_when_no_key(self):
        with _env({}), _no_dotenv():
            client = LiteLLMClient(purpose="attribution")
            self.assertFalse(client.is_configured)
            ext = client.extract_event("h", "s", "NVDA", "DIRECT")
            self.assertEqual(ext.status, "SKIPPED_NO_KEY")
            attr = client.attribute_price_move("payload")
            self.assertEqual(attr.status, "SKIPPED_NO_KEY")
            fc = LiteLLMFactChecker()
            res = fc.verify_claim("Test claim", "NVDA")
            self.assertEqual(res.status, "SKIPPED_NO_KEY")

    def test_company_defaults_and_demo_alias_map(self):
        with _env({
            "LITELLM_BASE_URL": "http://litellm.internal/v1",
            "LITELLM_API_KEY": "sk-corp",
        }), _no_dotenv():
            self.assertEqual(resolve_litellm_model("attribution"), "gemini-flash-lite")
            self.assertEqual(resolve_litellm_model("factcheck"), "perplexity-sonar")
            self.assertEqual(resolve_litellm_model("label"), "gemini-flash-lite")
            c = LiteLLMClient(purpose="attribution")
            self.assertEqual(c.provider, "litellm")
            self.assertEqual(c.base_url, "http://litellm.internal/v1")
            self.assertEqual(c.model, "gemini-flash-lite")

        with _env({
            "LITELLM_BASE_URL": "https://openrouter.ai/api/v1",
            "LITELLM_API_KEY": "sk-or-demo",
        }), _no_dotenv():
            self.assertEqual(resolve_litellm_model("attribution"), "google/gemini-2.5-flash-lite")
            self.assertEqual(resolve_litellm_model("factcheck"), "perplexity/sonar")

    def test_purpose_specific_model_env(self):
        with _env({
            "LITELLM_BASE_URL": "http://litellm.internal/v1",
            "LITELLM_API_KEY": "sk-corp",
            "LITELLM_MODEL_ATTRIBUTION": "corp-attr",
            "LITELLM_MODEL_LABEL": "corp-label",
            "LITELLM_MODEL_FACTCHECK": "corp-sonar",
        }), _no_dotenv():
            self.assertEqual(LiteLLMClient(purpose="attribution").model, "corp-attr")
            self.assertEqual(LiteLLMClient(purpose="label").model, "corp-label")
            self.assertEqual(LiteLLMClient(purpose="factcheck").model, "corp-sonar")

    def test_openrouter_api_key_is_demo_fallback_only(self):
        with _env({
            "LITELLM_BASE_URL": "http://127.0.0.1:4000/v1",
            "OPENROUTER_API_KEY": "sk-or-demo",
        }), _no_dotenv():
            c = LiteLLMClient(purpose="attribution")
            self.assertEqual(c.api_key, "sk-or-demo")
            self.assertTrue(c.is_configured)

    def test_factcheck_success_via_litellm(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{
                "message": {
                    "content": '{"status":"VERIFIED","independent_sources_count":3,"authority_tier":"official","key_sources":["NVIDIA Newsroom","SEC","Reuters"],"summary":"已确认。"}',
                    "annotations": [
                        {"type": "url_citation", "url_citation": {"url": "https://nvidianews.nvidia.com/1"}},
                        {"type": "url_citation", "url_citation": {"url": "https://www.reuters.com/1"}},
                    ],
                }
            }],
            "usage": {"prompt_tokens": 50, "completion_tokens": 40, "cost": 0.0051},
        }
        with _env({
            "LITELLM_BASE_URL": "http://litellm.internal/v1",
            "LITELLM_API_KEY": "sk-corp",
        }), _no_dotenv(), patch("fin_news_events.llm_clients.requests.post", return_value=mock_resp):
            fc = LiteLLMFactChecker()
            self.assertEqual(fc.provider, "litellm")
            r = fc.verify_claim("Huang reinstated", "NVDA", "2026-11-23")
            self.assertEqual(r.status, "VERIFIED")
            self.assertEqual(r.provider, "litellm")
            self.assertEqual(r.verification_tier, "confirmed")
            self.assertEqual(len(r.citations), 2)
            self.assertAlmostEqual(r.cost_usd, 0.0051, places=4)

    def test_http_401_402_timeout_degrade(self):
        def _resp(code: int) -> MagicMock:
            m = MagicMock()
            m.status_code = code
            m.text = f"err {code}"
            return m

        with _env({
            "LITELLM_BASE_URL": "http://litellm.internal/v1",
            "LITELLM_API_KEY": "sk-corp",
        }), _no_dotenv():
            with patch("fin_news_events.llm_clients.requests.post", return_value=_resp(401)):
                attr = LiteLLMClient(purpose="attribution").attribute_price_move("x")
                self.assertEqual(attr.status, "AUTH_ERROR_401")
                fc = LiteLLMFactChecker().verify_claim("c", "NVDA")
                self.assertEqual(fc.status, "AUTH_ERROR_401")
            with patch("fin_news_events.llm_clients.requests.post", return_value=_resp(402)):
                attr = LiteLLMClient(purpose="attribution").attribute_price_move("x")
                self.assertEqual(attr.status, "PAYMENT_REQUIRED")
                fc = LiteLLMFactChecker().verify_claim("c", "NVDA")
                self.assertEqual(fc.status, "PAYMENT_REQUIRED")
            with patch("fin_news_events.llm_clients.requests.post", side_effect=requests.Timeout("t")):
                attr = LiteLLMClient(purpose="attribution").attribute_price_move("x")
                self.assertEqual(attr.status, "TIMEOUT")
                fc = LiteLLMFactChecker().verify_claim("c", "NVDA")
                self.assertEqual(fc.status, "TIMEOUT")

    def test_health_models_endpoint(self):
        ok = MagicMock()
        ok.status_code = 200
        with _env({
            "LITELLM_BASE_URL": "http://litellm.internal/v1",
            "LITELLM_API_KEY": "sk-corp",
        }), _no_dotenv(), patch("fin_news_events.llm_clients.requests.get", return_value=ok):
            healthy, code, msg = LiteLLMClient().check_health()
            self.assertTrue(healthy)
            self.assertEqual(code, 200)
            self.assertEqual(msg, "OK")

        pay = MagicMock()
        pay.status_code = 402
        pay.text = "payment"
        with _env({
            "LITELLM_BASE_URL": "http://litellm.internal/v1",
            "LITELLM_API_KEY": "sk-corp",
        }), _no_dotenv(), patch("fin_news_events.llm_clients.requests.get", return_value=pay):
            healthy, code, msg = LiteLLMClient().check_health()
            self.assertFalse(healthy)
            self.assertEqual(code, 402)
            self.assertEqual(msg, "PAYMENT_REQUIRED")


if __name__ == "__main__":
    unittest.main()
