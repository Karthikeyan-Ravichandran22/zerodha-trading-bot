"""
Trade Journal Viewer - View all trades and performance stats
"""

import sqlite3
from datetime import date
import os

DB_PATH = "data/trades.db"

def view_trades():
    """View all trades"""
    if not os.path.exists(DB_PATH):
        print("❌ No trades yet! Trade journal will be created after first trade.")
        return
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Today's trades
    print("="*60)
    print("📓 TRADE JOURNAL")
    print("="*60)
    
    cursor.execute("SELECT * FROM trades ORDER BY id DESC LIMIT 20")
    trades = cursor.fetchall()
    
    if not trades:
        print("\n📭 No trades recorded yet.")
    else:
        print(f"\n📋 Last 20 Trades:\n")
        print(f"{'ID':<5} {'Date':<12} {'Symbol':<8} {'Action':<5} {'Entry':<10} {'Exit':<10} {'Net P&L':<12} {'Result'}")
        print("-"*75)
        
        for t in trades:
            net_pnl = t['net_pnl'] if t['net_pnl'] else 0
            pnl_str = f"₹{net_pnl:+.2f}" if net_pnl else "-"
            exit_price = f"₹{t['exit_price']:.2f}" if t['exit_price'] else "-"
            result = t['result'] or "OPEN"
            emoji = "💚" if net_pnl > 0 else "💔" if net_pnl < 0 else "⏳"
            
            print(f"{t['id']:<5} {t['date']:<12} {t['symbol']:<8} {t['action']:<5} ₹{t['entry_price']:<9.2f} {exit_price:<10} {pnl_str:<12} {emoji} {result}")
    
    # Daily summaries
    print("\n" + "="*60)
    print("📊 DAILY SUMMARIES")
    print("="*60)
    
    cursor.execute("SELECT * FROM daily_summary ORDER BY date DESC LIMIT 7")
    summaries = cursor.fetchall()
    
    if summaries:
        print(f"\n{'Date':<12} {'Trades':<8} {'Wins':<6} {'Losses':<8} {'Win Rate':<10} {'Net P&L'}")
        print("-"*60)
        
        for s in summaries:
            net = s['net_pnl'] or 0
            emoji = "💚" if net > 0 else "💔" if net < 0 else "➖"
            print(f"{s['date']:<12} {s['total_trades']:<8} {s['wins']:<6} {s['losses']:<8} {s['win_rate']:.1f}%{'':<5} {emoji} ₹{net:+.2f}")
    else:
        print("\n📭 No daily summaries yet.")
    
    # Overall stats
    print("\n" + "="*60)
    print("📈 OVERALL STATISTICS")
    print("="*60)
    
    cursor.execute("SELECT COUNT(*) as total, SUM(net_pnl) as total_pnl FROM trades WHERE result != 'OPEN'")
    overall = cursor.fetchone()
    
    if overall and overall['total'] > 0:
        cursor.execute("SELECT COUNT(*) FROM trades WHERE net_pnl > 0")
        wins = cursor.fetchone()[0]
        
        print(f"\n  Total Closed Trades: {overall['total']}")
        print(f"  Total Wins: {wins}")
        print(f"  Win Rate: {(wins/overall['total']*100):.1f}%")
        print(f"  Total Net P&L: ₹{overall['total_pnl'] or 0:+,.2f}")
    
    conn.close()
    print("\n" + "="*60)

if __name__ == "__main__":
    view_trades()
