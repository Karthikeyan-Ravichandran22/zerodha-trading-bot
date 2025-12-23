"""
Trade Journal - SQLite database to store all trades for analysis
"""

import sqlite3
from datetime import datetime, date
from typing import List, Dict, Optional
from loguru import logger
import os


class TradeJournal:
    """Store and analyze all trades in SQLite database"""
    
    def __init__(self, db_path: str = "data/trades.db"):
        self.db_path = db_path
        self._ensure_db_dir()
        self._init_db()
    
    def _ensure_db_dir(self):
        """Ensure data directory exists"""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
    
    def _init_db(self):
        """Initialize database tables"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Trades table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                symbol TEXT NOT NULL,
                action TEXT NOT NULL,
                entry_time TEXT,
                exit_time TEXT,
                entry_price REAL,
                exit_price REAL,
                quantity INTEGER,
                stop_loss REAL,
                target REAL,
                gross_pnl REAL,
                charges REAL,
                net_pnl REAL,
                result TEXT,
                entry_order_id TEXT,
                sl_order_id TEXT,
                target_order_id TEXT,
                notes TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Daily summary table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS daily_summary (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT UNIQUE NOT NULL,
                total_trades INTEGER,
                wins INTEGER,
                losses INTEGER,
                win_rate REAL,
                gross_pnl REAL,
                total_charges REAL,
                net_pnl REAL,
                best_trade REAL,
                worst_trade REAL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
        logger.debug("Trade journal database initialized")
    
    def record_entry(self, symbol: str, action: str, entry_price: float, 
                     quantity: int, stop_loss: float, target: float,
                     entry_order_id: str, sl_order_id: str = None, 
                     target_order_id: str = None) -> int:
        """Record a new trade entry"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO trades (date, symbol, action, entry_time, entry_price, 
                               quantity, stop_loss, target, entry_order_id, 
                               sl_order_id, target_order_id, result)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'OPEN')
        ''', (
            date.today().isoformat(),
            symbol,
            action,
            datetime.now().strftime("%H:%M:%S"),
            entry_price,
            quantity,
            stop_loss,
            target,
            entry_order_id,
            sl_order_id,
            target_order_id
        ))
        
        trade_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        logger.info(f"📓 Trade recorded: #{trade_id} {action} {symbol}")
        return trade_id
    
    def record_exit(self, trade_id: int = None, symbol: str = None, 
                    exit_price: float = None, result: str = "CLOSED",
                    charges: float = 0, notes: str = None):
        """Record trade exit and calculate P&L"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Find the trade
        if trade_id:
            cursor.execute("SELECT * FROM trades WHERE id = ?", (trade_id,))
        elif symbol:
            cursor.execute(
                "SELECT * FROM trades WHERE symbol = ? AND result = 'OPEN' ORDER BY id DESC LIMIT 1",
                (symbol,)
            )
        else:
            conn.close()
            return
        
        trade = cursor.fetchone()
        if not trade:
            conn.close()
            return
        
        trade_id = trade[0]
        entry_price = trade[7]  # entry_price column
        quantity = trade[8]     # quantity column
        action = trade[3]       # action column
        
        # Calculate P&L
        if action == "BUY":
            gross_pnl = (exit_price - entry_price) * quantity
        else:
            gross_pnl = (entry_price - exit_price) * quantity
        
        net_pnl = gross_pnl - charges
        
        # Update trade
        cursor.execute('''
            UPDATE trades 
            SET exit_time = ?, exit_price = ?, gross_pnl = ?, charges = ?, 
                net_pnl = ?, result = ?, notes = ?
            WHERE id = ?
        ''', (
            datetime.now().strftime("%H:%M:%S"),
            exit_price,
            gross_pnl,
            charges,
            net_pnl,
            result,
            notes,
            trade_id
        ))
        
        conn.commit()
        conn.close()
        
        emoji = "💚" if net_pnl >= 0 else "💔"
        logger.info(f"📓 Trade closed: #{trade_id} | {emoji} Net P&L: ₹{net_pnl:.2f}")
    
    def get_today_trades(self) -> List[Dict]:
        """Get all trades for today"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT * FROM trades WHERE date = ? ORDER BY id",
            (date.today().isoformat(),)
        )
        
        trades = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return trades
    
    def get_today_stats(self) -> Dict:
        """Get today's trading statistics"""
        trades = self.get_today_trades()
        
        if not trades:
            return {
                'total_trades': 0,
                'wins': 0,
                'losses': 0,
                'win_rate': 0,
                'gross_pnl': 0,
                'total_charges': 0,
                'net_pnl': 0,
                'best_trade': 0,
                'worst_trade': 0,
                'open_trades': 0
            }
        
        closed_trades = [t for t in trades if t['result'] != 'OPEN']
        open_trades = [t for t in trades if t['result'] == 'OPEN']
        
        wins = len([t for t in closed_trades if t['net_pnl'] and t['net_pnl'] > 0])
        losses = len([t for t in closed_trades if t['net_pnl'] and t['net_pnl'] <= 0])
        
        pnls = [t['net_pnl'] for t in closed_trades if t['net_pnl'] is not None]
        
        return {
            'total_trades': len(trades),
            'open_trades': len(open_trades),
            'closed_trades': len(closed_trades),
            'wins': wins,
            'losses': losses,
            'win_rate': (wins / len(closed_trades) * 100) if closed_trades else 0,
            'gross_pnl': sum(t['gross_pnl'] or 0 for t in closed_trades),
            'total_charges': sum(t['charges'] or 0 for t in closed_trades),
            'net_pnl': sum(pnls) if pnls else 0,
            'best_trade': max(pnls) if pnls else 0,
            'worst_trade': min(pnls) if pnls else 0
        }
    
    def save_daily_summary(self):
        """Save today's summary to database"""
        stats = self.get_today_stats()
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO daily_summary 
            (date, total_trades, wins, losses, win_rate, gross_pnl, 
             total_charges, net_pnl, best_trade, worst_trade)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            date.today().isoformat(),
            stats['total_trades'],
            stats['wins'],
            stats['losses'],
            stats['win_rate'],
            stats['gross_pnl'],
            stats['total_charges'],
            stats['net_pnl'],
            stats['best_trade'],
            stats['worst_trade']
        ))
        
        conn.commit()
        conn.close()
        logger.info("📓 Daily summary saved to database")
    
    def get_performance_report(self, days: int = 7) -> Dict:
        """Get performance report for last N days"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM daily_summary 
            ORDER BY date DESC 
            LIMIT ?
        ''', (days,))
        
        summaries = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        if not summaries:
            return {'days': 0, 'total_pnl': 0, 'avg_daily_pnl': 0}
        
        total_pnl = sum(s['net_pnl'] or 0 for s in summaries)
        total_trades = sum(s['total_trades'] or 0 for s in summaries)
        total_wins = sum(s['wins'] or 0 for s in summaries)
        
        return {
            'days': len(summaries),
            'total_trades': total_trades,
            'total_wins': total_wins,
            'win_rate': (total_wins / total_trades * 100) if total_trades else 0,
            'total_pnl': total_pnl,
            'avg_daily_pnl': total_pnl / len(summaries),
            'best_day': max(s['net_pnl'] or 0 for s in summaries),
            'worst_day': min(s['net_pnl'] or 0 for s in summaries)
        }


# Global instance
trade_journal = TradeJournal()
