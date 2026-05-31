"""
TrendPulse v2 — Real-time Data Aggregation Dashboard
=====================================================
Multi-source: 50+ stocks, 20+ crypto, HN, Reddit, ProductHunt,
Fear & Greed, VIX, Treasury yields, GitHub trending.
Programmatic SEO pages for every asset.
"""

from flask import Flask, render_template, jsonify, request, make_response, send_file
from data.collector import (
    fetch_hn_trending, fetch_stock_movers, fetch_stocks_by_sector,
    fetch_crypto_prices, fetch_github_trending,
    fetch_reddit_trending, fetch_producthunt_trending,
    fetch_fear_greed, fetch_vix, fetch_treasury_yields,
    fetch_single_stock, fetch_single_crypto,
    STOCK_TICKERS, CRYPTO_SYMBOLS, ALL_TICKERS,
)
from og_image import generate_og_image
from auto_promote import ping_all_services, ping_sitemap, SITE_URL, SITE_NAME, RSS_URL, SITEMAP_URL
from analytics import track_pageview, track_ad_click, get_stats
from serenity_collector import get_serenity_data, get_serenity_summary
import time, threading, io
from datetime import datetime

app = Flask(__name__)
_cache = {}
_cache_lock = threading.Lock()
_refresh_lock = threading.Lock()
CACHE_TTL = 300

def refresh_cache():
    global _cache
    if _refresh_lock.locked():
        return
    with _refresh_lock:
        try:
            # Fetch stocks once, derive both views
            stocks_by_sector = fetch_stocks_by_sector()
            all_stocks = []
            for tickers in stocks_by_sector.values():
                all_stocks.extend(tickers)
            all_stocks.sort(key=lambda x: abs(x.get("change_pct", 0)), reverse=True)

            new = {
                "updated_at": int(time.time()),
                "hn": fetch_hn_trending(),
                "stocks": all_stocks[:15],
                "stocks_by_sector": stocks_by_sector,
                "crypto": fetch_crypto_prices(15),
                "github": fetch_github_trending(),
                "reddit": fetch_reddit_trending(),
                "producthunt": fetch_producthunt_trending(),
                "fear_greed": fetch_fear_greed(),
                "vix": fetch_vix(),
                "treasury": fetch_treasury_yields(),
            }
            with _cache_lock:
                _cache = new
        except Exception as e:
            print(f"[TrendPulse] Refresh error: {e}")

def get_cache():
    with _cache_lock:
        data = dict(_cache) if _cache else None
        stale = not _cache or (time.time() - _cache.get("updated_at", 0)) > CACHE_TTL
    if stale and not _refresh_lock.locked():
        threading.Thread(target=refresh_cache, daemon=True).start()
    return data or {
        "updated_at": 0,
        "hn": [], "stocks": [], "stocks_by_sector": {}, "crypto": [],
        "github": [], "reddit": [], "producthunt": [],
        "fear_greed": None, "vix": None, "treasury": [],
    }

def bg_updater():
    last_ping = 0
    while True:
        try:
            refresh_cache()
            now = time.time()
            if now - last_ping > 3600:
                try:
                    ping_all_services(SITE_URL, SITE_NAME, RSS_URL)
                    ping_sitemap(SITEMAP_URL)
                    last_ping = now
                except:
                    pass
        except Exception as e:
            print(f"[TrendPulse] BG error: {e}")
        time.sleep(CACHE_TTL)

def public_url():
    return "https://trendscan.org"

# ── Analytics tracking ────────────────────────────
@app.before_request
def track_request():
    if request.path.startswith('/api/') or request.path.startswith('/static/'):
        return
    if request.path in ('/health', '/og-image.png', '/robots.txt', '/sitemap.xml', '/rss.xml', '/feed.json'):
        return
    track_pageview(
        ip=request.headers.get('CF-Connecting-IP', request.remote_addr or ''),
        path=request.path,
        referrer=request.referrer or '',
        ua=request.headers.get('User-Agent', ''),
        lang=request.headers.get('Accept-Language', ''))

# ── Core Routes ────────────────────────────────────
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/robots.txt")
def robots():
    # Dynamic robots.txt with all SEO page paths
    base = public_url()
    lines = ["User-agent: *", "Allow: /", f"Sitemap: {base}/sitemap.xml", ""]
    # Disallow API/Analytics from crawling
    lines.append("Disallow: /api/")
    lines.append("Disallow: /analytics")
    return make_response("\n".join(lines), {"Content-Type": "text/plain"})

@app.route("/sitemap.xml")
def sitemap():
    base = public_url()
    today = datetime.utcnow().strftime("%Y-%m-%d")

    # Core pages
    paths = [
        ("/", "1.0"),
        ("/about", "0.8"), ("/privacy", "0.5"), ("/contact", "0.5"),
        ("/stocks", "0.9"), ("/crypto", "0.9"),
        ("/crypto-prices", "0.9"), ("/stock-market-today", "0.9"),
        ("/trending-github", "0.8"), ("/tech-news", "0.8"),
        ("/market-sentiment", "0.9"), ("/reddit-trending", "0.8"),
    ]

    # Stock pages
    for ticker in ALL_TICKERS:
        paths.append((f"/stock/{ticker}", "0.8"))

    # Crypto pages
    for coin in CRYPTO_SYMBOLS:
        paths.append((f"/crypto/{coin}", "0.8"))

    urls = "".join(
        f'  <url>\n    <loc>{base}{p}</loc>\n    <lastmod>{today}</lastmod>\n    <changefreq>hourly</changefreq>\n    <priority>{pr}</priority>\n  </url>\n'
        for p, pr in paths
    )
    return make_response(
        f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{urls}</urlset>',
        {"Content-Type": "application/xml"},
    )

@app.route("/rss.xml")
def rss_feed():
    base, data = public_url(), get_cache()
    today = datetime.utcnow().strftime("%a, %d %b %Y %H:%M:%S +0000")
    items = ""
    # HN stories
    for item in data.get("hn", [])[:3]:
        items += f'    <item><title>{_esc(item.get("title",""))}</title><link>{_esc(item.get("url",base))}</link><description>Score: {item.get("score",0)} | Comments: {item.get("comments",0)}</description><pubDate>{today}</pubDate><guid>{base}/hn#{item.get("id")}</guid></item>\n'
    # Top stocks
    for item in data.get("stocks", [])[:5]:
        pct = item.get("change_pct", 0)
        d = "↑" if pct >= 0 else "↓"
        items += f'    <item><title>{item.get("symbol","")} {d}{abs(pct):.1f}% — ${item.get("price",0):.2f}</title><link>{base}/stock/{item.get("symbol")}</link><description>Price: ${item.get("price",0):.2f} | Change: {pct:+.2f}%</description><pubDate>{today}</pubDate><guid>{base}/stock/{item.get("symbol")}</guid></item>\n'
    xml = f'<?xml version="1.0" encoding="UTF-8"?>\n<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">\n  <channel>\n    <title>TrendPulse — Live Market Data & Tech News</title>\n    <link>{base}</link>\n    <description>Real-time stocks, crypto, HN, Reddit, ProductHunt, and market sentiment.</description>\n    <lastBuildDate>{today}</lastBuildDate>\n    <atom:link href="{base}/rss.xml" rel="self" type="application/rss+xml"/>\n{items}  </channel>\n</rss>'
    return make_response(xml, {"Content-Type": "application/xml; charset=utf-8"})

# ── API Routes ─────────────────────────────────────
@app.route("/api/all")
def api_all():
    return jsonify(get_cache())

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
@app.route("/api/reddit")
def api_reddit():
    return jsonify(get_cache().get("reddit", []))
@app.route("/api/producthunt")
def api_producthunt():
    return jsonify(get_cache().get("producthunt", []))
@app.route("/api/sentiment")
def api_sentiment():
    data = get_cache()
    return jsonify({"fear_greed": data.get("fear_greed"), "vix": data.get("vix"), "treasury": data.get("treasury")})

@app.route("/health")
def health():
    return jsonify({"status": "ok", "updated_at": get_cache().get("updated_at", 0)})

@app.route("/og-image.png")
def og_image():
    return send_file(io.BytesIO(generate_og_image()), mimetype="image/png")

@app.route("/api/track-click")
def track_click():
    ad_type = request.args.get('type', 'unknown')
    target = request.args.get('url', '')
    track_ad_click(
        ip=request.headers.get('CF-Connecting-IP', request.remote_addr or ''),
        ad_type=ad_type, target_url=target)
    return jsonify({"ok": True})

@app.route("/api/wechat-digest")
def wechat_digest():
    data = get_cache()
    lines = ["📊 TrendPulse 市场摘要", ""]

    # Market sentiment
    fg = data.get("fear_greed")
    if fg:
        emoji = {"Extreme Fear": "😱", "Fear": "😨", "Neutral": "😐", "Greed": "😊", "Extreme Greed": "🤑"}.get(fg.get("sentiment", ""), "❓")
        lines.append(f"{emoji} 恐惧贪婪: {fg['score']} — {fg['sentiment']}")

    vix = data.get("vix")
    if vix:
        lines.append(f"📊 VIX: {vix['price']:.1f} ({vix['change_pct']:+.1f}%)")

    # Top stock movers
    stocks = data.get("stocks", [])[:3]
    for s in stocks:
        d = "📈" if s.get("change_pct", 0) >= 0 else "📉"
        lines.append(f"{d} {s['symbol']}: ${s['price']:.2f} ({s['change_pct']:+.2f}%)")

    # BTC
    crypto = data.get("crypto", [])
    btc = next((c for c in crypto if c["symbol"] == "BTC"), None)
    if btc:
        lines.append(f"₿ BTC: ${btc['price']:,.0f} ({btc['change_pct']:+.1f}%)")

    # Top HN
    hn = data.get("hn", [])
    if hn:
        lines.append(f"🔗 HN: {hn[0]['title'][:60]}")

    # Top Reddit
    reddit = data.get("reddit", [])
    if reddit:
        lines.append(f"💬 r/{reddit[0]['subreddit']}: {reddit[0]['title'][:60]}")

    lines.append(f"\n→ trendscan.org")
    return jsonify({"message": "\n".join(lines)})

# ── Newsletter ──────────────────────────────────────
@app.route("/api/subscribe", methods=["POST"])
def subscribe():
    email = (request.json or {}).get("email", "").strip() if request.is_json else ""
    if not email or "@" not in email:
        return jsonify({"ok": False, "error": "Invalid email"}), 400
    from analytics import add_subscriber
    ok = add_subscriber(email)
    return jsonify({"ok": ok})

@app.route("/api/subscribers/count")
def subscriber_count():
    from analytics import get_subscriber_count
    return jsonify({"count": get_subscriber_count()})

# ── Analytics Dashboard ────────────────────────────
@app.route("/analytics")
def analytics_dashboard():
    pw = request.args.get('pw', '')
    if pw != 'trendscan2026':
        return "<h2>Access denied</h2><p>Add ?pw=trendscan2026 to the URL</p>", 403
    data = get_cache()
    stats = get_stats(7)
    return render_template("analytics.html", stats=stats, cache=data)

@app.route("/api/stats")
def api_stats():
    return jsonify(get_stats(7))


@app.route("/api/serenity")
def api_serenity():
    return jsonify(get_serenity_summary())


@app.route("/serenity")
def serenity_page():
    picks = get_serenity_data()
    return render_template("serenity.html", picks=picks)

# ── Static Info Pages ──────────────────────────────
@app.route("/about")
def about():
    return render_template("static_page.html", title="About TrendPulse", content="""<h1>About TrendPulse</h1>
<p>TrendPulse is a real-time data aggregation dashboard tracking 50+ stocks, 20+ cryptocurrencies, Hacker News, Reddit, ProductHunt, and market sentiment indicators — all in one place.</p>
<p>Built with Python Flask. All data from public APIs — zero API keys required. Open source on <a href="https://github.com/darkotan/trendpulse">GitHub</a>.</p>""")

@app.route("/privacy")
def privacy():
    return render_template("static_page.html", title="Privacy Policy", content="""<h1>Privacy Policy</h1>
<p>TrendPulse does not collect, store, or share personal data. No cookies, no user accounts.</p>
<p>All data from public APIs. Affiliate links are clearly marked.</p>""")

@app.route("/contact")
def contact():
    return render_template("static_page.html", title="Contact", content="""<h1>Contact</h1>
<p>GitHub: <a href="https://github.com/darkotan/trendpulse">darkotan/trendpulse</a></p>
<p>Email: darkotan@hotmail.com</p>""")

# ── Section Landing Pages ──────────────────────────
@app.route("/stocks")
def stocks_landing():
    data = get_cache()
    return render_template("stocks_landing.html",
        title="Stock Market Today — 50+ Stocks Live | TrendPulse",
        description="Live stock prices for 50+ tickers. Tech, finance, ETFs, meme stocks. Real-time quotes.",
        sectors=data.get("stocks_by_sector", {}))

@app.route("/crypto")
def crypto_landing():
    data = get_cache()
    return render_template("crypto_landing.html",
        title="Crypto Prices Today — BTC, ETH, SOL & 20+ Coins | TrendPulse",
        description="Live cryptocurrency prices for 20+ coins. Real-time from Binance.",
        coins=data.get("crypto", []))

@app.route("/market-sentiment")
def sentiment_page():
    data = get_cache()
    return render_template("sentiment.html",
        title="Market Sentiment — Fear & Greed Index, VIX, Yields | TrendPulse",
        description="CNN Fear & Greed Index, VIX volatility, US Treasury yields. Real-time market sentiment indicators.",
        fg=data.get("fear_greed"), vix=data.get("vix"), treasury=data.get("treasury"))

@app.route("/reddit-trending")
def reddit_page():
    data = get_cache()
    return render_template("reddit.html",
        title="Reddit Trending — r/WallStreetBets, Stocks, Crypto | TrendPulse",
        description="Hot posts from r/wallstreetbets, r/stocks, r/CryptoCurrency, r/investing.",
        posts=data.get("reddit", []))

# ── Individual Stock Pages (Programmatic SEO) ──────
@app.route("/stock/<symbol>")
def stock_page(symbol: str):
    symbol = symbol.upper()
    quote = fetch_single_stock(symbol)
    if not quote:
        return render_template("stock_page.html", symbol=symbol, quote=None,
            title=f"{symbol} Stock Price Today — Live Quote | TrendPulse",
            description=f"{symbol} stock price unavailable. Check back for live data.")
    pct = quote.get("change_pct", 0)
    d = "↑" if pct >= 0 else "↓"
    return render_template("stock_page.html",
        symbol=symbol, quote=quote,
        title=f"{symbol} Stock Price ${quote['price']:.2f} — {d}{abs(pct):.2f}% Today | TrendPulse",
        description=f"{symbol} live stock price: ${quote['price']:.2f}. Change: {pct:+.2f}%. High ${quote['high']:.2f}, Low ${quote['low']:.2f}. Real-time from Yahoo Finance.")

# ── Individual Crypto Pages (Programmatic SEO) ─────
@app.route("/crypto/<symbol>")
def crypto_page(symbol: str):
    symbol = symbol.upper()
    coin = fetch_single_crypto(symbol)
    if not coin:
        return render_template("crypto_page.html", symbol=symbol, coin=None,
            title=f"{symbol} Price Today — Live USD | TrendPulse",
            description=f"{symbol} price unavailable. Check back for live data.")
    pct = coin.get("change_pct", 0)
    d = "↑" if pct >= 0 else "↓"
    return render_template("crypto_page.html",
        symbol=symbol, coin=coin,
        title=f"{symbol} Price ${coin['price']:,.2f} — {d}{abs(pct):.2f}% Today | TrendPulse",
        description=f"{symbol} live crypto price: ${coin['price']:,.2f}. 24h change: {pct:+.2f}%. Volume: {coin.get('volume_fmt','')}. Real-time from Binance.")

# ── Legacy SEO Pages ───────────────────────────────
_PAGES = [
    ("/bitcoin-price", "Bitcoin (BTC) Price Today — Live USD | TrendPulse",
     "Live Bitcoin price. Real-time BTC price, 24h change.",
     "Bitcoin Price Today", "bitcoin price, btc usd, bitcoin live",
     "crypto", "symbol", "BTC"),
    ("/crypto-prices", "Crypto Prices Today — BTC, ETH, SOL | TrendPulse",
     "Live crypto prices: BTC, ETH, SOL, DOGE. 24h change.",
     "Crypto Prices Today", "crypto prices, btc eth sol, crypto tracker",
     "crypto", None, None),
    ("/stock-market-today", "Stock Market Today — Top Movers Live | TrendPulse",
     "Live stock movers: AAPL, TSLA, NVDA, MSFT, 50+ tickers.",
     "Stock Market Today", "stock market today, stock movers",
     "stocks", None, None),
    ("/trending-github", "Trending GitHub Repos Today | TrendPulse",
     "Discover trending GitHub repos. Most starred projects today.",
     "Trending on GitHub", "trending github, top repos, open source",
     "github", None, None),
    ("/tech-news", "Tech News Today — Hacker News Top Stories | TrendPulse",
     "Latest tech news from Hacker News. Top stories today.",
     "Today's Tech News", "tech news, hacker news, technology news",
     "hn", None, None),
    ("/cathie-wood-arkk", "Cathie Wood ARKK ETF — Latest Price & News | TrendPulse",
     "Cathie Wood's ARK Innovation ETF. Live price, top holdings.",
     "Cathie Wood & ARKK ETF", "cathie wood, arkk etf, ark invest",
     "stocks", None, None),
]
for path, title, desc, h1, kw, sec, fk, fv in _PAGES:
    def _make_seo(p=path, t=title, d=desc, h=h1, k=kw, s=sec, fkk=fk, fvv=fv):
        def handler():
            items = get_cache().get(s, [])
            if fkk and fvv:
                items = [i for i in items if i.get(fkk) == fvv]
            return render_template("seo_page.html", title=t, description=d, h1=h, keywords=k, items=items, section=s)
        return handler
    app.add_url_rule(path, f"seo_{path.replace('/','_').replace('-','_')}", _make_seo())

# ── Utility ────────────────────────────────────────
def _esc(s):
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")

# ── Main ───────────────────────────────────────────
if __name__ == "__main__":
    threading.Thread(target=bg_updater, daemon=True).start()
    print("[TrendPulse v2] Starting http://localhost:8766", flush=True)
    app.run(host="0.0.0.0", port=8766, debug=False)
