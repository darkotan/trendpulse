/**
 * TrendPulse i18n — Language Bundles
 * Add a new language by copying the "en" block below.
 * Keys are the English source string, values are translations.
 */

const I18N = {
  en: {
    // Header
    "Pulse on what matters.": "Pulse on what matters.",
    "Real-time data from Hacker News, stock markets, crypto, and GitHub — aggregated in one place.":
      "Real-time data from Hacker News, stock markets, crypto, and GitHub — aggregated in one place.",
    "Live": "Live",

    // Badges
    "🔗 Hacker News": "🔗 Hacker News",
    "📈 Stocks": "📈 Stocks",
    "₿ Crypto": "₿ Crypto",
    "💻 GitHub": "💻 GitHub",

    // Card headers
    "Hacker News": "Hacker News",
    "Market Movers": "Market Movers",
    "Crypto": "Crypto",
    "GitHub Trending": "GitHub Trending",

    // Labels
    "TOP": "TOP",
    "Trade": "Trade",
    "Loading": "Loading",

    // Newsletter
    "Get the daily digest": "Get the daily digest",
    "Top stories, market moves, and trending repos — delivered to your inbox every morning.":
      "Top stories, market moves, and trending repos — delivered to your inbox every morning.",
    "you@email.com": "you@email.com",
    "Subscribe": "Subscribe",
    "✓ Subscribed! Check your inbox.": "✓ Subscribed! Check your inbox.",

    // Ad cards
    "📈 Trade Stocks": "📈 Trade Stocks",
    "Commission-free trading. Sign up and get free stocks.":
      "Commission-free trading. Sign up and get free stocks.",
    "Affiliate · Webull / Robinhood / Tiger Brokers":
      "Affiliate · Webull / Robinhood / Tiger Brokers",
    "₿ Trade Crypto": "₿ Trade Crypto",
    "Lowest fees on Binance. Get 10% off trading fees.":
      "Lowest fees on Binance. Get 10% off trading fees.",
    "Affiliate · Binance / OKX / Bybit": "Affiliate · Binance / OKX / Bybit",

    // Footer
    "About": "About",
    "Privacy": "Privacy",
    "Contact": "Contact",
    "GitHub": "GitHub",
    "TrendPulse © 2026 · Real-time data aggregation · Not financial advice · Some links may contain affiliate referrals":
      "TrendPulse © 2026 · Real-time data aggregation · Not financial advice · Some links may contain affiliate referrals",
    "by": "by",

    // Volume
    "Vol:": "Vol:",

    // Error
    "⚠️ Failed to load data. Retrying...": "⚠️ Failed to load data. Retrying...",
  },

  zh: {
    // Header
    "Pulse on what matters.": "把握关键脉搏。",
    "Real-time data from Hacker News, stock markets, crypto, and GitHub — aggregated in one place.":
      "来自 Hacker News、股票市场、加密货币和 GitHub 的实时数据，一站聚合。",
    "Live": "实时",

    // Badges
    "🔗 Hacker News": "🔗 科技资讯",
    "📈 Stocks": "📈 股票行情",
    "₿ Crypto": "₿ 加密货币",
    "💻 GitHub": "💻 开源项目",

    // Card headers
    "Hacker News": "科技资讯",
    "Market Movers": "股票异动",
    "Crypto": "加密货币",
    "GitHub Trending": "热门仓库",

    // Labels
    "TOP": "热门",
    "Trade": "交易",
    "Loading": "加载中",

    // Newsletter
    "Get the daily digest": "订阅每日摘要",
    "Top stories, market moves, and trending repos — delivered to your inbox every morning.":
      "热门资讯、市场异动和趋势仓库，每天早上送达你的邮箱。",
    "you@email.com": "你的邮箱",
    "Subscribe": "订阅",
    "✓ Subscribed! Check your inbox.": "✓ 订阅成功！请查看邮箱。",

    // Ad cards
    "📈 Trade Stocks": "📈 交易股票",
    "Commission-free trading. Sign up and get free stocks.":
      "零佣金交易。开户即送免费股票。",
    "Affiliate · Webull / Robinhood / Tiger Brokers":
      "推广 · 微牛 / Robinhood / 老虎证券",
    "₿ Trade Crypto": "₿ 交易加密货币",
    "Lowest fees on Binance. Get 10% off trading fees.":
      "Binance 最低费率。立享9折手续费。",
    "Affiliate · Binance / OKX / Bybit": "推广 · Binance / OKX / Bybit",

    // Footer
    "About": "关于",
    "Privacy": "隐私政策",
    "Contact": "联系我们",
    "GitHub": "GitHub",
    "TrendPulse © 2026 · Real-time data aggregation · Not financial advice · Some links may contain affiliate referrals":
      "TrendPulse © 2026 · 实时数据聚合 · 非投资建议 · 部分链接含推广返佣",
    "by": "作者",

    // Volume
    "Vol:": "成交量:",

    // Error
    "⚠️ Failed to load data. Retrying...": "⚠️ 数据加载失败，正在重试...",
  },
};

/**
 * Get current language: browser preference, fallback to EN.
 * Language priority: zh > zh-CN > zh-TW > zh-HK → Chinese; everything else → English.
 */
function detectLang() {
  const lang = (navigator.language || "en").toLowerCase();
  if (lang.startsWith("zh")) return "zh";
  return "en";
}

function t(key, lang) {
  const bundle = I18N[lang] || I18N["en"];
  return bundle[key] || I18N["en"][key] || key;
}
