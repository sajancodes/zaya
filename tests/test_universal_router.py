import unittest
from unittest.mock import patch, MagicMock
from core.universal_router import (
    UniversalLLMRouter,
    ProviderConfig,
    normalize_tools_for_openai,
    parse_tool_calls_from_response
)

class TestUniversalRouter(unittest.TestCase):
    def setUp(self):
        self.router = UniversalLLMRouter()

    def test_normalize_tools_for_openai(self):
        zaya_tool = {
            "name": "open_app",
            "description": "Opens an application",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "app_name": {"type": "STRING"}
                },
                "required": ["app_name"]
            }
        }
        normalized = normalize_tools_for_openai([zaya_tool])
        self.assertEqual(len(normalized), 1)
        self.assertEqual(normalized[0]["type"], "function")
        self.assertEqual(normalized[0]["function"]["name"], "open_app")
        self.assertEqual(normalized[0]["function"]["description"], "Opens an application")
        self.assertEqual(normalized[0]["function"]["parameters"]["type"], "object")

    @patch("requests.post")
    def test_openai_compatible_success(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "Hello! I am Zaya.",
                        "tool_calls": []
                    }
                }
            ]
        }
        mock_post.return_value = mock_resp

        config = ProviderConfig(
            provider="9router",
            base_url="https://api.9router.com/v1",
            api_key="sk-test-9router",
            model="gpt-4o-mini"
        )
        result = self.router.execute_request(config, [{"role": "user", "content": "hi"}])
        self.assertEqual(result["content"], "Hello! I am Zaya.")
        self.assertEqual(result["provider_used"], "9router")

    @patch("requests.post")
    def test_fallback_on_rate_limit(self, mock_post):
        # First call (e.g. primary provider) fails with 429 Rate Limit
        mock_resp_fail = MagicMock()
        mock_resp_fail.status_code = 429
        mock_resp_fail.text = "Rate limit reached"

        # Second call (fallback provider) succeeds with 200
        mock_resp_success = MagicMock()
        mock_resp_success.status_code = 200
        mock_resp_success.json.return_value = {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "Responded via fallback OpenRouter.",
                        "tool_calls": []
                    }
                }
            ]
        }
        mock_post.side_effect = [mock_resp_fail, mock_resp_success]

        primary = ProviderConfig(provider="primary", base_url="https://api.primary.com/v1", api_key="k1", model="m1")
        fallback = ProviderConfig(provider="openrouter", base_url="https://openrouter.ai/api/v1", api_key="k2", model="m2")

        result = self.router.route_with_fallback(
            messages=[{"role": "user", "content": "hello"}],
            chain=[primary, fallback]
        )
        self.assertEqual(result["content"], "Responded via fallback OpenRouter.")
        self.assertEqual(result["provider_used"], "openrouter")

    def test_parse_tool_calls(self):
        openai_resp = {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "",
                        "tool_calls": [
                            {
                                "id": "call_123",
                                "type": "function",
                                "function": {
                                    "name": "control_media_playback",
                                    "arguments": "{\"action\": \"pause\"}"
                                }
                            }
                        ]
                    }
                }
            ]
        }
        calls = parse_tool_calls_from_response(openai_resp)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["name"], "control_media_playback")
        self.assertEqual(calls[0]["arguments"], {"action": "pause"})

if __name__ == "__main__":
    unittest.main()
