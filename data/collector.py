"""
TrendPulse Data Collectors v2
=============================
Multi-source: stocks (50+), crypto (20+), HN, Reddit, ProductHunt,
Fear & Greed, VIX, US Treasury yields. All public APIs, zero keys.
"""

from __future__ import annotations

import json
import urllib.request
import urllib.error
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone


def _get(url: str, timeout: int = 10) -> dict:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "TrendPulse/2.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read())
    except Exception as e:
        print(f"[Collector] {url[:60]} → {e}")
        return {}


def _get_list(url: str, timeout: int = 10) -> list:
    result = _get(url, timeout)
    return result if isinstance(result, list) else []


def _get_text(url: str, timeout: int = 10) -> str:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "TrendPulse/2.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        print(f"[Collector] text {url[:60]} → {e}")
        return ""


# ═══════════════════════════════════════════════════════════════
# HACKER NEWS
# ═══════════════════════════════════════════════════════════════

def fetch_hn_trending(limit: int = 12) -> list:
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
# STOCKS — 50+ tickers, sector-aware, via Yahoo Finance
# ═══════════════════════════════════════════════════════════════

STOCK_TICKERS = {
    "tech":       ["AAPL","MSFT","GOOGL","NVDA","META","TSLA","AMZN","NFLX","AMD","INTC","CRM","ADBE","ORCL","IBM","CSCO","QCOM","AVGO","TXN","SHOP","SNAP","UBER","PYPL","SQ","ZM","SNOW","PLTR","CRWD","NET","DDOG"],
    "finance":    ["JPM","GS","BAC","WFC","MS","C","BLK","SCHW","V","MA","AXP","COIN"],
    "etf_index":  ["SPY","QQQ","IWM","DIA","ARKK","SOXX","SMH","XLF","XLE","XLK","TQQQ","SQQQ","UVXY","VIXY"],
    "meme_energy":["GME","AMC","BB","NOK","RIVN","LCID","NIO","XPEV","OXY","XOM","CVX","COP"],
}

STOCK_SECTORS = {}
for sector, tickers in STOCK_TICKERS.items():
    for t in tickers:
        STOCK_SECTORS[t] = sector

ALL_TICKERS = [t for tickers in STOCK_TICKERS.values() for t in tickers]


def fetch_stock_movers(limit: int = 15) -> list:
    """Fetch quotes for all tickers in parallel, return top by absolute change."""
    from concurrent.futures import ThreadPoolExecutor, as_completed
    results = []
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(_get_yahoo_quote, s): s for s in ALL_TICKERS}
        for future in as_completed(futures, timeout=30):
            try:
                quote = future.result()
                if quote:
                    results.append(quote)
            except Exception:
                pass
    results.sort(key=lambda x: abs(x.get("change_pct", 0)), reverse=True)
    return results[:limit]


def fetch_stocks_by_sector() -> dict:
    """Return stocks grouped by sector, fetched in parallel."""
    # Reuse results from fetch_stock_movers if recently called, else fetch
    from concurrent.futures import ThreadPoolExecutor, as_completed
    results = []
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(_get_yahoo_quote, s): s for s in ALL_TICKERS}
        for future in as_completed(futures, timeout=30):
            try:
                quote = future.result()
                if quote:
                    results.append(quote)
            except Exception:
                pass
    sectors = {}
    for q in results:
        sec = q.get("sector", "other")
        sectors.setdefault(sec, []).append(q)
    for sec in sectors:
        sectors[sec].sort(key=lambda x: abs(x["change_pct"]), reverse=True)
    return sectors


def fetch_single_stock(symbol: str) -> dict | None:
    """Fetch detailed quote for a single stock (for SEO pages)."""
    return _get_yahoo_quote(symbol)


def _get_yahoo_quote(symbol: str) -> dict | None:
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=5d"
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

        # Get 5-day price history for mini chart
        timestamps = result[0].get("timestamp", [])
        closes = result[0].get("indicators", {}).get("quote", [{}])[0].get("close", [])
        sparkline = [round(c, 2) for c in closes if c is not None] if closes else []

        return {
            "symbol": symbol,
            "price": round(price, 2),
            "change": round(change, 2),
            "change_pct": round(pct, 2),
            "high": round(meta.get("regularMarketDayHigh", price), 2),
            "low": round(meta.get("regularMarketDayLow", price), 2),
            "volume": meta.get("regularMarketVolume", 0),
            "market_cap": meta.get("marketCap", 0),
            "previous_close": round(prev, 2),
            "sparkline": sparkline,
            "sector": STOCK_SECTORS.get(symbol, "other"),
        }
    except Exception as e:
        print(f"[Collector] Yahoo {symbol}: {e}")
        return None


# ═══════════════════════════════════════════════════════════════
# CRYPTO — 20+ coins via Binance public API
# ═══════════════════════════════════════════════════════════════

CRYPTO_SYMBOLS = [
    "BTC","ETH","SOL","DOGE","XRP","ADA","AVAX","DOT","LINK","UNI",
    "MATIC","SHIB","LTC","ATOM","NEAR","ALGO","FTM","SAND","MANA","APE",
    "ARB","OP","SUI","APT","PEPE","WIF","BONK",
]


def fetch_crypto_prices(limit: int = 12) -> list:
    all_tickers = _get_list("https://api.binance.com/api/v3/ticker/24hr", timeout=8)
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
        high = float(t.get("highPrice", 0) or 0)
        low = float(t.get("lowPrice", 0) or 0)
        base = sym.replace("USDT", "")
        results.append({
            "symbol": base,
            "price": price,
            "change_pct": round(pct, 2),
            "volume": vol,
            "volume_fmt": _fmt_volume(vol),
            "high": high,
            "low": low,
            "url": f"https://www.binance.com/en/trade/{base}_USDT",
        })
    results.sort(key=lambda x: abs(x["change_pct"]), reverse=True)
    return results[:limit]


def fetch_single_crypto(symbol: str) -> dict | None:
    """Fetch detailed info for one crypto (for SEO pages)."""
    url = f"https://api.binance.com/api/v3/ticker/24hr?symbol={symbol}USDT"
    try:
        data = _get(url, timeout=5)
        if not data:
            return None
        price = float(data.get("lastPrice", 0))
        pct = float(data.get("priceChangePercent", 0))
        vol = float(data.get("quoteVolume", 0))
        high = float(data.get("highPrice", 0))
        low = float(data.get("lowPrice", 0))
        return {
            "symbol": symbol,
            "price": price,
            "change_pct": round(pct, 2),
            "volume": vol,
            "volume_fmt": _fmt_volume(vol),
            "high": high,
            "low": low,
            "url": f"https://www.binance.com/en/trade/{symbol}_USDT",
        }
    except Exception as e:
        print(f"[Collector] Binance {symbol}: {e}")
        return None


# ═══════════════════════════════════════════════════════════════
# REDDIT — hot posts from trading/crypto subs
# ═══════════════════════════════════════════════════════════════

REDDIT_SUBS = ["wallstreetbets", "stocks", "CryptoCurrency", "investing", "StockMarket"]


def fetch_reddit_trending(limit: int = 10) -> list:
    """Fetch hot posts from financial subreddits via public JSON API."""
    all_posts = []
    for sub in REDDIT_SUBS:
        url = f"https://www.reddit.com/r/{sub}/hot.json?limit=5"
        data = _get(url, timeout=8)
        children = data.get("data", {}).get("children", [])
        for child in children:
            post = child.get("data", {})
            if post.get("stickied"):
                continue
            all_posts.append({
                "subreddit": sub,
                "title": post.get("title", "")[:200],
                "url": f"https://www.reddit.com{post.get('permalink', '')}",
                "score": post.get("score", 0),
                "comments": post.get("num_comments", 0),
                "author": post.get("author", "anon"),
                "flair": post.get("link_flair_text", ""),
                "created": datetime.fromtimestamp(post.get("created_utc", 0), tz=timezone.utc).isoformat(),
            })
    all_posts.sort(key=lambda x: x["score"], reverse=True)
    return all_posts[:limit]


# ═══════════════════════════════════════════════════════════════
# PRODUCT HUNT — today's trending products
# ═══════════════════════════════════════════════════════════════

def fetch_producthunt_trending(limit: int = 8) -> list:
    """Fetch trending products from ProductHunt (public HTML scrape / community API)."""
    # Use the public GraphQL endpoint that PH frontend uses
    url = "https://api.producthunt.com/v2/api/graphql"
    query = """
    query {
      posts(first: 10, order: RANKING, topic: "") {
        edges {
          node {
            id name tagline description url votesCount commentsCount
            thumbnail { url }
            topics { edges { node { name } } }
          }
        }
      }
    }
    """
    try:
        req = urllib.request.Request(
            url,
            data=json.dumps({"query": query}).encode(),
            headers={
                "User-Agent": "TrendPulse/2.0",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
        posts = data.get("data", {}).get("posts", {}).get("edges", [])
        results = []
        for edge in posts[:limit]:
            node = edge.get("node", {})
            results.append({
                "name": node.get("name", ""),
                "tagline": node.get("tagline", ""),
                "description": (node.get("description") or "")[:150],
                "url": node.get("url", ""),
                "votes": node.get("votesCount", 0),
                "comments": node.get("commentsCount", 0),
                "topics": [t.get("node", {}).get("name", "") for t in node.get("topics", {}).get("edges", [])],
                "thumbnail": node.get("thumbnail", {}).get("url", ""),
            })
        return results
    except Exception as e:
        print(f"[Collector] ProductHunt: {e}")
        # Fallback: try the old public API
        return _fetch_ph_fallback(limit)


def _fetch_ph_fallback(limit: int = 8) -> list:
    """Fallback PH scraper via RSS."""
    try:
        text = _get_text("https://www.producthunt.com/feed", timeout=10)
        # Simple title extraction from RSS-like content
        results = []
        titles = re.findall(r'<title>(.*?)</title>', text)
        links = re.findall(r'<link>(.*?)</link>', text)
        for i, title in enumerate(titles[1:limit+1]):  # skip first (feed title)
            results.append({
                "name": title[:100],
                "tagline": "",
                "description": "",
                "url": links[i+1] if i+1 < len(links) else "https://www.producthunt.com",
                "votes": 0,
                "comments": 0,
                "topics": [],
                "thumbnail": "",
            })
        return results
    except Exception as e:
        print(f"[Collector] PH fallback: {e}")
        return []


# ═══════════════════════════════════════════════════════════════
# FEAR & GREED INDEX
# ═══════════════════════════════════════════════════════════════

def fetch_fear_greed() -> dict | None:
    """Fetch Fear & Greed Index from alternative.me API."""
    url = "https://api.alternative.me/fng/?limit=1"
    try:
        data = _get(url, timeout=8)
        item = data.get("data", [{}])[0]
        if not item:
            return None
        score = int(item.get("value", 50))
        sentiment = item.get("value_classification", "Neutral")
        return {
            "score": score,
            "sentiment": sentiment,
            "timestamp": int(item.get("timestamp", 0)),
        }
    except Exception as e:
        print(f"[Collector] FearGreed: {e}")
        return None


# ═══════════════════════════════════════════════════════════════
# VIX — CBOE Volatility Index via Yahoo
# ═══════════════════════════════════════════════════════════════

def fetch_vix() -> dict | None:
    """Fetch VIX (^VIX) from Yahoo Finance."""
    url = "https://query1.finance.yahoo.com/v8/finance/chart/%5EVIX?interval=1d&range=5d"
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
        pct = (change / prev) * 100
        timestamps = result[0].get("timestamp", [])
        closes = result[0].get("indicators", {}).get("quote", [{}])[0].get("close", [])
        sparkline = [round(c, 2) for c in closes if c is not None]
        return {
            "symbol": "VIX",
            "price": round(price, 2),
            "change": round(change, 2),
            "change_pct": round(pct, 2),
            "previous_close": round(prev, 2),
            "sparkline": sparkline,
        }
    except Exception as e:
        print(f"[Collector] VIX: {e}")
        return None


# ═══════════════════════════════════════════════════════════════
# US TREASURY YIELDS — via Treasury.gov
# ═══════════════════════════════════════════════════════════════

def fetch_treasury_yields() -> list:
    """Fetch latest US Treasury yields."""
    # Use Yahoo Finance for treasury yields
    etfs = {"SHY": "1-3Y", "IEF": "7-10Y", "TLT": "20+Y"}
    results = []
    for etf, label in etfs.items():
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{etf}?interval=1d&range=1d"
        try:
            data = _get(url, timeout=5)
            result = data.get("chart", {}).get("result", [])
            if result:
                meta = result[0].get("meta", {})
                price = meta.get("regularMarketPrice", 0)
                prev = meta.get("chartPreviousClose", 0)
                pct = ((price - prev) / prev * 100) if prev else 0
                results.append({"label": label, "etf": etf, "price": round(price, 2), "change_pct": round(pct, 2)})
        except Exception as e:
            print(f"[Collector] Treasury {etf}: {e}")
    return results


# ═══════════════════════════════════════════════════════════════
# GITHUB TRENDING
# ═══════════════════════════════════════════════════════════════

def fetch_github_trending(limit: int = 8) -> list:
    from datetime import datetime as dt, timedelta
    week_ago = (dt.utcnow() - timedelta(days=7)).strftime("%Y-%m-%d")
    url = (
        f"https://api.github.com/search/repositories"
        f"?q=stars:%3E100+pushed:%3E{week_ago}"
        f"&sort=stars&order=desc&per_page={limit}"
    )
    data = _get(url, timeout=15)
    items = data.get("items", []) if isinstance(data, dict) else []
    results = []
    for repo in items[:limit]:
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
    if vol >= 1_000_000_000:
        return f"${vol/1_000_000_000:.1f}B"
    if vol >= 1_000_000:
        return f"${vol/1_000_000:.1f}M"
    if vol >= 1_000:
        return f"${vol/1_000:.0f}K"
    return f"${vol:.0f}"
