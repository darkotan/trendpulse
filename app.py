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
from serenity_collector import get_serenity_raw, get_serenity_summary
from articles import get_articles, get_article
from company_info import get_company_info
import time, threading, io
from datetime import datetime
from pathlib import Path

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

# ── Language Detection ──────────────────────────────
def detect_lang(accept_lang: str = "") -> str:
    """Detect preferred language from Accept-Language header. Returns 'zh' or 'en'."""
    if not accept_lang:
        return "en"  # default to English when unknown
    al = accept_lang.lower()
    # Chinese browsers send zh-CN, zh-TW, zh-HK, zh
    if any(t in al for t in ("zh", "cmn", "yue")):
        return "zh"
    return "en"

# ── Analytics tracking ────────────────────────────
@app.before_request
def track_request():
    if request.path.startswith('/api/') or request.path.startswith('/static/'):
        return
    if request.path in ('/health', '/og-image.png', '/robots.txt', '/sitemap.xml', '/rss.xml', '/feed.json'):
        return
    raw_lang = request.headers.get('Accept-Language', '')
    parsed_lang = detect_lang(raw_lang)
    track_pageview(
        ip=request.headers.get('CF-Connecting-IP', request.remote_addr or ''),
        path=request.path,
        referrer=request.referrer or '',
        ua=request.headers.get('User-Agent', ''),
        lang=parsed_lang)  # store parsed: 'zh' or 'en'

# Inject language into all template contexts
@app.context_processor
def inject_lang():
    raw_lang = request.headers.get('Accept-Language', '') if request else ''
    return {'lang': detect_lang(raw_lang)}

# ── Core Routes ────────────────────────────────────
@app.route("/")
def index():
    """Serenity research homepage — server-rendered with full analysis."""
    from serenity_collector import get_serenity_summary
    serenity = get_serenity_summary()
    return render_template("serenity_home.html", serenity=serenity)


@app.route("/dashboard")
def dashboard():
    """Original data dashboard."""
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

    # Blog
    articles = get_articles()
    for art in articles:
        paths.append((f"/blog/{art['slug']}", "0.7"))
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


@app.route("/api/market-story")
def market_story():
    """Generate a one-paragraph narrative of what's happening today."""
    data = get_cache()
    stocks = data.get("stocks", [])
    crypto = data.get("crypto", [])
    hn = data.get("hn", [])


@app.route("/api/briefing")
def briefing():
    """Generate editorial context for each data card — the 'so what' layer."""
    data = get_cache()
    stocks = data.get("stocks", [])
    crypto = data.get("crypto", [])
    hn = data.get("hn", [])
    gh = data.get("github", [])

    result = {"stocks_narrative": "", "crypto_narrative": "", "hn_narrative": "", "github_narrative": ""}

    # Stocks: contextualize top movers
    if len(stocks) >= 3:
        up = [s for s in stocks if s["change_pct"] > 0]
        down = [s for s in stocks if s["change_pct"] < 0]
        parts = []
        if up:
            parts.append(f"{len(up)}/{len(stocks)} stocks rising.")
            top = up[0]
            parts.append(f"{top['symbol']} leads at +{top['change_pct']}%.")
        if down:
            parts.append(f"{len(down)} falling.")
        result["stocks_narrative"] = " ".join(parts)

    # Crypto: fear/greed + BTC context
    if crypto:
        btc = next((c for c in crypto if c["symbol"] == "BTC"), None)
        movers = sorted(crypto, key=lambda x: abs(x["change_pct"]), reverse=True)
        parts = []
        if btc:
            parts.append(f"BTC ${btc['price']:,.0f} ({btc['change_pct']:+.1f}%).")
        if movers:
            top_mover = movers[0]
            parts.append(f"Most active: {top_mover['symbol']} {top_mover['change_pct']:+.1f}%.")
        result["crypto_narrative"] = " ".join(parts)

    # HN: contextualize the front page
    if len(hn) >= 3:
        top = hn[0]
        rising = [s for s in hn[1:5] if s["comments"] > 50]
        parts = [f"'{top['title'][:50]}...' dominates ({top['score']} pts)."]
        if rising:
            parts.append(f"{len(rising)} active discussions with 50+ comments.")
        result["hn_narrative"] = " ".join(parts)

    # GitHub: trending context
    if len(gh) >= 3:
        parts = [f"Top: {gh[0]['name']} ({gh[0]['stars_fmt']} ⭐)."]
        languages = set(g["language"] for g in gh[:5] if g.get("language"))
        if languages:
            parts.append(f"Hot languages: {', '.join(list(languages)[:3])}.")
        result["github_narrative"] = " ".join(parts)

    return jsonify(result)
    stocks = data.get("stocks", [])
    crypto = data.get("crypto", [])
    hn = data.get("hn", [])

    if not stocks:
        return jsonify({"story": "Loading market data...", "highlights": []})

    up = [s for s in stocks if s["change_pct"] > 0]
    down = [s for s in stocks if s["change_pct"] < 0]
    top_up = up[0] if up else None
    top_down = down[0] if down else None
    btc = next((c for c in crypto if c["symbol"] == "BTC"), None)
    eth = next((c for c in crypto if c["symbol"] == "ETH"), None)

    # Build narrative
    parts = []
    highlights = []

    direction = "rallying" if len(up) > len(down) else "mixed" if len(up) == len(down) else "declining"
    parts.append(f"Markets are {direction} today with {len(up)}/{len(stocks)} tracked stocks in the green.")

    if top_up:
        parts.append(f"Top gainer: {top_up['symbol']} +{top_up['change_pct']}% (${top_up['price']}).")
        highlights.append({"symbol": top_up["symbol"], "change": f"+{top_up['change_pct']}%", "type": "gain"})
    if top_down:
        parts.append(f"Biggest drop: {top_down['symbol']} {top_down['change_pct']}%.")
        highlights.append({"symbol": top_down["symbol"], "change": f"{top_down['change_pct']}%", "type": "loss"})
    if btc:
        direction = "up" if btc["change_pct"] >= 0 else "down"
        parts.append(f"Bitcoin is {direction} {abs(btc['change_pct']):.1f}% at ${btc['price']:,.0f}.")
        highlights.append({"symbol": "BTC", "change": f"{btc['change_pct']:+.1f}%", "type": "crypto"})
    if hn:
        parts.append(f"On Hacker News, '{hn[0]['title'][:60]}' is trending with {hn[0]['score']} points.")

    story = " ".join(parts)
    return jsonify({"story": story, "highlights": highlights})


@app.route("/api/stock/<symbol>")
def stock_detail(symbol):
    """Get detail for one stock with referral links."""
    from data.collector import _get_yahoo_quote
    quote = _get_yahoo_quote(symbol.upper())
    if not quote:
        return jsonify({"error": "Not found"}), 404
    quote["binance_url"] = f"https://accounts.binance.com/en/register?ref=GRO_28502_3H9MX"
    return jsonify(quote)


@app.route("/api/subscribe", methods=["POST"])
def api_subscribe():
    """Save email subscription to file."""
    try:
        data = request.get_json(force=True)
        email = (data or {}).get("email", "").strip()
        if "@" not in email or "." not in email:
            return jsonify({"ok": False, "error": "Invalid email"}), 400
        sub_file = Path(__file__).parent / "data" / "subscribers.txt"
        with open(sub_file, "a") as f:
            f.write(f"{datetime.utcnow().isoformat()} {email}\n")
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/serenity")
def serenity_page():
    raw = get_serenity_raw()
    picks = raw.get("picks", [])
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
    company_name, sector, company_desc = get_company_info(symbol)
    pct = quote.get("change_pct", 0)
    d = "↑" if pct >= 0 else "↓"
    return render_template("stock_page.html",
        symbol=symbol, quote=quote, company_name=company_name, company_desc=company_desc,
        title=f"{symbol} Stock Price ${quote['price']:.2f} — {d}{abs(pct):.2f}% Today | TrendPulse",
        description=f"{symbol} ({company_name}) live stock price: ${quote['price']:.2f}. Change: {pct:+.2f}%. {company_desc[:100]}...")

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

# ── Blog / Articles ────────────────────────────────
@app.route("/blog")
def blog_index():
    articles = get_articles()
    desc = f"Market analysis & insights. {len(articles)} articles on AI, semiconductors, crypto, and more."
    return render_template("blog.html",
        title="Market Analysis & Insights — TrendPulse Blog",
        description=desc, articles=articles)
@app.route("/blog/<slug>")
def blog_article(slug: str):
    article = get_article(slug)
    if not article:
        return render_template("404.html"), 404
    return render_template("article.html",
        title=f"{article['title']} | TrendPulse",
        description=article.get("description", ""),
        article=article)


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


# ── Blog ────────────────────────────────────────────
@app.route("/blog")
def blog_list():
    articles = list_articles()
    return render_template("blog_list.html", articles=articles)


@app.route("/blog/<slug>")
def blog_post(slug):
    article = get_article(slug)
    if not article:
        return "Article not found", 404
    return render_template("blog_post.html", article=article)


@app.route("/performance")
def performance():
    return render_template("performance.html")


@app.route("/api/performance")
def api_performance():
    """Return historical performance data from JSON."""
    import json
    pf = Path(__file__).parent / "data" / "performance.json"
    if pf.exists():
        return jsonify(json.loads(pf.read_text()))
    return jsonify({"error": "No data yet"}), 404


# ── Main ───────────────────────────────────────────
if __name__ == "__main__":
    threading.Thread(target=bg_updater, daemon=True).start()
    print("[TrendPulse v2] Starting http://localhost:8766", flush=True)
    app.run(host="0.0.0.0", port=8766, debug=False)
