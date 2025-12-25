#!/usr/bin/env python3
"""
🚀 UNIFIED TRADING BOT - MAIN ENTRY POINT
==========================================

This runs:
1. Weekly Stock Selector (Every Monday 8 AM)
2. Stock Trading Bot (Mon-Fri 9:15 AM - 3:30 PM)
3. Web Dashboard (Always running)
4. Telegram Notifications

Usage:
    python main.py                    # Run full bot
    python main.py --stock-only       # Run only stock bot
    python main.py --scan-now         # Run stock scan immediately
    
Deployment:
    Railway/Cloud: python main.py
"""

import os
import sys
import time
import json
import threading
import pytz
from datetime import datetime, timedelta
from loguru import logger
import schedule

# Add project root
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

IST = pytz.timezone('Asia/Kolkata')

# Setup logging
os.makedirs("logs", exist_ok=True)
os.makedirs("data", exist_ok=True)
os.makedirs("config", exist_ok=True)

logger.remove()
logger.add(sys.stdout, format="{time:HH:mm:ss} | {level} | {message}", level="INFO")
logger.add("logs/main_{time:YYYY-MM-DD}.log", rotation="1 day", retention="7 days", level="INFO")


class TradingPipeline:
    """Main trading pipeline that orchestrates everything"""
    
    def __init__(self):
        self.stock_bot = None
        self.weekly_scheduler = None
        self.dashboard_thread = None
        self.stock_bot_thread = None
        self.is_running = False
    
    def check_watchlist_exists(self):
        """Check if watchlist exists, create if needed"""
        watchlist_file = "config/smart_watchlist.json"
        
        if not os.path.exists(watchlist_file):
            logger.info("📋 No watchlist found. Running initial stock scan...")
            self.run_stock_scan()
            return os.path.exists(watchlist_file)
        
        # Check if watchlist is recent (within 7 days)
        try:
            with open(watchlist_file, 'r') as f:
                data = json.load(f)
                last_updated = data.get('last_updated', '')
                if last_updated:
                    last_date = datetime.strptime(last_updated.split()[0], '%Y-%m-%d')
                    days_old = (datetime.now() - last_date).days
                    if days_old > 7:
                        logger.info(f"📋 Watchlist is {days_old} days old. Refreshing...")
                        self.run_stock_scan()
        except Exception as e:
            logger.warning(f"Error checking watchlist age: {e}")
        
        return True
    
    def run_stock_scan(self):
        """Run the smart stock selector"""
        try:
            from smart_stock_selector import run_smart_selector
            
            # Try to get capital from Angel One
            capital = 10000
            try:
                from core.angel_client import AngelClient
                client = AngelClient()
                if client.authenticate():
                    balance = client.get_margin()
                    if balance and balance > 1000:
                        capital = int(balance)
            except:
                pass
            
            logger.info(f"🔍 Running stock scan with capital: Rs {capital:,}")
            
            qualified = run_smart_selector(
                capital=capital,
                min_win_rate=80,
                leverage=5
            )
            
            if qualified:
                # Send Telegram notification
                try:
                    from utils.notifications import send_telegram_message
                    stocks_list = ", ".join([s['name'] for s in qualified[:5]])
                    msg = f"""
🏆 *WEEKLY STOCKS SELECTED*

{len(qualified)} stocks qualified (80%+ WR):
{stocks_list}

Trading will start at 9:15 AM
"""
                    send_telegram_message(msg)
                except Exception as e:
                    logger.warning(f"Telegram notification failed: {e}")
            
            return qualified
            
        except Exception as e:
            logger.error(f"Stock scan failed: {e}")
            return None
    
    def start_dashboard(self):
        """Start the web dashboard"""
        try:
            from dashboard import run_dashboard
            port = int(os.environ.get('PORT', 5050))
            run_dashboard(port)
        except Exception as e:
            logger.error(f"Dashboard error: {e}")
            # Fallback to simple dashboard
            try:
                from flask import Flask, jsonify
                
                app = Flask(__name__)
                
                @app.route('/')
                def home():
                    return """
                    <html>
                    <head><title>Trading Bot Dashboard</title></head>
                    <body style="font-family:Arial; padding:20px; background:#1e1e1e; color:#fff;">
                        <h1>📈 Trading Bot Dashboard</h1>
                        <p>Bot Status: 🟢 Running</p>
                        <p>View <a href="/api/status" style="color:#00ff00;">API Status</a></p>
                        <p>View <a href="/api/watchlist" style="color:#00ff00;">Watchlist</a></p>
                    </body>
                    </html>
                    """
                
                port = int(os.environ.get('PORT', 5050))
                logger.info(f"🌐 Fallback dashboard on port {port}")
                app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)
                
            except Exception as fallback_error:
                logger.error(f"Fallback dashboard also failed: {fallback_error}")
    
    def is_trading_hours(self):
        """Check if within trading hours"""
        now = datetime.now(IST)
        
        # Skip weekends
        if now.weekday() >= 5:
            return False
        
        # Market hours: 9:15 AM - 3:30 PM
        market_open = now.replace(hour=9, minute=15, second=0, microsecond=0)
        market_close = now.replace(hour=15, minute=30, second=0, microsecond=0)
        
        return market_open <= now <= market_close
    
    def is_scan_time(self):
        """Check if it's time for weekly scan (Monday 8 AM)"""
        now = datetime.now(IST)
        return now.weekday() == 0 and 7 <= now.hour <= 9
    
    def start_stock_bot(self):
        """Start the stock trading bot"""
        try:
            from stock_trading_bot import StockTradingBot
            
            bot = StockTradingBot()
            bot.run()
            
        except Exception as e:
            logger.error(f"Stock bot error: {e}")
    
    def run_scheduled_tasks(self):
        """Run scheduled tasks"""
        # Weekly stock scan - Monday 8 AM
        schedule.every().monday.at("08:00").do(self.run_stock_scan)
        
        # Daily health check
        schedule.every().day.at("09:00").do(self.health_check)
        
        while self.is_running:
            try:
                schedule.run_pending()
                time.sleep(30)
            except Exception as e:
                logger.error(f"Scheduler error: {e}")
                time.sleep(60)
    
    def health_check(self):
        """Daily health check"""
        now = datetime.now(IST)
        logger.info(f"💓 Health check at {now.strftime('%Y-%m-%d %H:%M')}")
        
        # Check watchlist
        self.check_watchlist_exists()
        
        # Send Telegram ping
        try:
            from utils.notifications import send_telegram_message
            send_telegram_message(f"💓 Bot health check OK at {now.strftime('%H:%M')}")
        except:
            pass
    
    def run(self, stock_only=False, scan_now=False):
        """Main run method"""
        logger.info("="*60)
        logger.info("🚀 UNIFIED TRADING BOT STARTING")
        logger.info("="*60)
        
        now = datetime.now(IST)
        logger.info(f"⏰ Current Time: {now.strftime('%Y-%m-%d %H:%M:%S')} IST")
        
        # Send startup message
        try:
            from utils.notifications import send_telegram_message
            send_telegram_message(f"""
🚀 *TRADING BOT STARTED*

Time: {now.strftime('%Y-%m-%d %H:%M')} IST
Mode: {'Stock Only' if stock_only else 'Full Pipeline'}

Components:
• Weekly Scanner: ✅
• Stock Bot: ✅
• Dashboard: ✅
• Telegram: ✅
""")
        except Exception as e:
            logger.warning(f"Telegram notification failed: {e}")
        
        self.is_running = True
        
        # Run immediate scan if requested
        if scan_now:
            logger.info("📋 Running immediate stock scan...")
            self.run_stock_scan()
        
        # Check and create watchlist if needed
        self.check_watchlist_exists()
        
        # Start dashboard in background
        if not stock_only:
            self.dashboard_thread = threading.Thread(target=self.start_dashboard, daemon=True)
            self.dashboard_thread.start()
            logger.info("🌐 Dashboard thread started")
            time.sleep(2)
        
        # Start scheduler in background
        scheduler_thread = threading.Thread(target=self.run_scheduled_tasks, daemon=True)
        scheduler_thread.start()
        logger.info("📅 Scheduler thread started")
        
        # Run stock bot in main thread
        logger.info("📈 Starting stock trading bot...")
        self.start_stock_bot()


def main():
    """Entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Unified Trading Bot')
    parser.add_argument('--stock-only', action='store_true', help='Run only stock bot')
    parser.add_argument('--scan-now', action='store_true', help='Run stock scan immediately')
    parser.add_argument('--scan-only', action='store_true', help='Just run scan and exit')
    
    args = parser.parse_args()
    
    if args.scan_only:
        # Just run scan and exit
        pipeline = TradingPipeline()
        pipeline.run_stock_scan()
        return
    
    # Run full pipeline
    pipeline = TradingPipeline()
    pipeline.run(stock_only=args.stock_only, scan_now=args.scan_now)


if __name__ == "__main__":
    main()
