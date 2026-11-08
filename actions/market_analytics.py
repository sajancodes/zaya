"""Market analytics and real-time financial quotes engine.

Provides real-time stock, ETF, index, and cryptocurrency market quotes,
multi-ticker comparisons, and performance metrics without external API keys.
"""
from __future__ import annotations

import json
import re
import time
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional


_COMMON_ALIASES: Dict[str, str] = {
    "apple": "AAPL",
    "microsoft": "MSFT",
    "nvidia": "NVDA",
    "google": "GOOGL",
    "alphabet": "GOOGL",
    "amazon": "AMZN",
    "tesla": "TSLA",
    "meta": "META",
    "facebook": "META",
    "netflix": "NFLX",
    "amd": "AMD",
    "intel": "INTC",
    "broadcom": "AVGO",
    "qualcomm": "QCOM",
    "taiwan semiconductor": "TSM",
    "tsmc": "TSM",
    "bitcoin": "BTC-USD",
    "btc": "BTC-USD",
    "ethereum": "ETH-USD",
    "eth": "ETH-USD",
    "solana": "SOL-USD",
    "sol": "SOL-USD",
    "dogecoin": "DOGE-USD",
    "doge": "DOGE-USD",
    "sp500": "^GSPC",
    "s&p 500": "^GSPC",
    "nasdaq": "^IXIC",
    "dow": "^DJI",
    "dow jones": "^DJI",
}

# Cache: symbol -> (timestamp, data_dict)
_QUOTE_CACHE: Dict[str, tuple[float, dict]] = {}
_CACHE_TTL = 60.0  # 60 seconds


def _normalize_symbol(sym: str) -> str:
    s = sym.strip().lower()
    if s in _COMMON_ALIASES:
        return _COMMON_ALIASES[s]
    return sym.strip().upper()


def _fetch_quote(symbol: str) -> Optional[Dict[str, Any]]:
    sym = _normalize_symbol(symbol)
    now = time.time()
    cached = _QUOTE_CACHE.get(sym)
    if cached and (now - cached[0] < _CACHE_TTL):
        return cached[1]

    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(sym)}?interval=1d&range=1d"
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    )

    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            result = data.get("chart", {}).get("result")
            if not result:
                return None
            meta = result[0].get("meta", {})
            price = meta.get("regularMarketPrice")
            if price is None:
                return None

            prev_close = meta.get("chartPreviousClose", price)
            change = price - prev_close
            change_pct = (change / prev_close * 100.0) if prev_close else 0.0

            quote_info = {
                "symbol": meta.get("symbol", sym),
                "name": meta.get("shortName") or meta.get("longName") or sym,
                "price": round(float(price), 2),
                "currency": meta.get("currency", "USD"),
                "change": round(float(change), 2),
                "change_percent": round(float(change_pct), 2),
                "day_high": round(float(meta.get("regularMarketDayHigh", price)), 2),
                "day_low": round(float(meta.get("regularMarketDayLow", price)), 2),
                "fifty_two_week_high": round(float(meta.get("fiftyTwoWeekHigh", price)), 2),
                "fifty_two_week_low": round(float(meta.get("fiftyTwoWeekLow", price)), 2),
                "volume": meta.get("regularMarketVolume", 0),
            }
            _QUOTE_CACHE[sym] = (now, quote_info)
            return quote_info
    except Exception as e:
        return None


def market_analytics(parameters: dict, **_kwargs) -> str:
    """Executes market quote queries or comparisons."""
    action = str(parameters.get("action") or "quote").lower().strip()
    symbols_input = parameters.get("symbols") or parameters.get("symbol") or parameters.get("query") or ""

    if isinstance(symbols_input, str):
        # Extract comma, space, or vs separated tickers
        raw_symbols = [s.strip() for s in re.split(r"[,;\s]+|\bvs\b", symbols_input, flags=re.IGNORECASE) if s.strip()]
    elif isinstance(symbols_input, list):
        raw_symbols = [str(s).strip() for s in symbols_input if str(s).strip()]
    else:
        raw_symbols = []

    if not raw_symbols:
        return json.dumps({
            "status": "error",
            "message": "Please specify at least one stock or crypto symbol (e.g., AAPL, NVDA, BTC)."
        }, indent=2)

    if action in ("compare", "versus", "vs") or len(raw_symbols) > 1:
        quotes = []
        for s in raw_symbols:
            q = _fetch_quote(s)
            if q:
                quotes.append(q)

        if not quotes:
            return json.dumps({
                "status": "error",
                "message": f"Could not retrieve market data for: {', '.join(raw_symbols)}."
            }, indent=2)

        # Sort by daily performance descending
        sorted_quotes = sorted(quotes, key=lambda x: x["change_percent"], reverse=True)
        winner = sorted_quotes[0]

        summary_parts = []
        for q in sorted_quotes:
            sign = "+" if q["change"] >= 0 else ""
            summary_parts.append(
                f"{q['name']} ({q['symbol']}): {q['currency']} {q['price']:.2f} ({sign}{q['change_percent']:.2f}%)"
            )

        summary_text = (
            f"Comparison of {len(quotes)} assets: {'; '.join(summary_parts)}. "
            f"Leader today: {winner['name']} with {winner['change_percent']:+.2f}%."
        )

        return json.dumps({
            "status": "success",
            "action": "compare",
            "assets": sorted_quotes,
            "leader": winner["symbol"],
            "summary": summary_text
        }, indent=2)

    # Single quote action
    sym = raw_symbols[0]
    q = _fetch_quote(sym)
    if not q:
        return json.dumps({
            "status": "error",
            "message": f"Unable to fetch market quote for symbol '{sym}'."
        }, indent=2)

    sign = "+" if q["change"] >= 0 else ""
    summary_text = (
        f"{q['name']} ({q['symbol']}) is currently trading at {q['currency']} {q['price']:.2f}, "
        f"up {sign}{q['change_percent']:.2f}% ({sign}{q['change']:.2f}) today. "
        f"Day range: {q['day_low']:.2f} - {q['day_high']:.2f}."
    )

    return json.dumps({
        "status": "success",
        "action": "quote",
        "data": q,
        "summary": summary_text
    }, indent=2)


TOOL = {
    "name": "market_analytics",
    "description": (
        "Real-time financial market analytics and price quotes for stocks, ETFs, crypto (Bitcoin, Ethereum), "
        "and market indices. Supports single asset quotes and multi-ticker performance comparisons."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "'quote' to get real-time price and day statistics; 'compare' to compare performance between two or more tickers.",
                "enum": ["quote", "compare"]
            },
            "symbols": {
                "type": "STRING",
                "description": "Ticker symbol(s) or asset name (e.g., 'AAPL', 'NVDA', 'BTC-USD', 'Tesla', or 'NVDA vs AMD')."
            }
        },
        "required": ["symbols"]
    },
    "handler": market_analytics,
}
