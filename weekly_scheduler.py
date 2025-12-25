#!/usr/bin/env python3
"""
📅 WEEKLY STOCK SCHEDULER
=========================

This runs every Sunday night / Monday morning to:
1. Run smart_stock_selector.py
2. Update the watchlist with 80%+ win rate stocks
3. Send Telegram notification

Usage:
    python weekly_scheduler.py          # Run manually
    python weekly_scheduler.py --now    # Force run now
"""

import os
import sys
import json
import schedule
import time
import pytz
from datetime import datetime
from loguru import logger

# Add project root
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.notifications import send_telegram_message
from smart_stock_selector import run_smart_selector

IST = pytz.timezone('Asia/Kolkata')

class WeeklyScheduler:
    """Runs stock selection every Monday morning"""
    
    def __init__(self):
        self.last_run = None
        
        # Setup logger
        os.makedirs("logs", exist_ok=True)
        logger.add(
            "logs/weekly_scheduler_{time:YYYY-MM-DD}.log",
            rotation="1 week",
            retention="4 weeks",
            level="INFO"
        )
    
    def get_capital_from_angel(self):
        """Get current capital from Angel One"""
        try:
            from core.angel_client import AngelClient
            client = AngelClient()
            if client.authenticate():
                balance = client.get_margin()
                if balance:
                    logger.info(f"Angel One balance: Rs {balance:,.2f}")
                    return balance
        except Exception as e:
            logger.warning(f"Could not get Angel balance: {e}")
        
        # Default capital
        return 10000
    
    def run_weekly_selection(self):
        """Run the weekly stock selection"""
        logger.info("="*60)
        logger.info("📅 WEEKLY STOCK SELECTION STARTED")
        logger.info("="*60)
        
        now = datetime.now(IST)
        logger.info(f"Time: {now.strftime('%Y-%m-%d %H:%M:%S')} IST")
        
        # Get capital from Angel One
        capital = self.get_capital_from_angel()
        
        # Send starting message
        send_telegram_message(f"""
📅 *WEEKLY STOCK SELECTION*

Starting stock scan...
Capital: Rs {capital:,}
Min Win Rate: 80%

Please wait 2-3 minutes...
""")
        
        try:
            # Run the smart selector
            qualified_stocks = run_smart_selector(
                capital=capital,
                min_win_rate=80,
                leverage=5
            )
            
            if qualified_stocks:
                # Build summary message
                stocks_list = "\n".join([
                    f"• {s['name']}: {s['win_rate']}% WR, Rs {s['pnl']:+,.0f}"
                    for s in qualified_stocks[:10]
                ])
                
                total_pnl = sum([s['pnl'] for s in qualified_stocks])
                avg_wr = sum([s['win_rate'] for s in qualified_stocks]) / len(qualified_stocks)
                
                msg = f"""
🏆 *WEEKLY STOCKS SELECTED*

📊 *{len(qualified_stocks)} Qualified Stocks (80%+ WR)*

{stocks_list}

📈 *Summary:*
Average Win Rate: {avg_wr:.1f}%
Expected 2-Week P&L: Rs {total_pnl:+,.0f}
Monthly Projection: Rs {total_pnl * 2:+,.0f}

✅ Watchlist updated!
Trading starts Monday 9:15 AM
"""
                send_telegram_message(msg)
                
                self.last_run = now
                logger.info(f"Selection complete: {len(qualified_stocks)} stocks qualified")
                
            else:
                send_telegram_message("""
⚠️ *NO STOCKS QUALIFIED*

No stocks met the 80% win rate criteria.
Try again next week or lower the threshold.
""")
                logger.warning("No stocks qualified")
                
        except Exception as e:
            logger.error(f"Error in weekly selection: {e}")
            send_telegram_message(f"❌ Weekly selection failed: {str(e)[:100]}")
    
    def check_and_run(self):
        """Check if it's time to run (Monday 8 AM)"""
        now = datetime.now(IST)
        
        # Run on Monday around 8 AM
        if now.weekday() == 0 and 7 <= now.hour <= 9:
            # Check if already run today
            if self.last_run:
                if self.last_run.date() == now.date():
                    return  # Already ran today
            
            self.run_weekly_selection()
    
    def run_scheduler(self):
        """Run the scheduler loop"""
        logger.info("📅 Weekly Scheduler Started")
        logger.info("Will run every Monday at 8:00 AM IST")
        
        # Schedule for Monday 8 AM
        schedule.every().monday.at("08:00").do(self.run_weekly_selection)
        
        # Also check every hour in case we missed it
        schedule.every().hour.do(self.check_and_run)
        
        while True:
            try:
                schedule.run_pending()
                time.sleep(60)
            except KeyboardInterrupt:
                logger.info("Scheduler stopped")
                break
            except Exception as e:
                logger.error(f"Scheduler error: {e}")
                time.sleep(300)


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Weekly Stock Scheduler')
    parser.add_argument('--now', action='store_true', help='Run selection immediately')
    parser.add_argument('--capital', type=int, help='Override capital')
    
    args = parser.parse_args()
    
    scheduler = WeeklyScheduler()
    
    if args.now:
        # Run immediately
        scheduler.run_weekly_selection()
    else:
        # Run scheduler loop
        scheduler.run_scheduler()


if __name__ == "__main__":
    main()
