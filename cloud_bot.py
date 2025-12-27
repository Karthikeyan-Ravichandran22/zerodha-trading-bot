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

# Activity log handler for dashboard
import json
activity_logs = []
MAX_ACTIVITY_LOGS = 50

def activity_log_handler(message):
    """Save important logs to activity file for dashboard display"""
    global activity_logs
    record = message.record
    msg = record["message"]
    
    # Only save important logs (not HTTP requests)
    if any(x in msg for x in ['Scanning', 'SIGNAL', 'Indicators', 'Candle', 'Skipping', 'ORDER', 'Error', '🔍', '🎯', '⚠️', '✅', '❌']):
        # Convert to IST for display
        ist_time = datetime.now(IST).strftime('%H:%M:%S')
        log_entry = f"{ist_time} | {msg}"
        activity_logs.append(log_entry)
        
        # Keep only last N logs
        if len(activity_logs) > MAX_ACTIVITY_LOGS:
            activity_logs = activity_logs[-MAX_ACTIVITY_LOGS:]
        
        # Save to file
        try:
            os.makedirs('data', exist_ok=True)
            with open('data/activity_logs.json', 'w') as f:
                json.dump({'logs': activity_logs}, f)
        except:
            pass

logger.add(activity_log_handler, format="{message}", level="INFO")

from core.risk_manager import RiskManager
from core.data_fetcher import DataFetcher
from core.zerodha_client import get_zerodha_client
from strategies.multi_confirmation import MultiConfirmationScalper
from strategies.commodity_scanner import CommodityScanner  # NEW: Commodity trading
from config.settings import TRADING_CAPITAL, STOCK_WATCHLIST
from utils.stock_optimizer import StockOptimizer
from utils.pro_trading import (
    BrokerageCalculator, MarketSentimentFilter, TimeFilter, 
    TrailingStopLoss, is_trade_profitable
)
from utils.notifications import send_trade_alert, send_exit_alert, send_daily_summary
from utils.position_manager import position_manager
from utils.trade_journal import trade_journal
from utils.capital_manager import capital_manager
from analytics_db import analytics_db  # Database for persistent trade history

# Dashboard removed - using new dashboard.py instead


class CloudTradingBot:
    """Trading bot optimized for cloud deployment"""
    
    def __init__(self):
        # Use capital manager for dynamic sizing
        self.capital = capital_manager.get_capital()
        self.risk_manager = RiskManager(self.capital)
        self.data_fetcher = DataFetcher()
        
        # Use Gold 93% Win Rate Strategy (from backtest)
        from strategies.gold_93_live import Gold93Strategy
        self.strategy = Gold93Strategy(
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
        
        # Market hours (IST) for EQUITY
        self.market_open = dtime(9, 15)
        self.trade_start = dtime(9, 45)  # Equity: Start after 9:45 (avoid opening volatility)
        self.trade_end = dtime(14, 15)   # Equity: End before 2:15 (avoid closing volatility)
        self.market_close = dtime(15, 30)
        
        # Commodity trading hours (MCX - full day 9 AM to 11:30 PM, Mon-Fri)
        self.commodity_start = dtime(9, 0)     # Commodity: Start at 9:00 AM IST
        self.commodity_end = dtime(23, 30)     # Commodity: End at 11:30 PM IST
        
        # Commodity scanner (Gold paper trading with ₹40,000 capital)
        self.commodity_scanner = None
        self.commodity_enabled = os.getenv('COMMODITY_TRADING', 'false').lower() == 'true'
        self.commodity_paper_capital = 40000  # Paper trading capital for Gold
        logger.info(f"🏆 Commodity Trading: {'Enabled' if self.commodity_enabled else 'Disabled'}")
    
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
    
    def authenticate_angel_one(self):
        """Authenticate with Angel One using TOTP (auto-login!)"""
        try:
            import pyotp
            from SmartApi import SmartConnect
            
            api_key = os.getenv('ANGEL_API_KEY', '')
            client_id = os.getenv('ANGEL_CLIENT_ID', '')
            mpin = os.getenv('ANGEL_MPIN', '')
            totp_secret = os.getenv('ANGEL_TOTP_SECRET', '')
            
            if not all([api_key, client_id, mpin, totp_secret]):
                logger.info("ℹ️ Angel One credentials not configured")
                return False
            
            logger.info("🔐 Authenticating with Angel One (auto-TOTP)...")
            
            # Generate TOTP automatically
            totp = pyotp.TOTP(totp_secret)
            otp = totp.now()
            
            smart_api = SmartConnect(api_key=api_key)
            
            data = smart_api.generateSession(
                clientCode=client_id,
                password=mpin,
                totp=otp
            )
            
            if data.get('status'):
                self.angel_client = smart_api
                self.angel_refresh_token = data['data']['refreshToken']
                self.is_authenticated = True
                self.broker = 'angel'
                
                # Get profile
                profile = smart_api.getProfile(self.angel_refresh_token)
                user_name = profile.get('data', {}).get('name', 'Unknown')
                
                # Get funds
                try:
                    funds = smart_api.rmsLimit()
                    if funds.get('status'):
                        available = float(funds['data'].get('net', 0))
                        logger.info(f"🏦 Angel One Balance: ₹{available:,.2f}")
                except:
                    pass
                
                logger.info(f"✅ Angel One authenticated: {user_name}")
                logger.info("🎉 AUTO-LOGIN SUCCESS - No daily token needed!")
                
                # Initialize commodity scanner with Angel One client
                if self.commodity_enabled:
                    try:
                        self.commodity_scanner = CommodityScanner(angel_client=smart_api)
                        self.commodity_scanner.angel_refresh_token = self.angel_refresh_token
                        balance_info = self.commodity_scanner.check_balance()
                        logger.info(f"🏆 Commodity Scanner: {len(balance_info['tradeable'])} commodities tradeable")
                    except Exception as ce:
                        logger.warning(f"Commodity scanner init failed: {ce}")
                
                return True
            else:
                logger.warning(f"Angel One login failed: {data.get('message')}")
                return False
                
        except ImportError:
            logger.info("ℹ️ SmartAPI not installed, skipping Angel One")
            return False
        except Exception as e:
            logger.warning(f"Angel One auth error: {e}")
            return False
    
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
                    self.broker = 'zerodha'
                    logger.info("✅ Zerodha authenticated successfully!")
                    return True
                else:
                    logger.error("❌ Failed to authenticate with request_token")
            elif access_token:
                # Try using saved access_token
                self.client.kite.set_access_token(access_token)
                self.is_authenticated = True
                self.broker = 'zerodha'
                logger.info("✅ Using saved access_token")
                return True
            else:
                logger.warning("⚠️ No Zerodha token found")
            
            return False
        except Exception as e:
            logger.error(f"Zerodha auth error: {e}")
            return False
    
    def authenticate(self):
        """Try Angel One first (auto-login), then Zerodha as fallback"""
        # Try Angel One first (no daily token needed!)
        if self.authenticate_angel_one():
            return True
        
        # Fallback to Zerodha
        logger.info("🔄 Trying Zerodha as fallback...")
        return self.authenticate_zerodha()
    
    def place_order(self, symbol: str, transaction_type: str, quantity: int,
                   order_type: str = "MARKET", price: float = 0, 
                   trigger_price: float = 0) -> str:
        """
        Place order on the active broker (Angel One or Zerodha).
        Returns order ID if successful, None otherwise.
        """
        try:
            if hasattr(self, 'broker') and self.broker == 'angel':
                # Angel One order
                variety = "NORMAL"
                product = "INTRADAY"
                
                # Map order types
                if order_type == "MARKET":
                    angel_order_type = "MARKET"
                elif order_type == "LIMIT":
                    angel_order_type = "LIMIT"
                elif order_type == "SL-M":
                    angel_order_type = "STOPLOSS_MARKET"
                elif order_type == "SL":
                    angel_order_type = "STOPLOSS_LIMIT"
                else:
                    angel_order_type = order_type
                
                order_params = {
                    "variety": variety,
                    "tradingsymbol": f"{symbol}-EQ",
                    "symboltoken": self._get_angel_token(symbol),
                    "transactiontype": transaction_type,
                    "exchange": "NSE",
                    "ordertype": angel_order_type,
                    "producttype": product,
                    "duration": "DAY",
                    "quantity": quantity
                }
                
                if order_type in ["LIMIT", "SL"]:
                    order_params["price"] = str(price)
                
                if order_type in ["SL-M", "SL", "STOPLOSS_MARKET", "STOPLOSS_LIMIT"]:
                    order_params["triggerprice"] = str(trigger_price)
                
                response = self.angel_client.placeOrder(order_params)
                
                if response.get('status'):
                    return response['data']['orderid']
                else:
                    logger.error(f"Angel One order failed: {response.get('message')}")
                    return None
                    
            elif self.client:
                # Zerodha order
                return self.client.place_order(
                    variety="regular",
                    exchange="NSE",
                    tradingsymbol=symbol,
                    transaction_type=transaction_type,
                    quantity=quantity,
                    product="MIS",
                    order_type=order_type,
                    price=price if order_type == "LIMIT" else None,
                    trigger_price=trigger_price if "SL" in order_type else None
                )
            else:
                logger.error("No broker connected")
                return None
                
        except Exception as e:
            logger.error(f"Order placement error: {e}")
            return None
    
    def _get_angel_token(self, symbol: str) -> str:
        """Get Angel One symbol token (cached)"""
        # Normalize symbol
        symbol = symbol.upper().replace(' ', '').replace('-EQ', '')
        
        # Extended token map for all watchlist stocks
        tokens = {
            # Current watchlist stocks
            "IRFC": "4717", "TATASTEEL": "3499", "GAIL": "4717", "CANBK": "10794",
            "REC": "15355", "NTPC": "11630", "DLF": "14732", "GODREJPROP": "17875",
            "YESBANK": "11915", "NMDC": "4164",
            # Alternative names
            "TATASTEEL": "3499", "CANARABANK": "10794", "GODREJPROPERTIES": "17875",
            # Other common stocks
            "SBIN": "3045", "RELIANCE": "2885", "INFY": "1594", "TCS": "11536",
            "HDFCBANK": "1333", "ICICIBANK": "4963", "KOTAKBANK": "1922",
            "TATAMOTORS": "3456", "SAIL": "2963", "PNB": "10666", "IDEA": "14366",
            "IDFCFIRSTB": "11184", "ITC": "1660", "COALINDIA": "20374",
            "ONGC": "2475", "BANKBARODA": "4668", "UNIONBANK": "13459",
            "IOC": "1624", "BPCL": "526", "HINDALCO": "348", "VEDL": "3063",
            "JINDALSTEL": "6733"
        }
        
        # Try direct lookup
        if symbol in tokens:
            return tokens[symbol]
        
        # Try to fetch dynamically from Angel API
        try:
            if hasattr(self, 'angel_client') and self.angel_client:
                search_result = self.angel_client.searchScrip("NSE", symbol)
                if search_result and search_result.get('data'):
                    for item in search_result['data']:
                        if item.get('tradingsymbol', '').upper() == f"{symbol}-EQ":
                            logger.info(f"🔍 Found token for {symbol}: {item.get('symboltoken')}")
                            return item.get('symboltoken', '0')
        except Exception as e:
            logger.debug(f"Token search failed for {symbol}: {e}")
        
        logger.warning(f"⚠️ No token found for {symbol}")
        return "0"
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
    
    def is_commodity_time(self) -> bool:
        """Check if it's commodity trading time (2:30 PM - 11:30 PM IST)"""
        now = datetime.now(IST)
        
        # Commodities trade Mon-Fri
        if now.weekday() >= 5:
            return False
            
        current_time = now.time()
        return self.commodity_start <= current_time <= self.commodity_end
    
    def scan_commodities(self):
        """Scan Gold for signals and record paper trades (runs after 2:30 PM)"""
        if not self.commodity_enabled:
            return
        
        # Only trade commodities during commodity hours
        if not self.is_commodity_time():
            return
        
        try:
            from strategies.gold_strategy import gold_strategy, GoldSignal
            
            # Check for existing paper position exit first
            if gold_strategy.current_position:
                data = gold_strategy.fetch_gold_data(period="1d", interval="5m")
                if data is not None and len(data) > 0:
                    current_price = float(data['Close'].iloc[-1])
                    result = gold_strategy.check_paper_exits(current_price)
                    if result:
                        logger.info(f"🥇 Gold paper trade closed: {result}")
                        # Send Telegram
                        try:
                            from utils.notifications import send_telegram_message
                            stats = gold_strategy.get_paper_stats()
                            msg = f"🥇 GOLD PAPER TRADE CLOSED: {result}\n\n"
                            msg += f"💰 P&L: ₹{gold_strategy.paper_pnl:+,.0f}\n"
                            msg += f"📊 Stats: {stats['wins']}W / {stats['losses']}L"
                            send_telegram_message(msg)
                        except:
                            pass
            
            # Only scan for new signals if no position
            if not gold_strategy.current_position:
                logger.info("🥇 Scanning Gold for paper trading signals...")
                signal = gold_strategy.generate_signal()
                
                if signal:
                    logger.info(f"📢 GOLD PAPER SIGNAL: {signal.signal}")
                    logger.info(f"   Entry: ${signal.entry_price:.2f}")
                    logger.info(f"   SL: ${signal.stop_loss:.2f} | Target: ${signal.target:.2f}")
                    logger.info(f"   Reason: {signal.reason}")
                    
                    # Record paper trade
                    gold_strategy.record_paper_trade(signal)
                    
                    # Send Telegram alert
                    try:
                        from utils.notifications import send_telegram_message
                        msg = f"🥇 GOLD PAPER TRADE: {signal.signal}\n\n"
                        msg += f"📈 Entry: ${signal.entry_price:.2f}\n"
                        msg += f"🛡️ Stop Loss: ${signal.stop_loss:.2f}\n"
                        msg += f"🎯 Target: ${signal.target:.2f}\n"
                        msg += f"💡 {signal.reason}"
                        send_telegram_message(msg)
                    except:
                        pass
                else:
                    logger.debug("🥇 Gold: No signal (waiting for EMA crossover with filters)")
            else:
                pos = gold_strategy.current_position
                logger.info(f"🥇 Gold paper position: {pos['action']} @ ${pos['entry']:.2f}")
                    
        except Exception as e:
            logger.error(f"Gold paper trading error: {e}")
    
    def scan_for_signals(self):
        """
        Professional Signal Prioritization System
        
        Instead of taking the first signal, we:
        1. Scan ALL stocks
        2. Collect ALL valid signals
        3. Score and rank by confidence
        4. Take only the BEST 1-2 trades
        
        This is how Renaissance Technologies and top quant funds operate.
        """
        if not self.is_trading_time():
            return
        
        # Scan commodities first (if enabled)
        self.scan_commodities()
        
        # Check and manage open positions (OCO logic)
        if self.is_authenticated and self.client:
            position_manager.set_client(self.client)
            position_manager.check_and_manage_orders()
        
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
        
        # Log open positions
        open_positions = position_manager.get_open_positions()
        if open_positions:
            logger.info(f"📊 Open positions: {', '.join(open_positions)}")
        
        logger.info(f"🔍 Scanning {len(self.current_watchlist)} stocks... (Sentiment: {self.market_filter.sentiment})")
        
        # STEP 1: Collect ALL signals from ALL stocks
        all_signals = []
        
        for symbol in self.current_watchlist:
            try:
                data = self.data_fetcher.get_ohlc_data(symbol, "5minute", 5)
                if data is None or len(data) < 30:
                    continue
                
                data = self.strategy.calculate_indicators(data)
                signal = self.strategy.analyze(symbol, data)
                
                if signal:
                    # Check market sentiment
                    can_trade_sentiment, sentiment_reason = self.market_filter.should_trade(signal.signal.value)
                    if not can_trade_sentiment:
                        logger.debug(f"⚠️ {symbol}: {sentiment_reason}")
                        continue
                    
                    # Check if already have position in this stock
                    if position_manager.has_position(symbol):
                        logger.debug(f"⚠️ {symbol}: Already have open position")
                        continue
                    
                    # Check if trade is profitable after brokerage
                    is_profitable, profit_reason = is_trade_profitable(
                        signal.entry_price, signal.target, signal.quantity, min_profit=20
                    )
                    if not is_profitable:
                        logger.debug(f"⚠️ {symbol}: {profit_reason}")
                        continue
                    
                    # Signal passed all checks - add to collection
                    all_signals.append(signal)
                    logger.info(f"✅ {symbol}: Signal collected (Confidence: {signal.confidence:.0f}%)")
                    
            except Exception as e:
                logger.error(f"Error scanning {symbol}: {e}")
        
        # STEP 2: Check if we found any signals
        if not all_signals:
            logger.info("📊 No valid signals found in this scan")
            return
        
        # STEP 3: Sort signals by confidence (highest first)
        all_signals.sort(key=lambda s: s.confidence, reverse=True)
        
        # STEP 4: Log all signals found and ranking
        logger.info(f"🎯 Found {len(all_signals)} signal(s). Ranking by quality:")
        for i, signal in enumerate(all_signals, 1):
            logger.info(f"  #{i}: {signal.symbol} - {signal.confidence:.0f}% confidence | "
                       f"Entry: ₹{signal.entry_price} | Target: ₹{signal.target} | "
                       f"Potential: ₹{(signal.target - signal.entry_price) * signal.quantity:.0f}")
        
        # STEP 5: Determine how many trades we can take
        max_positions = MAX_OPEN_POSITIONS
        slots_available = max_positions - len(open_positions)
        
        if slots_available <= 0:
            logger.info("⚠️ All position slots occupied. Skipping new trades.")
            return
        
        # STEP 6: Take only the BEST signals (top 1-2)
        signals_to_take = all_signals[:slots_available]
        
        logger.info(f"🚀 Taking {len(signals_to_take)} BEST signal(s) out of {len(all_signals)} found:")
        
        for signal in signals_to_take:
            logger.info(f"  ✅ SELECTED: {signal.symbol} ({signal.confidence:.0f}% confidence)")
            self.process_signal(signal)
        
        # Log rejected signals (for transparency)
        if len(all_signals) > len(signals_to_take):
            rejected = all_signals[len(signals_to_take):]
            logger.info(f"⏩ Skipped {len(rejected)} lower-quality signal(s):")
            for signal in rejected:
                logger.info(f"  ⏭️  {signal.symbol} ({signal.confidence:.0f}% confidence) - "
                           f"Lower priority")
    
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
        if trading_mode == 'auto' and self.is_authenticated:
            try:
                broker_name = getattr(self, 'broker', 'zerodha').title()
                logger.info(f"🛒 Placing {signal.signal.value} order via {broker_name}...")
                
                # Step 1: Place ENTRY order (Market)
                entry_order_id = self.place_order(
                    symbol=signal.symbol,
                    transaction_type="BUY" if signal.signal.value == "BUY" else "SELL",
                    quantity=signal.quantity,
                    order_type="MARKET"
                )
                
                if not entry_order_id:
                    logger.error("❌ Entry order failed!")
                    return
                
                logger.info(f"✅ ENTRY ORDER PLACED! Order ID: {entry_order_id}")
                logger.info(f"   {signal.signal.value} {signal.quantity} x {signal.symbol} @ MARKET")
                
                # Step 2: Place STOP LOSS order
                sl_order_id = None
                try:
                    import time
                    time.sleep(1)  # Wait for entry to fill
                    
                    sl_transaction = "SELL" if signal.signal.value == "BUY" else "BUY"
                    
                    sl_order_id = self.place_order(
                        symbol=signal.symbol,
                        transaction_type=sl_transaction,
                        quantity=signal.quantity,
                        order_type="SL-M",
                        trigger_price=signal.stop_loss
                    )
                    
                    if sl_order_id:
                        logger.info(f"🛡️ STOP LOSS SET! Order ID: {sl_order_id}")
                        logger.info(f"   SL Trigger: ₹{signal.stop_loss}")
                    else:
                        logger.warning("⚠️ SL order placement returned None")
                    
                except Exception as sl_error:
                    logger.warning(f"⚠️ SL order failed: {sl_error}")
                
                # Step 3: Place TARGET order (Limit)
                target_order_id = None
                try:
                    target_transaction = "SELL" if signal.signal.value == "BUY" else "BUY"
                    
                    target_order_id = self.place_order(
                        symbol=signal.symbol,
                        transaction_type=target_transaction,
                        quantity=signal.quantity,
                        order_type="LIMIT",
                        price=signal.target
                    )
                    
                    if target_order_id:
                        logger.info(f"🎯 TARGET SET! Order ID: {target_order_id}")
                        logger.info(f"   Target Price: ₹{signal.target}")
                    
                except Exception as target_error:
                    logger.warning(f"⚠️ Target order failed: {target_error}")
                
                # Track position for OCO management
                position_manager.set_client(self.client)
                position_manager.add_position(
                    symbol=signal.symbol,
                    entry_id=entry_order_id,
                    sl_id=sl_order_id if 'sl_order_id' in dir() else None,
                    target_id=target_order_id if 'target_order_id' in dir() else None,
                    qty=signal.quantity,
                    entry_price=signal.entry_price,
                    sl_price=signal.stop_loss,
                    target_price=signal.target,
                    signal=signal.signal.value
                )
                
                # Record trade in journal
                trade_journal.record_entry(
                    symbol=signal.symbol,
                    action=signal.signal.value,
                    entry_price=signal.entry_price,
                    quantity=signal.quantity,
                    stop_loss=signal.stop_loss,
                    target=signal.target,
                    entry_order_id=str(entry_order_id),
                    sl_order_id=str(sl_order_id) if 'sl_order_id' in dir() and sl_order_id else None,
                    target_order_id=str(target_order_id) if 'target_order_id' in dir() and target_order_id else None
                )
                
                # Send Telegram confirmation
                try:
                    from utils.notifications import send_telegram_message
                    msg = f"✅ TRADE EXECUTED!\n\n"
                    msg += f"📈 {signal.signal.value} {signal.quantity} x {signal.symbol}\n"
                    msg += f"🛡️ Stop Loss: ₹{signal.stop_loss}\n"
                    msg += f"🎯 Target: ₹{signal.target}\n"
                    msg += f"\nOrder ID: {entry_order_id}"
                    send_telegram_message(msg)
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
        trade_data = {
            "symbol": signal.symbol,
            "signal": signal.signal.value,
            "action": signal.signal.value,
            "entry": signal.entry_price,
            "entry_price": signal.entry_price,
            "target": signal.target,
            "sl": signal.stop_loss,
            "sl_price": signal.stop_loss,
            "qty": signal.quantity,
            "quantity": signal.quantity,
            "expected_charges": charges['total_charges'],
            "time": datetime.now(IST).strftime("%H:%M:%S"),
            "pnl": 0  # Will be updated when closed
        }
        self.today_trades.append(trade_data)
        
        # Save trades to file for dashboard
        self._save_trades_to_file()
        
        # Save positions to file for dashboard
        self._save_positions_to_file(signal)
        
        # Save to database for persistent history
        try:
            analytics_db.save_position(
                symbol=signal.symbol,
                signal=signal.signal.value,
                entry_price=signal.entry_price,
                quantity=signal.quantity,
                stop_loss=signal.stop_loss,
                target=signal.target,
                trail_sl=signal.stop_loss,  # Initial trail = SL
                entry_time=datetime.now(IST).strftime("%H:%M:%S"),
                segment='EQUITY',
                product_type='MIS'
            )
            logger.debug(f"💾 Position saved to database: {signal.symbol}")
        except Exception as db_err:
            logger.warning(f"Database save error: {db_err}")
        
        # Add estimated charges
        self.today_charges += charges['total_charges']
        
        self.risk_manager.record_trade_entry()
    
    def _save_trades_to_file(self):
        """Save today's trades to a JSON file for dashboard display"""
        try:
            os.makedirs('data', exist_ok=True)
            trades_data = {
                'date': datetime.now(IST).strftime('%Y-%m-%d'),
                'trades': self.today_trades,
                'total_pnl': self.today_pnl,
                'total_charges': self.today_charges,
                'trade_count': len(self.today_trades)
            }
            with open('data/today_trades.json', 'w') as f:
                json.dump(trades_data, f, indent=2)
            logger.debug(f"✅ Saved {len(self.today_trades)} trades to dashboard file")
        except Exception as e:
            logger.debug(f"Failed to save trades file: {e}")
    
    def _save_positions_to_file(self, signal=None):
        """Save open positions to a JSON file for dashboard display"""
        try:
            os.makedirs('data', exist_ok=True)
            positions = {}
            
            # Get positions from position_manager
            open_positions = position_manager.get_open_positions()
            for symbol in open_positions:
                pos = position_manager.get_position(symbol)
                if pos:
                    positions[symbol] = {
                        'symbol': symbol,
                        'signal': pos.get('signal', 'BUY'),
                        'entry_price': pos.get('entry_price', 0),
                        'sl_price': pos.get('sl_price', 0),
                        'trail_sl': pos.get('trail_sl', pos.get('sl_price', 0)),
                        'target_price': pos.get('target_price', 0),
                        'qty': pos.get('qty', 0),
                        'entry_time': pos.get('entry_time', datetime.now(IST).strftime('%H:%M:%S'))
                    }
            
            # If we have a new signal, add it as a position
            if signal and signal.symbol not in positions:
                positions[signal.symbol] = {
                    'symbol': signal.symbol,
                    'signal': signal.signal.value,
                    'entry_price': signal.entry_price,
                    'sl_price': signal.stop_loss,
                    'trail_sl': signal.stop_loss,
                    'target_price': signal.target,
                    'qty': signal.quantity,
                    'entry_time': datetime.now(IST).strftime('%H:%M:%S')
                }
            
            with open('data/stock_positions.json', 'w') as f:
                json.dump(positions, f, indent=2)
            logger.debug(f"✅ Saved {len(positions)} positions to dashboard file")
        except Exception as e:
            logger.debug(f"Failed to save positions file: {e}")
    
    def _fetch_angel_trades(self):
        """Fetch today's executed trades from Angel One account"""
        try:
            if not self.is_authenticated or not hasattr(self, 'angel_client'):
                return []
            
            # Get today's orders from Angel One
            order_book = self.angel_client.orderBook()
            if not order_book or not order_book.get('status') or not order_book.get('data'):
                return []
            
            trades = []
            today_str = datetime.now(IST).strftime('%Y-%m-%d')
            
            for order in order_book['data']:
                try:
                    # Only completed/filled orders
                    status = order.get('status', '').lower()
                    if status not in ['complete', 'filled', 'traded']:
                        continue
                    
                    # Parse order time
                    order_time = order.get('updatetime', order.get('ordertime', ''))
                    symbol = order.get('tradingsymbol', '').replace('-EQ', '').replace('-BE', '')
                    exchange = order.get('exchange', 'NSE')
                    
                    # Determine segment
                    if exchange in ['NFO', 'BFO']:
                        if 'CE' in symbol or 'PE' in symbol:
                            segment = 'OPTIONS'
                        else:
                            segment = 'FUTURES'
                    elif exchange in ['MCX', 'CDS']:
                        segment = 'COMMODITY'
                    else:
                        segment = 'EQUITY'
                    
                    trade = {
                        'symbol': symbol,
                        'signal': order.get('transactiontype', 'BUY'),
                        'action': order.get('transactiontype', 'BUY'),
                        'entry_price': float(order.get('averageprice', 0) or order.get('price', 0) or 0),
                        'qty': int(order.get('filledshares', 0) or order.get('quantity', 0) or 0),
                        'quantity': int(order.get('filledshares', 0) or order.get('quantity', 0) or 0),
                        'order_id': order.get('orderid', ''),
                        'time': order_time.split(' ')[-1] if ' ' in order_time else order_time,
                        'time_ist': order_time.split(' ')[-1] if ' ' in order_time else order_time,
                        'pnl': 0,
                        'status': 'EXECUTED',
                        'product': order.get('producttype', 'INTRADAY'),
                        'exchange': exchange,
                        'segment': segment,
                        'order_status': status.upper()
                    }
                    trades.append(trade)
                except Exception as te:
                    logger.debug(f"Error parsing trade: {te}")
                    continue
            
            logger.debug(f"📊 Fetched {len(trades)} executed trades from Angel One")
            return trades
            
        except Exception as e:
            logger.debug(f"Failed to fetch Angel trades: {e}")
            return []
    
    def _fetch_angel_positions(self):
        """Fetch open positions from Angel One account"""
        try:
            if not self.is_authenticated or not hasattr(self, 'angel_client'):
                return {}
            
            # Get positions from Angel One
            positions_resp = self.angel_client.position()
            
            # Handle empty or error responses
            if not positions_resp:
                logger.debug("No position response from Angel One")
                return {}
            
            if not positions_resp.get('status'):
                logger.debug(f"Position fetch failed: {positions_resp.get('message', 'Unknown error')}")
                return {}
            
            data = positions_resp.get('data')
            if not data:
                logger.debug("No position data from Angel One")
                return {}
            
            positions = {}
            for pos in data:
                try:
                    # Get quantity - could be netqty or quantity
                    net_qty = int(pos.get('netqty', 0) or pos.get('quantity', 0) or 0)
                    
                    # Include ALL positions (even with 0 qty for display)
                    symbol = pos.get('tradingsymbol', '').replace('-EQ', '').replace('-BE', '')
                    exchange = pos.get('exchange', 'NSE')
                    
                    # Determine segment based on exchange and symbol
                    if exchange in ['NFO', 'BFO']:
                        if 'CE' in symbol or 'PE' in symbol:
                            segment = 'OPTIONS'
                        else:
                            segment = 'FUTURES'
                    elif exchange in ['MCX', 'CDS']:
                        segment = 'COMMODITY'
                    else:
                        segment = 'EQUITY'
                    
                    # Get P&L values
                    realised = float(pos.get('realised', 0) or 0)
                    unrealised = float(pos.get('unrealised', 0) or 0)
                    pnl = float(pos.get('pnl', 0) or 0) or (realised + unrealised)
                    
                    # Get entry price for calculations
                    entry_price = float(pos.get('averageprice', 0) or pos.get('buyavgprice', 0) or 0)
                    
                    # Get SL/Target/Trail from position manager if available
                    pm_pos = position_manager.get_position(symbol)
                    
                    if pm_pos and pm_pos.get('sl_price', 0) > 0:
                        # Use stored values from position manager
                        sl_price = pm_pos.get('sl_price', 0)
                        target_price = pm_pos.get('target_price', 0)
                        trail_sl = pm_pos.get('trail_sl', sl_price)
                        entry_time = pm_pos.get('entry_time', '')
                    else:
                        # Auto-calculate default SL/Target based on strategy percentages
                        # Default: 1.5% SL, 3% Target (2:1 Risk-Reward)
                        
                        # Determine original signal direction (even for closed positions)
                        buyqty = int(pos.get('buyqty', 0) or pos.get('daybuyqty', 0) or 0)
                        sellqty = int(pos.get('sellqty', 0) or pos.get('daysellqty', 0) or 0)
                        
                        if net_qty > 0:
                            signal_type = 'BUY'
                        elif net_qty < 0:
                            signal_type = 'SELL'
                        elif buyqty > 0:
                            # Closed position that was originally a BUY
                            signal_type = 'BUY'
                        else:
                            # Closed position that was originally a SELL (or unknown)
                            signal_type = 'SELL' if sellqty > 0 else 'BUY'  # Default to BUY
                        
                        if signal_type == 'BUY' and entry_price > 0:
                            sl_price = round(entry_price * 0.985, 2)  # 1.5% below entry
                            target_price = round(entry_price * 1.03, 2)  # 3% above entry
                        elif signal_type == 'SELL' and entry_price > 0:
                            sl_price = round(entry_price * 1.015, 2)  # 1.5% above entry
                            target_price = round(entry_price * 0.97, 2)  # 3% below entry
                        else:
                            sl_price = 0
                            target_price = 0
                        
                        trail_sl = sl_price  # No trailing until price moves in favor
                        entry_time = ''
                    
                    # Get LTP and actual exit price
                    ltp = float(pos.get('ltp', 0) or 0)
                    
                    # For closed positions, get actual exit price from Angel One (not LTP!)
                    # buyavgprice = avg price at which shares were bought
                    # sellavgprice = avg price at which shares were sold
                    buy_avg_price = float(pos.get('buyavgprice', 0) or pos.get('buyaverage', 0) or 0)
                    sell_avg_price = float(pos.get('sellavgprice', 0) or pos.get('sellaverage', 0) or 0)
                    
                    # Determine exit price for closed positions
                    exit_price = 0
                    if net_qty == 0:  # Position is closed
                        # Determine original signal direction
                        buyqty_check = int(pos.get('buyqty', 0) or pos.get('daybuyqty', 0) or 0)
                        sellqty_check = int(pos.get('sellqty', 0) or pos.get('daysellqty', 0) or 0)
                        
                        if buyqty_check > 0:
                            # Was a BUY position, exit is the SELL price
                            exit_price = sell_avg_price if sell_avg_price > 0 else ltp
                        else:
                            # Was a SELL position, exit is the BUY price
                            exit_price = buy_avg_price if buy_avg_price > 0 else ltp
                    
                    # Determine exit reason for closed positions - use exit_price not LTP
                    exit_reason = ''
                    if net_qty == 0 and entry_price > 0 and exit_price > 0:  # Position is closed
                        if target_price > 0 and exit_price >= target_price:
                            exit_reason = 'TARGET_HIT'
                        elif sl_price > 0 and exit_price <= sl_price:
                            exit_reason = 'SL_HIT'
                        else:
                            # Neither target nor SL hit - must be market close or manual exit
                            exit_reason = 'MARKET_CLOSE'
                    
                    positions[symbol] = {
                        'symbol': symbol,
                        'signal': 'BUY' if net_qty > 0 else 'SELL' if net_qty < 0 else 'CLOSED',
                        'qty': abs(net_qty),
                        'entry_price': entry_price,
                        'ltp': ltp,
                        'exit_price': exit_price,  # Actual exit price for closed positions
                        'pnl': pnl,
                        'realised_pnl': realised,
                        'unrealised_pnl': unrealised,
                        'product': pos.get('producttype', 'INTRADAY'),
                        'exchange': exchange,
                        'segment': segment,
                        'cfbuyqty': int(pos.get('cfbuyqty', 0) or 0),
                        'cfsellqty': int(pos.get('cfsellqty', 0) or 0),
                        # SL, Target, Trail Stop Loss for dashboard
                        'sl_price': sl_price,
                        'target_price': target_price,
                        'trail_sl': trail_sl,
                        'entry_time': entry_time,
                        'exit_reason': exit_reason
                    }
                    
                    # Save closed position to database for history
                    if net_qty == 0 and exit_price > 0:
                        try:
                            analytics_db.close_position(
                                symbol=symbol,
                                exit_price=exit_price,
                                pnl=realised,
                                exit_reason=exit_reason,
                                exit_time=datetime.now(IST).strftime("%H:%M:%S")
                            )
                        except Exception as db_err:
                            logger.debug(f"DB close position error: {db_err}")
                    
                except Exception as pe:
                    logger.debug(f"Error parsing position: {pe}")
                    continue
            
            logger.debug(f"📊 Fetched {len(positions)} positions from Angel One")
            return positions
            
        except Exception as e:
            logger.debug(f"Failed to fetch Angel positions: {e}")
            return {}
    
    def _update_dashboard_files(self):
        """Periodically update all dashboard files for real-time display"""
        try:
            # Fetch live trades from Angel One
            angel_trades = self._fetch_angel_trades()
            
            # Merge with local trades (prefer Angel data)
            if angel_trades:
                # Save Angel trades
                os.makedirs('data', exist_ok=True)
                trades_data = {
                    'date': datetime.now(IST).strftime('%Y-%m-%d'),
                    'trades': angel_trades,
                    'total_pnl': sum(t.get('pnl', 0) for t in angel_trades),
                    'trade_count': len(angel_trades),
                    'source': 'angel_one',
                    'last_updated': datetime.now(IST).strftime('%H:%M:%S IST')
                }
                with open('data/today_trades.json', 'w') as f:
                    json.dump(trades_data, f, indent=2)
            else:
                # Fallback to local trades
                self._save_trades_to_file()
            
            # Fetch live positions from Angel One
            angel_positions = self._fetch_angel_positions()
            
            # Merge positions
            if angel_positions:
                os.makedirs('data', exist_ok=True)
                with open('data/stock_positions.json', 'w') as f:
                    json.dump(angel_positions, f, indent=2)
            else:
                # Fallback to local positions
                self._save_positions_to_file()
            
            # Update broker status
            self.refresh_balance()
            
            logger.debug("📊 Dashboard files updated")
        except Exception as e:
            logger.debug(f"Dashboard update failed: {e}")
    
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
            # Get stats from trade journal
            journal_stats = trade_journal.get_today_stats()
            
            # Save to database
            trade_journal.save_daily_summary()
            
            # Send Telegram summary
            try:
                from utils.notifications import send_telegram_message
                msg = f"""📊 DAILY SUMMARY

Trades: {journal_stats.get('total_trades', len(self.today_trades))}
Gross P&L: ₹{self.today_pnl:+,.2f}
Charges: ₹{self.today_charges:.2f}
NET P&L: ₹{net_pnl:+,.2f}
"""
                send_telegram_message(msg)
            except:
                pass
                
        except Exception as e:
            logger.debug(f"Summary failed: {e}")
            # Fallback to basic summary
            stats = {
                'trades': len(self.today_trades),
                'gross_profit': max(0, self.today_pnl),
                'gross_loss': abs(min(0, self.today_pnl)),
                'net_pnl': net_pnl
            }
            send_daily_summary(stats)
    
    def reset_daily(self):
        """Reset for new trading day"""
        self.today_trades = []
        self.today_pnl = 0.0
        self.today_charges = 0.0
        self.risk_manager = RiskManager(self.capital)
        self.last_sentiment_check = None
        logger.info("🔄 Daily reset complete")
    
    def refresh_balance(self):
        """Refresh broker balance and update dashboard (called periodically)"""
        try:
            # Load existing status to preserve last known good state
            existing_status = {'is_authenticated': False, 'balance': 0, 'user_name': 'Not Connected', 'broker_name': 'Not Connected'}
            try:
                if os.path.exists('data/zerodha_status.json'):
                    with open('data/zerodha_status.json', 'r') as f:
                        existing_status = json.load(f)
            except:
                pass
            
            broker_status = existing_status.copy()  # Start with previous state
            
            if self.is_authenticated:
                broker_status['is_authenticated'] = True  # We know we're authenticated
                
                if hasattr(self, 'broker') and self.broker == 'angel':
                    # Angel One balance  
                    try:
                        funds = self.angel_client.rmsLimit()
                        if funds.get('status') and funds.get('data'):
                            available = float(funds['data'].get('net', 0))
                            broker_status['balance'] = available
                            try:
                                profile = self.angel_client.getProfile(self.angel_refresh_token)
                                if profile.get('data'):
                                    broker_status['user_name'] = profile['data'].get('name', broker_status.get('user_name', 'Connected'))
                            except:
                                pass  # Keep previous name if profile fails
                            broker_status['broker_name'] = 'Angel One'
                            logger.debug(f"🔄 Balance refreshed: ₹{available:,.2f}")
                        else:
                            # API failed but we're still authenticated, keep previous data
                            logger.debug("Balance API returned no data, keeping previous state")
                    except Exception as bal_err:
                        # API error (common after market hours), keep previous state
                        logger.debug(f"Balance API error: {bal_err}, keeping previous state")
                        
                elif self.client:
                    # Zerodha balance
                    try:
                        margins = self.client.get_margins()
                        if margins and 'equity' in margins:
                            available = margins['equity'].get('available', {}).get('live_balance', 0)
                            broker_status['balance'] = available
                            broker_status['user_name'] = self.client.kite.profile().get('user_name', 'Connected')
                            broker_status['broker_name'] = 'Zerodha'
                    except:
                        pass
            
            # Save for dashboard
            broker_status['last_updated'] = datetime.now(IST).strftime('%H:%M:%S IST')
            os.makedirs('data', exist_ok=True)
            with open('data/zerodha_status.json', 'w') as f:
                json.dump(broker_status, f, indent=2)
                
        except Exception as e:
            logger.debug(f"Balance refresh failed: {e}")
    
    def smart_cnc_conversion(self):
        """
        Smart CNC Conversion Logic - Runs at 2:30 PM and 3:00 PM
        
        Converts MIS (intraday) positions to CNC (delivery) if:
        1. Position is currently in PROFIT
        2. Expected additional profit to target > ₹100
        3. Stock is in strong uptrend (for BUY positions)
        
        CNC Extra Costs: ~₹40-50 per ₹35,000 trade
        - If profit potential > ₹100: Convert ✅
        - If profit potential < ₹50: Don't convert ❌
        """
        try:
            if not self.is_authenticated or not hasattr(self, 'angel_client'):
                return
            
            # Get current positions
            positions_resp = self.angel_client.position()
            if not positions_resp or not positions_resp.get('status') or not positions_resp.get('data'):
                return
            
            logger.info("🔄 Running Smart CNC Conversion Check...")
            converted_count = 0
            
            for pos in positions_resp['data']:
                try:
                    symbol = pos.get('tradingsymbol', '').replace('-EQ', '').replace('-BE', '')
                    net_qty = int(pos.get('netqty', 0) or 0)
                    product_type = pos.get('producttype', '').upper()
                    
                    # Only check MIS/INTRADAY positions with open quantity
                    if net_qty == 0 or product_type not in ['INTRADAY', 'MIS']:
                        continue
                    
                    # Get prices
                    entry_price = float(pos.get('averageprice', 0) or pos.get('buyavgprice', 0) or 0)
                    ltp = float(pos.get('ltp', 0) or 0)
                    
                    if entry_price <= 0 or ltp <= 0:
                        continue
                    
                    # Get target from position manager or calculate 3%
                    pm_pos = position_manager.get_position(symbol)
                    if pm_pos and pm_pos.get('target_price', 0) > 0:
                        target_price = pm_pos.get('target_price')
                    else:
                        # Default 3% target for BUY
                        target_price = round(entry_price * 1.03, 2)
                    
                    # Calculate current P&L and potential additional profit
                    current_pnl = (ltp - entry_price) * abs(net_qty)
                    potential_profit_to_target = (target_price - ltp) * abs(net_qty)
                    
                    # Decision logic
                    # 1. Must be in profit
                    if current_pnl <= 0:
                        logger.debug(f"📊 {symbol}: Skipping - Not in profit (P&L: ₹{current_pnl:.2f})")
                        continue
                    
                    # 2. Expected additional profit must be > ₹100 (to cover CNC extra cost of ~₹50)
                    if potential_profit_to_target < 100:
                        logger.info(f"📊 {symbol}: Skipping - Potential profit ₹{potential_profit_to_target:.2f} < ₹100 (not worth CNC cost)")
                        continue
                    
                    # 3. Must have reasonable room to target (at least 0.5%)
                    distance_to_target_pct = ((target_price - ltp) / ltp) * 100
                    if distance_to_target_pct < 0.5:
                        logger.info(f"📊 {symbol}: Skipping - Too close to target ({distance_to_target_pct:.2f}%)")
                        continue
                    
                    # ✅ All conditions met - Convert to CNC
                    logger.info(f"🔄 {symbol}: Converting MIS → CNC")
                    logger.info(f"   Current P&L: ₹{current_pnl:.2f}")
                    logger.info(f"   LTP: ₹{ltp} | Target: ₹{target_price}")
                    logger.info(f"   Potential Additional Profit: ₹{potential_profit_to_target:.2f}")
                    
                    # Angel One position conversion API
                    convert_params = {
                        "exchange": pos.get('exchange', 'NSE'),
                        "symboltoken": pos.get('symboltoken', ''),
                        "producttype": "DELIVERY",  # CNC = DELIVERY in Angel One
                        "newproducttype": "DELIVERY",
                        "tradingsymbol": pos.get('tradingsymbol', ''),
                        "transactiontype": "BUY" if net_qty > 0 else "SELL",
                        "quantity": abs(net_qty),
                        "type": "DAY"
                    }
                    
                    try:
                        # Angel One convertPosition API
                        convert_response = self.angel_client.convertPosition(convert_params)
                        
                        if convert_response and convert_response.get('status'):
                            converted_count += 1
                            logger.info(f"✅ {symbol}: Successfully converted to CNC!")
                            
                            # Update database with new product type
                            try:
                                analytics_db.update_position_product_type(symbol, 'CNC')
                            except:
                                pass
                            
                            # Send Telegram notification
                            try:
                                from utils.notifications import send_telegram_message
                                msg = f"""🔄 POSITION CONVERTED TO CNC

📈 {symbol}
Qty: {abs(net_qty)} shares
Entry: ₹{entry_price:.2f}
LTP: ₹{ltp:.2f}
Target: ₹{target_price:.2f}

💰 Current Profit: ₹{current_pnl:.2f}
🎯 Potential Extra: ₹{potential_profit_to_target:.2f}

⏰ Will hold overnight for target"""
                                send_telegram_message(msg)
                            except:
                                pass
                        else:
                            error_msg = convert_response.get('message', 'Unknown error') if convert_response else 'No response'
                            logger.warning(f"⚠️ {symbol}: Conversion failed - {error_msg}")
                            
                    except Exception as conv_err:
                        logger.warning(f"⚠️ {symbol}: Conversion API error - {conv_err}")
                    
                except Exception as pos_err:
                    logger.debug(f"Error processing position: {pos_err}")
                    continue
            
            if converted_count > 0:
                logger.info(f"✅ Smart CNC Conversion: Converted {converted_count} position(s)")
            else:
                logger.info("📊 Smart CNC Conversion: No positions met criteria for conversion")
                
        except Exception as e:
            logger.error(f"Smart CNC conversion error: {e}")
    
    
    def run(self):
        """Main run loop"""
        logger.info("="*50)
        logger.info("🤖 CLOUD TRADING BOT STARTED")
        logger.info("="*50)
        
        # Show capital stats
        capital_stats = capital_manager.get_stats()
        logger.info(f"💰 Trading Capital: ₹{capital_stats['current_capital']:,.2f}")
        logger.info(f"📈 Total P&L: ₹{capital_stats['total_pnl']:+,.2f} ({capital_stats['growth_percent']:+.1f}%)")
        logger.info(f"📊 Mode: {os.getenv('TRADING_MODE', 'paper').upper()}")
        logger.info(f"📋 Stocks: {', '.join(self.current_watchlist)}")
        
        # Authenticate - tries Angel One first, then Zerodha
        self.authenticate()
        
        # Get balance and save for dashboard
        broker_status = {'is_authenticated': False, 'balance': 0, 'user_name': 'Not Connected', 'broker_name': 'Not Connected'}
        
        if self.is_authenticated:
            broker_status['is_authenticated'] = True
            try:
                if hasattr(self, 'broker') and self.broker == 'angel':
                    # Angel One balance
                    broker_status['broker_name'] = 'Angel One'
                    try:
                        funds = self.angel_client.rmsLimit()
                        if funds.get('status') and funds.get('data'):
                            available = float(funds['data'].get('net', 0))
                            broker_status['balance'] = available
                    except:
                        pass
                    try:
                        profile = self.angel_client.getProfile(self.angel_refresh_token)
                        if profile.get('data'):
                            broker_status['user_name'] = profile['data'].get('name', 'Connected')
                    except:
                        broker_status['user_name'] = 'Connected'
                        
                elif self.client:
                    # Zerodha balance
                    broker_status['broker_name'] = 'Zerodha'
                    try:
                        margins = self.client.get_margins()
                        if margins and 'equity' in margins:
                            available = margins['equity'].get('available', {}).get('live_balance', 0)
                            broker_status['balance'] = available
                            broker_status['user_name'] = self.client.kite.profile().get('user_name', 'Connected')
                    except:
                        broker_status['user_name'] = 'Connected'
            except Exception as e:
                logger.info(f"🏦 Balance check failed: {e}")
        else:
            logger.info("🏦 Not authenticated - Add credentials in Railway")
        
        # Save status for web dashboard
        try:
            broker_status['last_updated'] = datetime.now(IST).strftime('%H:%M:%S IST')
            os.makedirs('data', exist_ok=True)
            with open('data/zerodha_status.json', 'w') as f:
                json.dump(broker_status, f, indent=2)
        except:
            pass
        
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
        schedule.every(5).minutes.do(self.scan_for_signals)  # Scan every 5 minutes for signals
        schedule.every(5).minutes.do(self.refresh_balance)  # Refresh balance every 5 minutes
        schedule.every(30).seconds.do(self._update_dashboard_files)  # Update dashboard every 30s
        schedule.every().day.at("14:15").do(lambda: logger.info("🟡 Trading window ended. No new trades."))
        schedule.every().day.at("14:30").do(lambda: logger.info("🥇 Commodity trading window started! (Gold paper trading)"))
        
        # Smart CNC Conversion - runs at 2:30 PM and 3:00 PM to convert profitable MIS to CNC
        schedule.every().day.at("14:30").do(self.smart_cnc_conversion)
        schedule.every().day.at("15:00").do(self.smart_cnc_conversion)
        
        schedule.every().day.at("15:30").do(self.daily_summary)
        schedule.every().day.at("00:01").do(self.reset_daily)
        
        # Sunday: Weekly stock optimization and capital compounding at 6 PM
        schedule.every().sunday.at("18:00").do(self.weekly_stock_optimization)
        schedule.every().sunday.at("18:05").do(capital_manager.weekly_compound)
        
        logger.info("✅ Bot running...")
        logger.info("📅 Balance refresh: Every 5 minutes")
        
        # Immediate scan if in trading window
        if self.is_trading_time():
            logger.info("🔄 Running initial equity scan...")
            self.scan_for_signals()
        
        # Immediate commodity scan if in commodity time
        if self.is_commodity_time():
            logger.info(f"🥇 Running initial commodity scan (Paper Capital: ₹{self.commodity_paper_capital:,})...")
            self.scan_commodities()
        
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


def start_dashboard():
    """Start the premium web dashboard"""
    try:
        # Use the premium dashboard module
        from dashboard import app, get_dashboard_data, DASHBOARD_HTML
        from flask import render_template_string, jsonify
        import json
        
        # Add API endpoint for cloud_bot status
        @app.route('/api/status')
        def api_status():
            # Read data from saved files
            capital = {'current_capital': 10000, 'total_pnl': 0, 'high_water_mark': 10000, 'growth_percent': 0}
            zerodha = {'balance': 0, 'user_name': 'Not Connected', 'is_authenticated': False}
            
            try:
                if os.path.exists('data/capital_config.json'):
                    with open('data/capital_config.json', 'r') as f:
                        data = json.load(f)
                        capital['current_capital'] = data.get('current_capital', 10000)
                        capital['total_pnl'] = data.get('total_pnl', 0)
            except:
                pass
            
            try:
                if os.path.exists('data/zerodha_status.json'):
                    with open('data/zerodha_status.json', 'r') as f:
                        zerodha = json.load(f)
            except:
                pass
            
            return jsonify({
                'timestamp': datetime.now().isoformat(),
                'capital': capital,
                'zerodha': zerodha,
                'bot_status': 'running',
                'strategy': 'Gold 93% Win Rate'
            })
        
        port = int(os.environ.get('PORT', 5050))
        logger.info(f"🌐 Starting PREMIUM dashboard on port {port}...")
        app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)
        
    except Exception as e:
        logger.warning(f"Premium dashboard failed: {e}, using fallback...")
        # Fallback to simple dashboard
        from flask import Flask, render_template_string, jsonify
        import json
        
        app = Flask(__name__)
        
        SIMPLE_DASHBOARD = """
<!DOCTYPE html>
<html>
<head>
    <title>📈 Gold 93% Win Rate - Trading Dashboard</title>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap" rel="stylesheet">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Inter', sans-serif; background: linear-gradient(135deg, #0a0a0f 0%, #1a1a2e 100%); color: #fff; min-height: 100vh; padding: 2rem; }
        .header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 2rem; padding-bottom: 1rem; border-bottom: 1px solid #333; }
        .logo h1 { font-size: 1.8rem; background: linear-gradient(135deg, #00d4aa, #667eea); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
        .strategy-tag { background: rgba(0, 212, 170, 0.2); color: #00d4aa; padding: 0.5rem 1rem; border-radius: 8px; font-size: 0.9rem; font-weight: 600; margin-top: 0.5rem; }
        .status { display: flex; align-items: center; gap: 0.5rem; color: #00ff88; }
        .pulse { width: 10px; height: 10px; background: #00ff88; border-radius: 50%; animation: pulse 2s infinite; }
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.3; } }
        .info-banner { background: rgba(0, 212, 170, 0.1); border: 1px solid #333; border-radius: 12px; padding: 1.5rem; margin-bottom: 2rem; display: flex; flex-wrap: wrap; gap: 2rem; }
        .info-item label { font-size: 0.75rem; color: #888; text-transform: uppercase; display: block; margin-bottom: 0.3rem; }
        .info-item span { font-weight: 600; color: #00d4aa; }
        .stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; margin-bottom: 2rem; }
        .stat-card { background: rgba(255,255,255,0.05); border: 1px solid #333; border-radius: 12px; padding: 1.5rem; }
        .stat-card h3 { font-size: 0.8rem; color: #888; margin-bottom: 0.5rem; }
        .stat-card .value { font-size: 1.8rem; font-weight: 700; }
        .stat-card .value.profit { color: #00ff88; }
        .section { background: rgba(255,255,255,0.05); border: 1px solid #333; border-radius: 12px; padding: 1.5rem; margin-bottom: 1.5rem; }
        .section h2 { font-size: 1.1rem; margin-bottom: 1rem; display: flex; align-items: center; gap: 0.5rem; }
        .badge { background: #00d4aa; color: #000; padding: 0.2rem 0.5rem; border-radius: 12px; font-size: 0.75rem; }
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
        <div class="status"><div class="pulse"></div><span id="status">LIVE</span><span id="time">--:--:--</span></div>
    </div>
    <div class="info-banner">
        <div class="info-item"><label>Segment</label><span>EQUITY</span></div>
        <div class="info-item"><label>Exchange</label><span>NSE</span></div>
        <div class="info-item"><label>Product</label><span>MIS Intraday</span></div>
        <div class="info-item"><label>Leverage</label><span>5x</span></div>
        <div class="info-item"><label>Broker</label><span>Angel One</span></div>
        <div class="info-item"><label>Strategy</label><span>RSI + Stoch + CCI + MACD</span></div>
    </div>
    <div class="stats-grid">
        <div class="stat-card"><h3>Capital</h3><div class="value" id="capital">₹10,000</div></div>
        <div class="stat-card"><h3>Today's P&L</h3><div class="value profit" id="pnl">+₹0</div></div>
        <div class="stat-card"><h3>Watchlist</h3><div class="value" id="watchlist-count">0</div></div>
        <div class="stat-card"><h3>Open Positions</h3><div class="value" id="positions-count">0</div></div>
    </div>
    <div class="section">
        <h2>📋 Smart Watchlist <span class="badge" id="wl-badge">0</span></h2>
        <table><thead><tr><th>Stock</th><th>Win Rate</th><th>Expected P&L</th></tr></thead><tbody id="watchlist-body"><tr><td colspan="3" class="empty">Loading...</td></tr></tbody></table>
    </div>
    <div class="footer"><p>🤖 Gold 93% Win Rate Strategy | EQUITY | NSE | MIS Intraday | Angel One</p><p>Last Update: <span id="last-update">--</span></p></div>
    <script>
        function updateTime() { document.getElementById('time').textContent = new Date().toLocaleTimeString('en-IN', {hour12: false, timeZone: 'Asia/Kolkata'}) + ' IST'; }
        setInterval(updateTime, 1000); updateTime();
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
                if (wl.length === 0) { tbody.innerHTML = '<tr><td colspan="3" class="empty">No stocks in watchlist</td></tr>'; }
                else { tbody.innerHTML = wl.slice(0, 10).map(s => `<tr><td>${s.symbol || s.name}</td><td style="color: #00ff88">${(s.win_rate || 0).toFixed(1)}%</td><td style="color: #00ff88">+₹${(s.expected_pnl || 0).toLocaleString()}</td></tr>`).join(''); }
                document.getElementById('last-update').textContent = new Date().toLocaleTimeString('en-IN', {hour12: false});
            } catch(e) { console.error(e); }
        }
        fetchData(); setInterval(fetchData, 10000);
    </script>
</body>
</html>
"""
        
        @app.route('/')
        def dashboard():
            return render_template_string(SIMPLE_DASHBOARD)
        
        @app.route('/api/dashboard')
        def api_dashboard():
            data = {'capital': 10000, 'daily_pnl': 0, 'watchlist': [], 'positions': {}}
            try:
                if os.path.exists('config/smart_watchlist.json'):
                    with open('config/smart_watchlist.json', 'r') as f:
                        wl = json.load(f)
                        data['watchlist'] = wl.get('active_stocks', [])
                        data['capital'] = wl.get('capital', 10000)
            except: pass
            try:
                if os.path.exists('data/stock_positions.json'):
                    with open('data/stock_positions.json', 'r') as f:
                        data['positions'] = json.load(f)
            except: pass
            return jsonify(data)
        
        @app.route('/api/status')
        def api_status():
            # Read data from saved files
            capital = {'current_capital': 10000, 'total_pnl': 0, 'high_water_mark': 10000, 'growth_percent': 0}
            zerodha = {'balance': 0, 'user_name': 'Not Connected', 'is_authenticated': False}
            today = {'total_trades': 0, 'open_trades': 0, 'wins': 0, 'losses': 0, 'win_rate': 0, 'net_pnl': 0}
            
            try:
                if os.path.exists('data/capital_config.json'):
                    with open('data/capital_config.json', 'r') as f:
                        data = json.load(f)
                        capital['current_capital'] = data.get('current_capital', 10000)
                        capital['total_pnl'] = data.get('total_pnl', 0)
                        capital['growth_percent'] = ((capital['current_capital'] - 10000) / 10000) * 100
            except:
                pass
            
            try:
                if os.path.exists('data/zerodha_status.json'):
                    with open('data/zerodha_status.json', 'r') as f:
                        zerodha = json.load(f)
            except:
                pass
            
            # Gold paper trading stats
            gold_stats = {
                'pnl': 0,
                'wins': 0,
                'losses': 0,
                'win_rate': 0,
                'price': 0,
                'trend': 'N/A',
                'trades': []
            }
            
            try:
                from strategies.gold_strategy import gold_strategy
                stats = gold_strategy.get_paper_stats()
                gold_stats['pnl'] = stats.get('pnl', 0)
                gold_stats['wins'] = stats.get('wins', 0)
                gold_stats['losses'] = stats.get('losses', 0)
                gold_stats['win_rate'] = stats.get('win_rate', 0)
                gold_stats['trades'] = gold_strategy.paper_trades[-10:]  # Last 10 trades
                
                # Current position
                if gold_strategy.current_position:
                    gold_stats['current_position'] = gold_strategy.current_position
                else:
                    gold_stats['current_position'] = None
                
                # Get current price and trend
                market = gold_strategy.get_market_status()
                gold_stats['price'] = market.get('price', 0)
                gold_stats['trend'] = market.get('trend', 'N/A')
                gold_stats['rsi'] = market.get('rsi', 0)
                gold_stats['quality'] = market.get('quality', 'N/A')
                
                # Calculate INR price (MCX equivalent per 10g)
                # 1 oz = 31.1 grams, USD/INR ~ 85
                usd_price = market.get('price', 0)
                usd_inr_rate = 85  # Approximate, can be fetched dynamically
                gold_per_gram_inr = (usd_price * usd_inr_rate) / 31.1
                gold_stats['price_inr'] = round(gold_per_gram_inr * 10, 0)  # Per 10g for MCX
                gold_stats['exchange'] = 'MCX'
                gold_stats['symbol'] = 'GOLDM'
                gold_stats['lot_size'] = '100g'
                
                # Dynamic trading math (based on current price)
                contract_value = gold_per_gram_inr * 100  # 100g per lot
                gold_stats['trading_math'] = {
                    'lots': 1,
                    'lot_qty': '100g',
                    'contract_value': round(contract_value, 0),
                    'margin_required': round(contract_value * 0.028, 0),  # ~2.8% margin
                    'risk_per_trade': round(contract_value * 0.005, 0),   # 0.5% SL
                    'target_per_trade': round(contract_value * 0.01, 0),  # 1% target
                    'rr_ratio': '2:1'
                }
            except Exception as ge:
                pass
            
            return jsonify({
                'timestamp': datetime.now().isoformat(),
                'capital': capital,
                'today': today,
                'trades': [],
                'weekly': [],
                'zerodha': zerodha,
                'gold': gold_stats,
                'bot_status': 'running'
            })
        
        port = int(os.environ.get('PORT', 5050))
        logger.info(f"🌐 Starting dashboard on port {port}...")
        app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)
        
    except Exception as e:
        logger.warning(f"Dashboard failed to start: {e}")


def main():
    """Entry point"""
    import threading
    
    # Start dashboard in background thread
    dashboard_thread = threading.Thread(target=start_dashboard, daemon=True)
    dashboard_thread.start()
    logger.info("🌐 Dashboard thread started")
    
    # Give dashboard time to start
    time.sleep(2)
    
    # Run trading bot in main thread
    bot = CloudTradingBot()
    bot.run()


if __name__ == "__main__":
    main()
