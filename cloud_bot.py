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
from datetime import datetime, date, timedelta, time as dtime, timezone
from typing import Optional, List
from loguru import logger
import sys

# IST timezone (UTC+5:30)
IST = timezone(timedelta(hours=5, minutes=30))

# Setup logging for cloud
logger.remove()
logger.add(sys.stdout, format="{time:HH:mm:ss} | {level} | {message}", level="INFO")
logger.add("logs/cloud_bot.log", rotation="1 day", retention="7 days")

from core.risk_manager import RiskManager
from core.data_fetcher import DataFetcher
from core.zerodha_client import get_zerodha_client
from strategies.multi_confirmation import MultiConfirmationScalper
from config.settings import TRADING_CAPITAL, STOCK_WATCHLIST
from utils.stock_optimizer import StockOptimizer
from utils.pro_trading import (
    BrokerageCalculator, MarketSentimentFilter, TimeFilter, 
    TrailingStopLoss, is_trade_profitable
)
from utils.notifications import send_trade_alert, send_exit_alert, send_daily_summary


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
        self.today_charges = 0.0  # Track brokerage
        self.is_authenticated = False
        self.client = None
        
        # Current watchlist (updated weekly)
        self.current_watchlist = list(STOCK_WATCHLIST)
        self.stock_optimizer = StockOptimizer(capital=self.capital)
        self.last_optimization_date = None
        
        # Professional trading features
        self.market_filter = MarketSentimentFilter()
        self.last_sentiment_check = None
        
        # Market hours (IST)
        self.market_open = dtime(9, 15)
        self.trade_start = dtime(9, 45)  # Changed: Start after 9:45 (avoid opening volatility)
        self.trade_end = dtime(14, 15)   # Changed: End before 2:15 (avoid closing volatility)
        self.market_close = dtime(15, 30)
    
    def weekly_stock_optimization(self):
        """Run weekly stock optimization - called every Sunday"""
        today = date.today()
        
        # Only run on Sunday
        if today.weekday() != 6:
            return
        
        # Only run once per week
        if self.last_optimization_date == today:
            return
        
        logger.info("="*50)
        logger.info("🔄 WEEKLY STOCK OPTIMIZATION - SUNDAY")
        logger.info("="*50)
        
        try:
            # Run optimization
            best_stocks, report = self.stock_optimizer.get_recommendation()
            
            if best_stocks:
                old_watchlist = self.current_watchlist.copy()
                self.current_watchlist = best_stocks
                
                logger.info(f"📋 Old watchlist: {', '.join(old_watchlist)}")
                logger.info(f"📋 New watchlist: {', '.join(best_stocks)}")
                
                # Log which stocks changed
                added = set(best_stocks) - set(old_watchlist)
                removed = set(old_watchlist) - set(best_stocks)
                
                if added:
                    logger.info(f"✅ Added: {', '.join(added)}")
                if removed:
                    logger.info(f"❌ Removed: {', '.join(removed)}")
                if not added and not removed:
                    logger.info("✅ No changes - current stocks are best!")
                
                self.last_optimization_date = today
                logger.info("✅ Weekly optimization complete!")
            else:
                logger.warning("⚠️ Optimization returned no stocks - keeping current")
                
        except Exception as e:
            logger.error(f"❌ Optimization error: {e}")
            logger.info("Keeping current watchlist")
        
        logger.info("="*50)
    
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
        """Check if market is open (IST timezone)"""
        now = datetime.now(IST)
        
        # Weekend check
        if now.weekday() >= 5:
            return False
        
        current_time = now.time()
        return self.market_open <= current_time <= self.market_close
    
    def is_trading_time(self) -> bool:
        """Check if it's time to take trades (IST timezone)"""
        now = datetime.now(IST)
        
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
        
        # Time filter - avoid volatile periods
        is_safe, time_reason = TimeFilter.is_safe_time()
        if not is_safe:
            logger.info(f"⏰ Skipping scan: {time_reason}")
            return
        
        # Update market sentiment (once per hour)
        now = datetime.now()
        if self.last_sentiment_check is None or (now - self.last_sentiment_check).seconds > 3600:
            self.market_filter.update()
            self.last_sentiment_check = now
        
        logger.info(f"🔍 Scanning {len(self.current_watchlist)} stocks... (Sentiment: {self.market_filter.sentiment})")
        
        for symbol in self.current_watchlist:
            try:
                data = self.data_fetcher.get_ohlc_data(symbol, "5minute", 5)
                if data is None or len(data) < 30:
                    continue
                
                data = self.strategy.calculate_indicators(data)
                signal = self.strategy.analyze(symbol, data)
                
                if signal:
                    # Check market sentiment
                    can_trade, sentiment_reason = self.market_filter.should_trade(signal.signal.value)
                    if not can_trade:
                        logger.info(f"⚠️ Skipping {symbol}: {sentiment_reason}")
                        continue
                    
                    # Check if trade is profitable after brokerage
                    is_profitable, profit_reason = is_trade_profitable(
                        signal.entry_price, signal.target, signal.quantity, min_profit=20
                    )
                    if not is_profitable:
                        logger.info(f"⚠️ Skipping {symbol}: {profit_reason}")
                        continue
                    
                    self.process_signal(signal)
                    
            except Exception as e:
                logger.error(f"Error scanning {symbol}: {e}")
    
    def process_signal(self, signal):
        """Process a trading signal"""
        logger.info(f"📢 SIGNAL: {signal.signal.value} {signal.symbol}")
        logger.info(f"   Entry: ₹{signal.entry_price} | SL: ₹{signal.stop_loss} | Target: ₹{signal.target}")
        logger.info(f"   Quantity: {signal.quantity} | Confidence: {signal.confidence:.0f}%")
        
        # Calculate expected profit after brokerage
        charges = BrokerageCalculator.calculate(
            signal.entry_price, signal.target, signal.quantity
        )
        logger.info(f"   Expected Net P&L: ₹{charges['net_pnl']:+.2f} (Charges: ₹{charges['total_charges']:.2f})")
        
        # Send Telegram alert
        try:
            send_trade_alert(
                action=signal.signal.value,
                symbol=signal.symbol,
                entry=signal.entry_price,
                sl=signal.stop_loss,
                target=signal.target,
                qty=signal.quantity
            )
        except Exception as e:
            logger.debug(f"Telegram notification failed: {e}")
        
        # EXECUTE ORDER if in AUTO mode and authenticated
        trading_mode = os.getenv('TRADING_MODE', 'paper').lower()
        if trading_mode == 'auto' and self.is_authenticated and self.client:
            try:
                logger.info(f"🛒 Placing {signal.signal.value} order for {signal.symbol}...")
                
                # Place market order
                order_id = self.client.place_order(
                    variety="regular",
                    exchange="NSE",
                    tradingsymbol=signal.symbol,
                    transaction_type="BUY" if signal.signal.value == "BUY" else "SELL",
                    quantity=signal.quantity,
                    product="MIS",  # Intraday
                    order_type="MARKET"
                )
                
                logger.info(f"✅ ORDER PLACED! Order ID: {order_id}")
                logger.info(f"   {signal.signal.value} {signal.quantity} x {signal.symbol} @ MARKET")
                
                # Send Telegram confirmation
                try:
                    from utils.notifications import send_telegram_message
                    send_telegram_message(f"✅ ORDER EXECUTED!\n\n{signal.signal.value} {signal.quantity} x {signal.symbol}\nOrder ID: {order_id}")
                except:
                    pass
                    
            except Exception as e:
                logger.error(f"❌ Order failed: {e}")
                try:
                    from utils.notifications import send_telegram_message
                    send_telegram_message(f"❌ Order failed for {signal.symbol}: {e}")
                except:
                    pass
        else:
            if trading_mode != 'auto':
                logger.info(f"   Mode: {trading_mode.upper()} - Not executing order")
            elif not self.is_authenticated:
                logger.warning(f"   ⚠️ Not authenticated - Cannot execute order")
        
        # Record trade
        self.today_trades.append({
            "symbol": signal.symbol,
            "action": signal.signal.value,
            "entry": signal.entry_price,
            "target": signal.target,
            "sl": signal.stop_loss,
            "qty": signal.quantity,
            "expected_charges": charges['total_charges'],
            "time": datetime.now().strftime("%H:%M:%S")
        })
        
        # Add estimated charges
        self.today_charges += charges['total_charges']
        
        self.risk_manager.record_trade_entry()
    
    def daily_summary(self):
        """Print daily summary with brokerage included"""
        logger.info("="*50)
        logger.info("📊 DAILY SUMMARY")
        logger.info("="*50)
        logger.info(f"Date: {date.today()}")
        logger.info(f"Trades: {len(self.today_trades)}")
        logger.info(f"Gross P&L: ₹{self.today_pnl:+,.2f}")
        logger.info(f"Brokerage/Charges: ₹{self.today_charges:.2f}")
        net_pnl = self.today_pnl - self.today_charges
        logger.info(f"NET P&L: ₹{net_pnl:+,.2f}")
        logger.info("="*50)
        
        # Send Telegram summary
        try:
            stats = {
                'trades': len(self.today_trades),
                'gross_profit': max(0, self.today_pnl),
                'gross_loss': abs(min(0, self.today_pnl)),
                'net_pnl': net_pnl
            }
            send_daily_summary(stats)
        except Exception as e:
            logger.debug(f"Telegram summary failed: {e}")
    
    def reset_daily(self):
        """Reset for new trading day"""
        self.today_trades = []
        self.today_pnl = 0.0
        self.today_charges = 0.0
        self.risk_manager = RiskManager(self.capital)
        self.last_sentiment_check = None
        logger.info("🔄 Daily reset complete")
    
    def run(self):
        """Main run loop"""
        logger.info("="*50)
        logger.info("🤖 CLOUD TRADING BOT STARTED")
        logger.info("="*50)
        logger.info(f"💰 Capital: ₹{self.capital:,.2f}")
        logger.info(f"📊 Mode: {os.getenv('TRADING_MODE', 'paper').upper()}")
        logger.info(f"📋 Stocks: {', '.join(self.current_watchlist)}")
        
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
        
        # Show current IST time and trading status
        ist_now = datetime.now(IST)
        logger.info(f"🕐 Current IST Time: {ist_now.strftime('%H:%M:%S')}")
        logger.info(f"📅 Trading Window: 9:45 AM - 2:15 PM IST")
        
        # Check if in trading window
        if self.is_trading_time():
            logger.info("🟢 STATUS: ACTIVELY LOOKING FOR TRADES!")
        elif self.is_market_open():
            logger.info("🟡 STATUS: Market open, waiting for trading window (9:45 AM)")
        else:
            logger.info("🔴 STATUS: Outside market hours, waiting...")
        
        # Run weekly optimization if today is Sunday
        self.weekly_stock_optimization()
        
        # Schedule jobs
        schedule.every().day.at("09:15").do(lambda: logger.info("🔔 Market Open!"))
        schedule.every().day.at("09:45").do(lambda: logger.info("🟢 Trading window started! Actively looking for trades..."))
        schedule.every().day.at("09:30").do(self.scan_for_signals)
        schedule.every(5).minutes.do(self.scan_for_signals)
        schedule.every().day.at("14:15").do(lambda: logger.info("🟡 Trading window ended. No new trades."))
        schedule.every().day.at("15:30").do(self.daily_summary)
        schedule.every().day.at("00:01").do(self.reset_daily)
        
        # Sunday: Weekly stock optimization at 6 PM
        schedule.every().sunday.at("18:00").do(self.weekly_stock_optimization)
        
        logger.info("✅ Bot running...")
        logger.info("📅 Weekly optimization: Every Sunday at 6 PM")
        
        # Immediate scan if in trading window
        if self.is_trading_time():
            logger.info("🔄 Running initial scan...")
            self.scan_for_signals()
        
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
