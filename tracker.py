#!/usr/bin/env python3
"""
P&L Tracker — 自动跟踪所有活跃推荐的实时价格，检查止损/止盈，记录价格历史。
每15分钟由cron调用，美股开盘时间运行。
"""
import sys
import os
import json
from datetime import datetime

# Add project to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from recommendations_db import get_active, update_price, close_recommendation, add_price_history, get_stats

SCRIPTS = os.path.expanduser("~/.hermes/skills/futu/futuapi/scripts/quote")

def extract_json(text):
    """Extract first JSON object from text."""
    for marker in ['{"funds"', '{"data"', '{"code"']:
        start = text.find(marker)
        if start >= 0:
            depth = 0
            for i, ch in enumerate(text[start:], start):
                if ch == '{': depth += 1
                elif ch == '}':
                    depth -= 1
                    if depth == 0:
                        try: return json.loads(text[start:i+1])
                        except: return None
    return None

def get_current_price(ticker):
    """Get current stock price from Futu API."""
    import subprocess
    try:
        r = subprocess.run(
            ['/usr/bin/python3', f'{SCRIPTS}/get_snapshot.py', f'US.{ticker}', '--json'],
            capture_output=True, text=True, timeout=15
        )
        d = extract_json(r.stdout + r.stderr)
        if d and 'data' in d and d['data']:
            return d['data'][0].get('last_price', 0) or d['data'][0].get('prev_close_price', 0)
    except Exception as e:
        print(f"[Tracker] Error getting {ticker}: {e}")
    return None

def get_option_price(option_code):
    """Get current option price from Futu API."""
    import subprocess
    try:
        r = subprocess.run(
            ['/usr/bin/python3', f'{SCRIPTS}/get_snapshot.py', option_code, '--json'],
            capture_output=True, text=True, timeout=15
        )
        d = extract_json(r.stdout + r.stderr)
        if d and 'data' in d and d['data']:
            row = d['data'][0]
            # Use last price, fallback to bid/ask midpoint
            last = row.get('last_price', 0)
            if last and last > 0:
                return last
            bid = row.get('bid_price', 0) or 0
            ask = row.get('ask_price', 0) or 0
            if bid > 0 and ask > 0:
                return round((bid + ask) / 2, 2)
            return bid or ask or 0
    except Exception as e:
        print(f"[Tracker] Error getting {option_code}: {e}")
    return None

def run():
    """Main tracking loop."""
    active = get_active()
    if not active:
        print("[Tracker] No active recommendations")
        return

    now = datetime.now().isoformat()
    updated = 0
    closed = 0
    errors = 0

    for rec in active:
        rec_id = rec['id']
        ticker = rec['ticker']
        option_code = rec['option_code']
        entry_price = rec['entry_price']
        stop_loss = rec.get('stop_loss', 0)
        target = rec.get('target', 0)

        # Get current option price
        current = get_option_price(option_code)
        if current is None or current <= 0:
            # Option might be expired or delisted - try stock price as fallback
            stock_price = get_current_price(ticker)
            if stock_price:
                print(f"[Tracker] {ticker} option {option_code} price unavailable, stock={stock_price}")
            errors += 1
            continue

        # Update price in DB
        update_price(rec_id, current)
        add_price_history(rec_id, current)
        updated += 1

        # Calculate P&L
        pnl_pct = ((current - entry_price) / entry_price * 100) if entry_price > 0 else 0

        # Check stop loss
        if stop_loss and current <= stop_loss:
            close_recommendation(rec_id, current, 'hit_stop')
            closed += 1
            print(f"[Tracker] 🔴 STOP LOSS {ticker} @ ${current:.2f} (entry ${entry_price:.2f}, P&L {pnl_pct:+.1f}%)")
            continue

        # Check target
        if target and current >= target:
            close_recommendation(rec_id, current, 'hit_target')
            closed += 1
            print(f"[Tracker] 🎯 TARGET HIT {ticker} @ ${current:.2f} (entry ${entry_price:.2f}, P&L {pnl_pct:+.1f}%)")
            continue

        # Check expiry
        if rec.get('expiry'):
            try:
                expiry = datetime.strptime(rec['expiry'], '%Y-%m-%d')
                if expiry.date() < datetime.now().date():
                    close_recommendation(rec_id, current, 'expired')
                    closed += 1
                    print(f"[Tracker] ⏰ EXPIRED {ticker} @ ${current:.2f} (P&L {pnl_pct:+.1f}%)")
                    continue
            except:
                pass

        # Status update
        emoji = "🟢" if pnl_pct > 0 else "🔴" if pnl_pct < 0 else "⚪"
        print(f"[Tracker] {emoji} {ticker} ${current:.2f} (entry ${entry_price:.2f}, P&L {pnl_pct:+.1f}%)")

    # Summary
    stats = get_stats()
    print(f"\n[Tracker] Done: {updated} updated, {closed} closed, {errors} errors")
    print(f"[Tracker] Stats: {stats.get('total',0)} total, {stats.get('win_rate',0):.0f}% win rate, avg P&L {stats.get('avg_pnl',0):+.1f}%")

if __name__ == '__main__':
    run()
