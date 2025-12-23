"""
Web Dashboard - Real-time monitoring of the trading bot
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask, render_template, jsonify
from datetime import datetime, date
import sqlite3
import json

app = Flask(__name__)

# Database paths
TRADES_DB = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'trades.db')
CAPITAL_CONFIG = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'capital_config.json')


def get_capital_stats():
    """Get capital from config file"""
    try:
        if os.path.exists(CAPITAL_CONFIG):
            with open(CAPITAL_CONFIG, 'r') as f:
                data = json.load(f)
                return {
                    'current_capital': data.get('current_capital', 10000),
                    'total_pnl': data.get('total_pnl', 0),
                    'high_water_mark': data.get('high_water_mark', 10000),
                    'growth_percent': ((data.get('current_capital', 10000) - 10000) / 10000) * 100
                }
    except:
        pass
    return {'current_capital': 10000, 'total_pnl': 0, 'high_water_mark': 10000, 'growth_percent': 0}


def get_today_trades():
    """Get today's trades from database"""
    try:
        if not os.path.exists(TRADES_DB):
            return []
        
        conn = sqlite3.connect(TRADES_DB)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT * FROM trades WHERE date = ? ORDER BY id DESC",
            (date.today().isoformat(),)
        )
        trades = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return trades
    except:
        return []


def get_today_stats():
    """Get today's trading statistics"""
    trades = get_today_trades()
    
    if not trades:
        return {
            'total_trades': 0,
            'open_trades': 0,
            'wins': 0,
            'losses': 0,
            'win_rate': 0,
            'gross_pnl': 0,
            'net_pnl': 0
        }
    
    open_trades = [t for t in trades if t.get('result') == 'OPEN']
    closed_trades = [t for t in trades if t.get('result') != 'OPEN']
    wins = len([t for t in closed_trades if t.get('net_pnl', 0) and t['net_pnl'] > 0])
    losses = len([t for t in closed_trades if t.get('net_pnl', 0) and t['net_pnl'] <= 0])
    
    net_pnl = sum(t.get('net_pnl', 0) or 0 for t in closed_trades)
    gross_pnl = sum(t.get('gross_pnl', 0) or 0 for t in closed_trades)
    
    return {
        'total_trades': len(trades),
        'open_trades': len(open_trades),
        'closed_trades': len(closed_trades),
        'wins': wins,
        'losses': losses,
        'win_rate': (wins / len(closed_trades) * 100) if closed_trades else 0,
        'gross_pnl': gross_pnl,
        'net_pnl': net_pnl
    }


def get_weekly_stats():
    """Get weekly performance"""
    try:
        if not os.path.exists(TRADES_DB):
            return []
        
        conn = sqlite3.connect(TRADES_DB)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT * FROM daily_summary ORDER BY date DESC LIMIT 7"
        )
        summaries = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return summaries
    except:
        return []


@app.route('/')
def dashboard():
    """Main dashboard page"""
    return render_template('dashboard.html')


@app.route('/api/status')
def api_status():
    """API endpoint for dashboard data"""
    capital = get_capital_stats()
    today = get_today_stats()
    trades = get_today_trades()
    weekly = get_weekly_stats()
    
    return jsonify({
        'timestamp': datetime.now().isoformat(),
        'capital': capital,
        'today': today,
        'trades': trades[-10:],  # Last 10 trades
        'weekly': weekly,
        'bot_status': 'running'
    })


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5050))
    app.run(host='0.0.0.0', port=port, debug=False)
