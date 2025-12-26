#!/usr/bin/env python3
"""
📊 TRADING ANALYTICS DATABASE
==============================

SQLite database to store all trading data for analysis:
- Trades
- Daily P&L
- Weekly performance
- Stock performance
- Strategy performance

Usage:
    from analytics_db import analytics_db
    analytics_db.record_trade(...)
    analytics_db.get_weekly_pnl()
"""

import os
import sqlite3
import json
from datetime import datetime, timedelta
import pytz

IST = pytz.timezone('Asia/Kolkata')
DB_FILE = "data/trading_analytics.db"

class AnalyticsDatabase:
    """SQLite database for trading analytics"""
    
    def __init__(self, db_path=DB_FILE):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._init_db()
    
    def _init_db(self):
        """Initialize database tables"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Trades table - enhanced with all trade details
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                time TEXT NOT NULL,
                symbol TEXT NOT NULL,
                segment TEXT DEFAULT 'EQUITY',
                signal TEXT NOT NULL,
                entry_price REAL NOT NULL,
                exit_price REAL,
                quantity INTEGER NOT NULL,
                pnl REAL DEFAULT 0,
                status TEXT DEFAULT 'OPEN',
                strategy TEXT DEFAULT 'Gold 93% Win Rate',
                trail_percent REAL,
                stop_loss REAL,
                target REAL,
                trail_sl REAL,
                exit_time TEXT,
                product_type TEXT DEFAULT 'MIS',
                exit_reason TEXT,
                entry_time TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Add new columns if they don't exist (migration for existing DB)
        try:
            cursor.execute('ALTER TABLE trades ADD COLUMN stop_loss REAL')
        except sqlite3.OperationalError:
            pass  # Column already exists
        try:
            cursor.execute('ALTER TABLE trades ADD COLUMN target REAL')
        except sqlite3.OperationalError:
            pass
        try:
            cursor.execute('ALTER TABLE trades ADD COLUMN trail_sl REAL')
        except sqlite3.OperationalError:
            pass
        try:
            cursor.execute('ALTER TABLE trades ADD COLUMN exit_time TEXT')
        except sqlite3.OperationalError:
            pass
        try:
            cursor.execute('ALTER TABLE trades ADD COLUMN product_type TEXT DEFAULT "MIS"')
        except sqlite3.OperationalError:
            pass
        try:
            cursor.execute('ALTER TABLE trades ADD COLUMN exit_reason TEXT')
        except sqlite3.OperationalError:
            pass
        try:
            cursor.execute('ALTER TABLE trades ADD COLUMN entry_time TEXT')
        except sqlite3.OperationalError:
            pass
        
        # Daily summary table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS daily_summary (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT UNIQUE NOT NULL,
                total_trades INTEGER DEFAULT 0,
                winning_trades INTEGER DEFAULT 0,
                losing_trades INTEGER DEFAULT 0,
                total_pnl REAL DEFAULT 0,
                win_rate REAL DEFAULT 0,
                capital REAL DEFAULT 10000,
                roi REAL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Stock performance table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS stock_performance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                total_trades INTEGER DEFAULT 0,
                winning_trades INTEGER DEFAULT 0,
                total_pnl REAL DEFAULT 0,
                win_rate REAL DEFAULT 0,
                last_updated TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Weekly scan results
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS weekly_scans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scan_date TEXT NOT NULL,
                stocks_scanned INTEGER DEFAULT 0,
                stocks_qualified INTEGER DEFAULT 0,
                min_win_rate REAL DEFAULT 80,
                expected_pnl REAL DEFAULT 0,
                stocks_list TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Positions table - track all positions with full history
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS positions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                symbol TEXT NOT NULL,
                segment TEXT DEFAULT 'EQUITY',
                signal TEXT NOT NULL,
                entry_price REAL NOT NULL,
                entry_time TEXT,
                quantity INTEGER NOT NULL,
                stop_loss REAL,
                target REAL,
                trail_sl REAL,
                exit_price REAL,
                exit_time TEXT,
                exit_reason TEXT,
                product_type TEXT DEFAULT 'MIS',
                pnl REAL DEFAULT 0,
                status TEXT DEFAULT 'OPEN',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def record_trade(self, symbol, signal, entry_price, quantity, 
                     exit_price=None, pnl=0, status='OPEN', strategy='Gold 93% Win Rate'):
        """Record a new trade"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        now = datetime.now(IST)
        
        cursor.execute('''
            INSERT INTO trades (date, time, symbol, signal, entry_price, exit_price, 
                              quantity, pnl, status, strategy)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            now.strftime('%Y-%m-%d'),
            now.strftime('%H:%M:%S'),
            symbol, signal, entry_price, exit_price, quantity, pnl, status, strategy
        ))
        
        trade_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return trade_id
    
    def close_trade(self, trade_id, exit_price, pnl):
        """Close a trade with exit price and P&L"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE trades SET exit_price = ?, pnl = ?, status = 'CLOSED'
            WHERE id = ?
        ''', (exit_price, pnl, trade_id))
        
        conn.commit()
        conn.close()
        
        # Update daily summary
        self._update_daily_summary()
        
        # Update stock performance
        cursor = sqlite3.connect(self.db_path).cursor()
        cursor.execute('SELECT symbol FROM trades WHERE id = ?', (trade_id,))
        result = cursor.fetchone()
        if result:
            self._update_stock_performance(result[0])
    
    def _update_daily_summary(self):
        """Update today's summary"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        today = datetime.now(IST).strftime('%Y-%m-%d')
        
        cursor.execute('''
            SELECT COUNT(*), 
                   SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END),
                   SUM(CASE WHEN pnl <= 0 THEN 1 ELSE 0 END),
                   SUM(pnl)
            FROM trades 
            WHERE date = ? AND status = 'CLOSED'
        ''', (today,))
        
        result = cursor.fetchone()
        total = result[0] or 0
        wins = result[1] or 0
        losses = result[2] or 0
        total_pnl = result[3] or 0
        win_rate = (wins / total * 100) if total > 0 else 0
        
        cursor.execute('''
            INSERT OR REPLACE INTO daily_summary 
            (date, total_trades, winning_trades, losing_trades, total_pnl, win_rate)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (today, total, wins, losses, total_pnl, win_rate))
        
        conn.commit()
        conn.close()
    
    def _update_stock_performance(self, symbol):
        """Update stock performance stats"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT COUNT(*), 
                   SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END),
                   SUM(pnl)
            FROM trades 
            WHERE symbol = ? AND status = 'CLOSED'
        ''', (symbol,))
        
        result = cursor.fetchone()
        total = result[0] or 0
        wins = result[1] or 0
        total_pnl = result[2] or 0
        win_rate = (wins / total * 100) if total > 0 else 0
        
        now = datetime.now(IST).strftime('%Y-%m-%d %H:%M')
        
        cursor.execute('''
            INSERT OR REPLACE INTO stock_performance 
            (symbol, total_trades, winning_trades, total_pnl, win_rate, last_updated)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (symbol, total, wins, total_pnl, win_rate, now))
        
        conn.commit()
        conn.close()
    
    def record_weekly_scan(self, stocks_scanned, stocks_qualified, 
                           expected_pnl, stocks_list):
        """Record weekly scan results"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        now = datetime.now(IST).strftime('%Y-%m-%d')
        
        cursor.execute('''
            INSERT INTO weekly_scans 
            (scan_date, stocks_scanned, stocks_qualified, expected_pnl, stocks_list)
            VALUES (?, ?, ?, ?, ?)
        ''', (now, stocks_scanned, stocks_qualified, expected_pnl, json.dumps(stocks_list)))
        
        conn.commit()
        conn.close()
    
    def get_today_trades(self):
        """Get today's trades"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        today = datetime.now(IST).strftime('%Y-%m-%d')
        
        cursor.execute('''
            SELECT * FROM trades WHERE date = ? ORDER BY time DESC
        ''', (today,))
        
        columns = [description[0] for description in cursor.description]
        trades = [dict(zip(columns, row)) for row in cursor.fetchall()]
        
        conn.close()
        return trades
    
    def get_today_summary(self):
        """Get today's summary"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        today = datetime.now(IST).strftime('%Y-%m-%d')
        
        cursor.execute('SELECT * FROM daily_summary WHERE date = ?', (today,))
        result = cursor.fetchone()
        
        if result:
            columns = [description[0] for description in cursor.description]
            return dict(zip(columns, result))
        
        return {
            'total_trades': 0,
            'winning_trades': 0,
            'losing_trades': 0,
            'total_pnl': 0,
            'win_rate': 0
        }
    
    def get_weekly_summary(self):
        """Get this week's summary"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get last 7 days
        today = datetime.now(IST)
        week_ago = (today - timedelta(days=7)).strftime('%Y-%m-%d')
        
        cursor.execute('''
            SELECT SUM(total_trades), SUM(winning_trades), SUM(losing_trades), SUM(total_pnl)
            FROM daily_summary WHERE date >= ?
        ''', (week_ago,))
        
        result = cursor.fetchone()
        
        total = result[0] or 0
        wins = result[1] or 0
        losses = result[2] or 0
        pnl = result[3] or 0
        
        return {
            'total_trades': total,
            'winning_trades': wins,
            'losing_trades': losses,
            'total_pnl': pnl,
            'win_rate': (wins / total * 100) if total > 0 else 0
        }
    
    def get_monthly_summary(self):
        """Get this month's summary"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        today = datetime.now(IST)
        month_start = today.replace(day=1).strftime('%Y-%m-%d')
        
        cursor.execute('''
            SELECT SUM(total_trades), SUM(winning_trades), SUM(losing_trades), SUM(total_pnl)
            FROM daily_summary WHERE date >= ?
        ''', (month_start,))
        
        result = cursor.fetchone()
        
        total = result[0] or 0
        wins = result[1] or 0
        losses = result[2] or 0
        pnl = result[3] or 0
        
        return {
            'total_trades': total,
            'winning_trades': wins,
            'losing_trades': losses,
            'total_pnl': pnl,
            'win_rate': (wins / total * 100) if total > 0 else 0
        }
    
    def get_all_time_stats(self):
        """Get all time statistics"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT COUNT(*), 
                   SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END),
                   SUM(CASE WHEN pnl <= 0 THEN 1 ELSE 0 END),
                   SUM(pnl),
                   AVG(CASE WHEN pnl > 0 THEN pnl END),
                   AVG(CASE WHEN pnl < 0 THEN pnl END),
                   MAX(pnl),
                   MIN(pnl)
            FROM trades WHERE status = 'CLOSED'
        ''')
        
        result = cursor.fetchone()
        
        total = result[0] or 0
        wins = result[1] or 0
        losses = result[2] or 0
        total_pnl = result[3] or 0
        avg_win = result[4] or 0
        avg_loss = result[5] or 0
        best_trade = result[6] or 0
        worst_trade = result[7] or 0
        
        conn.close()
        
        return {
            'total_trades': total,
            'winning_trades': wins,
            'losing_trades': losses,
            'total_pnl': total_pnl,
            'win_rate': (wins / total * 100) if total > 0 else 0,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'best_trade': best_trade,
            'worst_trade': worst_trade,
            'profit_factor': abs(avg_win / avg_loss) if avg_loss != 0 else 0
        }
    
    def get_top_stocks(self, limit=5):
        """Get top performing stocks"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT symbol, total_trades, win_rate, total_pnl
            FROM stock_performance
            ORDER BY total_pnl DESC
            LIMIT ?
        ''', (limit,))
        
        columns = ['symbol', 'total_trades', 'win_rate', 'total_pnl']
        stocks = [dict(zip(columns, row)) for row in cursor.fetchall()]
        
        conn.close()
        return stocks
    
    def get_daily_pnl_chart(self, days=14):
        """Get daily P&L for chart"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        today = datetime.now(IST)
        start_date = (today - timedelta(days=days)).strftime('%Y-%m-%d')
        
        cursor.execute('''
            SELECT date, total_pnl, total_trades, win_rate
            FROM daily_summary
            WHERE date >= ?
            ORDER BY date ASC
        ''', (start_date,))
        
        columns = ['date', 'pnl', 'trades', 'win_rate']
        data = [dict(zip(columns, row)) for row in cursor.fetchall()]
        
        conn.close()
        return data
    
    def save_position(self, symbol, signal, entry_price, quantity, 
                      stop_loss=0, target=0, trail_sl=0, entry_time=None,
                      segment='EQUITY', product_type='MIS'):
        """Save a new position to database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        now = datetime.now(IST)
        date_str = now.strftime('%Y-%m-%d')
        time_str = entry_time or now.strftime('%H:%M:%S')
        
        cursor.execute('''
            INSERT INTO positions 
            (date, symbol, segment, signal, entry_price, entry_time, quantity,
             stop_loss, target, trail_sl, product_type, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'OPEN')
        ''', (date_str, symbol, segment, signal, entry_price, time_str, quantity,
              stop_loss, target, trail_sl, product_type))
        
        position_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return position_id
    
    def close_position(self, symbol, exit_price, pnl, exit_reason='MARKET_CLOSE', 
                       exit_time=None, date=None):
        """Close a position with exit details"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        now = datetime.now(IST)
        date_str = date or now.strftime('%Y-%m-%d')
        time_str = exit_time or now.strftime('%H:%M:%S')
        
        cursor.execute('''
            UPDATE positions 
            SET exit_price = ?, exit_time = ?, exit_reason = ?, pnl = ?, status = 'CLOSED'
            WHERE symbol = ? AND date = ? AND status = 'OPEN'
        ''', (exit_price, time_str, exit_reason, pnl, symbol, date_str))
        
        conn.commit()
        conn.close()
        
        # Update daily summary
        self._update_daily_summary()
    
    def update_position_trail(self, symbol, trail_sl, date=None):
        """Update trailing stop loss for a position"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        date_str = date or datetime.now(IST).strftime('%Y-%m-%d')
        
        cursor.execute('''
            UPDATE positions SET trail_sl = ?
            WHERE symbol = ? AND date = ? AND status = 'OPEN'
        ''', (trail_sl, symbol, date_str))
        
        conn.commit()
        conn.close()
    
    def update_position_product_type(self, symbol, product_type, date=None):
        """Update product type (MIS -> CNC conversion)"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        date_str = date or datetime.now(IST).strftime('%Y-%m-%d')
        
        cursor.execute('''
            UPDATE positions SET product_type = ?
            WHERE symbol = ? AND date = ? AND status = 'OPEN'
        ''', (product_type, symbol, date_str))
        
        conn.commit()
        conn.close()
    
    def get_positions_by_date(self, date=None):
        """Get all positions for a specific date"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        date_str = date or datetime.now(IST).strftime('%Y-%m-%d')
        
        cursor.execute('''
            SELECT * FROM positions WHERE date = ? ORDER BY entry_time DESC
        ''', (date_str,))
        
        columns = [description[0] for description in cursor.description]
        positions = [dict(zip(columns, row)) for row in cursor.fetchall()]
        
        conn.close()
        return positions
    
    def get_open_positions(self, date=None):
        """Get all open positions for a date"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        date_str = date or datetime.now(IST).strftime('%Y-%m-%d')
        
        cursor.execute('''
            SELECT * FROM positions WHERE date = ? AND status = 'OPEN' ORDER BY entry_time DESC
        ''', (date_str,))
        
        columns = [description[0] for description in cursor.description]
        positions = [dict(zip(columns, row)) for row in cursor.fetchall()]
        
        conn.close()
        return positions
    
    def get_trading_dates(self, limit=30):
        """Get list of dates with trading activity"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT DISTINCT date, COUNT(*) as trade_count, SUM(pnl) as total_pnl
            FROM positions
            GROUP BY date
            ORDER BY date DESC
            LIMIT ?
        ''', (limit,))
        
        columns = ['date', 'trade_count', 'total_pnl']
        dates = [dict(zip(columns, row)) for row in cursor.fetchall()]
        
        conn.close()
        return dates
    
    def get_trades_by_date(self, date=None):
        """Get all trades (from trades table) for a specific date"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        date_str = date or datetime.now(IST).strftime('%Y-%m-%d')
        
        cursor.execute('''
            SELECT * FROM trades WHERE date = ? ORDER BY time DESC
        ''', (date_str,))
        
        columns = [description[0] for description in cursor.description]
        trades = [dict(zip(columns, row)) for row in cursor.fetchall()]
        
        conn.close()
        return trades


# Singleton instance
analytics_db = AnalyticsDatabase()

