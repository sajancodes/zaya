import json
from unittest.mock import patch
from actions.market_analytics import (
    _normalize_symbol,
    market_analytics,
    TOOL,
)


def test_symbol_normalization():
    assert _normalize_symbol("apple") == "AAPL"
    assert _normalize_symbol("bitcoin") == "BTC-USD"
    assert _normalize_symbol("nvidia") == "NVDA"
    assert _normalize_symbol("tsla") == "TSLA"
    assert _normalize_symbol("AMD") == "AMD"


def test_market_analytics_missing_symbols():
    res = json.loads(market_analytics({"symbols": ""}))
    assert res["status"] == "error"
    assert "specify at least one" in res["message"]


def test_market_analytics_single_quote():
    mock_data = {
        "symbol": "AAPL",
        "name": "Apple Inc.",
        "price": 230.50,
        "currency": "USD",
        "change": 4.50,
        "change_percent": 1.99,
        "day_high": 232.00,
        "day_low": 228.00,
        "fifty_two_week_high": 240.00,
        "fifty_two_week_low": 165.00,
        "volume": 45000000,
    }

    with patch("actions.market_analytics._fetch_quote", return_value=mock_data):
        raw = market_analytics({"action": "quote", "symbols": "AAPL"})
        res = json.loads(raw)
        assert res["status"] == "success"
        assert res["action"] == "quote"
        assert res["data"]["symbol"] == "AAPL"
        assert res["data"]["price"] == 230.50
        assert "Apple Inc." in res["summary"]
        assert "230.50" in res["summary"]


def test_market_analytics_compare():
    mock_nvda = {
        "symbol": "NVDA",
        "name": "NVIDIA Corporation",
        "price": 140.00,
        "currency": "USD",
        "change": 5.00,
        "change_percent": 3.70,
        "day_high": 142.00,
        "day_low": 138.00,
        "fifty_two_week_high": 150.00,
        "fifty_two_week_low": 75.00,
        "volume": 70000000,
    }
    mock_amd = {
        "symbol": "AMD",
        "name": "Advanced Micro Devices",
        "price": 160.00,
        "currency": "USD",
        "change": 2.00,
        "change_percent": 1.25,
        "day_high": 162.00,
        "day_low": 158.00,
        "fifty_two_week_high": 220.00,
        "fifty_two_week_low": 120.00,
        "volume": 30000000,
    }

    def fake_fetch(sym):
        if "NVDA" in sym.upper():
            return mock_nvda
        if "AMD" in sym.upper():
            return mock_amd
        return None

    with patch("actions.market_analytics._fetch_quote", side_effect=fake_fetch):
        raw = market_analytics({"action": "compare", "symbols": "NVDA vs AMD"})
        res = json.loads(raw)
        assert res["status"] == "success"
        assert res["action"] == "compare"
        assert len(res["assets"]) == 2
        assert res["leader"] == "NVDA"
        assert "Leader today: NVIDIA Corporation" in res["summary"]


def test_tool_declaration():
    assert TOOL["name"] == "market_analytics"
    assert "market analytics" in TOOL["description"].lower()
    assert callable(TOOL["handler"])


def test_symbol_extraction_multiword_and_phrases():
    from actions.market_analytics import _extract_symbols

    # 1. Compare NVIDIA and Microsoft.
    assert _extract_symbols("Compare NVIDIA and Microsoft.") == ["NVDA", "MSFT"]

    # 2. Compare Taiwan Semiconductor and Apple.
    assert _extract_symbols("Compare Taiwan Semiconductor and Apple.") == ["TSM", "AAPL"]

    # 3. What's the price of Bitcoin?
    assert _extract_symbols("What's the price of Bitcoin?") == ["BTC-USD"]

    # 4. How is AAPL doing today?
    assert _extract_symbols("How is AAPL doing today?") == ["AAPL"]

    # 5. Compare NVDA, MSFT and TSM.
    assert _extract_symbols("Compare NVDA, MSFT and TSM.") == ["NVDA", "MSFT", "TSM"]

    # 6. Standalone multiword name
    assert _extract_symbols("Taiwan Semiconductor") == ["TSM"]
    assert _extract_symbols("S&P 500") == ["^GSPC"]

    # 7. Specific prompt regression requirements
    assert _extract_symbols("Meta Platforms") == ["META"]
    assert _extract_symbols("Compare Meta Platforms and Microsoft.") == ["META", "MSFT"]
    assert _extract_symbols("What's the price of Apple today?") == ["AAPL"]
    assert _extract_symbols("Compare NVIDIA, Microsoft and Taiwan Semiconductor.") == ["NVDA", "MSFT", "TSM"]
    assert _extract_symbols("How is AAPL performing?") == ["AAPL"]
    assert _extract_symbols("Compare NVDA vs AMD.") == ["NVDA", "AMD"]
    assert _extract_symbols("What's happening in the technology market?") == []
    assert _extract_symbols("Tell me about the stock market.") == []

    # 8. Natural language words must never become accidental ticker symbols
    assert _extract_symbols("Can you check the financial trends in the market?") == []
    assert _extract_symbols("Please show me the overall sector performance.") == []

