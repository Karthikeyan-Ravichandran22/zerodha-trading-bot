"""
CLOUD TRADING BOT - Optimized for Railway/Cloud Deployment

This version:
- Runs continuously in the cloud
- Checks time to only trade during market hours
- Logs everything for monitoring
- Handles Zerodha daily login
"""

import os
import time
import schedule
from datetime import datetime, date, timedelta, time as dtime
from typing import Optional, List
from loguru import logger
import sys

# Setup logging for cloud
logger.remove()
logger.add(sys.stdout, format="{time:HH:mm:ss} | {level} | {message}", level="INFO")
logger.add("logs/cloud_bot.log", rotation="1 day", retention="7 days")

from core.risk_manager import RiskManager
from core.data_fetcher import DataFetcher
from core.zerodha_client import get_zerodha_client
from strategies.multi_confirmation import MultiConfirmationScalper
from config.settings import TRADING_CAPITAL, STOCK_WATCHLIST


class CloudTradingBot:
    """Trading bot optimized for cloud deployment"""
    
    def __init__(self):
        self.capital = TRADING_CAPITAL
        self.risk_manager = RiskManager(self.capital)
        self.data_fetcher = DataFetcher()
        self.strategy = MultiConfirmationScalper(
            data_fetcher=self.data_fetcher,
            risk_manager=self.risk_manager
        )
        
        self.today_trades = []
        self.today_pnl = 0.0
        self.is_authenticated = False
        self.client = None
        
        # Market hours (IST)
        self.market_open = dtime(9, 15)
        self.trade_start = dtime(9, 30)
        self.trade_end = dtime(14, 30)
        self.market_close = dtime(15, 30)
    
    def authenticate_zerodha(self):
        """Authenticate with Zerodha using request_token or access_token"""
        try:
            self.client = get_zerodha_client()
            self.client.initialize()
            
            # Check for request_token first (needs conversion)
            request_token = os.getenv("REQUEST_TOKEN", "")
            access_token = os.getenv("ZERODHA_ACCESS_TOKEN", "")
            
            if request_token:
                logger.info("🔑 Found REQUEST_TOKEN, converting to access_token...")
                if self.client.authenticate(request_token):
                    self.is_authenticated = True
                    logger.info("✅ Zerodha authenticated successfully!")
                    return True
                else:
                    logger.error("❌ Failed to authenticate with request_token")
            elif access_token:
                # Try using saved access_token
                self.client.kite.set_access_token(access_token)
                self.is_authenticated = True
                logger.info("✅ Using saved access_token")
                return True
            else:
                logger.warning("⚠️ No token found. Add REQUEST_TOKEN or ZERODHA_ACCESS_TOKEN to Railway variables")
            
            return False
        except Exception as e:
            logger.error(f"Authentication error: {e}")
            return False
        
        
    def is_market_open(self) -> bool:
        """Check if market is open"""
        now = datetime.now()
        
        # Weekend check
        if now.weekday() >= 5:
            return False
        
        current_time = now.time()
        return self.market_open <= current_time <= self.market_close
    
    def is_trading_time(self) -> bool:
        """Check if it's time to take trades"""
        now = datetime.now()
        
        if now.weekday() >= 5:
            return False
            
        current_time = now.time()
        return self.trade_start <= current_time <= self.trade_end
    
    def scan_for_signals(self):
        """Scan all stocks for signals"""
        if not self.is_trading_time():
            return
        
        # Check daily limits
        can_trade, reason = self.risk_manager.can_take_trade()
        if not can_trade:
            logger.warning(f"Cannot trade: {reason}")
            return
        
        logger.info(f"🔍 Scanning {len(STOCK_WATCHLIST)} stocks...")
        
        for symbol in STOCK_WATCHLIST:
            try:
                data = self.data_fetcher.get_ohlc_data(symbol, "5minute", 5)
                if data is None or len(data) < 30:
                    continue
                
                data = self.strategy.calculate_indicators(data)
                signal = self.strategy.analyze(symbol, data)
                
                if signal:
                    self.process_signal(signal)
                    
            except Exception as e:
                logger.error(f"Error scanning {symbol}: {e}")
    
    def process_signal(self, signal):
        """Process a trading signal"""
        logger.info(f"📢 SIGNAL: {signal.signal.value} {signal.symbol}")
        logger.info(f"   Entry: ₹{signal.entry_price} | SL: ₹{signal.stop_loss} | Target: ₹{signal.target}")
        logger.info(f"   Quantity: {signal.quantity} | Confidence: {signal.confidence:.0f}%")
        
        # Paper trade - just log it
        self.today_trades.append({
            "symbol": signal.symbol,
            "action": signal.signal.value,
            "entry": signal.entry_price,
            "qty": signal.quantity,
            "time": datetime.now().strftime("%H:%M:%S")
        })
        
        self.risk_manager.record_trade_entry()
    
    def daily_summary(self):
        """Print daily summary"""
        logger.info("="*50)
        logger.info("📊 DAILY SUMMARY")
        logger.info("="*50)
        logger.info(f"Date: {date.today()}")
        logger.info(f"Trades: {len(self.today_trades)}")
        logger.info(f"P&L: ₹{self.today_pnl:+,.2f}")
        logger.info("="*50)
    
    def reset_daily(self):
        """Reset for new trading day"""
        self.today_trades = []
        self.today_pnl = 0.0
        self.risk_manager = RiskManager(self.capital)
        logger.info("🔄 Daily reset complete")
    
    def run(self):
        """Main run loop"""
        logger.info("="*50)
        logger.info("🤖 CLOUD TRADING BOT STARTED")
        logger.info("="*50)
        logger.info(f"💰 Capital: ₹{self.capital:,.2f}")
        logger.info(f"📊 Mode: {os.getenv('TRADING_MODE', 'paper').upper()}")
        logger.info(f"📋 Stocks: {', '.join(STOCK_WATCHLIST[:5])}...")
        
        # Authenticate with Zerodha
        self.authenticate_zerodha()
        
        # Try to get Zerodha balance
        if self.is_authenticated and self.client:
            try:
                margins = self.client.get_margins()
                if margins and 'equity' in margins:
                    available = margins['equity'].get('available', {}).get('live_balance', 0)
                    logger.info(f"🏦 Zerodha Balance: ₹{available:,.2f}")
                else:
                    logger.info("🏦 Zerodha Balance: ₹0.00")
            except Exception as e:
                logger.info(f"🏦 Balance check failed: {e}")
        else:
            logger.info("🏦 Zerodha: Not authenticated - Add REQUEST_TOKEN in Railway")
        
        logger.info("="*50)
        
        # Schedule jobs
        schedule.every().day.at("09:15").do(lambda: logger.info("🔔 Market Open!"))
        schedule.every().day.at("09:30").do(self.scan_for_signals)
        schedule.every(5).minutes.do(self.scan_for_signals)
        schedule.every().day.at("15:30").do(self.daily_summary)
        schedule.every().day.at("00:01").do(self.reset_daily)
        
        logger.info("✅ Bot running. Waiting for market hours...")
        
        while True:
            try:
                schedule.run_pending()
                
                now = datetime.now()
                
                # Status update every hour during market
                if now.minute == 0 and self.is_market_open():
                    logger.info(f"⏰ Status: {now.strftime('%H:%M')} | Trades: {len(self.today_trades)}")
                
                time.sleep(60)  # Check every minute
                
            except KeyboardInterrupt:
                logger.info("🛑 Shutting down...")
                break
            except Exception as e:
                logger.error(f"Error: {e}")
                time.sleep(60)


def main():
    """Entry point"""
    bot = CloudTradingBot()
    bot.run()


if __name__ == "__main__":
    main()
