"""
TrendPulse Data Collectors
===========================
Each function fetches from a public API, normalizes the output,
and returns a clean list of dicts. All use stdlib only — zero API keys.
"""

from __future__ import annotations

import json
import urllib.request
import urllib.error
from datetime import datetime, timezone


def _get(url: str, timeout: int = 10) -> dict:
    """Fetch JSON from URL, return empty dict on any error."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "TrendPulse/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read())
    except Exception as e:
        print(f"[Collector] {url[:60]} → {e}")
        return {}


def _get_list(url: str, timeout: int = 10) -> list:
    """Fetch JSON list from URL, return empty list on any error."""
    result = _get(url, timeout)
    return result if isinstance(result, list) else []


# ═══════════════════════════════════════════════════════════════
# HACKER NEWS — top stories
# ═══════════════════════════════════════════════════════════════

def fetch_hn_trending(limit: int = 10) -> list:
    """Fetch top HN stories with title, score, comments, url."""
    BASE = "https://hacker-news.firebaseio.com/v0"
    ids = _get_list(f"{BASE}/topstories.json")[:limit * 2]

    stories = []
    for item_id in ids:
        if len(stories) >= limit:
            break
        item = _get(f"{BASE}/item/{item_id}.json")
        if not item or item.get("type") != "story":
            continue
        stories.append({
            "id": item.get("id"),
            "title": item.get("title", "Untitled"),
            "url": item.get("url", f"https://news.ycombinator.com/item?id={item.get('id')}"),
            "score": item.get("score", 0),
            "comments": item.get("descendants", 0),
            "by": item.get("by", "anon"),
            "time": datetime.fromtimestamp(item.get("time", 0), tz=timezone.utc).isoformat(),
        })
    return stories


# ═══════════════════════════════════════════════════════════════
# STOCKS — major movers via Yahoo Finance (unofficial)
# ═══════════════════════════════════════════════════════════════

WATCH_TICKERS = [
    "AAPL", "MSFT", "GOOGL", "NVDA",
    "TSLA", "META", "SPY", "QQQ",
    "COIN", "GME",
]


def fetch_stock_movers() -> list:
    """Fetch quotes for major tickers, return top 10 by absolute change."""
    results = []
    for symbol in WATCH_TICKERS:
        quote = _get_yahoo_quote(symbol)
        if quote:
            results.append(quote)
    results.sort(key=lambda x: abs(x.get("change_pct", 0)), reverse=True)
    return results[:10]


def _get_yahoo_quote(symbol: str) -> dict | None:
    """Fetch a single quote from Yahoo Finance v8 API."""
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=1d"
    try:
        data = _get(url, timeout=5)
        result = data.get("chart", {}).get("result", [])
        if not result:
            return None
        meta = result[0].get("meta", {})
        price = meta.get("regularMarketPrice")
        prev = meta.get("chartPreviousClose") or meta.get("previousClose")
        if not price or not prev:
            return None
        change = price - prev
        pct = (change / prev) * 100 if prev else 0
        return {
            "symbol": symbol,
            "price": round(price, 2),
            "change": round(change, 2),
            "change_pct": round(pct, 2),
            "high": round(meta.get("regularMarketDayHigh", price), 2),
            "low": round(meta.get("regularMarketDayLow", price), 2),
        }
    except Exception as e:
        print(f"[Collector] Yahoo {symbol}: {e}")
        return None


# ═══════════════════════════════════════════════════════════════
# CRYPTO — top coins via Binance public API (works globally)
# ═══════════════════════════════════════════════════════════════

CRYPTO_SYMBOLS = ["BTC", "ETH", "SOL", "DOGE", "XRP", "ADA", "AVAX", "DOT", "LINK", "UNI"]
BINANCE_TICKER_URL = "https://api.binance.com/api/v3/ticker/24hr"


def fetch_crypto_prices() -> list:
    """Fetch 24hr price change for major crypto pairs via Binance public API."""
    all_tickers = _get_list(BINANCE_TICKER_URL, timeout=8)
    if not all_tickers:
        return []

    target = {f"{s}USDT" for s in CRYPTO_SYMBOLS}
    results = []
    for t in all_tickers:
        if not isinstance(t, dict):
            continue
        sym = t.get("symbol", "")
        if sym not in target:
            continue
        price = float(t.get("lastPrice", 0) or 0)
        pct = float(t.get("priceChangePercent", 0) or 0)
        vol = float(t.get("quoteVolume", 0) or 0)
        base = sym.replace("USDT", "")
        results.append({
            "symbol": base,
            "price": price,
            "change_pct": round(pct, 2),
            "volume": vol,
            "volume_fmt": _fmt_volume(vol),
            "url": f"https://www.binance.com/en/trade/{base}_USDT",
        })
    results.sort(key=lambda x: abs(x["change_pct"]), reverse=True)
    return results[:8]


# ═══════════════════════════════════════════════════════════════
# GITHUB — trending repositories
# ═══════════════════════════════════════════════════════════════

GH_TRENDING_URL = (
    "https://api.github.com/search/repositories"
    "?q=stars:%3E100+pushed:%3E2026-05-22"
    "&sort=stars&order=desc&per_page=10"
)


def fetch_github_trending(limit: int = 8) -> list:
    """Fetch trending GitHub repos."""
    data = _get(GH_TRENDING_URL, timeout=15)
    items = data.get("items", []) if isinstance(data, dict) else []
    results = []
    for repo in items:
        if len(results) >= limit:
            break
        results.append({
            "name": repo.get("full_name", "unknown/repo"),
            "description": (repo.get("description") or "No description")[:120],
            "stars": repo.get("stargazers_count", 0),
            "stars_fmt": _fmt_volume(repo.get("stargazers_count", 0)),
            "language": repo.get("language") or "",
            "url": repo.get("html_url", ""),
            "topics": repo.get("topics", [])[:4],
        })
    return results


# ═══════════════════════════════════════════════════════════════
# UTILITY
# ═══════════════════════════════════════════════════════════════

def _fmt_volume(vol: float) -> str:
    """Format volume: 1234567 → '$1.23M'"""
    if vol >= 1_000_000:
        return f"${vol / 1_000_000:.1f}M"
    if vol >= 1_000:
        return f"${vol / 1_000:.0f}K"
    return f"${vol:.0f}"
