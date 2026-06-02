"""
Serenity Data Collector
Reads analysissite.vercel.app scraped data from JSON cache.
Stores full picks + tweets for TrendPulse frontend.
"""

import json, os, re
from pathlib import Path

DATA_FILE = Path(__file__).parent / "data" / "serenity_picks.json"


def _parse_analysis_sections(full_analysis: str) -> dict:
    """Split full_analysis into logical sections for rendering."""
    if not full_analysis:
        return {"summary": "", "context": "", "signals": ""}

    # Split on "历史信号提示" marker
    parts = full_analysis.split("历史信号提示：", 1)
    if len(parts) == 2:
        context = parts[0].strip().rstrip("。")
        signals = parts[1].strip()
        # First 100 chars as summary preview
        summary = context[:120] + ("…" if len(context) > 120 else "")
        return {"summary": summary, "context": context, "signals": signals}
    else:
        return {"summary": full_analysis[:120] + ("…" if len(full_analysis) > 120 else ""),
                "context": full_analysis.strip(),
                "signals": ""}


def get_serenity_raw() -> dict:
    """Read the full JSON dict from cache file."""
    if not DATA_FILE.exists():
        return {"picks": [], "new_tweets_since_snapshot": [], "snapshot_date": "", "last_checked": ""}
    try:
        with open(DATA_FILE) as f:
            data = json.load(f)
        if isinstance(data, list):
            # Legacy format — wrap
            return {"picks": data, "new_tweets_since_snapshot": [], "snapshot_date": "", "last_checked": ""}
        return data
    except Exception:
        return {"picks": [], "new_tweets_since_snapshot": [], "snapshot_date": "", "last_checked": ""}


def get_serenity_summary() -> dict:
    """Return enriched summary for TrendPulse /api/serenity."""
    raw = get_serenity_raw()
    picks_raw = raw.get("picks", [])
    tweets = raw.get("new_tweets_since_snapshot", [])

    enriched = []
    for p in picks_raw[:10]:
        sections = _parse_analysis_sections(p.get("full_analysis", ""))
        enriched.append({
            **p,
            **sections,  # adds: summary, context, signals
        })

    bullish = sum(1 for p in picks_raw if "看多" in p.get("view", ""))
    bearish = sum(1 for p in picks_raw if "看空" in p.get("view", ""))

    return {
        "updated_at": os.path.getmtime(str(DATA_FILE)) if DATA_FILE.exists() else 0,
        "snapshot_date": raw.get("snapshot_date", ""),
        "last_checked": raw.get("last_checked", ""),
        "total_stocks": 704,
        "hot_picks": enriched,
        "bullish_count": bullish,
        "bearish_count": bearish,
        "latest_tweets": tweets,
    }
