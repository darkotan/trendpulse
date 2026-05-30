# TrendPulse

**Real-time data dashboard — HN, stocks, crypto & GitHub trending in one page.**

🔗 **[trendscan.org](https://trendscan.org)**

![TrendPulse](https://img.shields.io/badge/status-live-green) ![Python](https://img.shields.io/badge/python-3.9%2B-blue) ![License](https://img.shields.io/badge/license-MIT-lightgrey)

## What it does

Aggregates four live data feeds into a single clean dashboard:

- **Hacker News** — top stories with scores and comments
- **Stock Market** — top movers from Yahoo Finance (AAPL, TSLA, NVDA, MSFT...)
- **Crypto** — live prices from Binance (BTC, ETH, SOL, DOGE...)
- **GitHub Trending** — most starred repositories

Updates every 5 minutes. No accounts, no ads, no signup.

## Tech Stack

- **Backend:** Python 3.9+, Flask
- **Frontend:** Vanilla HTML/CSS/JS, Geist font
- **Data:** `urllib` only — zero external dependencies
- **Design:** Vercel-inspired (shadow-as-border, mono typography)
- **Infra:** Cloudflare Tunnel + Cloudflare CDN
- **i18n:** Auto-detect browser language (EN/ZH)

## Run Locally

```bash
pip install flask
python3 app.py
# → http://localhost:8766
```

## SEO Pages

| Page | Keywords |
|------|----------|
| `/` | Main dashboard |
| `/bitcoin-price` | Bitcoin price, BTC USD |
| `/crypto-prices` | Crypto prices, cryptocurrency |
| `/stock-market-today` | Stock market today, market movers |
| `/trending-github` | Trending GitHub repos |
| `/tech-news` | Tech news, Hacker News |

## License

MIT — built with AI assistance.
