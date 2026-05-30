"""
TrendPulse Auto-Promotion Engine
=================================
All functions use public endpoints — zero accounts, zero API keys.
"""

import urllib.request
import urllib.parse
import xmlrpc.client
import time
import threading


# ═══════════════════════════════════════════════════════════════
# PING SERVICES — Notify search engines of new content
# ═══════════════════════════════════════════════════════════════

PING_SERVICES = [
    # RSS / Blog search engines
    "http://rpc.pingomatic.com/",
    "http://blogsearch.google.com/ping/RPC2",
    "http://rpc.weblogs.com/RPC2",
    "http://ping.feedburner.com/",
    "http://rpc.technorati.com/rpc/ping",
    "http://blogsearch.google.com.tw/ping/RPC2",
    "http://rpc.blogrolling.com/pinger/",
    "http://ping.blo.gs/",
    "http://ping.weblogalot.com/rpc.php",
    "http://ping.blogmura.jp/rpc/",
    "http://blog.goo.ne.jp/XMLRPC",
    # Aggregators
    "http://bulkfeeds.net/rpc",
    "http://www.feedshark.brainbliss.com/rpc",
    "http://www.newsisfree.com/RPCCloud",
    "http://www.syndic8.com/xmlrpc.php",
]

SITEMAP_PING_URLS = [
    "https://www.google.com/webmasters/sitemaps/ping?sitemap={sitemap}",
    "https://www.bing.com/webmaster/ping.aspx?siteMap={sitemap}",
    "https://search.yandex.com/ping?sitemap={sitemap}",
]


def ping_all_services(site_url: str, site_name: str, rss_url: str):
    """Ping all XML-RPC services about new content."""
    results = {"ok": 0, "fail": 0}
    for url in PING_SERVICES:
        try:
            server = xmlrpc.client.ServerProxy(url)
            server.weblogUpdates.ping(site_name, site_url)
            results["ok"] += 1
        except Exception:
            results["fail"] += 1
    return results


def ping_sitemap(sitemap_url: str):
    """Ping Google/Bing/Yandex with sitemap URL."""
    results = {"ok": 0, "fail": 0}
    for template in SITEMAP_PING_URLS:
        url = template.format(sitemap=urllib.parse.quote(sitemap_url, safe=''))
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "TrendPulse/1.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.status < 400:
                    results["ok"] += 1
                else:
                    results["fail"] += 1
        except Exception:
            results["fail"] += 1
    return results


# ═══════════════════════════════════════════════════════════════
# RSS DIRECTORY SUBMISSION — One-time bulk submission
# ═══════════════════════════════════════════════════════════════

RSS_DIRECTORIES = [
    # Format: (name, submission_url_template)
    # Many accept RSS URL as a query parameter
    ("Feedage", "https://www.feedage.com/submit/?feed={rss}"),
    ("Feedspot", "https://www.feedspot.com/fs/add_feed?url={rss}"),
    ("Blogarama", "https://www.blogarama.com/add-blog/?feed={rss}"),
    ("Bloglovin", "https://www.bloglovin.com/blogs/add?url={site}"),
    ("Blog Flux", "https://dir.blogflux.com/add/?feed={rss}"),
    ("RSS Network", "https://www.rss-network.com/submitrss.php?url={rss}"),
    ("Bloggapedia", "https://www.bloggapedia.com/add/?url={site}"),
    ("Ontoplist", "https://www.ontoplist.com/submit/?url={site}"),
    ("AllTop", "https://alltop.com/submit/?url={site}"),
    ("SpyNote", "https://www.spynote.net/add/?url={site}"),
    ("FeedFury", "https://www.feedfury.com/submit?url={rss}"),
    ("BlogDigger", "https://www.blogdigger.com/add?url={site}"),
    ("KMax Blog", "https://www.kmaxblog.com/submit?url={site}"),
    ("BlogsCola", "https://www.blogscola.com/submit?url={site}"),
    ("Globe of Blogs", "https://www.globeofblogs.com/submit?url={site}"),
]


def submit_to_directories(site_url: str, rss_url: str):
    """Submit site/RSS to directories via HTTP GET. Many use simple URL params."""
    results = []
    for name, template in RSS_DIRECTORIES:
        url = template.format(rss=urllib.parse.quote(rss_url, safe=''),
                             site=urllib.parse.quote(site_url, safe=''))
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "TrendPulse/1.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                results.append({"name": name, "status": resp.status, "ok": True})
        except Exception as e:
            results.append({"name": name, "status": str(e)[:60], "ok": False})
    return results


# ═══════════════════════════════════════════════════════════════
# BACKLINK BUILDER — Create mentions on platforms that allow it
# ═══════════════════════════════════════════════════════════════

BACKLINK_PLATFORMS = [
    # Stack Exchange-style profile (edit existing if you have one)
    # GitHub profile README (add link)
    # These are one-time manual but high SEO value
]


# ═══════════════════════════════════════════════════════════════
# AUTO-PROMOTE RUNNER — Call this periodically
# ═══════════════════════════════════════════════════════════════

SITE_URL = "https://trendscan.org"
SITE_NAME = "TrendPulse"
RSS_URL = SITE_URL + "/rss.xml"
SITEMAP_URL = SITE_URL + "/sitemap.xml"


def run_auto_promote():
    """Main entry point: ping all services, submit to directories."""
    print(f"[Promote] Starting auto-promotion for {SITE_URL}")
    t0 = time.time()

    # 1. Ping XML-RPC services
    print("[Promote] Pinging XML-RPC services...")
    pr = ping_all_services(SITE_URL, SITE_NAME, RSS_URL)
    print(f"[Promote]   XP-RPC: {pr['ok']}/{pr['ok']+pr['fail']} succeeded")

    # 2. Ping sitemap to search engines
    print("[Promote] Pinging sitemap to Google/Bing/Yandex...")
    sr = ping_sitemap(SITEMAP_URL)
    print(f"[Promote]   Sitemap: {sr['ok']}/{sr['ok']+sr['fail']} succeeded")

    # 3. Submit to RSS directories (first run only, skip after)
    # Uncomment for first run:
    # print("[Promote] Submitting to RSS directories...")
    # dr = submit_to_directories(SITE_URL, RSS_URL)
    # ok = sum(1 for d in dr if d['ok'])
    # print(f"[Promote]   Directories: {ok}/{len(dr)} succeeded")

    elapsed = time.time() - t0
    print(f"[Promote] Done in {elapsed:.1f}s")
    return {"pings": pr, "sitemap": sr}


# ═══════════════════════════════════════════════════════════════
# STANDALONE: Bulk directory submission (run once)
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    run_auto_promote()
