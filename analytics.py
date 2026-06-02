"""
TrendPulse Analytics — Privacy-friendly, no cookies, no third-party.
Tracks page views and ad clicks using hashed IPs (anonymous).
"""

import sqlite3
import hashlib
import os
import threading
from datetime import datetime, date
from pathlib import Path

DB_PATH = Path(__file__).parent / "data" / "analytics.db"
_lock = threading.Lock()


def _db():
    """Get DB connection (auto-creates tables)."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""CREATE TABLE IF NOT EXISTS pageviews (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ip_hash TEXT, path TEXT, referrer TEXT, user_agent TEXT,
        lang TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS ad_clicks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ip_hash TEXT, ad_type TEXT, target_url TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_pv_date ON pageviews(created_at)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_ac_date ON ad_clicks(created_at)")
    return conn


def track_pageview(ip: str, path: str, referrer: str = "", ua: str = "", lang: str = ""):
    """Record a page view (runs in background thread)."""
    def _track():
        with _lock:
            try:
                conn = _db()
                ip_hash = hashlib.sha256((ip or "unknown").encode()).hexdigest()[:16]
                conn.execute(
                    "INSERT INTO pageviews (ip_hash, path, referrer, user_agent, lang) VALUES (?,?,?,?,?)",
                    (ip_hash, path, referrer or "", (ua or "")[:200], lang or ""))
                conn.commit()
                conn.close()
            except Exception as e:
                print(f"[Analytics] Error: {e}")
    threading.Thread(target=_track, daemon=True).start()


def track_ad_click(ip: str, ad_type: str, target_url: str = ""):
    """Record an ad/affiliate click."""
    def _track():
        with _lock:
            try:
                conn = _db()
                ip_hash = hashlib.sha256((ip or "unknown").encode()).hexdigest()[:16]
                conn.execute(
                    "INSERT INTO ad_clicks (ip_hash, ad_type, target_url) VALUES (?,?,?)",
                    (ip_hash, ad_type, target_url or ""))
                conn.commit()
                conn.close()
            except Exception as e:
                print(f"[Analytics] Error: {e}")
    threading.Thread(target=_track, daemon=True).start()


# ── Newsletter subscribers ─────────────────────────

def add_subscriber(email: str) -> bool:
    """Store email subscription. Returns True if new, False if duplicate."""
    with _lock:
        try:
            conn = _db()
            conn.execute("""CREATE TABLE IF NOT EXISTS subscribers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )""")
            conn.execute("INSERT OR IGNORE INTO subscribers (email) VALUES (?)", (email,))
            rows = conn.total_changes
            conn.commit()
            conn.close()
            return rows > 0
        except Exception as e:
            print(f"[Analytics] Subscriber error: {e}")
            return False


def get_subscriber_count() -> int:
    """Return total subscriber count."""
    with _lock:
        try:
            conn = _db()
            conn.execute("""CREATE TABLE IF NOT EXISTS subscribers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )""")
            count = conn.execute("SELECT COUNT(*) FROM subscribers").fetchone()[0]
            conn.close()
            return count
        except Exception:
            return 0


def get_subscribers() -> list:
    """Return list of subscriber emails."""
    with _lock:
        try:
            conn = _db()
            rows = conn.execute("SELECT email FROM subscribers ORDER BY created_at").fetchall()
            conn.close()
            return [r[0] for r in rows]
        except Exception:
            return []


def get_stats(days: int = 7) -> dict:
    """Return analytics summary for the last N days."""
    with _lock:
        conn = _db()
        since = f"datetime('now', '-{days} days')"

        # Total page views
        pv_total = conn.execute(
            f"SELECT COUNT(*) FROM pageviews WHERE created_at >= {since}").fetchone()[0]

        # Unique visitors (by IP hash)
        uv_total = conn.execute(
            f"SELECT COUNT(DISTINCT ip_hash) FROM pageviews WHERE created_at >= {since}").fetchone()[0]

        # Today's views
        today_views = conn.execute(
            "SELECT COUNT(*) FROM pageviews WHERE date(created_at) = date('now')").fetchone()[0]

        # Today's unique
        today_unique = conn.execute(
            "SELECT COUNT(DISTINCT ip_hash) FROM pageviews WHERE date(created_at) = date('now')").fetchone()[0]

        # Total ad clicks
        clicks = conn.execute(
            f"SELECT COUNT(*) FROM ad_clicks WHERE created_at >= {since}").fetchone()[0]

        # Daily breakdown
        daily = conn.execute(f"""
            SELECT date(created_at), COUNT(*) as pv, COUNT(DISTINCT ip_hash) as uv
            FROM pageviews WHERE created_at >= {since}
            GROUP BY date(created_at) ORDER BY date(created_at) DESC
        """).fetchall()

        # Top referrers
        referrers = conn.execute(f"""
            SELECT referrer, COUNT(*) as cnt FROM pageviews
            WHERE created_at >= {since} AND referrer != ''
            GROUP BY referrer ORDER BY cnt DESC LIMIT 10
        """).fetchall()

        # Top paths
        paths = conn.execute(f"""
            SELECT path, COUNT(*) as cnt FROM pageviews
            WHERE created_at >= {since}
            GROUP BY path ORDER BY cnt DESC LIMIT 10
        """).fetchall()

        # Language breakdown
        lang_rows = conn.execute(f"""
            SELECT lang, COUNT(*) as cnt, COUNT(DISTINCT ip_hash) as uv
            FROM pageviews WHERE created_at >= {since} AND lang != ''
            GROUP BY lang ORDER BY cnt DESC
        """).fetchall()

        conn.close()

        return {
            "period_days": days,
            "pageviews_total": pv_total,
            "visitors_unique": uv_total,
            "today_views": today_views,
            "today_unique": today_unique,
            "ad_clicks": clicks,
            "daily_breakdown": [{"date": d[0], "views": d[1], "visitors": d[2]} for d in daily],
            "top_referrers": [{"source": r[0] or "direct", "count": r[1]} for r in referrers],
            "top_pages": [{"path": p[0], "count": p[1]} for p in paths],
            "languages": [{"lang": l[0], "count": l[1], "unique": l[2]} for l in lang_rows],
        }
