"""
TrendPulse — Real-time Data Aggregation Dashboard
===================================================
Multi-source data aggregation with Vercel-inspired design.
Monetization: Ads → Affiliate → Premium → API access.
"""

from flask import Flask, render_template, jsonify, request, make_response, send_file
from data.collector import (
    fetch_hn_trending, fetch_stock_movers, fetch_crypto_prices, fetch_github_trending,
)
from og_image import generate_og_image
from auto_promote import ping_all_services, ping_sitemap, SITE_URL, SITE_NAME, RSS_URL, SITEMAP_URL
import time, threading, io
from datetime import datetime

app = Flask(__name__)
_cache = {}
_cache_lock = threading.Lock()
_refresh_lock = threading.Lock()
CACHE_TTL = 300

def refresh_cache():
    global _cache
    if _refresh_lock.locked(): return
    with _refresh_lock:
        try:
            new = {"updated_at": int(time.time()), "hn": fetch_hn_trending(),
                   "stocks": fetch_stock_movers(), "crypto": fetch_crypto_prices(),
                   "github": fetch_github_trending()}
            with _cache_lock: _cache = new
        except Exception as e: print(f"[TrendPulse] Refresh error: {e}")

def get_cache():
    with _cache_lock:
        data = dict(_cache) if _cache else None
        stale = not _cache or (time.time() - _cache.get("updated_at", 0)) > CACHE_TTL
    if stale and not _refresh_lock.locked():
        threading.Thread(target=refresh_cache, daemon=True).start()
    return data or {"updated_at": 0, "hn": [], "stocks": [], "crypto": [], "github": []}

def bg_updater():
    last_ping = 0
    while True:
        try:
            refresh_cache()
            now = time.time()
            if now - last_ping > 3600:
                try: ping_all_services(SITE_URL, SITE_NAME, RSS_URL); ping_sitemap(SITEMAP_URL); last_ping = now
                except: pass
        except Exception as e: print(f"[TrendPulse] BG error: {e}")
        time.sleep(CACHE_TTL)

def public_url(): return "https://trendscan.org"

# ── Routes ────────────────────────────────────────
@app.route("/")
def index(): return render_template("index.html")

@app.route("/robots.txt")
def robots():
    txt = f"User-agent: *\nAllow: /\nSitemap: {public_url()}/sitemap.xml\n"
    return make_response(txt, {"Content-Type": "text/plain"})

@app.route("/sitemap.xml")
def sitemap():
    base, today = public_url(), datetime.utcnow().strftime("%Y-%m-%d")
    paths = ["/", "/bitcoin-price", "/crypto-prices", "/stock-market-today", "/trending-github", "/tech-news"]
    urls = "".join(f'  <url>\n    <loc>{base}{p}</loc>\n    <lastmod>{today}</lastmod>\n    <changefreq>hourly</changefreq>\n    <priority>{"1.0" if p=="/" else "0.8"}</priority>\n  </url>\n' for p in paths)
    return make_response(f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{urls}</urlset>', {"Content-Type": "application/xml"})

@app.route("/rss.xml")
def rss_feed():
    base, data, today = public_url(), get_cache(), datetime.utcnow().strftime("%a, %d %b %Y %H:%M:%S +0000")
    items = ""
    for item in data.get("hn", [])[:3]:
        items += f'    <item><title>{_esc(item.get("title",""))}</title><link>{_esc(item.get("url",base))}</link><description>Score: {item.get("score",0)} | Comments: {item.get("comments",0)}</description><pubDate>{today}</pubDate><guid>{base}/hn#{item.get("id")}</guid></item>\n'
    for item in data.get("stocks", [])[:3]:
        pct = item.get("change_pct", 0); d = "↑" if pct >= 0 else "↓"
        items += f'    <item><title>{item.get("symbol","")} {d}{abs(pct):.1f}% — ${item.get("price",0):.2f}</title><link>{base}/stock-market-today</link><description>Price: ${item.get("price",0):.2f} | Change: {pct:+.2f}%</description><pubDate>{today}</pubDate><guid>{base}/stocks#{item.get("symbol")}</guid></item>\n'
    xml = f'<?xml version="1.0" encoding="UTF-8"?>\n<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">\n  <channel>\n    <title>TrendPulse</title>\n    <link>{base}</link>\n    <description>Live market data & tech news</description>\n    <lastBuildDate>{today}</lastBuildDate>\n    <atom:link href="{base}/rss.xml" rel="self" type="application/rss+xml"/>\n{items}  </channel>\n</rss>'
    return make_response(xml, {"Content-Type": "application/xml; charset=utf-8"})

@app.route("/feed.json")
def json_feed():
    base, data = public_url(), get_cache()
    items = [{"id": f"{base}/hn#{i.get('id')}", "title": i.get("title",""), "url": i.get("url",base), "content_text": f"Score: {i.get('score',0)} | Comments: {i.get('comments',0)}", "date_published": i.get("time","")} for i in data.get("hn",[])[:5]]
    return jsonify({"version": "https://jsonfeed.org/version/1.1", "title": "TrendPulse", "home_page_url": base, "feed_url": f"{base}/feed.json", "description": "Live market data & tech news", "items": items})

def _esc(s): return (s or "").replace("&","&amp;").replace("<","&lt;").replace(">","&gt;").replace('"',"&quot;")

@app.route("/api/all")
def api_all(): return jsonify(get_cache())

@app.route("/api/hn")
def api_hn(): return jsonify(get_cache().get("hn",[]))
@app.route("/api/stocks")
def api_stocks(): return jsonify(get_cache().get("stocks",[]))
@app.route("/api/crypto")
def api_crypto(): return jsonify(get_cache().get("crypto",[]))
@app.route("/api/github")
def api_github(): return jsonify(get_cache().get("github",[]))

@app.route("/health")
def health(): return jsonify({"status":"ok","updated_at":get_cache().get("updated_at",0)})

@app.route("/og-image.png")
def og_image(): return send_file(io.BytesIO(generate_og_image()), mimetype="image/png")

# ── SEO Pages ──────────────────────────────────────
_PAGES = [
    ("/bitcoin-price", "Bitcoin (BTC) Price Today — Live USD Price | TrendPulse", "Live Bitcoin price. Real-time BTC price, 24h change, volume.", "Bitcoin Price Today", "bitcoin price, btc usd, bitcoin live", "crypto", "symbol", "BTC"),
    ("/crypto-prices", "Crypto Prices Today — BTC, ETH, SOL, DOGE | TrendPulse", "Live crypto prices: Bitcoin, Ethereum, Solana. Real-time 24h change.", "Crypto Prices Today", "crypto prices, btc eth sol, crypto tracker", "crypto", None, None),
    ("/stock-market-today", "Stock Market Today — Top Movers, Live Prices | TrendPulse", "Live stock movers: AAPL, TSLA, NVDA, MSFT. Real-time prices.", "Stock Market Today", "stock market today, stock movers, live stocks", "stocks", None, None),
    ("/trending-github", "Trending GitHub Repos Today — Top Open Source | TrendPulse", "Discover trending GitHub repos. Most starred open source projects.", "Trending on GitHub", "trending github, top repos, open source", "github", None, None),
    ("/tech-news", "Tech News Today — Hacker News Top Stories | TrendPulse", "Latest tech news from Hacker News. Top stories by votes.", "Today's Tech News", "tech news, hacker news, technology news", "hn", None, None),
]
for path, title, desc, h1, kw, sec, fk, fv in _PAGES:
    def _make_seo(p=path, t=title, d=desc, h=h1, k=kw, s=sec, fkk=fk, fvv=fv):
        def handler():
            items = get_cache().get(s, [])
            if fkk and fvv: items = [i for i in items if i.get(fkk) == fvv]
            return render_template("seo_page.html", title=t, description=d, h1=h, keywords=k, items=items, section=s)
        return handler
    app.add_url_rule(path, f"seo_{path.replace('/','_').replace('-','_')}", _make_seo())

# ── Main ───────────────────────────────────────────
if __name__ == "__main__":
    threading.Thread(target=bg_updater, daemon=True).start()
    print("[TrendPulse] Starting http://localhost:8766", flush=True)
    app.run(host="0.0.0.0", port=8766, debug=False)
