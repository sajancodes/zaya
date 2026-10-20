"""Unit tests for the Unified LLM Router, policies, health tracking, and failover.
Created and developed by Sajan Rai for Zaya.
"""

import unittest
from unittest.mock import Mock, patch

import requests

from core.llm.adapters.ollama import OllamaAdapter
from core.llm.health import CircuitState, CooldownTracker, ProviderHealth
from core.llm.policies import RetryPolicy
from core.llm.registry import ProviderConfig, ProviderRegistry
from core.llm.router import LLMRouter
from core.llm.types import (
    ImagePart,
    InvalidRequestError,
    LLMError,
    LLMMessage,
    ProviderUnavailableError,
    ToolDefinition,
)
from core.universal_router import UniversalLLMRouter, normalize_tools_for_openai


class TestLLMRouter(unittest.TestCase):

    def setUp(self):
        self.registry = ProviderRegistry()
        self.health = ProviderHealth(failure_threshold=2, recovery_timeout_sec=5.0)
        self.cooldown = CooldownTracker()
        self.retry_policy = RetryPolicy(max_retries=1, initial_backoff_sec=0.01, sleep_fn=lambda _: None)

        # Mock primary and fallback configs
        self.cfg_primary = ProviderConfig(
            name="mock_primary",
            provider_type="openai",
            base_url="https://primary.example/v1",
            api_keys=["key1", "key2"],
            model="mock-p1",
            priority=1,
        )
        self.cfg_secondary = ProviderConfig(
            name="mock_secondary",
            provider_type="groq",
            base_url="https://secondary.example/v1",
            api_keys=["key_sec"],
            model="mock-s1",
            priority=2,
        )
        self.registry.register(self.cfg_primary)
        self.registry.register(self.cfg_secondary)
        self.registry.primary_provider = "mock_primary"
        self.registry.fallback_chain = ["mock_primary", "mock_secondary"]

        self.router = LLMRouter(
            registry=self.registry,
            health=self.health,
            cooldown=self.cooldown,
            retry_policy=self.retry_policy,
            logger_fn=lambda _: None,
        )

    def test_schema_translation(self):
        """Validates tool schema translation into OpenAI compatible format."""
        tools = [
            {"name": "get_weather", "description": "Fetch weather", "parameters": {"type": "OBJECT", "properties": {"loc": {"type": "STRING"}}}},
            {"type": "function", "function": {"name": "get_time", "description": "Fetch time", "parameters": {"type": "object"}}}
        ]
        norm = normalize_tools_for_openai(tools)
        self.assertEqual(len(norm), 2)
        self.assertEqual(norm[0]["type"], "function")
        self.assertEqual(norm[0]["function"]["name"], "get_weather")
        self.assertEqual(norm[1]["function"]["name"], "get_time")

    @patch("requests.post")
    def test_successful_provider(self, mock_post):
        """Tests standard successful chat completion."""
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "Hello from primary!"}, "finish_reason": "stop"}],
            "usage": {"total_tokens": 15}
        }
        mock_post.return_value = mock_resp

        messages = [LLMMessage.user("Hi")]
        res = self.router.route(messages)

        self.assertEqual(res.content, "Hello from primary!")
        self.assertEqual(res.provider, "mock_primary")
        self.assertEqual(res.model, "mock-p1")
        self.assertEqual(self.health.metrics["mock_primary"].successful_requests, 1)

    @patch("requests.post")
    def test_tool_calls_parsing(self, mock_post):
        """Tests parsing of function tool calls."""
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{
                "message": {
                    "content": None,
                    "tool_calls": [{
                        "id": "call_123",
                        "type": "function",
                        "function": {"name": "calculate", "arguments": "{\"expr\": \"2+2\"}"}
                    }]
                },
                "finish_reason": "tool_calls"
            }]
        }
        mock_post.return_value = mock_resp

        tool = ToolDefinition(name="calculate", description="compute math", parameters={"type": "object"})
        res = self.router.route([LLMMessage.user("compute 2+2")], tools=[tool])

        self.assertEqual(len(res.tool_calls), 1)
        self.assertEqual(res.tool_calls[0].name, "calculate")
        self.assertEqual(res.tool_calls[0].arguments, {"expr": "2+2"})
        self.assertEqual(res.tool_calls[0].id, "call_123")

    @patch("requests.post")
    def test_multimodal_request(self, mock_post):
        """Tests multimodal message payload construction."""
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"choices": [{"message": {"content": "I see an image."}}]}
        mock_post.return_value = mock_resp

        img = ImagePart(data=b"\x89PNG\r\n\x1a\nfakeimage", mime_type="image/png")
        msg = LLMMessage.user("What is this?", image=img)
        res = self.router.route([msg])

        self.assertEqual(res.content, "I see an image.")
        # Verify request json payload had image_url
        call_args = mock_post.call_args[1]
        payload = call_args["json"]
        parts = payload["messages"][0]["content"]
        self.assertEqual(len(parts), 2)
        self.assertEqual(parts[0]["type"], "text")
        self.assertEqual(parts[1]["type"], "image_url")
        self.assertTrue(parts[1]["image_url"]["url"].startswith("data:image/png;base64,"))

    @patch("requests.post")
    def test_fallback_on_429_rate_limit(self, mock_post):
        """When primary returns 429, router cools primary and falls back to secondary."""
        resp_429 = Mock()
        resp_429.status_code = 429
        resp_429.text = "Rate limit exceeded"
        resp_429.headers = {"Retry-After": "5"}

        resp_ok = Mock()
        resp_ok.status_code = 200
        resp_ok.json.return_value = {"choices": [{"message": {"content": "Fallback answer"}}]}

        mock_post.side_effect = [resp_429, resp_ok]

        res = self.router.route([LLMMessage.user("Hello")])

        self.assertEqual(res.content, "Fallback answer")
        self.assertEqual(res.provider, "mock_secondary")
        self.assertTrue(self.cooldown.is_cooling("mock_primary"))

    @patch("requests.post")
    def test_fallback_on_500_server_error(self, mock_post):
        """When primary returns 500, router falls back to secondary."""
        resp_500 = Mock()
        resp_500.status_code = 500
        resp_500.text = "Internal Server Error"
        resp_500.headers = {}

        resp_ok = Mock()
        resp_ok.status_code = 200
        resp_ok.json.return_value = {"choices": [{"message": {"content": "Recovered!"}}]}

        mock_post.side_effect = [resp_500, resp_500, resp_ok]

        res = self.router.route([LLMMessage.user("Hello")])
        self.assertEqual(res.content, "Recovered!")
        self.assertEqual(res.provider, "mock_secondary")

    @patch("requests.post")
    def test_fallback_on_timeout(self, mock_post):
        """When primary times out, router falls back to secondary."""
        resp_ok = Mock()
        resp_ok.status_code = 200
        resp_ok.json.return_value = {"choices": [{"message": {"content": "Secondary survived timeout"}}]}

        mock_post.side_effect = [
            requests.exceptions.Timeout("Connection timed out"),
            requests.exceptions.Timeout("Retry timed out"),
            resp_ok
        ]

        res = self.router.route([LLMMessage.user("Hello")])
        self.assertEqual(res.content, "Secondary survived timeout")
        self.assertEqual(res.provider, "mock_secondary")

    @patch("requests.post")
    def test_key_rotation_on_auth_error(self, mock_post):
        """When 401 is encountered and multiple keys exist, rotates key before abandoning."""
        resp_401 = Mock()
        resp_401.status_code = 401
        resp_401.text = "Invalid API key"
        resp_401.headers = {}

        resp_ok = Mock()
        resp_ok.status_code = 200
        mock_post.return_value = resp_ok
        resp_ok.json.return_value = {"choices": [{"message": {"content": "Success with rotated key!"}}]}

        mock_post.side_effect = [resp_401, resp_ok]

        res = self.router.route([LLMMessage.user("Hello")])
        self.assertEqual(res.content, "Success with rotated key!")
        self.assertEqual(self.cfg_primary.active_key_index, 1)

    @patch("requests.post")
    def test_invalid_request_surfaces_immediately(self, mock_post):
        """Client 400 error (e.g. malformed JSON/invalid parameters) must NOT fall back."""
        resp_400 = Mock()
        resp_400.status_code = 400
        resp_400.text = "Bad Request: unknown parameter"
        resp_400.headers = {}
        mock_post.return_value = resp_400

        with self.assertRaises(InvalidRequestError):
            self.router.route([LLMMessage.user("Hello")])

        # Verify fallback was NOT attempted
        self.assertEqual(mock_post.call_count, 1)

    @patch("requests.post")
    def test_malformed_json_raises(self, mock_post):
        """Malformed response body raises clear error."""
        resp_bad = Mock()
        resp_bad.status_code = 200
        resp_bad.text = "<html>502 Bad Gateway nginx</html>"
        resp_bad.json.side_effect = ValueError("Invalid JSON")
        mock_post.return_value = resp_bad

        with self.assertRaises(LLMError):
            self.router.route([LLMMessage.user("Hello")])

    def test_circuit_breaker(self):
        """Circuit opens after consecutive failures and blocks requests until recovery timeout."""
        health = ProviderHealth(failure_threshold=2, recovery_timeout_sec=10.0)
        self.assertTrue(health.allow_request("prov1"))

        health.record_failure("prov1", "Err 1")
        self.assertTrue(health.allow_request("prov1"))

        health.record_failure("prov1", "Err 2")
        self.assertEqual(health.circuit_state["prov1"], CircuitState.OPEN)
        self.assertFalse(health.allow_request("prov1"))

    @patch("requests.post")
    def test_ollama_native_handling(self, mock_post):
        """Tests Ollama adapter cleanly uses /api/chat when native url is provided."""
        cfg = ProviderConfig(name="ollama", provider_type="ollama", base_url="http://localhost:11434")
        adapter = OllamaAdapter(cfg)

        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "model": "llama3.2",
            "message": {"role": "assistant", "content": "Local Ollama response"},
            "done": True
        }
        mock_post.return_value = mock_resp

        res = adapter.chat([LLMMessage.user("test")])
        self.assertEqual(res.content, "Local Ollama response")

        # Verify url called is /api/chat and NOT /chat/completions
        url_called = mock_post.call_args[0][0]
        self.assertEqual(url_called, "http://localhost:11434/api/chat")

    @patch("requests.post")
    def test_ollama_unavailable_raises_clean_error(self, mock_post):
        """Tests offline Ollama raises ProviderUnavailableError with actionable message."""
        cfg = ProviderConfig(name="ollama", provider_type="ollama", base_url="http://localhost:11434")
        adapter = OllamaAdapter(cfg)
        mock_post.side_effect = requests.exceptions.ConnectionError("Connection refused")

        with self.assertRaises(ProviderUnavailableError) as ctx:
            adapter.chat([LLMMessage.user("test")])

        self.assertIn("ollama serve", str(ctx.exception).lower())

    @patch("requests.post")
    def test_streaming_chat(self, mock_post):
        """Tests streaming response decoding chunks."""
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.iter_lines.return_value = [
            b"data: {\"choices\": [{\"delta\": {\"content\": \"Hello \"}}]}",
            b"data: {\"choices\": [{\"delta\": {\"content\": \"world!\"}, \"finish_reason\": \"stop\"}]}",
            b"data: [DONE]"
        ]
        mock_post.return_value = mock_resp

        chunks = list(self.router.stream_route([LLMMessage.user("Hi")]))
        text = "".join(c.delta_text for c in chunks)
        self.assertEqual(text, "Hello world!")

    @patch("requests.post")
    def test_universal_router_backward_compatibility(self, mock_post):
        """Validates UniversalLLMRouter legacy facade calls LLMRouter smoothly."""
        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"choices": [{"message": {"content": "Facade working!"}}]}
        mock_post.return_value = mock_resp

        legacy = UniversalLLMRouter(router=self.router)
        res = legacy.route_with_fallback([{"role": "user", "content": "hello"}])
        self.assertEqual(res["content"], "Facade working!")


if __name__ == "__main__":
    unittest.main()
