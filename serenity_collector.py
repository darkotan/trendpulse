"""
Serenity Data Collector
Scrapes analysissite.vercel.app for hot stock rankings.
Stores as JSON for TrendPulse frontend.
"""

import json, os, time
from pathlib import Path

DATA_FILE = Path(__file__).parent / "data" / "serenity_picks.json"


def get_serenity_data() -> list:
    """Read cached Serenity picks from JSON file."""
    if not DATA_FILE.exists():
        return []
    try:
        with open(DATA_FILE) as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def get_serenity_summary() -> dict:
    """Return summary of Serenity's latest view for TrendPulse API."""
    picks = get_serenity_data()
    return {
        "updated_at": os.path.getmtime(str(DATA_FILE)) if DATA_FILE.exists() else 0,
        "total_stocks": 704,
        "hot_picks": picks[:10],
        "bullish_count": sum(1 for p in picks if "看多" in p.get("view", "")),
        "bearish_count": sum(1 for p in picks if "看空" in p.get("view", "")),
    }
