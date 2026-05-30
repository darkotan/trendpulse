"""
TrendPulse — Real-time Data Aggregation Dashboard
===================================================
Multi-source data aggregation with Vercel-inspired design.
Monetization: Ads → Affiliate → Premium → API access.

Run: python3 app.py
Open: http://localhost:8766
"""

from flask import Flask, render_template, jsonify, request, make_response, send_file
from data.collector import (
    fetch_hn_trending,
    fetch_stock_movers,
    fetch_crypto_prices,
    fetch_github_trending,
)
from og_image import generate_og_image
import time
import threading
from datetime import datetime
import io

app = Flask(__name__)

# ── In-memory cache ──────────────────────────────────────────
_cache = {}
_cache_lock = threading.Lock()
_refresh_lock = threading.Lock()
CACHE_TTL = 300  # seconds


def refresh_cache():
    """Pull all data sources and update cache. Non-blocking if already refreshing."""
    global _cache
    if _refresh_lock.locked():
        return  # Already refreshing, skip
    with _refresh_lock:
        try:
            new_cache = {
                "updated_at": int(time.time()),
                "hn": fetch_hn_trending(),
                "stocks": fetch_stock_movers(),
                "crypto": fetch_crypto_prices(),
                "github": fetch_github_trending(),
            }
            with _cache_lock:
                _cache = new_cache
        except Exception as e:
            print(f"[TrendPulse] Refresh error: {e}")


def get_cache():
    """Return cached data, refreshing async if stale. Never blocks."""
    with _cache_lock:
        data = dict(_cache) if _cache else None
        stale = not _cache or (time.time() - _cache.get("updated_at", 0)) > CACHE_TTL
    if stale and not _refresh_lock.locked():
        # Fire-and-forget refresh in background
        t = threading.Thread(target=refresh_cache, daemon=True)
        t.start()
    return data or {"updated_at": 0, "hn": [], "stocks": [], "crypto": [], "github": []}


def bg_updater():
    """Continuously refresh cache in background."""
    while True:
        try:
            refresh_cache()
        except Exception as e:
            print(f"[TrendPulse] Cache refresh error: {e}")
        time.sleep(CACHE_TTL)


# ── SEO: get current public URL ───────────────────────────────
def public_url():
    """Return the canonical public URL — always https://trendscan.org."""
    return "https://trendscan.org"


# ── Routes ───────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/robots.txt")
def robots():
    """Tell search engines what to crawl."""
    base = public_url()
    txt = f"""User-agent: *
Allow: /
Sitemap: {base}/sitemap.xml
"""
    resp = make_response(txt)
    resp.headers["Content-Type"] = "text/plain"
    return resp


@app.route("/rss.xml")
def rss_feed():
    """RSS feed for feed readers and directories."""
    base = public_url()
    data = get_cache()
    today = datetime.utcnow().strftime("%a, %d %b %Y %H:%M:%S +0000")

    items_xml = ""
    # Hacker News top 3 as RSS items
    for item in data.get("hn", [])[:3]:
        items_xml += f"""    <item>
      <title>{_xml_escape(item.get('title', ''))}</title>
      <link>{_xml_escape(item.get('url', base))}</link>
      <description>Score: {item.get('score', 0)} | Comments: {item.get('comments', 0)}</description>
      <pubDate>{today}</pubDate>
      <guid>{base}/hn#{item.get('id', '')}</guid>
    </item>
"""
    # Stock movers as RSS items
    for item in data.get("stocks", [])[:3]:
        pct = item.get('change_pct', 0)
        direction = "↑" if pct >= 0 else "↓"
        items_xml += f"""    <item>
      <title>{item.get('symbol', '')} {direction}{abs(pct):.1f}% — ${item.get('price', 0):.2f}</title>
      <link>{base}/stock-market-today</link>
      <description>Price: ${item.get('price', 0):.2f} | Change: {pct:+.2f}% | High: ${item.get('high', 0):.2f} | Low: ${item.get('low', 0):.2f}</description>
      <pubDate>{today}</pubDate>
      <guid>{base}/stocks#{item.get('symbol', '')}</guid>
    </item>
"""

    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>TrendPulse — Real-time Market Data & Tech News</title>
    <link>{base}</link>
    <description>Live Hacker News, stock market, crypto, and GitHub trending data. Updated every 5 minutes.</description>
    <language>en</language>
    <lastBuildDate>{today}</lastBuildDate>
    <atom:link href="{base}/rss.xml" rel="self" type="application/rss+xml"/>
{items_xml}  </channel>
</rss>"""
    resp = make_response(xml)
    resp.headers["Content-Type"] = "application/xml; charset=utf-8"
    return resp


def _xml_escape(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


@app.route("/sitemap.xml")
def sitemap():
    """Dynamic XML sitemap for search engines."""
    base = public_url()
    today = datetime.utcnow().strftime("%Y-%m-%d")
    seo_urls = [
        "/", "/bitcoin-price", "/crypto-prices", "/stock-market-today",
        "/trending-github", "/tech-news",
    ]
    urls_xml = ""
    for path in seo_urls:
        priority = "1.0" if path == "/" else "0.8"
        urls_xml += f"""  <url>
    <loc>{base}{path}</loc>
    <lastmod>{today}</lastmod>
    <changefreq>hourly</changefreq>
    <priority>{priority}</priority>
  </url>
"""
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
{urls_xml}</urlset>"""
    resp = make_response(xml)
    resp.headers["Content-Type"] = "application/xml"
    return resp


@app.route("/api/all")
def api_all():
    data = get_cache()
    return jsonify(data)


@app.route("/api/hn")
def api_hn():
    return jsonify(get_cache().get("hn", []))


@app.route("/api/stocks")
def api_stocks():
    return jsonify(get_cache().get("stocks", []))


@app.route("/api/crypto")
def api_crypto():
    return jsonify(get_cache().get("crypto", []))


@app.route("/api/github")
def api_github():
    return jsonify(get_cache().get("github", []))


@app.route("/health")
def health():
    updated = 0
    try:
        with _cache_lock:
            updated = _cache.get("updated_at", 0) if _cache else 0
    except:
        pass
    return jsonify({"status": "ok", "updated_at": updated})


# ── SEO Landing Pages ──────────────────────────────────────

@app.route("/bitcoin-price")
def seo_bitcoin():
    return _seo_page(
        title="Bitcoin (BTC) Price Today — Live USD Price | TrendPulse",
        desc="Live Bitcoin price in USD. Real-time BTC price, 24h change, volume. Updated every 5 min.",
        h1="Bitcoin Price Today",
        keywords="bitcoin price, btc usd, bitcoin live, btc price today",
        section="crypto", filter_key="symbol", filter_val="BTC")

@app.route("/crypto-prices")
def seo_crypto():
    return _seo_page(
        title="Crypto Prices Today — BTC, ETH, SOL, DOGE | TrendPulse",
        desc="Live crypto prices: Bitcoin, Ethereum, Solana, Dogecoin. Real-time 24h change.",
        h1="Crypto Prices Today",
        keywords="crypto prices, cryptocurrency, btc eth sol, crypto tracker",
        section="crypto")

@app.route("/stock-market-today")
def seo_stocks():
    return _seo_page(
        title="Stock Market Today — Top Movers, Live Prices | TrendPulse",
        desc="Live stock market movers: AAPL, TSLA, NVDA, MSFT. Real-time prices and daily change.",
        h1="Stock Market Today",
        keywords="stock market today, stock movers, live stocks, market today",
        section="stocks")

@app.route("/trending-github")
def seo_github():
    return _seo_page(
        title="Trending GitHub Repos Today — Top Open Source | TrendPulse",
        desc="Discover trending GitHub repositories. Most starred open source projects today.",
        h1="Trending on GitHub",
        keywords="trending github, open source, top repos, github trending today",
        section="github")

@app.route("/tech-news")
def seo_hn():
    return _seo_page(
        title="Tech News Today — Hacker News Top Stories | TrendPulse",
        desc="Latest technology news from Hacker News. Top stories by votes. Updated every 5 min.",
        h1="Today's Tech News",
        keywords="tech news, hacker news, technology news, programming news, startup news",
        section="hn")


def _seo_page(title, desc, h1, keywords, section, filter_key=None, filter_val=None):
    """Render a generic SEO landing page."""
    data = get_cache()
    items = data.get(section, [])
    if filter_key and filter_val:
        items = [i for i in items if i.get(filter_key) == filter_val]
    return render_template("seo_page.html",
        title=title, description=desc, h1=h1, keywords=keywords,
        items=items, section=section)


@app.route("/og-image.png")
def og_image():
    """Generate OG share image for social media previews."""
    img_bytes = generate_og_image()
    return send_file(io.BytesIO(img_bytes), mimetype="image/png")


# ── Main ─────────────────────────────────────────────────────

if __name__ == "__main__":
    updater = threading.Thread(target=bg_updater, daemon=True)
    updater.start()
    print("[TrendPulse] Server starting at http://localhost:8766", flush=True)
    app.run(host="0.0.0.0", port=8766, debug=False)
