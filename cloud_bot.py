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
from utils.position_manager import position_manager
from utils.trade_journal import trade_journal
from utils.dashboard import dashboard
from utils.capital_manager import capital_manager


class CloudTradingBot:
    """Trading bot optimized for cloud deployment"""
    
    def __init__(self):
        # Use capital manager for dynamic sizing
        self.capital = capital_manager.get_capital()
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
        # Common NSE tokens - add more as needed
        tokens = {
            "SBIN": "3045", "RELIANCE": "2885", "INFY": "1594", "TCS": "11536",
            "HDFCBANK": "1333", "ICICIBANK": "4963", "KOTAKBANK": "1922",
            "TATAMOTORS": "3456", "TATASTEEL": "3499", "SAIL": "2963",
            "PNB": "10666", "IRFC": "3041", "IDEA": "14366", "CANBK": "10794",
            "IDFCFIRSTB": "11184", "ITC": "1660", "COALINDIA": "20374",
            "ONGC": "2475", "BANKBARODA": "4668", "UNIONBANK": "13459",
            "IOC": "1624", "BPCL": "526", "HINDALCO": "348", "VEDL": "3063",
            "JINDALSTEL": "6733", "NMDC": "4164", "NTPC": "11630"
        }
        return tokens.get(symbol, "0")
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
                    
                    # Check if already have position in this stock
                    if position_manager.has_position(symbol):
                        logger.info(f"⚠️ Skipping {symbol}: Already have open position")
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
                    target_price=signal.target
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
            # Get stats from trade journal
            journal_stats = trade_journal.get_today_stats()
            
            # Display performance dashboard
            dashboard.display_daily(journal_stats)
            
            # Save to database
            trade_journal.save_daily_summary()
            
            # Send Telegram summary
            try:
                from utils.notifications import send_telegram_message
                telegram_msg = dashboard.get_telegram_summary(journal_stats)
                send_telegram_message(telegram_msg)
            except:
                pass
                
        except Exception as e:
            logger.debug(f"Dashboard failed: {e}")
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
            broker_status = {'is_authenticated': False, 'balance': 0, 'user_name': 'Not Connected'}
            
            if self.is_authenticated:
                if hasattr(self, 'broker') and self.broker == 'angel':
                    # Angel One balance  
                    funds = self.angel_client.rmsLimit()
                    if funds.get('status'):
                        available = float(funds['data'].get('net', 0))
                        broker_status['balance'] = available
                        profile = self.angel_client.getProfile(self.angel_refresh_token)
                        broker_status['user_name'] = profile.get('data', {}).get('name', 'Connected')
                        broker_status['is_authenticated'] = True
                        broker_status['broker'] = 'Angel One'
                        logger.debug(f"🔄 Balance refreshed: ₹{available:,.2f}")
                elif self.client:
                    # Zerodha balance
                    margins = self.client.get_margins()
                    if margins and 'equity' in margins:
                        available = margins['equity'].get('available', {}).get('live_balance', 0)
                        broker_status['balance'] = available
                        broker_status['user_name'] = self.client.kite.profile().get('user_name', 'Connected')
                        broker_status['is_authenticated'] = True
                        broker_status['broker'] = 'Zerodha'
            
            # Save for dashboard
            import json
            broker_status['last_updated'] = datetime.now().strftime('%H:%M:%S')
            os.makedirs('data', exist_ok=True)
            with open('data/zerodha_status.json', 'w') as f:
                json.dump(broker_status, f, indent=2)
                
        except Exception as e:
            logger.debug(f"Balance refresh failed: {e}")
    
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
        broker_status = {'is_authenticated': False, 'balance': 0, 'user_name': 'Not Connected'}
        
        if self.is_authenticated:
            try:
                if hasattr(self, 'broker') and self.broker == 'angel':
                    # Angel One balance
                    funds = self.angel_client.rmsLimit()
                    if funds.get('status'):
                        available = float(funds['data'].get('net', 0))
                        broker_status['balance'] = available
                        profile = self.angel_client.getProfile(self.angel_refresh_token)
                        broker_status['user_name'] = profile.get('data', {}).get('name', 'Connected')
                        broker_status['is_authenticated'] = True
                        broker_status['broker'] = 'Angel One'
                elif self.client:
                    # Zerodha balance
                    margins = self.client.get_margins()
                    if margins and 'equity' in margins:
                        available = margins['equity'].get('available', {}).get('live_balance', 0)
                        broker_status['balance'] = available
                        broker_status['user_name'] = self.client.kite.profile().get('user_name', 'Connected')
                        broker_status['is_authenticated'] = True
                        broker_status['broker'] = 'Zerodha'
            except Exception as e:
                logger.info(f"🏦 Balance check failed: {e}")
        else:
            logger.info("🏦 Not authenticated - Add credentials in Railway")
        
        # Save status for web dashboard
        try:
            import json
            broker_status['last_updated'] = datetime.now().strftime('%H:%M:%S')
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
        schedule.every(1).minutes.do(self.scan_for_signals)  # Scan every 1 minute
        schedule.every(5).minutes.do(self.refresh_balance)  # Refresh balance every 5 minutes
        schedule.every().day.at("14:15").do(lambda: logger.info("🟡 Trading window ended. No new trades."))
        schedule.every().day.at("15:30").do(self.daily_summary)
        schedule.every().day.at("00:01").do(self.reset_daily)
        
        # Sunday: Weekly stock optimization and capital compounding at 6 PM
        schedule.every().sunday.at("18:00").do(self.weekly_stock_optimization)
        schedule.every().sunday.at("18:05").do(capital_manager.weekly_compound)
        
        logger.info("✅ Bot running...")
        logger.info("📅 Balance refresh: Every 5 minutes")
        
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


def start_dashboard():
    """Start the web dashboard in a separate thread"""
    try:
        from flask import Flask, render_template, jsonify
        import json
        
        app = Flask(__name__, 
                    template_folder='web_dashboard/templates',
                    static_folder='web_dashboard/static')
        
        @app.route('/')
        def dashboard():
            return render_template('dashboard.html')
        
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
            
            return jsonify({
                'timestamp': datetime.now().isoformat(),
                'capital': capital,
                'today': today,
                'trades': [],
                'weekly': [],
                'zerodha': zerodha,
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
