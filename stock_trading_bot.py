#!/usr/bin/env python3
"""
📈 STOCK TRADING BOT - INTRADAY
================================

This bot:
1. Reads qualified stocks from smart_watchlist.json
2. Scans for BUY/SELL signals every minute
3. Places orders on Angel One (MIS - Intraday)
4. Manages trailing stop loss
5. Sends Telegram alerts

Works with: Angel One, existing Telegram config
"""

import os
import sys
import json
import time
import pytz
import schedule
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from loguru import logger

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Imports from existing project
from utils.notifications import send_telegram_message
from core.angel_client import AngelOneClient

# Constants
IST = pytz.timezone('Asia/Kolkata')
WATCHLIST_FILE = "config/smart_watchlist.json"
POSITIONS_FILE = "data/stock_positions.json"

class StockTradingBot:
    """Intraday stock trading bot using smart watchlist"""
    
    def __init__(self):
        self.watchlist = []
        self.positions = {}
        self.capital = 10000
        self.leverage = 5
        self.buying_power = self.capital * self.leverage
        self.angel_client = None
        self.is_authenticated = False
        self.daily_trades = 0
        self.daily_pnl = 0
        self.max_trades_per_day = 10
        self.trade_cooldown = {}  # Prevent multiple trades on same stock
        
        # Setup logger
        os.makedirs("logs", exist_ok=True)
        logger.add(
            "logs/stock_bot_{time:YYYY-MM-DD}.log",
            rotation="1 day",
            retention="7 days",
            level="INFO"
        )
    
    def load_watchlist(self):
        """Load qualified stocks from smart watchlist"""
        try:
            if os.path.exists(WATCHLIST_FILE):
                with open(WATCHLIST_FILE, 'r') as f:
                    data = json.load(f)
                    self.watchlist = [s for s in data.get('active_stocks', []) if s.get('enabled', True)]
                    self.capital = data.get('capital', 10000)
                    self.leverage = data.get('leverage', 5)
                    self.buying_power = self.capital * self.leverage
                    logger.info(f"Loaded {len(self.watchlist)} stocks from watchlist")
                    return True
            else:
                logger.warning("Watchlist not found. Run smart_stock_selector.py first")
                return False
        except Exception as e:
            logger.error(f"Error loading watchlist: {e}")
            return False
    
    def load_positions(self):
        """Load open positions from file"""
        try:
            if os.path.exists(POSITIONS_FILE):
                with open(POSITIONS_FILE, 'r') as f:
                    self.positions = json.load(f)
            else:
                self.positions = {}
        except Exception as e:
            logger.error(f"Error loading positions: {e}")
            self.positions = {}
    
    def save_positions(self):
        """Save positions to file"""
        try:
            os.makedirs(os.path.dirname(POSITIONS_FILE), exist_ok=True)
            with open(POSITIONS_FILE, 'w') as f:
                json.dump(self.positions, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Error saving positions: {e}")
    
    def authenticate(self):
        """Authenticate with Angel One"""
        try:
            self.angel_client = AngelOneClient()
            
            # Initialize first, then authenticate
            if not self.angel_client.initialize():
                logger.warning("Angel One client initialization failed")
                return False
                
            if self.angel_client.authenticate():
                self.is_authenticated = True
                
                # Get balance and update capital
                margins = self.angel_client.get_margins()
                if margins and margins.get('available'):
                    balance = margins['available']
                    self.capital = balance
                    self.buying_power = self.capital * self.leverage
                    logger.info(f"Angel One authenticated. Balance: Rs {balance:,.2f}")
                    
                return True
            else:
                logger.error("Angel One authentication failed")
                return False
        except Exception as e:
            logger.error(f"Authentication error: {e}")
            return False
    
    def is_trading_hours(self):
        """Check if within trading hours (9:15 AM - 3:15 PM IST)"""
        now = datetime.now(IST)
        market_open = now.replace(hour=9, minute=15, second=0, microsecond=0)
        market_close = now.replace(hour=15, minute=15, second=0, microsecond=0)
        
        # Skip weekends
        if now.weekday() >= 5:
            return False
        
        return market_open <= now <= market_close
    
    def is_no_new_trades_time(self):
        """Check if after 2:30 PM (no new trades)"""
        now = datetime.now(IST)
        no_new_trades = now.replace(hour=14, minute=30, second=0, microsecond=0)
        return now >= no_new_trades
    
    def fetch_stock_data(self, symbol):
        """Fetch recent candle data for a stock"""
        try:
            import yfinance as yf
            
            # Fetch 15-min data for last 2 days
            data = yf.download(symbol, period="2d", interval="15m", progress=False)
            
            if hasattr(data.columns, "levels") and data.columns.nlevels > 1:
                data.columns = data.columns.droplevel(1)
            
            if len(data) < 20:
                return None
            
            data['close'] = data['Close']
            data['high'] = data['High']
            data['low'] = data['Low']
            data['open'] = data['Open']
            
            return data
            
        except Exception as e:
            logger.error(f"Error fetching data for {symbol}: {e}")
            return None
    
    def calculate_indicators(self, data):
        """Calculate technical indicators"""
        try:
            high = data['high']
            low = data['low']
            close = data['close']
            opn = data['open']
            
            # RSI (2)
            delta = close.diff()
            gain = delta.where(delta > 0, 0).rolling(2).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(2).mean()
            rs = gain / loss
            data['rsi'] = 100 - (100 / (1 + rs))
            
            # Stochastic (10, 3, 3)
            lowest_low = low.rolling(10).min()
            highest_high = high.rolling(10).max()
            k = 100 * (close - lowest_low) / (highest_high - lowest_low)
            data['stoch_k'] = k.rolling(3).mean()
            data['stoch_d'] = data['stoch_k'].rolling(3).mean()
            
            # CCI (20)
            tp = (high + low + close) / 3
            sma_tp = tp.rolling(20).mean()
            mean_dev = tp.rolling(20).apply(lambda x: np.mean(np.abs(x - x.mean())))
            data['cci'] = (tp - sma_tp) / (0.015 * mean_dev)
            
            # MACD (12, 26, 9)
            ema12 = close.ewm(span=12).mean()
            ema26 = close.ewm(span=26).mean()
            data['macd'] = ema12 - ema26
            data['macd_signal'] = data['macd'].ewm(span=9).mean()
            
            # Candle color
            data['is_red'] = close < opn
            
            return data
            
        except Exception as e:
            logger.error(f"Error calculating indicators: {e}")
            return None
    
    def check_signal(self, data):
        """Check for BUY/SELL signal"""
        try:
            if len(data) < 50:
                return None
            
            curr = data.iloc[-1]
            
            # Check if indicators are valid
            if pd.isna(curr['rsi']) or pd.isna(curr['stoch_k']) or pd.isna(curr['cci']) or pd.isna(curr['macd']):
                return None
            
            MIN_INDICATORS = 3
            HIGHER_TF_CANDLES = 8
            LOWER_TF_CANDLES = 4
            
            # Check higher timeframe trend (last 8 candles)
            bear_count = sum([data.iloc[-j]['is_red'] for j in range(1, min(HIGHER_TF_CANDLES + 1, len(data)))])
            higher_bear = bear_count >= HIGHER_TF_CANDLES * 0.6
            
            bull_count = sum([not data.iloc[-j]['is_red'] for j in range(1, min(HIGHER_TF_CANDLES + 1, len(data)))])
            higher_bull = bull_count >= HIGHER_TF_CANDLES * 0.6
            
            # Check lower timeframe (last 4 candles)
            red_lower = sum([data.iloc[-j]['is_red'] for j in range(1, min(LOWER_TF_CANDLES + 1, len(data)))])
            all_red = red_lower >= LOWER_TF_CANDLES - 1
            
            green_lower = sum([not data.iloc[-j]['is_red'] for j in range(1, min(LOWER_TF_CANDLES + 1, len(data)))])
            all_green = green_lower >= LOWER_TF_CANDLES - 1
            
            # Indicator signals
            sell_ind = 0
            if curr['stoch_k'] < curr['stoch_d']: sell_ind += 1
            if curr['rsi'] < 50: sell_ind += 1
            if curr['cci'] < 0: sell_ind += 1
            if curr['macd'] < curr['macd_signal']: sell_ind += 1
            
            buy_ind = 0
            if curr['stoch_k'] > curr['stoch_d']: buy_ind += 1
            if curr['rsi'] > 50: buy_ind += 1
            if curr['cci'] > 0: buy_ind += 1
            if curr['macd'] > curr['macd_signal']: buy_ind += 1
            
            # Final signal
            if higher_bear and all_red and sell_ind >= MIN_INDICATORS:
                return 'SELL'
            elif higher_bull and all_green and buy_ind >= MIN_INDICATORS:
                return 'BUY'
            
            return None
            
        except Exception as e:
            logger.error(f"Error checking signal: {e}")
            return None
    
    def place_order(self, stock, signal, price, qty):
        """Place order on Angel One"""
        try:
            symbol = stock['symbol']
            
            if not self.is_authenticated:
                logger.warning("Not authenticated, cannot place order")
                return None
            
            # Calculate SL and Target
            trail_pct = stock.get('trail_percent', 0.5) / 100
            
            if signal == 'BUY':
                sl_price = round(price * (1 - trail_pct * 2), 2)
                target_price = round(price * (1 + trail_pct * 4), 2)
                transaction_type = 'BUY'
            else:
                sl_price = round(price * (1 + trail_pct * 2), 2)
                target_price = round(price * (1 - trail_pct * 4), 2)
                transaction_type = 'SELL'
            
            # Place order via Angel One
            order_id = self.angel_client.place_order(
                symbol=symbol,
                token=stock.get('token', ''),
                quantity=qty,
                transaction_type=transaction_type,
                order_type='MARKET',
                product_type='INTRADAY'
            )
            
            if order_id:
                # Save position
                self.positions[symbol] = {
                    'order_id': order_id,
                    'signal': signal,
                    'entry_price': price,
                    'qty': qty,
                    'sl_price': sl_price,
                    'target_price': target_price,
                    'entry_time': datetime.now(IST).isoformat(),
                    'trail_pct': trail_pct,
                    'trail_active': False,
                    'trail_sl': sl_price
                }
                self.save_positions()
                
                # Send Telegram alert
                msg = f"""
🎯 *{signal} SIGNAL - {symbol}*

Entry: Rs {price:,.2f}
Qty: {qty}
Stop Loss: Rs {sl_price:,.2f}
Target: Rs {target_price:,.2f}

Order ID: {order_id}
"""
                send_telegram_message(msg)
                
                logger.info(f"Order placed: {signal} {symbol} @ {price}")
                return order_id
            
            return None
            
        except Exception as e:
            logger.error(f"Error placing order: {e}")
            return None
    
    def scan_for_signals(self):
        """Scan all watchlist stocks for signals"""
        if not self.is_trading_hours():
            return
        
        if self.is_no_new_trades_time():
            logger.info("After 2:30 PM - No new trades")
            return
        
        if self.daily_trades >= self.max_trades_per_day:
            logger.info(f"Max daily trades ({self.max_trades_per_day}) reached")
            return
        
        now = datetime.now(IST)
        
        for stock in self.watchlist:
            symbol = stock['symbol']
            nse_symbol = stock.get('nse_symbol', f"{symbol}.NS")
            
            # Skip if already have position
            if symbol in self.positions:
                continue
            
            # Skip if in cooldown
            if symbol in self.trade_cooldown:
                if (now - self.trade_cooldown[symbol]).seconds < 3600:  # 1 hour cooldown
                    continue
            
            try:
                # Fetch data
                data = self.fetch_stock_data(nse_symbol)
                if data is None:
                    continue
                
                # Calculate indicators
                data = self.calculate_indicators(data)
                if data is None:
                    continue
                
                # Check signal
                signal = self.check_signal(data)
                
                if signal:
                    price = float(data['close'].iloc[-1])
                    qty = int(self.buying_power / price)
                    
                    if qty > 0:
                        logger.info(f"Signal found: {signal} on {symbol} @ {price}")
                        
                        # Place order
                        order_id = self.place_order(stock, signal, price, qty)
                        
                        if order_id:
                            self.daily_trades += 1
                            self.trade_cooldown[symbol] = now
                        
            except Exception as e:
                logger.error(f"Error scanning {symbol}: {e}")
    
    def manage_positions(self):
        """Manage open positions - trailing SL, exits"""
        if not self.positions:
            return
        
        for symbol, pos in list(self.positions.items()):
            try:
                # Fetch current price
                nse_symbol = f"{symbol}.NS"
                data = self.fetch_stock_data(nse_symbol)
                
                if data is None:
                    continue
                
                current_price = float(data['close'].iloc[-1])
                current_high = float(data['high'].iloc[-1])
                current_low = float(data['low'].iloc[-1])
                
                entry_price = pos['entry_price']
                signal = pos['signal']
                trail_pct = pos['trail_pct']
                trail_offset = entry_price * trail_pct
                
                # Check for trailing stop activation
                if signal == 'BUY':
                    # Activate trail if price moved up by offset
                    if not pos['trail_active'] and current_high >= entry_price + trail_offset:
                        pos['trail_active'] = True
                        pos['trail_sl'] = current_high - trail_offset
                        logger.info(f"{symbol}: Trailing stop activated at {pos['trail_sl']:.2f}")
                    
                    if pos['trail_active']:
                        # Update trail SL
                        new_sl = current_high - trail_offset
                        if new_sl > pos['trail_sl']:
                            pos['trail_sl'] = new_sl
                        
                        # Check if SL hit
                        if current_low <= pos['trail_sl']:
                            self.close_position(symbol, pos['trail_sl'], 'TRAILING_SL')
                            continue
                
                elif signal == 'SELL':
                    # Activate trail if price moved down by offset
                    if not pos['trail_active'] and current_low <= entry_price - trail_offset:
                        pos['trail_active'] = True
                        pos['trail_sl'] = current_low + trail_offset
                        logger.info(f"{symbol}: Trailing stop activated at {pos['trail_sl']:.2f}")
                    
                    if pos['trail_active']:
                        # Update trail SL
                        new_sl = current_low + trail_offset
                        if new_sl < pos['trail_sl']:
                            pos['trail_sl'] = new_sl
                        
                        # Check if SL hit
                        if current_high >= pos['trail_sl']:
                            self.close_position(symbol, pos['trail_sl'], 'TRAILING_SL')
                            continue
                
                self.save_positions()
                
            except Exception as e:
                logger.error(f"Error managing position {symbol}: {e}")
    
    def close_position(self, symbol, exit_price, reason):
        """Close a position"""
        try:
            pos = self.positions.get(symbol)
            if not pos:
                return
            
            entry_price = pos['entry_price']
            qty = pos['qty']
            signal = pos['signal']
            
            # Calculate P&L
            if signal == 'BUY':
                pnl = (exit_price - entry_price) * qty
            else:
                pnl = (entry_price - exit_price) * qty
            
            pnl -= 40  # Brokerage
            self.daily_pnl += pnl
            
            # Send Telegram
            emoji = "💰" if pnl > 0 else "📉"
            msg = f"""
{emoji} *TRADE CLOSED - {symbol}*

Entry: Rs {entry_price:,.2f}
Exit: Rs {exit_price:,.2f}
Qty: {qty}
P&L: Rs {pnl:+,.2f}
Reason: {reason}
"""
            send_telegram_message(msg)
            
            logger.info(f"Position closed: {symbol} @ {exit_price}, P&L: {pnl:+.2f}")
            
            # Remove position
            del self.positions[symbol]
            self.save_positions()
            
        except Exception as e:
            logger.error(f"Error closing position {symbol}: {e}")
    
    def square_off_all(self):
        """Square off all positions at end of day"""
        for symbol in list(self.positions.keys()):
            try:
                nse_symbol = f"{symbol}.NS"
                data = self.fetch_stock_data(nse_symbol)
                if data is not None:
                    current_price = float(data['close'].iloc[-1])
                    self.close_position(symbol, current_price, 'EOD_SQUARE_OFF')
            except Exception as e:
                logger.error(f"Error squaring off {symbol}: {e}")
    
    def send_daily_summary(self):
        """Send daily P&L summary"""
        msg = f"""
📊 *DAILY SUMMARY*

Date: {datetime.now(IST).strftime('%Y-%m-%d')}
Total Trades: {self.daily_trades}
Daily P&L: Rs {self.daily_pnl:+,.2f}
Open Positions: {len(self.positions)}
"""
        send_telegram_message(msg)
        logger.info(f"Daily summary sent: {self.daily_trades} trades, P&L: {self.daily_pnl:+.2f}")
        
        # Reset daily counters
        self.daily_trades = 0
        self.daily_pnl = 0
    
    def run(self):
        """Main bot loop"""
        logger.info("="*50)
        logger.info("📈 STOCK TRADING BOT STARTING")
        logger.info("="*50)
        
        # Load watchlist
        if not self.load_watchlist():
            logger.error("Failed to load watchlist. Exiting.")
            return
        
        # Load positions
        self.load_positions()
        
        # Authenticate
        if not self.authenticate():
            logger.warning("Running in PAPER mode (no real orders)")
        
        # Log startup
        logger.info(f"Capital: Rs {self.capital:,}")
        logger.info(f"Buying Power: Rs {self.buying_power:,}")
        logger.info(f"Watchlist: {len(self.watchlist)} stocks")
        
        # Send startup message
        stocks_list = ", ".join([s['symbol'] for s in self.watchlist[:5]])
        send_telegram_message(f"""
🚀 *STOCK BOT STARTED*

Capital: Rs {self.capital:,}
Watchlist: {len(self.watchlist)} stocks
Top stocks: {stocks_list}

Scanning for signals...
""")
        
        # Schedule tasks
        schedule.every(1).minutes.do(self.scan_for_signals)
        schedule.every(1).minutes.do(self.manage_positions)
        schedule.every().day.at("15:20").do(self.square_off_all)
        schedule.every().day.at("15:30").do(self.send_daily_summary)
        
        # Main loop
        while True:
            try:
                schedule.run_pending()
                time.sleep(10)
            except KeyboardInterrupt:
                logger.info("Bot stopped by user")
                break
            except Exception as e:
                logger.error(f"Error in main loop: {e}")
                time.sleep(60)


if __name__ == "__main__":
    bot = StockTradingBot()
    bot.run()
