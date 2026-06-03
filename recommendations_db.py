"""
Recommendations Database Module for TrendPulse Options Scanner

Manages a SQLite database for storing and tracking options recommendations,
price history, and subscriber information.
"""

import sqlite3
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

DB_PATH = Path(__file__).parent / "data" / "recommendations.db"

# Thread lock for database operations
_db_lock = threading.Lock()


def _get_connection() -> sqlite3.Connection:
    """Get a database connection with row factory enabled."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    """Create tables if they don't exist."""
    with _db_lock:
        conn = _get_connection()
        try:
            cursor = conn.cursor()

            # Main recommendations table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS recommendations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticker TEXT NOT NULL,
                    option_code TEXT NOT NULL,
                    direction TEXT NOT NULL CHECK(direction IN ('call', 'put', 'straddle')),
                    entry_price REAL NOT NULL,
                    total_cost REAL NOT NULL,
                    strike REAL NOT NULL,
                    expiry TEXT NOT NULL,
                    dte INTEGER NOT NULL,
                    otm_pct REAL,
                    stop_loss REAL,
                    target REAL,
                    current_price REAL DEFAULT 0,
                    pnl_pct REAL DEFAULT 0,
                    status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active', 'hit_target', 'hit_stop', 'expired', 'closed')),
                    logic TEXT,
                    dark_pool TEXT DEFAULT 'no' CHECK(dark_pool IN ('yes', 'no')),
                    risk_note TEXT,
                    scan_time TEXT NOT NULL,
                    close_time TEXT,
                    close_price REAL,
                    close_reason TEXT,
                    max_gain_pct REAL DEFAULT 0,
                    max_loss_pct REAL DEFAULT 0
                )
            """)

            # Price history table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS price_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    recommendation_id INTEGER NOT NULL,
                    price REAL NOT NULL,
                    timestamp TEXT NOT NULL,
                    FOREIGN KEY (recommendation_id) REFERENCES recommendations(id) ON DELETE CASCADE
                )
            """)

            # Subscribers table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS subscribers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email TEXT UNIQUE NOT NULL,
                    stripe_id TEXT,
                    plan TEXT NOT NULL DEFAULT 'free_trial' CHECK(plan IN ('free_trial', 'monthly', 'yearly')),
                    trial_end TEXT,
                    subscription_end TEXT,
                    created_at TEXT NOT NULL
                )
            """)

            # Create indices for faster queries
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_recommendations_status 
                ON recommendations(status)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_recommendations_ticker 
                ON recommendations(ticker)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_price_history_rec_id 
                ON price_history(recommendation_id)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_subscribers_email 
                ON subscribers(email)
            """)

            conn.commit()
        finally:
            conn.close()


def add_recommendation(data: Dict) -> int:
    """
    Add a new recommendation to the database.
    
    Args:
        data: Dictionary with recommendation details. Required fields:
            - ticker, option_code, direction, entry_price, strike, expiry, dte
        Optional fields:
            - otm_pct, stop_loss, target, logic, dark_pool, risk_note
    
    Returns:
        The ID of the newly created recommendation.
    """
    with _db_lock:
        conn = _get_connection()
        try:
            cursor = conn.cursor()
            
            # Calculate total cost
            entry_price = data.get('entry_price', 0)
            total_cost = entry_price * 100
            
            # Set scan_time if not provided
            scan_time = data.get('scan_time', datetime.utcnow().isoformat())
            
            cursor.execute("""
                INSERT INTO recommendations (
                    ticker, option_code, direction, entry_price, total_cost,
                    strike, expiry, dte, otm_pct, stop_loss, target,
                    logic, dark_pool, risk_note, scan_time
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                data['ticker'],
                data['option_code'],
                data['direction'],
                entry_price,
                total_cost,
                data['strike'],
                data['expiry'],
                data['dte'],
                data.get('otm_pct'),
                data.get('stop_loss'),
                data.get('target'),
                data.get('logic'),
                data.get('dark_pool', 'no'),
                data.get('risk_note'),
                scan_time
            ))
            
            conn.commit()
            return cursor.lastrowid
        finally:
            conn.close()


def update_price(rec_id: int, price: float) -> None:
    """
    Update the current price of a recommendation and calculate P&L.
    
    Args:
        rec_id: The recommendation ID.
        price: The current option price.
    """
    with _db_lock:
        conn = _get_connection()
        try:
            cursor = conn.cursor()
            
            # Get entry price
            cursor.execute(
                "SELECT entry_price, max_gain_pct, max_loss_pct, status FROM recommendations WHERE id = ?",
                (rec_id,)
            )
            row = cursor.fetchone()
            if not row:
                return
            
            entry_price = row['entry_price']
            current_status = row['status']
            
            # Don't update closed/reached targets
            if current_status != 'active':
                return
            
            # Calculate P&L percentage
            pnl_pct = ((price - entry_price) / entry_price) * 100 if entry_price > 0 else 0
            
            # Track max gain/loss
            max_gain_pct = row['max_gain_pct'] or 0
            max_loss_pct = row['max_loss_pct'] or 0
            
            if pnl_pct > max_gain_pct:
                max_gain_pct = pnl_pct
            if pnl_pct < max_loss_pct:
                max_loss_pct = pnl_pct
            
            # Update the recommendation
            cursor.execute("""
                UPDATE recommendations 
                SET current_price = ?, pnl_pct = ?, max_gain_pct = ?, max_loss_pct = ?
                WHERE id = ?
            """, (price, pnl_pct, max_gain_pct, max_loss_pct, rec_id))
            
            # Add to price history
            cursor.execute("""
                INSERT INTO price_history (recommendation_id, price, timestamp)
                VALUES (?, ?, ?)
            """, (rec_id, price, datetime.utcnow().isoformat()))
            
            conn.commit()
        finally:
            conn.close()


def get_active() -> List[Dict]:
    """
    Get all active recommendations.
    
    Returns:
        List of dictionaries with active recommendations.
    """
    with _db_lock:
        conn = _get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM recommendations WHERE status = 'active' ORDER BY scan_time DESC"
            )
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()


def get_all(limit: int = 100) -> List[Dict]:
    """
    Get all recommendations with optional limit.
    
    Args:
        limit: Maximum number of recommendations to return.
    
    Returns:
        List of dictionaries with recommendations.
    """
    with _db_lock:
        conn = _get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM recommendations ORDER BY scan_time DESC LIMIT ?",
                (limit,)
            )
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()


def get_stats() -> Dict:
    """
    Get statistics about recommendations.
    
    Returns:
        Dictionary with total, win_rate, avg_pnl, total_pnl, best, worst.
    """
    with _db_lock:
        conn = _get_connection()
        try:
            cursor = conn.cursor()
            
            # Total recommendations
            cursor.execute("SELECT COUNT(*) as total FROM recommendations")
            total = cursor.fetchone()['total']
            
            # Closed recommendations (hit_target, hit_stop, expired, closed)
            cursor.execute("""
                SELECT COUNT(*) as closed_count 
                FROM recommendations 
                WHERE status IN ('hit_target', 'hit_stop', 'expired', 'closed')
            """)
            closed_count = cursor.fetchone()['closed_count']
            
            # Win rate (hit_target / total closed)
            cursor.execute("""
                SELECT COUNT(*) as wins 
                FROM recommendations 
                WHERE status = 'hit_target'
            """)
            wins = cursor.fetchone()['wins']
            win_rate = (wins / closed_count * 100) if closed_count > 0 else 0
            
            # Average P&L (for closed recommendations)
            cursor.execute("""
                SELECT AVG(pnl_pct) as avg_pnl, SUM(pnl_pct) as total_pnl
                FROM recommendations 
                WHERE status IN ('hit_target', 'hit_stop', 'expired', 'closed')
            """)
            pnl_row = cursor.fetchone()
            avg_pnl = pnl_row['avg_pnl'] or 0
            total_pnl = pnl_row['total_pnl'] or 0
            
            # Best performer
            cursor.execute("""
                SELECT ticker, pnl_pct FROM recommendations 
                WHERE status IN ('hit_target', 'hit_stop', 'expired', 'closed')
                ORDER BY pnl_pct DESC LIMIT 1
            """)
            best_row = cursor.fetchone()
            best = {'ticker': best_row['ticker'], 'pnl_pct': best_row['pnl_pct']} if best_row else None
            
            # Worst performer
            cursor.execute("""
                SELECT ticker, pnl_pct FROM recommendations 
                WHERE status IN ('hit_target', 'hit_stop', 'expired', 'closed')
                ORDER BY pnl_pct ASC LIMIT 1
            """)
            worst_row = cursor.fetchone()
            worst = {'ticker': worst_row['ticker'], 'pnl_pct': worst_row['pnl_pct']} if worst_row else None
            
            return {
                'total': total,
                'closed_count': closed_count,
                'win_rate': round(win_rate, 2),
                'avg_pnl': round(avg_pnl, 2),
                'total_pnl': round(total_pnl, 2),
                'best': best,
                'worst': worst
            }
        finally:
            conn.close()


def close_recommendation(rec_id: int, close_price: float, reason: str) -> None:
    """
    Close a recommendation with a final price and reason.
    
    Args:
        rec_id: The recommendation ID.
        close_price: The final price when closed.
        reason: Reason for closing (e.g., 'target_reached', 'stop_loss', 'expired').
    """
    with _db_lock:
        conn = _get_connection()
        try:
            cursor = conn.cursor()
            
            # Get entry price for final P&L calculation
            cursor.execute(
                "SELECT entry_price, target, stop_loss FROM recommendations WHERE id = ?",
                (rec_id,)
            )
            row = cursor.fetchone()
            if not row:
                return
            
            entry_price = row['entry_price']
            final_pnl = ((close_price - entry_price) / entry_price) * 100 if entry_price > 0 else 0
            
            # Determine status based on reason
            status_map = {
                'target_reached': 'hit_target',
                'target': 'hit_target',
                'stop_loss': 'hit_stop',
                'stop': 'hit_stop',
                'expired': 'expired',
                'manual': 'closed'
            }
            status = status_map.get(reason.lower(), 'closed')
            
            cursor.execute("""
                UPDATE recommendations 
                SET current_price = ?, pnl_pct = ?, status = ?,
                    close_time = ?, close_price = ?, close_reason = ?
                WHERE id = ?
            """, (
                close_price,
                final_pnl,
                status,
                datetime.utcnow().isoformat(),
                close_price,
                reason,
                rec_id
            ))
            
            conn.commit()
        finally:
            conn.close()


def add_price_history(recommendation_id: int, price: float) -> None:
    """
    Add a price data point to the history for a recommendation.
    
    Args:
        recommendation_id: The recommendation ID.
        price: The price at this point in time.
    """
    with _db_lock:
        conn = _get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO price_history (recommendation_id, price, timestamp)
                VALUES (?, ?, ?)
            """, (recommendation_id, price, datetime.utcnow().isoformat()))
            conn.commit()
        finally:
            conn.close()


def get_price_history(recommendation_id: int) -> List[Tuple[str, float]]:
    """
    Get price history for a recommendation.
    
    Args:
        recommendation_id: The recommendation ID.
    
    Returns:
        List of (timestamp, price) tuples.
    """
    with _db_lock:
        conn = _get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT timestamp, price 
                FROM price_history 
                WHERE recommendation_id = ? 
                ORDER BY timestamp ASC
            """, (recommendation_id,))
            rows = cursor.fetchall()
            return [(row['timestamp'], row['price']) for row in rows]
        finally:
            conn.close()


def add_subscriber(email: str, plan: str = 'free_trial') -> bool:
    """
    Add a new subscriber.
    
    Args:
        email: The subscriber's email address.
        plan: The subscription plan ('free_trial', 'monthly', 'yearly').
    
    Returns:
        True if subscriber was added, False if email already exists.
    """
    with _db_lock:
        conn = _get_connection()
        try:
            cursor = conn.cursor()
            
            # Calculate trial end (14 days from now for free trial)
            now = datetime.utcnow()
            if plan == 'free_trial':
                trial_end = (now + timedelta(days=14)).isoformat()
                subscription_end = None
            elif plan == 'monthly':
                trial_end = None
                subscription_end = (now + timedelta(days=30)).isoformat()
            elif plan == 'yearly':
                trial_end = None
                subscription_end = (now + timedelta(days=365)).isoformat()
            else:
                return False
            
            try:
                cursor.execute("""
                    INSERT INTO subscribers (email, plan, trial_end, subscription_end, created_at)
                    VALUES (?, ?, ?, ?, ?)
                """, (email, plan, trial_end, subscription_end, now.isoformat()))
                conn.commit()
                return True
            except sqlite3.IntegrityError:
                # Email already exists
                return False
        finally:
            conn.close()


def check_subscription(email: str) -> Optional[Dict]:
    """
    Check subscription status for an email.
    
    Args:
        email: The subscriber's email address.
    
    Returns:
        Dictionary with subscription info, or None if not found.
    """
    with _db_lock:
        conn = _get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM subscribers WHERE email = ?",
                (email,)
            )
            row = cursor.fetchone()
            
            if not row:
                return None
            
            result = dict(row)
            now = datetime.utcnow()
            
            # Check if trial/subscription is active
            if result['trial_end']:
                trial_end = datetime.fromisoformat(result['trial_end'])
                result['is_active'] = now < trial_end
                result['days_remaining'] = max(0, (trial_end - now).days)
            elif result['subscription_end']:
                sub_end = datetime.fromisoformat(result['subscription_end'])
                result['is_active'] = now < sub_end
                result['days_remaining'] = max(0, (sub_end - now).days)
            else:
                result['is_active'] = False
                result['days_remaining'] = 0
            
            return result
        finally:
            conn.close()


def remove_subscriber(email: str) -> bool:
    """Remove a subscriber by email."""
    with _db_lock:
        conn = _get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM subscribers WHERE email = ?", (email,))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()


def remove_subscriber_by_stripe_id(stripe_id: str) -> bool:
    """Remove a subscriber by Stripe customer ID."""
    with _db_lock:
        conn = _get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM subscribers WHERE stripe_id = ?", (stripe_id,))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()


def update_subscriber(email: str, plan: str, stripe_id: str = None,
                      subscription_end: str = None) -> bool:
    """Update an existing subscriber's plan and subscription details."""
    with _db_lock:
        conn = _get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE subscribers SET plan = ?, stripe_id = COALESCE(?, stripe_id), "
                "subscription_end = COALESCE(?, subscription_end) WHERE email = ?",
                (plan, stripe_id, subscription_end, email)
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()


def update_subscriber_by_stripe_id(stripe_id: str, plan: str = None,
                                   subscription_end: str = None) -> bool:
    """Update a subscriber by Stripe customer ID."""
    with _db_lock:
        conn = _get_connection()
        try:
            cursor = conn.cursor()
            if plan and subscription_end:
                cursor.execute(
                    "UPDATE subscribers SET plan = ?, subscription_end = ? WHERE stripe_id = ?",
                    (plan, subscription_end, stripe_id)
                )
            elif plan:
                cursor.execute(
                    "UPDATE subscribers SET plan = ? WHERE stripe_id = ?",
                    (plan, stripe_id)
                )
            elif subscription_end:
                cursor.execute(
                    "UPDATE subscribers SET subscription_end = ? WHERE stripe_id = ?",
                    (subscription_end, stripe_id)
                )
            else:
                return False
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()


# Initialize database on module import
init_db()


if __name__ == "__main__":
    # Demo/test the database module
    print("Initializing recommendations database...")
    init_db()
    print(f"Database location: {DB_PATH}")
    
    # Test adding a recommendation
    test_rec = {
        'ticker': 'NVDA',
        'option_code': 'US.NVDA260606C235000',
        'direction': 'call',
        'entry_price': 12.50,
        'strike': 235.00,
        'expiry': '2026-06-06',
        'dte': 3,
        'otm_pct': 2.5,
        'stop_loss': 228.00,
        'target': 245.00,
        'logic': 'NVDA showing strong momentum with bullish engulfing pattern',
        'dark_pool': 'yes',
        'risk_note': 'High volume expected around earnings'
    }
    
    rec_id = add_recommendation(test_rec)
    print(f"Added recommendation with ID: {rec_id}")
    
    # Test updating price
    update_price(rec_id, 13.25)
    print("Updated price to $13.25")
    
    # Test getting active
    active = get_active()
    print(f"Active recommendations: {len(active)}")
    
    # Test stats
    stats = get_stats()
    print(f"Stats: {stats}")
    
    # Test closing
    close_recommendation(rec_id, 15.00, 'target_reached')
    print("Closed recommendation")
    
    # Test subscriber
    add_subscriber('test@example.com', 'free_trial')
    sub = check_subscription('test@example.com')
    print(f"Subscriber: {sub}")
