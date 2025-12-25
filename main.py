#!/usr/bin/env python3
"""
🚀 RAILWAY CLOUD ENTRY POINT
=============================

Simple, robust entry point for Railway deployment.
Runs:
1. Premium Dashboard (main thread - PORT binding)
2. Stock Trading Bot (background thread)
3. Weekly Scheduler (background thread)
"""

import os
import sys
import json
import time
import threading
import pytz
from datetime import datetime
from flask import Flask, render_template_string, jsonify
from loguru import logger

# Setup
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.makedirs("logs", exist_ok=True)
os.makedirs("data", exist_ok=True)
os.makedirs("config", exist_ok=True)

logger.remove()
logger.add(sys.stdout, format="{time:HH:mm:ss} | {level} | {message}", level="INFO")

IST = pytz.timezone('Asia/Kolkata')
app = Flask(__name__)

# Trading Config
STRATEGY = {
    "name": "Gold 93% Win Rate Strategy",
    "segment": "EQUITY",
    "exchange": "NSE",
    "product": "MIS Intraday",
    "broker": "Angel One",
    "leverage": "5x"
}


def get_dashboard_data():
    """Get dashboard data"""
    data = {
        'capital': 10000,
        'daily_pnl': 0,
        'trades': [],
        'positions': {},
        'watchlist': [],
        'strategy': STRATEGY
    }
    
    try:
        if os.path.exists("config/smart_watchlist.json"):
            with open("config/smart_watchlist.json", 'r') as f:
                wl = json.load(f)
                data['watchlist'] = wl.get('active_stocks', [])
                data['capital'] = wl.get('capital', 10000)
    except:
        pass
    
    try:
        if os.path.exists("data/stock_positions.json"):
            with open("data/stock_positions.json", 'r') as f:
                data['positions'] = json.load(f)
    except:
        pass
    
    return data


# Simple but beautiful dark theme dashboard
DASHBOARD_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>📈 Gold 93% Win Rate - Trading Dashboard</title>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap" rel="stylesheet">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { 
            font-family: 'Inter', sans-serif; 
            background: linear-gradient(135deg, #0a0a0f 0%, #1a1a2e 100%);
            color: #fff; 
            min-height: 100vh;
            padding: 2rem;
        }
        .header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 2rem;
            padding-bottom: 1rem;
            border-bottom: 1px solid #333;
        }
        .logo h1 { 
            font-size: 1.8rem;
            background: linear-gradient(135deg, #00d4aa, #667eea);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        .strategy-tag {
            background: rgba(0, 212, 170, 0.2);
            color: #00d4aa;
            padding: 0.5rem 1rem;
            border-radius: 8px;
            font-size: 0.9rem;
            font-weight: 600;
        }
        .status { 
            display: flex; 
            align-items: center; 
            gap: 0.5rem;
            color: #00ff88;
        }
        .pulse {
            width: 10px; height: 10px;
            background: #00ff88;
            border-radius: 50%;
            animation: pulse 2s infinite;
        }
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.3; }
        }
        .info-banner {
            background: rgba(0, 212, 170, 0.1);
            border: 1px solid #333;
            border-radius: 12px;
            padding: 1.5rem;
            margin-bottom: 2rem;
            display: flex;
            flex-wrap: wrap;
            gap: 2rem;
        }
        .info-item label { 
            font-size: 0.75rem; 
            color: #888; 
            text-transform: uppercase; 
            display: block;
            margin-bottom: 0.3rem;
        }
        .info-item span { 
            font-weight: 600; 
            color: #00d4aa;
        }
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 1rem;
            margin-bottom: 2rem;
        }
        .stat-card {
            background: rgba(255,255,255,0.05);
            border: 1px solid #333;
            border-radius: 12px;
            padding: 1.5rem;
        }
        .stat-card h3 { font-size: 0.8rem; color: #888; margin-bottom: 0.5rem; }
        .stat-card .value { font-size: 1.8rem; font-weight: 700; }
        .stat-card .value.profit { color: #00ff88; }
        .section {
            background: rgba(255,255,255,0.05);
            border: 1px solid #333;
            border-radius: 12px;
            padding: 1.5rem;
            margin-bottom: 1.5rem;
        }
        .section h2 { 
            font-size: 1.1rem; 
            margin-bottom: 1rem;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }
        .badge {
            background: #00d4aa;
            color: #000;
            padding: 0.2rem 0.5rem;
            border-radius: 12px;
            font-size: 0.75rem;
        }
        table { width: 100%; border-collapse: collapse; }
        th, td { padding: 0.75rem; text-align: left; border-bottom: 1px solid #333; }
        th { color: #888; font-size: 0.75rem; text-transform: uppercase; }
        .empty { text-align: center; padding: 2rem; color: #666; }
        .footer { text-align: center; padding: 2rem 0; color: #666; font-size: 0.85rem; }
    </style>
</head>
<body>
    <div class="header">
        <div class="logo">
            <h1>📈 Trading Dashboard</h1>
            <div class="strategy-tag">Gold 93% Win Rate Strategy</div>
        </div>
        <div class="status">
            <div class="pulse"></div>
            <span id="status">LIVE</span>
            <span id="time">--:--:--</span>
        </div>
    </div>
    
    <div class="info-banner">
        <div class="info-item">
            <label>Segment</label>
            <span>EQUITY</span>
        </div>
        <div class="info-item">
            <label>Exchange</label>
            <span>NSE</span>
        </div>
        <div class="info-item">
            <label>Product</label>
            <span>MIS Intraday</span>
        </div>
        <div class="info-item">
            <label>Leverage</label>
            <span>5x</span>
        </div>
        <div class="info-item">
            <label>Broker</label>
            <span>Angel One</span>
        </div>
        <div class="info-item">
            <label>Strategy</label>
            <span>RSI + Stoch + CCI + MACD</span>
        </div>
    </div>
    
    <div class="stats-grid">
        <div class="stat-card">
            <h3>Capital</h3>
            <div class="value" id="capital">₹10,000</div>
        </div>
        <div class="stat-card">
            <h3>Today's P&L</h3>
            <div class="value profit" id="pnl">+₹0</div>
        </div>
        <div class="stat-card">
            <h3>Watchlist</h3>
            <div class="value" id="watchlist-count">0</div>
        </div>
        <div class="stat-card">
            <h3>Open Positions</h3>
            <div class="value" id="positions-count">0</div>
        </div>
    </div>
    
    <div class="section">
        <h2>📋 Smart Watchlist <span class="badge" id="wl-badge">0</span></h2>
        <table>
            <thead>
                <tr><th>Stock</th><th>Win Rate</th><th>Expected P&L</th></tr>
            </thead>
            <tbody id="watchlist-body">
                <tr><td colspan="3" class="empty">Loading...</td></tr>
            </tbody>
        </table>
    </div>
    
    <div class="footer">
        <p>🤖 Gold 93% Win Rate Strategy | EQUITY | NSE | MIS Intraday | Angel One</p>
        <p>Last Update: <span id="last-update">--</span></p>
    </div>
    
    <script>
        function updateTime() {
            document.getElementById('time').textContent = 
                new Date().toLocaleTimeString('en-IN', {hour12: false, timeZone: 'Asia/Kolkata'}) + ' IST';
        }
        setInterval(updateTime, 1000);
        updateTime();
        
        async function fetchData() {
            try {
                const res = await fetch('/api/dashboard');
                const data = await res.json();
                
                document.getElementById('capital').textContent = '₹' + (data.capital || 10000).toLocaleString();
                document.getElementById('pnl').textContent = '+₹' + (data.daily_pnl || 0);
                document.getElementById('watchlist-count').textContent = (data.watchlist || []).length;
                document.getElementById('positions-count').textContent = Object.keys(data.positions || {}).length;
                document.getElementById('wl-badge').textContent = (data.watchlist || []).length;
                
                const tbody = document.getElementById('watchlist-body');
                const wl = data.watchlist || [];
                
                if (wl.length === 0) {
                    tbody.innerHTML = '<tr><td colspan="3" class="empty">No stocks in watchlist</td></tr>';
                } else {
                    tbody.innerHTML = wl.slice(0, 10).map(s => `
                        <tr>
                            <td>${s.symbol || s.name}</td>
                            <td style="color: #00ff88">${(s.win_rate || 0).toFixed(1)}%</td>
                            <td style="color: #00ff88">+₹${(s.expected_pnl || 0).toLocaleString()}</td>
                        </tr>
                    `).join('');
                }
                
                document.getElementById('last-update').textContent = 
                    new Date().toLocaleTimeString('en-IN', {hour12: false});
            } catch(e) {
                console.error(e);
            }
        }
        
        fetchData();
        setInterval(fetchData, 10000);
    </script>
</body>
</html>
"""


@app.route('/')
def index():
    return render_template_string(DASHBOARD_HTML)


@app.route('/api/dashboard')
def api_dashboard():
    return jsonify(get_dashboard_data())


@app.route('/api/health')
def api_health():
    return jsonify({
        'status': 'ok',
        'strategy': 'Gold 93% Win Rate',
        'segment': 'EQUITY',
        'exchange': 'NSE',
        'broker': 'Angel One'
    })


@app.route('/api/watchlist')
def api_watchlist():
    try:
        with open("config/smart_watchlist.json", 'r') as f:
            return jsonify(json.load(f))
    except:
        return jsonify({'active_stocks': []})


def run_stock_bot():
    """Run stock trading bot in background"""
    try:
        import schedule
        from stock_trading_bot import StockTradingBot
        
        logger.info("📈 Starting stock bot in background...")
        bot = StockTradingBot()
        bot.run()
    except Exception as e:
        logger.error(f"Stock bot error: {e}")


def run_scheduler():
    """Run weekly scheduler"""
    try:
        import schedule
        
        # Weekly scan on Monday
        def weekly_scan():
            try:
                from smart_stock_selector import run_smart_selector
                logger.info("🔍 Running weekly stock scan...")
                run_smart_selector(capital=10000, min_win_rate=80, leverage=5)
            except Exception as e:
                logger.error(f"Scan error: {e}")
        
        schedule.every().monday.at("08:00").do(weekly_scan)
        
        while True:
            schedule.run_pending()
            time.sleep(60)
    except Exception as e:
        logger.error(f"Scheduler error: {e}")


def main():
    """Main entry point"""
    logger.info("="*50)
    logger.info("🚀 RAILWAY TRADING BOT STARTING")
    logger.info(f"📊 Strategy: Gold 93% Win Rate")
    logger.info(f"📈 Segment: EQUITY | Exchange: NSE")
    logger.info("="*50)
    
    # Send startup notification
    try:
        from utils.notifications import send_telegram_message
        now = datetime.now(IST)
        send_telegram_message(f"""
🚀 *TRADING BOT STARTED*

Strategy: Gold 93% Win Rate
Segment: EQUITY | Exchange: NSE
Product: MIS Intraday
Broker: Angel One

Time: {now.strftime('%Y-%m-%d %H:%M')} IST
""")
    except:
        pass
    
    # Start stock bot in background
    bot_thread = threading.Thread(target=run_stock_bot, daemon=True)
    bot_thread.start()
    logger.info("📈 Stock bot thread started")
    
    # Start scheduler in background
    scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
    scheduler_thread.start()
    logger.info("📅 Scheduler thread started")
    
    # Run Flask in main thread (required for Railway PORT)
    port = int(os.environ.get('PORT', 5050))
    logger.info(f"🌐 Dashboard starting on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)


if __name__ == "__main__":
    main()
